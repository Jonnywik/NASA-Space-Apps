from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from processing.change_frequency import ChangeFrequencyError, build_frequency
from processing.p3 import core


EVENT = "frequency_fixture"


def _source_details(index: int) -> dict:
    first = f"scene-{index:03d}-A"
    middle = f"scene-{index:03d}-B"
    last = f"scene-{index:03d}-C"
    common = {
        "relativeOrbit": 123,
        "flightDirection": "ASCENDING",
        "polarization": "VV",
        "processingVersion": "fixture-1",
    }
    return {
        "pre": {**common, "sceneIds": [first, middle]},
        "co": {**common, "sceneIds": [middle, last]},
    }


class ChangeFrequencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="change-frequency-")
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def _publish_change(
        self,
        index: int,
        mask: np.ndarray,
        *,
        transform=None,
        crs="EPSG:32651",
        comparison_id=None,
        pre_pair=None,
        co_pair=None,
        sources=None,
        parameters=None,
    ) -> Path:
        values = np.asarray(mask, dtype=np.float64)
        if values.ndim != 2:
            raise ValueError("fixture masks must be two-dimensional")
        transform = transform or from_origin(500000, 1700000, 30, 30)
        pre_pair = pre_pair or [f"2024-01-{index * 10 + 1:02d}", f"2024-01-{index * 10 + 5:02d}"]
        co_pair = co_pair or [pre_pair[1], f"2024-01-{index * 10 + 9:02d}"]
        source_details = sources if sources is not None else _source_details(index)
        encoded = np.full(values.shape, 255, dtype=np.uint8)
        valid = np.isfinite(values)
        encoded[valid] = values[valid].astype(np.uint8)
        grid = {
            "crs": crs,
            "transform": list(tuple(transform)[:6]),
            "width": values.shape[1],
            "height": values.shape[0],
            "resolutionMetres": max(abs(transform.a), abs(transform.e)),
        }
        metadata = {
            "dataKind": "synthetic",
            "syntheticLineage": [f"fixture-mask-{index}"],
            "comparisonId": comparison_id or f"comparison-{index}",
            "prePair": pre_pair,
            "coPair": co_pair,
            "parameters": parameters or {
                "preMin": 0.5,
                "lossMin": 0.3,
                "minPixels": 1,
                "smoothingKernel": "3x3",
            },
            "algorithmVersion": "paired-coherence-change-1.0",
            "grid": grid,
            "sources": source_details,
            "sourceRunIds": [f"legacy-change-run-{index}"],
        }

        def writer(stage):
            with rasterio.open(
                stage / "change_mask.tif",
                "w",
                driver="GTiff",
                width=values.shape[1],
                height=values.shape[0],
                count=1,
                dtype="uint8",
                crs=crs,
                transform=transform,
                nodata=255,
                compress="lzw",
            ) as dataset:
                dataset.write(encoded, 1)
                dataset.update_tags(dataKind="synthetic", productType="coherence-change-mask")
            (stage / "change.geojson").write_text(
                json.dumps({"type": "FeatureCollection", "features": []}), encoding="utf-8"
            )
            return {"changeMask": "change_mask.tif", "changeGeometry": "change.geojson"}

        manifest_path = core.publish(
            EVENT,
            "coherence-change",
            metadata,
            writer,
            output_root=self.root / "inputs",
        )
        return Path(manifest_path)

    def _load_output(self, paths, *, minimum_observations=2):
        manifest_path = build_frequency(
            EVENT,
            paths,
            output_root=self.root / "frequency-output",
            minimum_observations=minimum_observations,
        )
        manifest = core.load_manifest(manifest_path)
        return Path(manifest_path), manifest

    def test_aligns_different_grids_to_union_at_coarsest_resolution_and_publishes_counts(self):
        # Each 2x2 block has a constant category so nearest-neighbor tie locations
        # cannot affect the expected 20 m alignment of the 10 m source.
        fine = np.repeat(np.repeat(np.array([[1, 0], [1, 0]], dtype=np.float32), 2, axis=0), 2, axis=1)
        coarse = np.array([[1, 0], [0, 1]], dtype=np.float32)
        first = self._publish_change(
            0, fine, transform=from_origin(0, 40, 10, 10),
            pre_pair=["2024-01-01", "2024-01-05"], co_pair=["2024-01-05", "2024-01-10"],
        )
        second = self._publish_change(
            1, coarse, transform=from_origin(20, 40, 20, 20),
            pre_pair=["2024-02-01", "2024-02-05"], co_pair=["2024-02-05", "2024-02-10"],
        )

        manifest_path, manifest = self._load_output([first, second])

        self.assertEqual(manifest["product"], "change-frequency")
        self.assertEqual(manifest["dataKind"], "synthetic")
        self.assertEqual(manifest["comparisonCount"], 2)
        self.assertEqual(manifest["units"]["frequency"], "fraction")
        self.assertEqual(manifest["grid"]["width"], 3)
        self.assertEqual(manifest["grid"]["height"], 2)
        self.assertEqual(manifest["grid"]["resolution"], {"x": 20.0, "y": 20.0})
        self.assertEqual(manifest["grid"]["bounds"], [0.0, 0.0, 60.0, 40.0])
        self.assertEqual(set(manifest["assets"]), {"frequency", "detectionCount", "validComparisonCount"})
        self.assertEqual(set(manifest["sourceRunIds"]), {core.load_manifest(first)["runId"], core.load_manifest(second)["runId"]})
        self.assertEqual(len(manifest["syntheticLineage"]), 2)
        for item in manifest["syntheticLineage"]:
            self.assertEqual(len(item["manifestSha256"]), 64)
            self.assertIn("changeMask", item["assetSha256"])

        frequency, grid = core.read_raster(manifest, "frequency")
        detections, _ = core.read_raster(manifest, "detectionCount")
        support, _ = core.read_raster(manifest, "validComparisonCount")
        self.assertEqual(grid["width"], 3)
        np.testing.assert_allclose(support, [[1, 2, 1], [1, 2, 1]])
        np.testing.assert_allclose(detections, [[1, 1, 0], [1, 0, 1]])
        self.assertTrue(np.isnan(frequency[0, 0]))
        self.assertAlmostEqual(float(frequency[0, 1]), 0.5)
        self.assertTrue(np.isnan(frequency[0, 2]))
        self.assertTrue(np.isnan(frequency[1, 0]))
        self.assertAlmostEqual(float(frequency[1, 1]), 0.0)
        self.assertTrue(np.isnan(frequency[1, 2]))
        self.assertTrue(any("not independent measurements" in warning for warning in manifest["warnings"]))
        self.assertEqual(core.load_manifest(manifest_path)["runId"], manifest["runId"])

    def test_nodata_has_nan_counts_and_below_minimum_support_keeps_numeric_counts(self):
        first = self._publish_change(
            0,
            np.array([[np.nan, 1], [0, 1]], dtype=np.float32),
            transform=from_origin(0, 60, 30, 30),
            pre_pair=["2024-01-01", "2024-01-05"], co_pair=["2024-01-05", "2024-01-10"],
        )
        second = self._publish_change(
            1,
            np.array([[np.nan, np.nan], [0, 1]], dtype=np.float32),
            transform=from_origin(0, 60, 30, 30),
            pre_pair=["2024-02-01", "2024-02-05"], co_pair=["2024-02-05", "2024-02-10"],
        )

        _, manifest = self._load_output([first, second])
        frequency, _ = core.read_raster(manifest, "frequency")
        detections, _ = core.read_raster(manifest, "detectionCount")
        support, _ = core.read_raster(manifest, "validComparisonCount")

        self.assertTrue(np.isnan(frequency[0, 0]))
        self.assertTrue(np.isnan(detections[0, 0]))
        self.assertTrue(np.isnan(support[0, 0]))
        self.assertTrue(np.isnan(frequency[0, 1]))
        self.assertEqual(float(detections[0, 1]), 1.0)
        self.assertEqual(float(support[0, 1]), 1.0)
        np.testing.assert_allclose(frequency[1], [0.0, 1.0])
        np.testing.assert_allclose(detections[1], [0.0, 2.0])
        np.testing.assert_allclose(support[1], [2.0, 2.0])
        self.assertEqual(manifest["statistics"]["supportedPixelCount"], 3)
        self.assertEqual(manifest["statistics"]["frequencyPixelCount"], 2)

    def test_default_two_observation_minimum_does_not_publish_single_comparison_frequency(self):
        one = self._publish_change(0, np.array([[0, 1], [1, 0]], dtype=np.float32))

        _, manifest = self._load_output([one])

        frequency, _ = core.read_raster(manifest, "frequency")
        detections, _ = core.read_raster(manifest, "detectionCount")
        support, _ = core.read_raster(manifest, "validComparisonCount")
        self.assertTrue(np.all(np.isnan(frequency)))
        np.testing.assert_allclose(detections, [[0, 1], [1, 0]])
        np.testing.assert_allclose(support, np.ones((2, 2)))

    def test_renamed_duplicate_comparison_is_rejected_even_when_run_ids_differ(self):
        dates = ["2024-01-01", "2024-01-05"]
        event_dates = ["2024-01-05", "2024-01-10"]
        sources = _source_details(0)
        sources["pre"]["productId"] = "processed-product-v1"
        sources["co"]["productId"] = "processed-product-v1"
        first = self._publish_change(
            0, np.ones((2, 2)), comparison_id="comparison-original",
            pre_pair=dates, co_pair=event_dates, sources=sources,
        )
        reprocessed_sources = _source_details(0)
        reprocessed_sources["pre"]["productId"] = "processed-product-v2"
        reprocessed_sources["co"]["productId"] = "processed-product-v2"
        second = self._publish_change(
            1, np.zeros((2, 2)), comparison_id="comparison-renamed",
            pre_pair=dates, co_pair=event_dates, sources=reprocessed_sources,
        )
        self.assertNotEqual(core.load_manifest(first)["runId"], core.load_manifest(second)["runId"])
        self.assertNotEqual(core.load_manifest(first)["sourceRunIds"], core.load_manifest(second)["sourceRunIds"])

        with self.assertRaisesRegex(ChangeFrequencyError, "same date and source IDs"):
            build_frequency(EVENT, [first, second], output_root=self.root / "should-not-publish")

    def test_threshold_and_source_basis_incompatibility_are_rejected(self):
        first = self._publish_change(0, np.ones((2, 2)))
        altered_parameters = {"preMin": 0.5, "lossMin": 0.4, "minPixels": 1, "smoothingKernel": "3x3"}
        second = self._publish_change(1, np.ones((2, 2)), parameters=altered_parameters)
        with self.assertRaisesRegex(ChangeFrequencyError, "incompatible method and parameters"):
            build_frequency(EVENT, [first, second], output_root=self.root / "threshold-output")

        changed_sources = _source_details(2)
        changed_sources["pre"]["polarization"] = "HH"
        third = self._publish_change(2, np.ones((2, 2)), sources=changed_sources)
        with self.assertRaisesRegex(ChangeFrequencyError, "incompatible sourceBasis"):
            build_frequency(EVENT, [first, third], output_root=self.root / "basis-output")

    def test_shared_acquisition_and_overlapping_periods_are_reported(self):
        first_sources = _source_details(0)
        first_sources["pre"]["sceneIds"] = ["acq-01", "shared-acq"]
        first_sources["co"]["sceneIds"] = ["shared-acq", "acq-10"]
        second_sources = _source_details(1)
        second_sources["pre"]["sceneIds"] = ["shared-acq", "acq-12"]
        second_sources["co"]["sceneIds"] = ["acq-12", "acq-20"]
        first = self._publish_change(
            0, np.ones((2, 2)),
            pre_pair=["2024-01-01", "2024-01-05"],
            co_pair=["2024-01-05", "2024-01-10"],
            sources=first_sources,
        )
        second = self._publish_change(
            1, np.zeros((2, 2)),
            pre_pair=["2024-01-05", "2024-01-12"],
            co_pair=["2024-01-12", "2024-01-20"],
            sources=second_sources,
        )

        _, manifest = self._load_output([first, second], minimum_observations=1)

        self.assertTrue(any("share acquisition dates: 2024-01-05" in warning for warning in manifest["warnings"]))
        self.assertTrue(any("periods overlap" in warning for warning in manifest["warnings"]))

    def test_mixed_crs_inputs_are_rejected(self):
        first = self._publish_change(0, np.ones((2, 2)), transform=from_origin(0, 60, 30, 30))
        second = self._publish_change(
            1, np.ones((2, 2)), transform=from_origin(0, 0.02, 0.01, 0.01), crs="EPSG:4326"
        )
        with self.assertRaisesRegex(ChangeFrequencyError, "different CRS"):
            build_frequency(EVENT, [first, second], output_root=self.root / "crs-output")


if __name__ == "__main__":
    unittest.main()
