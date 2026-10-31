from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from processing.p3.briefing import build_briefing, generate
from processing.p3 import core


class BriefingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = {
            "event": "test_event",
            "eventName": "Harbor",
            "product": "flood-observation",
            "runId": "run-main",
            "dataKind": "observed",
            "observationStart": "2026-01-01",
            "observationEnd": "2026-01-03",
            "coverage": {"validCoveragePercent": 94.5},
            "stats": {"km2Changed": 0, "floodArea": None},
            "sources": [{"name": "SAR source", "productId": "P-1", "sha256": "abc"}],
        }

    def test_zero_area_is_distinct_from_missing_and_text_is_repeatable(self):
        first = build_briefing(self.manifest)
        second = build_briefing(self.manifest)
        self.assertEqual(first, second)
        self.assertEqual(first["facts"]["metrics"]["changedAreaKm2"], 0)
        self.assertIsNone(first["facts"]["metrics"]["floodAreaKm2"])
        self.assertIn("reported changed area is 0 km²", first["text"])
        self.assertNotIn("reported flood area", first["text"])
        self.assertIn("empty detection", first["text"])
        self.assertIn("observations 2026-01-01 to 2026-01-03", first["text"])

    def test_html_like_region_and_source_names_are_treated_as_data(self):
        manifest = dict(self.manifest)
        manifest["eventName"] = '<img src=x onerror="alert(1)">'
        manifest["sources"] = [{"name": "<script>alert(1)</script>"}]
        text = build_briefing(manifest)["text"]
        self.assertIn("&lt;img", text)
        self.assertIn("&lt;script&gt;", text)
        self.assertNotIn("<script>", text)
        self.assertNotIn("onerror=\"", text)

    def test_regional_summary_is_required_and_does_not_fall_back_to_whole_event(self):
        manifest = dict(self.manifest)
        manifest["regionalSummaries"] = {"north": {"name": "North", "stats": {"km2Changed": None}}}
        result = build_briefing(manifest, "north")
        self.assertIsNone(result["facts"]["metrics"]["changedAreaKm2"])
        with self.assertRaisesRegex(ValueError, "Unknown region_id"):
            build_briefing(manifest, "south")

    def test_mixed_synthetic_lineage_is_labeled_synthetic_and_expired_snapshot_warns(self):
        exposure = {
            "event": "test_event",
            "runId": "exposure-run",
            "dataKind": "synthetic",
            "timestamp": "2020-01-01T00:00:00Z",
            "expiresAt": "2020-01-02T00:00:00Z",
            "coverage": {"percent": 80},
            "assetCount": 0,
        }
        result = build_briefing(self.manifest, exposure=exposure)
        self.assertEqual(result["dataKind"], "synthetic")
        self.assertIn("synthetic", result["provenance"]["dataKinds"])
        self.assertIn("exposure snapshot expired", " ".join(result["facts"]["warnings"]))
        self.assertIn("labeled synthetic", result["text"])
        self.assertIn("exposure-run", result["sourceRunIds"])

    def test_exposure_event_region_and_linked_run_mismatches_are_rejected(self):
        for exposure in (
            {"event": "another_event"},
            {"regionId": "south"},
            {"inputRunId": "wrong-run"},
        ):
            with self.subTest(exposure=exposure), self.assertRaises(ValueError):
                build_briefing(self.manifest, region_id="north", exposure=exposure)

    def test_deduplicates_unique_positive_area_footprints_clipped_to_metric_region(self):
        manifest = dict(self.manifest)
        manifest["regionalSummaries"] = {
            "north": {
                "name": "North",
                "geometryCrs": "EPSG:32651",
                "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [100, 0], [100, 100], [0, 100], [0, 0]]]},
            }
        }
        exposure = {
            "event": "test_event",
            "regionId": "north",
            "crs": "EPSG:32651",
            "timestamp": "2026-02-01T12:00:00Z",
            "coverage": {"percent": 80},
            "footprints": [
                {"id": "building-1", "geometry": {"type": "Polygon", "coordinates": [[[10, 10], [20, 10], [20, 20], [10, 20], [10, 10]]]}},
                {"id": "building-1", "geometry": {"type": "Polygon", "coordinates": [[[15, 15], [30, 15], [30, 30], [15, 30], [15, 15]]]}},
                {"id": "outside", "geometry": {"type": "Polygon", "coordinates": [[[110, 10], [120, 10], [120, 20], [110, 20], [110, 10]]]}},
                {"id": "touching-edge", "geometry": {"type": "Polygon", "coordinates": [[[100, 10], [110, 10], [110, 20], [100, 20], [100, 10]]]}},
            ],
        }
        result = build_briefing(manifest, "north", exposure)
        self.assertEqual(result["facts"]["metrics"]["regionAssetOverlapCount"], 1)
        self.assertIn("unique mapped asset overlaps in the named region", result["text"])
        self.assertIn("snapshot as of 2026-02-01T12:00:00Z", result["text"])
        self.assertIn("snapshot coverage 80%", result["text"])
        self.assertNotIn("indicating exposure rather than damage", result["text"])

    def test_exposed_assets_require_an_explicit_metric_exposure_footprint(self):
        manifest = dict(self.manifest)
        manifest["regionalSummaries"] = {
            "north": {
                "name": "North",
                "geometryCrs": "EPSG:32651",
                "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [100, 0], [100, 100], [0, 100], [0, 0]]]},
            }
        }
        exposure = {
            "event": "test_event",
            "regionId": "north",
            "crs": "EPSG:32651",
            "exposureGeometry": {"type": "Polygon", "coordinates": [[[0, 0], [12, 0], [12, 12], [0, 12], [0, 0]]]},
            "footprints": [
                {"id": "inside", "geometry": {"type": "Polygon", "coordinates": [[[10, 10], [20, 10], [20, 20], [10, 20], [10, 10]]]}},
                {"id": "outside-hazard", "geometry": {"type": "Polygon", "coordinates": [[[30, 30], [40, 30], [40, 40], [30, 40], [30, 30]]]}},
            ],
        }
        result = build_briefing(manifest, "north", exposure)
        self.assertEqual(result["facts"]["metrics"]["exposedAssetCount"], 1)
        self.assertIn("exposure context, not damage", result["text"])

    def test_task_specific_series_and_biomass_fields_are_normalized(self):
        motion = {
            "event": "test_event", "product": "ground-motion", "runId": "motion-run", "dataKind": "synthetic",
            "epochs": ["2024-01-01", "2024-02-01", "2024-03-01"], "referenceEpoch": "2024-01-01",
            "nativeResolutionMetres": 30, "regionalSummary": {"medianRateMmPerYear": -4.5, "validRateCellCount": 12,
                                                                     "selectedCellCount": 20, "medianValidEpochCount": 3},
        }
        motion_result = build_briefing(motion)
        self.assertEqual(motion_result["facts"]["metrics"]["losRateMmPerYear"], -4.5)
        self.assertEqual(motion_result["facts"]["nativeSupport"]["nativeResolution"], 30)
        self.assertEqual(motion_result["facts"]["nativeSupport"]["validPixelCount"], 12)
        self.assertIn("observations 2024-01-01 to 2024-03-01", motion_result["text"])
        self.assertEqual(motion_result["dataKind"], "synthetic")

        biomass = {
            "event": "test_event", "product": "biomass", "dataKind": "derived",
            "statistics": {"medianMgPerHa": 46.25, "validPixelCount": 18},
            "nativeResolution": 30,
            "regionalMetrics": [{"regionId": "north", "medianMgPerHa": 28.5, "validPixelCount": 3,
                                 "observationStartDate": "2025-01-02", "observationEndDate": "2025-01-12", "resolutionMetres": 30}],
        }
        whole = build_briefing(biomass)
        north = build_briefing(biomass, "north")
        self.assertEqual(whole["facts"]["metrics"]["biomassMgHa"], 46.25)
        self.assertEqual(north["facts"]["metrics"]["biomassMgHa"], 28.5)
        self.assertEqual(north["facts"]["nativeSupport"]["validPixelCount"], 3)
        self.assertIn("2025-01-02 to 2025-01-12", north["text"])

    def test_projection_briefing_requires_and_uses_one_supported_year_only(self):
        projection = {
            "event": "test_event",
            "product": "projection",
            "scenarioId": "central",
            "runId": "projection-run",
            "dataKind": "scenario",
            "supportedYears": [2026, 2027],
            "baselineEpoch": "2025-01-01",
            "nativeResolutionMetres": 30,
            # Root stats are deliberately an all-years aggregate and must not leak.
            "stats": {"exposedAreaKm2": 999.0},
            "annualMetrics": {
                "2026": {
                    "medianLosMm": -2.5,
                    "validLosCellCount": 7,
                    "validTerrainCellCount": 12,
                    "validExposureCellCount": 6,
                    "exposedCellCount": 4,
                    "exposedAreaKm2": 0.4,
                    "exposedAssetCount": None,
                    "exposedPopulationCount": None,
                    "snapshotMetricsAvailability": {
                        "exposedAssetCount": {"available": False, "reason": "No asset snapshot supplied."},
                        "exposedPopulationCount": {"available": False, "reason": "No population snapshot supplied."},
                    },
                },
                "2027": {
                    "medianLosMm": -5.0,
                    "validTerrainCellCount": 12,
                    "exposedCellCount": 9,
                    "exposedAreaKm2": 0.9,
                    "exposedAssetCount": 2,
                    "exposedPopulationCount": 10,
                },
            },
        }
        with self.assertRaisesRegex(ValueError, "year is required"):
            build_briefing(projection)
        first = build_briefing(projection, year=2026)
        second = build_briefing(projection, year=2027)
        self.assertEqual(first["selectedYear"], 2026)
        self.assertEqual(first["facts"]["metrics"]["scenarioExposureAreaKm2"], 0.4)
        self.assertEqual(first["facts"]["metrics"]["medianLosDisplacementMm"], -2.5)
        self.assertEqual(first["facts"]["nativeSupport"]["validPixelCount"], 12)
        self.assertEqual(first["facts"]["metricReasons"]["exposedAssetCount"], "No asset snapshot supplied.")
        self.assertIn("projection 2026", first["text"])
        self.assertIn("No population snapshot supplied", first["text"])
        self.assertNotIn("999", first["text"])
        self.assertEqual(second["facts"]["metrics"]["scenarioExposureAreaKm2"], 0.9)
        self.assertEqual(second["facts"]["metrics"]["exposedAssetCount"], 2)
        self.assertIn("exposure context, not damage", second["text"])
        with self.assertRaisesRegex(ValueError, "Unsupported projection year"):
            build_briefing(projection, year=2028)

    def test_generate_hash_checks_input_and_publishes_named_briefing_asset(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.txt"
            source.write_text("source", encoding="utf-8")
            source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            input_manifest = dict(self.manifest)
            input_manifest["assets"] = {"source": {"path": "source.txt", "sha256": source_hash}}
            input_path = root / "input.json"
            input_path.write_text(json.dumps(input_manifest), encoding="utf-8")
            output = generate("test_event", input_path, output_root=root / "output")
            published = core.load_manifest(output)
            self.assertEqual(published["product"], "briefing")
            self.assertEqual(published["dataKind"], "observed")
            self.assertIn("briefing", published["assets"])
            payload = json.loads(core.asset_path(published, "briefing").read_text(encoding="utf-8"))
            self.assertEqual(payload["text"], build_briefing(self.manifest)["text"])

            input_manifest["assets"]["source"]["sha256"] = "0" * 64
            input_path.write_text(json.dumps(input_manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Asset hash mismatch"):
                generate("test_event", input_path, output_root=root / "bad-output")


if __name__ == "__main__":
    unittest.main()
