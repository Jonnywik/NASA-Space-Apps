from __future__ import annotations

import json
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import rasterio
from rasterio.transform import from_origin

from coherence_fixtures import (
    EVENT,
    EVENT_ID,
    prepared_pair,
    sha256,
    valid_manifest,
    write_event_catalog,
    write_geotiff,
)
from processing import coherence_io
from processing import coherence_change


class CoherenceChangeMathTests(unittest.TestCase):
    def test_constant_7_by_7_contract_has_45_supported_detections_and_expected_area(self):
        pre = np.full((7, 7), 0.8, dtype=np.float32)
        co = np.full((7, 7), 0.4, dtype=np.float32)

        result = coherence_change.compute_change(pre, co, np.ones((7, 7), dtype=bool))

        self.assertEqual(np.count_nonzero(result["supported"]), 45)
        self.assertEqual(np.count_nonzero(result["eligible"]), 45)
        self.assertEqual(np.count_nonzero(result["rawChanged"]), 45)
        self.assertEqual(np.count_nonzero(result["changed"]), 45)
        self.assertTrue(np.allclose(result["loss"][result["supported"]], 0.4, atol=1e-6))
        self.assertAlmostEqual(45 * 30 * 30 / 1_000_000, 0.0405)

    def test_common_neighborhood_smoothing_preserves_constant_beside_nodata(self):
        pre = np.full((11, 11), 0.8, dtype=np.float32)
        co = np.full((11, 11), 0.4, dtype=np.float32)
        valid = np.ones((11, 11), dtype=bool)
        valid[5, 5] = False

        result = coherence_change.compute_change(pre, co, valid)

        self.assertFalse(result["supported"][5, 5])
        self.assertTrue(result["supported"][5, 4])
        self.assertTrue(np.allclose(result["loss"][result["supported"]], 0.4, atol=1e-6))

    def test_threshold_boundaries_are_inclusive_and_values_beyond_tolerance_are_rejected(self):
        shape = (5, 5)
        exact = coherence_change.compute_change(
            np.full(shape, 0.5), np.full(shape, 0.2), np.ones(shape, dtype=bool),
            pre_min=0.5, loss_min=0.3, min_pixels=1,
        )
        self.assertEqual(np.count_nonzero(exact["eligible"]), 21)
        self.assertEqual(np.count_nonzero(exact["rawChanged"]), 21)

        below_baseline = coherence_change.compute_change(
            np.full(shape, 0.5 - 2e-6), np.full(shape, 0.2), np.ones(shape, dtype=bool),
            pre_min=0.5, loss_min=0.3, min_pixels=1,
        )
        self.assertEqual(np.count_nonzero(below_baseline["eligible"]), 0)
        self.assertEqual(np.count_nonzero(below_baseline["rawChanged"]), 0)

        below_loss = coherence_change.compute_change(
            np.full(shape, 0.8), np.full(shape, 0.5 + 2e-6), np.ones(shape, dtype=bool),
            pre_min=0.5, loss_min=0.3, min_pixels=1,
        )
        self.assertGreater(np.count_nonzero(below_loss["eligible"]), 0)
        self.assertEqual(np.count_nonzero(below_loss["rawChanged"]), 0)

    def test_diagonally_touching_components_use_eight_connectivity_and_exact_size_cutoff(self):
        pre = np.ones((11, 11), dtype=np.float32)
        co = np.ones((11, 11), dtype=np.float32)
        co[3, 3] = 0
        co[6, 6] = 0
        valid = np.ones((11, 11), dtype=bool)

        kept_at_exact_cutoff = coherence_change.compute_change(
            pre, co, valid, pre_min=0.5, loss_min=0.1, min_pixels=18,
        )
        removed_above_cutoff = coherence_change.compute_change(
            pre, co, valid, pre_min=0.5, loss_min=0.1, min_pixels=19,
        )

        self.assertEqual(np.count_nonzero(kept_at_exact_cutoff["rawChanged"]), 18)
        self.assertEqual(np.count_nonzero(kept_at_exact_cutoff["changed"]), 18)
        self.assertEqual(np.count_nonzero(removed_above_cutoff["rawChanged"]), 18)
        self.assertEqual(np.count_nonzero(removed_above_cutoff["changed"]), 0)


class CoherenceChangeOutputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="coherence-change-")
        self.root = Path(self.temp.name)
        self.events_path = write_event_catalog(self.root / "events.json")
        self.events_patch = mock.patch.object(coherence_io, "EVENTS_FILE", self.events_path)
        self.events_patch.start()

    def tearDown(self):
        self.events_patch.stop()
        self.temp.cleanup()

    def test_change_outputs_include_area_mask_geojson_and_qa_image(self):
        pre = np.full((7, 7), 0.8, dtype=np.float32)
        co = np.full((7, 7), 0.4, dtype=np.float32)
        input_dir = self.root / "pair"
        prepared_pair(input_dir, pre, co)
        output_dir = self.root / "changed"

        result = coherence_change.create_change_map(
            EVENT_ID,
            input_dir=input_dir,
            output_dir=output_dir,
            pre_min=0.5,
            loss_min=0.3,
            min_pixels=1,
            simplify=0,
        )

        expected_files = {
            "change_mask.tif",
            "change.geojson",
            "change_extent.json",
            "06_change_check.png",
        }
        self.assertTrue(expected_files.issubset({path.name for path in output_dir.iterdir()}))
        extent = json.loads((output_dir / "change_extent.json").read_text(encoding="utf-8"))
        self.assertEqual(extent["event"], EVENT_ID)
        self.assertEqual(extent["dataKind"], "synthetic")
        self.assertAlmostEqual(extent["stats"]["km2Changed"], 0.0405, places=8)
        self.assertEqual(extent["stats"]["rawChangedPixelCount"], 45)
        self.assertEqual(extent["stats"]["changedPixelCount"], 45)
        self.assertEqual(extent["parameters"]["preMin"], 0.5)
        self.assertEqual(extent["parameters"]["lossMin"], 0.3)
        self.assertEqual(result["stats"]["km2Changed"], extent["stats"]["km2Changed"])
        with rasterio.open(output_dir / "change_mask.tif") as mask:
            values = mask.read(1)
            self.assertEqual(mask.dtypes, ("uint8",))
            self.assertEqual(np.count_nonzero(values == 1), 45)
            self.assertEqual(np.count_nonzero(values == 255), 4)
        geojson = json.loads((output_dir / "change.geojson").read_text(encoding="utf-8"))
        self.assertEqual(geojson["type"], "FeatureCollection")
        self.assertEqual(len(geojson["features"]), 1)
        self.assertGreater(geojson["features"][0]["properties"]["areaKm2"], 0)
        for filename in ("change_mask.tif", "change.geojson", "06_change_check.png"):
            self.assertEqual(extent["outputs"][filename]["sha256"], sha256(output_dir / filename))

    def test_valid_unchanged_pair_writes_a_successful_empty_geojson(self):
        pre = np.full((7, 7), 0.8, dtype=np.float32)
        co = np.full((7, 7), 0.8, dtype=np.float32)
        input_dir = self.root / "unchanged-pair"
        prepared_pair(input_dir, pre, co)
        output_dir = self.root / "unchanged"

        coherence_change.create_change_map(
            EVENT_ID,
            input_dir=input_dir,
            output_dir=output_dir,
            pre_min=0.5,
            loss_min=0.3,
            min_pixels=1,
            simplify=0,
        )

        features = json.loads((output_dir / "change.geojson").read_text(encoding="utf-8"))
        extent = json.loads((output_dir / "change_extent.json").read_text(encoding="utf-8"))
        self.assertEqual(features, {"type": "FeatureCollection", "features": []})
        self.assertEqual(extent["stats"]["km2Changed"], 0)
        self.assertEqual(extent["stats"]["changedPixelCount"], 0)

    def test_mapper_requires_overwrite_and_staging_failure_preserves_previous_output_set(self):
        pre = np.full((7, 7), 0.8, dtype=np.float32)
        co = np.full((7, 7), 0.4, dtype=np.float32)
        input_dir = self.root / "overwrite-pair"
        prepared_pair(input_dir, pre, co)
        output_dir = self.root / "overwrite-map"
        kwargs = {
            "event_id": EVENT_ID,
            "input_dir": input_dir,
            "output_dir": output_dir,
            "pre_min": 0.5,
            "loss_min": 0.3,
            "min_pixels": 1,
            "simplify": 0,
        }
        first = coherence_change.create_change_map(**kwargs)
        output_names = (
            "change_mask.tif", "change.geojson", "06_change_check.png", "change_extent.json"
        )
        previous = {name: (output_dir / name).read_bytes() for name in output_names}

        with self.assertRaises(ValueError):
            coherence_change.create_change_map(**kwargs)
        self.assertEqual(previous, {name: (output_dir / name).read_bytes() for name in output_names})

        with mock.patch.object(coherence_change, "_write_qa", side_effect=OSError("synthetic staging failure")):
            with self.assertRaises(ValueError):
                coherence_change.create_change_map(**kwargs, overwrite=True)
        self.assertEqual(previous, {name: (output_dir / name).read_bytes() for name in output_names})
        self.assertFalse(any(path.name.startswith(".change-stage-") for path in output_dir.iterdir()))

        replaced = coherence_change.create_change_map(**kwargs, overwrite=True)
        self.assertNotEqual(replaced["runId"], first["runId"])

    def test_no_valid_and_no_eligible_inputs_fail_as_distinct_conditions(self):
        cases = (
            ("no-valid", np.full((7, 7), np.nan), np.full((7, 7), np.nan), "valid"),
            ("no-eligible", np.full((7, 7), 0.2), np.full((7, 7), 0.1), "eligible"),
        )
        for name, pre, co, message_fragment in cases:
            with self.subTest(case=name):
                input_dir = self.root / name
                prepared_pair(input_dir, pre, co)
                with self.assertRaises(ValueError) as caught:
                    coherence_change.create_change_map(
                        EVENT_ID, input_dir=input_dir, output_dir=self.root / f"out-{name}"
                    )
                self.assertIn(message_fragment, str(caught.exception).lower())

    def test_input_hash_and_prepared_grid_mismatches_are_rejected_before_publication(self):
        base_pre = np.full((7, 7), 0.8, dtype=np.float32)
        base_co = np.full((7, 7), 0.4, dtype=np.float32)

        hash_dir = self.root / "hash-mismatch"
        prepared_pair(hash_dir, base_pre, base_co)
        with rasterio.open(hash_dir / "coh_pre.tif", "r+") as pre:
            values = pre.read(1)
            values[2, 2] = 0.7
            pre.write(values, 1)
        hash_output = self.root / "hash-output"
        with self.assertRaises((ValueError, OSError)):
            coherence_change.create_change_map(EVENT_ID, input_dir=hash_dir, output_dir=hash_output)
        self.assertFalse(hash_output.exists())

        grid_dir = self.root / "grid-mismatch"
        prepared_pair(grid_dir, base_pre, base_co)
        metadata_path = grid_dir / "coherence_info.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        original = grid_dir / "coh_co.tif"
        with rasterio.open(original) as src:
            values = src.read(1)
            profile = src.profile.copy()
            tags = src.tags()
        profile["transform"] = from_origin(500030, 1700000, 30, 30)
        replacement = self.root / "co-misaligned.tif"
        with rasterio.open(replacement, "w", **profile) as dst:
            dst.write(values, 1)
            dst.update_tags(**tags)
        replacement.replace(original)
        metadata["outputs"]["coh_co.tif"]["sha256"] = sha256(original)
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        grid_output = self.root / "grid-output"
        with self.assertRaises((ValueError, OSError)):
            coherence_change.create_change_map(EVENT_ID, input_dir=grid_dir, output_dir=grid_output)
        self.assertFalse(grid_output.exists())

    def test_both_command_line_scripts_run_on_disposable_synthetic_products(self):
        from rasterio.warp import transform_bounds

        west, south, east, north = transform_bounds("EPSG:4326", "EPSG:32651", *EVENT["bbox"])
        resolution = 30
        width = int(np.ceil((east - west + 600) / resolution))
        height = int(np.ceil((north - south + 600) / resolution))
        transform = from_origin(west - 300, north + 300, resolution, resolution)
        pre = write_geotiff(
            self.root / "synthetic-pre.tif",
            np.full((height, width), 0.8, dtype=np.float32),
            transform=transform,
        )
        co = write_geotiff(
            self.root / "synthetic-co.tif",
            np.full((height, width), 0.4, dtype=np.float32),
            transform=transform,
        )
        manifest = valid_manifest(pre.name, co.name)
        inputs = self.root / "pairs.json"
        inputs.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        events = write_event_catalog(self.root / "events.json")
        extracted = self.root / "prepared"
        mapped = self.root / "mapped"
        backend_dir = Path(__file__).resolve().parents[1]
        old_argv = sys.argv[:]
        try:
            with mock.patch.object(coherence_io, "EVENTS_FILE", events):
                sys.argv = [
                    str(backend_dir / "scripts" / "05_coherence_extract.py"),
                    EVENT_ID,
                    "--inputs", str(inputs),
                    "--output-dir", str(extracted),
                ]
                try:
                    runpy.run_path(sys.argv[0], run_name="__main__")
                except SystemExit as exc:
                    self.assertEqual(exc.code, 0)

                sys.argv = [
                    str(backend_dir / "scripts" / "06_change_map.py"),
                    EVENT_ID,
                    "--input-dir", str(extracted),
                    "--output-dir", str(mapped),
                    "--pre-min", "0.5",
                    "--loss-min", "0.3",
                    "--min-pixels", "1",
                    "--simplify", "0",
                ]
                try:
                    runpy.run_path(sys.argv[0], run_name="__main__")
                except SystemExit as exc:
                    self.assertEqual(exc.code, 0)
        finally:
            sys.argv = old_argv

        self.assertTrue((extracted / "coherence_info.json").is_file())
        self.assertTrue((mapped / "change_extent.json").is_file())
        self.assertTrue((mapped / "change.geojson").is_file())
        extent = json.loads((mapped / "change_extent.json").read_text(encoding="utf-8"))
        self.assertGreater(extent["stats"]["km2Changed"], 0)


if __name__ == "__main__":
    unittest.main()
