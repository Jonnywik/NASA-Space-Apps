from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine
from pyproj import CRS
from rasterio.transform import from_origin
from shapely.geometry import box, mapping

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from processing import building_exposure
from processing.p3 import core


EVENT = "exposure_fixture"


def _raster(path: Path, values: np.ndarray, *, crs: str, transform: Affine, nodata=np.nan) -> Path:
    array = np.asarray(values, dtype="float32")
    with rasterio.open(
        path, "w", driver="GTiff", width=array.shape[1], height=array.shape[0],
        count=1, dtype="float32", crs=crs, transform=transform, nodata=nodata,
    ) as dataset:
        dataset.write(array, 1)
    return path


class BuildingExposureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="building-exposure-")
        self.root = Path(self.temp.name)
        self.output = self.root / "published"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _hazard(
        self,
        values: np.ndarray,
        *,
        product: str = "coherence-change",
        crs: str = "EPSG:32651",
        transform: Affine = from_origin(0, 20, 10, 10),
        source_run_ids: object = None,
        declared_grid: dict | None = None,
    ) -> Path:
        base = self.root / f"hazard-{len(list(self.root.glob('hazard-*')))}"
        base.mkdir()
        shape_values = values[0] if product == "change-frequency" else values
        height, width = shape_values.shape
        grid = {"crs": crs, "transform": list(transform)[:6], "width": width, "height": height}
        metadata = {"dataKind": "synthetic", "grid": declared_grid or grid, "sourceRunIds": source_run_ids or ["comparison-run"]}

        def writer(stage: Path) -> dict[str, str]:
            if product in {"coherence-change", "flood-extent"}:
                _raster(stage / "change_mask.tif", values, crs=crs, transform=transform)
                (stage / "change.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": []}), encoding="utf-8")
                return {"changeMask": "change_mask.tif", "changeGeometry": "change.geojson"}
            else:
                frequency, detection, support, minimum = values
                _raster(stage / "frequency.tif", frequency, crs=crs, transform=transform)
                _raster(stage / "detection.tif", detection, crs=crs, transform=transform)
                _raster(stage / "support.tif", support, crs=crs, transform=transform)
                return {"frequency": "frequency.tif", "detectionCount": "detection.tif", "validComparisonCount": "support.tif"}

        if product == "change-frequency":
            metadata["minimumObservations"] = int(values[3])
        manifest = core.publish(EVENT, product, metadata, writer, output_root=self.output)
        return Path(manifest)

    def _snapshot(
        self,
        features: list[dict],
        coverage,
        *,
        crs: str = "EPSG:32651",
        completeness: str | None = "complete",
        source_date: str = "2026-01-01",
        data_kind: str = "synthetic",
    ) -> Path:
        base = self.root / f"snapshot-{len(list(self.root.glob('snapshot-*')))}"
        base.mkdir()
        geojson = base / "buildings.geojson"
        geojson.write_text(json.dumps({
            "type": "FeatureCollection",
            "crs": {"type": "name", "properties": {"name": crs}},
            "features": features,
        }), encoding="utf-8")
        coverage_record = {"geometry": mapping(coverage), "crs": crs}
        if completeness is not None:
            coverage_record["completeness"] = completeness
        config = {
            "schemaVersion": "1.0", "dataKind": data_kind, "sourceDate": source_date,
            "source": "synthetic OSM fixture", "geojsonPath": geojson.name,
            "sha256": core.digest(geojson), "coverage": coverage_record,
        }
        config_path = base / "snapshot.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        return config_path

    @staticmethod
    def _feature(osm_type: str, osm_id: int | str, geometry, **properties) -> dict:
        return {
            "type": "Feature",
            "properties": {"osmType": osm_type, "osmId": osm_id, **properties},
            "geometry": mapping(geometry),
        }

    def _report(self, hazard: Path, snapshot: Path, *, regions: Path | None = None, threshold: float | None = None) -> tuple[dict, dict]:
        manifest_path = building_exposure.build_exposure(
            EVENT, hazard, snapshot, output_root=self.output, regions_path=regions,
            frequency_threshold=threshold,
        )
        manifest = core.load_manifest(manifest_path)
        return manifest, json.loads(core.asset_path(manifest, "exposure").read_text(encoding="utf-8"))

    def test_duplicate_composite_osm_ids_and_overlapping_regions_union_before_combined_total(self):
        hazard = self._hazard(np.array([[1, 0], [1, 0]], dtype="float32"))
        buildings = [
            self._feature("way", 7, box(2, 2, 6, 18)),
            self._feature("way", "007", box(4, 2, 9, 18)),
            self._feature("relation", 7, box(2, 2, 6, 18)),
            # Shares only an edge with the detected left column.
            self._feature("way", 8, box(10, 11, 14, 19)),
        ]
        snapshot = self._snapshot(buildings, box(0, 0, 20, 20))
        regions_path = self.root / "regions.geojson"
        regions_path.write_text(json.dumps({
            "type": "FeatureCollection",
            "crs": {"type": "name", "properties": {"name": "EPSG:32651"}},
            "features": [
                {"type": "Feature", "properties": {"regionId": "west"}, "geometry": mapping(box(0, 0, 12, 20))},
                {"type": "Feature", "properties": {"regionId": "east"}, "geometry": mapping(box(8, 0, 20, 20))},
            ],
        }), encoding="utf-8")

        manifest, report = self._report(hazard, snapshot, regions=regions_path)
        rows = {row["regionId"]: row for row in report["regions"]}
        self.assertEqual(rows["west"]["mappedHazardOverlapCount"], 2)
        self.assertEqual(rows["east"]["mappedHazardOverlapCount"], 1)
        self.assertEqual(report["combined"]["mappedHazardOverlapCount"], 2)
        self.assertEqual(report["combined"]["uniqueOsmIds"], ["relation/7", "way/7"])
        self.assertEqual(manifest["product"], "building-exposure")
        self.assertEqual(manifest["hazardRunId"], core.load_manifest(hazard)["runId"])
        self.assertIn("comparison-run", manifest["sourceRunIds"])

    def test_nodata_is_not_dry_and_unknown_snapshot_returns_partial_count(self):
        values = np.array([[1, 0], [np.nan, 0]], dtype="float32")
        hazard = self._hazard(values)
        snapshot = self._snapshot(
            [self._feature("way", 3, box(1, 11, 9, 19))],
            box(0, 10, 10, 20), completeness=None,
        )
        _, report = self._report(hazard, snapshot)
        row = report["regions"][0]
        self.assertEqual(report["hazardSupport"]["validPixelCount"], 3)
        self.assertIsNone(row["mappedHazardOverlapCount"])
        self.assertEqual(row["partialMappedHazardOverlapCount"], 1)
        self.assertEqual(row["countStatus"], "partial")
        self.assertIn("unknown", row["countReason"])
        self.assertLess(row["snapshotCoverage"]["percentOfValidHazardArea"], 100)

    def test_valid_empty_detection_is_zero_only_when_snapshot_and_hazard_cover_region(self):
        hazard = self._hazard(np.zeros((2, 2), dtype="float32"))
        snapshot = self._snapshot([], box(0, 0, 20, 20), completeness="complete")
        _, report = self._report(hazard, snapshot)
        row = report["regions"][0]
        self.assertEqual(row["countStatus"], "complete")
        self.assertEqual(row["mappedHazardOverlapCount"], 0)
        self.assertEqual(row["partialMappedHazardOverlapCount"], 0)

    def test_partial_hazard_support_in_registered_region_never_claims_a_complete_count(self):
        hazard = self._hazard(np.zeros((2, 2), dtype="float32"))
        snapshot = self._snapshot([], box(0, 0, 30, 20), completeness="complete")
        regions_path = self.root / "wide-region.geojson"
        regions_path.write_text(json.dumps({
            "type": "FeatureCollection",
            "crs": {"type": "name", "properties": {"name": "EPSG:32651"}},
            "features": [{"type": "Feature", "properties": {"regionId": "wide"},
                          "geometry": mapping(box(0, 0, 30, 20))}],
        }), encoding="utf-8")
        _, report = self._report(hazard, snapshot, regions=regions_path)
        row = report["regions"][0]
        self.assertIsNone(row["mappedHazardOverlapCount"])
        self.assertEqual(row["partialMappedHazardOverlapCount"], 0)
        self.assertIn("Hazard raster support", row["countReason"])

    def test_frequency_threshold_uses_explicit_valid_comparison_support(self):
        frequency = np.array([[0.5, 0.0], [np.nan, 2 / 3]], dtype="float32")
        detections = np.array([[1, 0], [1, 2]], dtype="float32")
        support = np.array([[2, 2], [1, 3]], dtype="float32")
        hazard = self._hazard((frequency, detections, support, 2), product="change-frequency")
        buildings = [
            self._feature("way", 1, box(1, 11, 9, 19)),
            self._feature("way", 2, box(11, 1, 19, 9)),
        ]
        snapshot = self._snapshot(buildings, box(0, 0, 20, 20))
        with self.assertRaisesRegex(ValueError, "explicit frequency_threshold"):
            building_exposure.build_exposure(EVENT, hazard, snapshot, output_root=self.output)
        _, report = self._report(hazard, snapshot, threshold=0.5)
        self.assertEqual(report["hazardSupport"]["validPixelCount"], 3)
        self.assertEqual(report["hazardSupport"]["detectionPixelCount"], 2)
        self.assertEqual(report["regions"][0]["mappedHazardOverlapCount"], 2)

    def test_geographic_raster_is_reprojected_to_local_metric_crs_for_area(self):
        transform = from_origin(120.9, 15.0, 0.001, 0.001)
        hazard = self._hazard(np.array([[0, 0]], dtype="float32"), crs="EPSG:4326", transform=transform)
        snapshot = self._snapshot([], box(120.9, 14.999, 120.902, 15.0), crs="EPSG:4326")
        _, report = self._report(hazard, snapshot)
        self.assertEqual(CRS.from_user_input(report["analysisCrs"]).to_epsg(), 32651)
        self.assertAlmostEqual(CRS.from_user_input(report["analysisCrs"]).axis_info[0].unit_conversion_factor, 1.0)
        self.assertGreater(report["regions"][0]["validHazardCoverage"]["validAreaKm2"], 0.01)

    def test_hash_and_hazard_lineage_mismatches_are_rejected(self):
        hazard = self._hazard(np.array([[1]], dtype="float32"))
        snapshot = self._snapshot([], box(0, 10, 10, 20))
        config_path = snapshot
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["sha256"] = "0" * 64
        config_path.write_text(json.dumps(config), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            building_exposure.build_exposure(EVENT, hazard, config_path, output_root=self.output)

        bad_lineage = self._hazard(np.array([[1]], dtype="float32"), source_run_ids="not-a-list")
        good_snapshot = self._snapshot([], box(0, 10, 10, 20))
        with self.assertRaisesRegex(ValueError, "sourceRunIds must be a list"):
            building_exposure.build_exposure(EVENT, bad_lineage, good_snapshot, output_root=self.output)

    def test_frequency_raster_must_match_count_ratio(self):
        frequency = np.array([[0.75]], dtype="float32")
        detections = np.array([[1]], dtype="float32")
        support = np.array([[2]], dtype="float32")
        hazard = self._hazard((frequency, detections, support, 1), product="change-frequency")
        snapshot = self._snapshot([], box(0, 10, 10, 20))
        with self.assertRaisesRegex(ValueError, "must equal detectionCount"):
            building_exposure.build_exposure(EVENT, hazard, snapshot, output_root=self.output, frequency_threshold=0.5)


if __name__ == "__main__":
    unittest.main()
