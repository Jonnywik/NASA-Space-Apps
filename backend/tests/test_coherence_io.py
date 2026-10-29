from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import transform_bounds

from coherence_fixtures import (
    EVENT,
    EVENT_ID,
    sha256,
    valid_manifest,
    write_event_catalog,
    write_geotiff,
    write_zip,
)
from processing import coherence_io


def make_sources(root: Path, *, pre_resolution=20, co_resolution=30,
                 pre_values=None, co_values=None, pre_nodata=None, co_nodata=None):
    """Create two small EPSG:32651 rasters covering the temporary event AOI."""
    west, south, east, north = transform_bounds("EPSG:4326", "EPSG:32651", *EVENT["bbox"])

    def write_source(name, resolution, values, nodata):
        pad = 300
        width = int(np.ceil((east - west + pad * 2) / resolution))
        height = int(np.ceil((north - south + pad * 2) / resolution))
        transform = from_origin(west - pad, north + pad, resolution, resolution)
        if values is None:
            array = np.full((height, width), 0.8 if name == "pre" else 0.5, dtype=np.float32)
        else:
            array = np.resize(np.asarray(values), (height, width)).astype(np.float32)
        return write_geotiff(root / f"{name}.tif", array, transform=transform, nodata=nodata)

    pre_path = write_source("pre", pre_resolution, pre_values, pre_nodata)
    co_path = write_source("co", co_resolution, co_values, co_nodata)
    return pre_path, co_path


def write_manifest(path: Path, pre_source: str, co_source: str, *, changes=None) -> Path:
    data = valid_manifest(pre_source, co_source)
    if changes:
        changes(data)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


class CoherenceIOTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="coherence-io-")
        self.root = Path(self.temp.name)
        self.events_path = write_event_catalog(self.root / "events.json")
        self.events_patch = mock.patch.object(coherence_io, "EVENTS_FILE", self.events_path)
        self.events_patch.start()

    def tearDown(self):
        self.events_patch.stop()
        self.temp.cleanup()

    def test_event_reader_and_paired_extraction_write_matching_hash_bound_outputs(self):
        loaded = coherence_io.load_event(EVENT_ID, events_path=self.events_path)
        self.assertEqual(loaded["id"], EVENT_ID)
        self.assertEqual(loaded["bbox"], EVENT["bbox"])
        self.assertEqual(self.events_path.read_text(encoding="utf-8"), json.dumps([EVENT]))

        pre_path, co_path = make_sources(self.root)
        source_zip = write_zip(
            self.root / "pre.zip", {"nested/product_corr.tif": pre_path}
        )
        manifest_path = write_manifest(self.root / "pairs.json", "pre.zip", "co.tif")
        output_dir = self.root / "prepared"

        manifest = coherence_io.extract_pair(
            EVENT_ID, manifest_path, output_dir=output_dir
        )

        self.assertEqual(manifest["schemaVersion"], "1.0")
        self.assertEqual(manifest["event"], EVENT_ID)
        self.assertEqual(manifest["dataKind"], "synthetic")
        self.assertEqual(manifest["prePair"], ["2024-01-01", "2024-01-05"])
        self.assertEqual(manifest["coPair"], ["2024-01-05", "2024-01-15"])
        self.assertEqual(manifest["sources"]["pre"]["sourceSha256"], sha256(source_zip))
        self.assertEqual(manifest["sources"]["co"]["sourceSha256"], sha256(co_path))
        self.assertFalse(manifest["parameters"]["waterMaskApplied"])
        self.assertEqual(manifest["grid"]["crs"], "EPSG:32651")
        self.assertGreater(manifest["grid"]["resolutionMetres"], 0)
        self.assertGreater(manifest["grid"]["width"], 0)
        self.assertGreater(manifest["grid"]["height"], 0)
        self.assertGreater(manifest["coverage"]["commonValidPixelCount"], 0)

        expected_names = {"coh_pre.tif", "coh_co.tif", "coherence_info.json"}
        self.assertTrue(expected_names.issubset({item.name for item in output_dir.iterdir()}))
        stored = json.loads((output_dir / "coherence_info.json").read_text(encoding="utf-8"))
        self.assertEqual(stored["extractionId"], manifest["extractionId"])
        for name in ("coh_pre.tif", "coh_co.tif"):
            self.assertEqual(stored["outputs"][name]["sha256"], sha256(output_dir / name))

        with rasterio.open(output_dir / "coh_pre.tif") as pre, rasterio.open(output_dir / "coh_co.tif") as co:
            self.assertEqual(pre.crs, co.crs)
            self.assertEqual(pre.shape, co.shape)
            self.assertEqual(pre.transform, co.transform)
            self.assertEqual(pre.dtypes, ("float32",))
            self.assertTrue(np.isnan(pre.nodata))
            self.assertEqual(pre.tags()["extractionId"], manifest["extractionId"])
            self.assertEqual(co.tags()["event"], EVENT_ID)
            self.assertEqual(pre.tags()["dataKind"], "synthetic")
            self.assertGreater(np.isfinite(pre.read(1)).sum(), 0)

    def test_zip_with_zero_or_multiple_coherence_rasters_fails_without_publication(self):
        pre_path, co_path = make_sources(self.root)
        extra_a = write_geotiff(self.root / "a.tif", np.ones((8, 8), dtype=np.float32))
        extra_b = write_geotiff(self.root / "b.tif", np.ones((8, 8), dtype=np.float32))
        cases = (
            ("none", {}),
            ("multiple", {"one_corr.tif": extra_a, "two_corr.tif": extra_b}),
        )
        for name, members in cases:
            with self.subTest(case=name):
                zip_path = write_zip(self.root / f"{name}.zip", members)
                manifest_path = write_manifest(
                    self.root / f"{name}.json", zip_path.name, co_path.name
                )
                output = self.root / f"out-{name}"
                with self.assertRaises((ValueError, OSError)):
                    coherence_io.extract_pair(EVENT_ID, manifest_path, output_dir=output)
                self.assertFalse((output / "coh_pre.tif").exists())
                self.assertFalse((output / "coh_co.tif").exists())
                self.assertFalse((output / "coherence_info.json").exists())

    def test_preflight_rejects_event_date_scene_track_and_processing_mismatches(self):
        pre_path, co_path = make_sources(self.root)
        cases = {
            "unknown event": lambda data: data.update(event="not_registered"),
            "pre pair not before event": lambda data: data["pre"]["acquisitionDates"].__setitem__(1, "2024-01-11"),
            "shared scene mismatch": lambda data: data["co"]["sceneIds"].__setitem__(0, "OTHER-B"),
            "shared date mismatch": lambda data: data["co"]["acquisitionDates"].__setitem__(0, "2024-01-06"),
            "co pair does not end after event": lambda data: data["co"]["acquisitionDates"].__setitem__(1, "2024-01-12"),
            "relative orbit mismatch": lambda data: data["co"].update(relativeOrbit=124),
            "flight direction mismatch": lambda data: data["co"].update(flightDirection="DESCENDING"),
            "polarization mismatch": lambda data: data["co"].update(polarization="VH"),
            "processing version mismatch": lambda data: data["co"].update(processingVersion="fixture-2"),
        }
        for index, (label, mutate) in enumerate(cases.items()):
            with self.subTest(case=label):
                manifest_path = self.root / f"bad-{index}.json"
                write_manifest(manifest_path, pre_path.name, co_path.name, changes=mutate)
                output = self.root / f"bad-output-{index}"
                with self.assertRaises((ValueError, OSError)):
                    coherence_io.extract_pair(EVENT_ID, manifest_path, output_dir=output)
                self.assertFalse((output / "coh_pre.tif").exists())
                self.assertFalse((output / "coherence_info.json").exists())

    def test_zero_is_valid_unless_source_declares_zero_as_nodata(self):
        west, south, east, north = transform_bounds("EPSG:4326", "EPSG:32651", *EVENT["bbox"])
        resolution = 30
        width = int(np.ceil((east - west + 600) / resolution))
        height = int(np.ceil((north - south + 600) / resolution))
        transform = from_origin(west - 300, north + 300, resolution, resolution)
        pre_values = np.zeros((height, width), dtype=np.float32)
        co_values = np.full((height, width), 0.6, dtype=np.float32)
        co_values[: height // 3, : width // 3] = 0
        pre_path = write_geotiff(self.root / "zeros-valid.tif", pre_values, transform=transform)
        co_path = write_geotiff(self.root / "zeros-nodata.tif", co_values, transform=transform, nodata=0)
        manifest_path = write_manifest(self.root / "zeros.json", pre_path.name, co_path.name)
        output = self.root / "zeros-out"

        manifest = coherence_io.extract_pair(EVENT_ID, manifest_path, output_dir=output)
        with rasterio.open(output / "coh_pre.tif") as pre, rasterio.open(output / "coh_co.tif") as co:
            pre_values_out = pre.read(1)
            co_values_out = co.read(1)
            self.assertGreater(np.count_nonzero(np.isfinite(pre_values_out) & (pre_values_out == 0)), 0)
            self.assertGreater(np.count_nonzero(np.isfinite(co_values_out)), 0)
            self.assertLess(np.isfinite(co_values_out).sum(), np.isfinite(pre_values_out).sum())
        self.assertGreater(manifest["coverage"]["preValidPixelCount"], manifest["coverage"]["coValidPixelCount"])

    def test_raster_mask_nonfinite_and_out_of_range_source_values_are_excluded_and_counted(self):
        pre_path, co_path = make_sources(
            self.root,
            pre_values=np.array([0.8, np.nan, 1.2], dtype=np.float32),
            co_values=np.array([0.6], dtype=np.float32),
        )
        with rasterio.open(pre_path, "r+") as pre:
            mask = np.full((pre.height, pre.width), 255, dtype=np.uint8)
            row0, col0 = pre.height // 3, pre.width // 3
            mask[row0:row0 + pre.height // 4, col0:col0 + pre.width // 4] = 0
            pre.write_mask(mask)
        manifest_path = write_manifest(self.root / "invalid-values.json", pre_path.name, co_path.name)
        output = self.root / "invalid-values-out"

        manifest = coherence_io.extract_pair(EVENT_ID, manifest_path, output_dir=output)

        source_stats = manifest["sources"]["pre"]
        self.assertGreater(source_stats["readWindowMaskInvalidPixelCount"], 0)
        self.assertGreater(source_stats["readWindowNonFinitePixelCount"], 0)
        self.assertGreater(source_stats["readWindowOutOfRangePixelCount"], 0)
        with rasterio.open(output / "coh_pre.tif") as pre:
            values = pre.read(1)
            finite = values[np.isfinite(values)]
            self.assertGreater(finite.size, 0)
            self.assertTrue(np.all((finite >= 0) & (finite <= 1)))
            self.assertGreater(np.count_nonzero(~np.isfinite(values)), 0)

    def test_existing_outputs_require_overwrite_and_failed_run_leaves_them_intact(self):
        pre_path, co_path = make_sources(self.root)
        manifest_path = write_manifest(self.root / "overwrite.json", pre_path.name, co_path.name)
        output = self.root / "overwrite-out"
        first = coherence_io.extract_pair(EVENT_ID, manifest_path, output_dir=output)
        previous = {
            name: (output / name).read_bytes()
            for name in ("coh_pre.tif", "coh_co.tif", "coherence_info.json")
        }

        with self.assertRaises((ValueError, OSError)):
            coherence_io.extract_pair(EVENT_ID, manifest_path, output_dir=output)
        self.assertEqual(
            previous,
            {name: (output / name).read_bytes() for name in previous},
        )

        second = coherence_io.extract_pair(
            EVENT_ID, manifest_path, output_dir=output, overwrite=True
        )
        self.assertEqual(second["event"], first["event"])
        self.assertEqual(second["outputs"]["coh_pre.tif"]["sha256"], sha256(output / "coh_pre.tif"))

    def test_output_path_collision_with_source_is_rejected_without_replacing_input(self):
        output = self.root / "collision"
        output.mkdir()
        pre_path = write_geotiff(
            output / "coh_pre.tif", np.full((32, 32), 0.8, dtype=np.float32)
        )
        co_path = write_geotiff(
            self.root / "collision-co.tif", np.full((32, 32), 0.5, dtype=np.float32)
        )
        manifest_path = write_manifest(
            self.root / "collision.json", str(pre_path.relative_to(self.root)), co_path.name
        )
        original = pre_path.read_bytes()

        with self.assertRaises((ValueError, OSError)):
            coherence_io.extract_pair(
                EVENT_ID, manifest_path, output_dir=output, overwrite=True
            )

        self.assertEqual(pre_path.read_bytes(), original)
        self.assertFalse((output / "coh_co.tif").exists())
        self.assertFalse((output / "coherence_info.json").exists())


if __name__ == "__main__":
    unittest.main()
