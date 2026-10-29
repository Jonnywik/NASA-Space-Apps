from __future__ import annotations

from datetime import datetime, timedelta, timezone
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

from processing.p3 import core
from processing.p3.projection import project
from processing.p3.series import YEAR_DAYS, build_series
from processing.p3.terrain import prepare_inputs


EVENT = "projection_fixture"
CRS = "EPSG:32651"
TRANSFORM = from_origin(500000, 1700000, 10, 10)


def _write_raster(path: Path, array: np.ndarray, *, nodata=None, transform=TRANSFORM) -> Path:
    array = np.asarray(array)
    with rasterio.open(
        path, "w", driver="GTiff", width=array.shape[1], height=array.shape[0],
        count=1, dtype=array.dtype, crs=CRS, transform=transform, nodata=nodata,
    ) as dataset:
        dataset.write(array, 1)
    return path


def _stamp(day: int) -> str:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return (start + timedelta(days=day)).isoformat().replace("+00:00", "Z")


class ProjectionPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="p3-projection-")
        self.root = Path(self.temp.name)
        self.output = self.root / "published"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _motion_manifest(self, *, rate_mm_per_year: float = 12.0, all_nodata: bool = False) -> Path:
        pair_paths = []
        days = [0, 30, 60, 90, 120, 150]
        for index, (first, second) in enumerate(zip(days[:-1], days[1:])):
            pair_dir = self.root / f"pair-run-{index}"
            pair_dir.mkdir(exist_ok=True)
            displacement = np.full((4, 4), np.nan if all_nodata else rate_mm_per_year * (second - first) / YEAR_DAYS,
                                   dtype=np.float32)
            displacement_path = _write_raster(pair_dir / "displacement.tif", displacement, nodata=np.nan)
            valid_path = _write_raster(pair_dir / "valid.tif", np.ones((4, 4), dtype=np.float32))
            pair_manifest = {
                "schemaVersion": "1.0", "event": EVENT, "product": "los-pair",
                "runId": f"pair-run-{index}", "dataKind": "synthetic", "syntheticLineage": True,
                "displacementUnits": "mm", "units": {"displacement": "mm"},
                "displacementConvention": "positive_away_from_satellite",
                "acquisitionDates": [_stamp(first), _stamp(second)],
                "spatialReferenceId": "fixture-reference", "spatialReferenceHash": "fixture-reference-hash",
                "correctionState": "provider-as-delivered", "correctionsApplied": [],
                "geometry": {"lookDirection": "right"},
                "sourceBasis": {"orbit": "ascending-fixture", "frame": "frame-1", "maturity": "synthetic",
                                "sensor": "fixture", "sourceProfile": "fixture", "frequency": "L", "polarization": "HH"},
                "assets": {
                    "displacementMm": {"path": displacement_path.name, "sha256": core.digest(displacement_path)},
                    "validMask": {"path": valid_path.name, "sha256": core.digest(valid_path)},
                },
            }
            manifest_path = pair_dir / "manifest.json"
            manifest_path.write_text(json.dumps(pair_manifest), encoding="utf-8")
            pair_paths.append(manifest_path)
        return build_series(EVENT, pair_paths, output_root=self.output)

    def _terrain_manifest(self, *, barriers: bool = True, nodata_cell: bool = True) -> Path:
        dem = np.zeros((4, 4), dtype=np.float32)
        seeds = np.zeros((4, 4), dtype=np.uint8)
        seeds[:, 0] = 1
        if nodata_cell:
            dem[1, 1] = -9999
        dem_path = _write_raster(self.root / "dem.tif", dem, nodata=-9999)
        seeds_path = _write_raster(self.root / "seeds.tif", seeds)
        barrier_spec = None
        if barriers:
            walls = np.zeros((4, 4), dtype=np.uint8)
            walls[:, 2] = 1
            wall_path = _write_raster(self.root / "barriers.tif", walls, nodata=255)
            barrier_spec = {"path": wall_path.name, "trueValues": [1]}
        config = {
            "dataKind": "synthetic", "verticalDatum": "FIXTURE_DATUM",
            "verticalReferenceEpoch": "2010.0", "projectionBaselineEpoch": "2026-01-01",
            "targetCrs": CRS,
            "terrain": {
                "path": dem_path.name, "units": "m", "positiveDirection": "up",
                "representation": "ground", "verticalDatum": "FIXTURE_DATUM",
                "verticalReferenceEpoch": "2010.0", "baselineEpoch": "2026-01-01",
                "sourceDate": "2026-01-01",
            },
            "coastalSeeds": {"path": seeds_path.name, "trueValues": [1]},
            "barriers": barrier_spec,
            "waterLevels": [
                {"year": 2026, "scenario": "central", "mode": "total",
                 "source": {"kind": "scalar", "value": 0.5, "units": "m",
                            "positiveDirection": "up", "semantics": "total_water_level",
                            "verticalDatum": "FIXTURE_DATUM", "verticalReferenceEpoch": "2010.0",
                            "sourceDate": "2026-01-01", "provenance": "synthetic fixture"}},
                {"year": 2027, "scenario": "central", "mode": "total",
                 "source": {"kind": "scalar", "value": 0.5, "units": "m",
                            "positiveDirection": "up", "semantics": "total_water_level",
                            "verticalDatum": "FIXTURE_DATUM", "verticalReferenceEpoch": "2010.0",
                            "sourceDate": "2027-01-01", "provenance": "synthetic fixture"}},
            ],
        }
        path = self.root / "terrain-inputs.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        return prepare_inputs(EVENT, path, output_root=self.output)

    def _scenario(self, *, los=True, exposure=True, years=None, vertical="direct") -> Path:
        if years is None:
            years = [2026, 2027]
        v_rate = np.full((4, 4), 1000.0, dtype=np.float32)
        v_rate_path = _write_raster(self.root / "vertical-rate.tif", v_rate, nodata=np.nan)
        vertical_motion = {
            "mode": "independent-rate", "path": v_rate_path.name,
            "units": "mm/year", "positive": "up", "sourceId": "vertical-fixture",
            "sourceRunId": "vertical-run-1", "sourceDate": "2025-12-01",
            "verticalDatum": "FIXTURE_DATUM", "verticalReferenceEpoch": "2010.0",
            "baselineEpoch": "2026-01-01", "dataKind": "synthetic",
            "review": {"reviewedBy": "fixture reviewer", "evidence": "fixture vertical-rate review"},
        }
        if vertical == "missing":
            vertical_motion = None
        elif vertical == "inference":
            vertical_motion = {
                "mode": "verticalOnlyLosInference", "horizontalMotionNegligible": True,
                "review": {"reviewedBy": "fixture reviewer", "evidence": "fixture horizontal-motion assessment"},
                "incidenceAngle": {"kind": "scalar", "valueDegrees": 35,
                                   "angleConvention": "from_vertical", "sourceId": "incidence-fixture",
                                   "review": {"reviewedBy": "fixture reviewer", "evidence": "fixture incidence geometry"}},
            }
        config = {
            "schemaVersion": "1.0", "dataKind": "synthetic", "scenarioId": "central",
            "baselineEpoch": "2026-01-01", "horizon": {"startYear": 2026, "endYear": 2035},
            "supportedYears": years,
            "review": {"reviewedBy": "fixture reviewer", "evidence": "fixture scenario review"},
            "losProjection": {"enabled": los}, "waterExposure": {"enabled": exposure, "publishDepth": True},
        }
        if vertical_motion is not None:
            config["verticalMotion"] = vertical_motion
        if vertical == "inference":
            config["allowVerticalOnlyLosInference"] = False
        path = self.root / "projection.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        return path

    def test_actual_series_and_terrain_chain_publishes_numeric_year_assets_and_comparisons(self) -> None:
        motion_path = self._motion_manifest()
        terrain_path = self._terrain_manifest()
        motion = core.load_manifest(motion_path)
        rate, _ = core.read_raster(motion, "rateMmPerYear")
        np.testing.assert_allclose(rate, 12.0, atol=1e-5)

        config_path = self._scenario()
        projection_path = project(EVENT, motion_path, terrain_path, config_path, self.output)
        manifest = core.load_manifest(projection_path)
        self.assertEqual(manifest["product"], "projection")
        self.assertEqual(manifest["supportedYears"], [2026, 2027])
        self.assertEqual(manifest["baselineEpoch"], "2026-01-01")
        self.assertIn("vertical-run-1", manifest["sourceRunIds"])
        self.assertTrue(manifest["syntheticLineage"])
        los_2026, grid = core.read_raster(manifest, "losMm2026")
        los_2027, _ = core.read_raster(manifest, "losMm2027")
        self.assertAlmostEqual(float(np.nanmedian(los_2026)), 12 * (datetime(2026, 1, 1, tzinfo=timezone.utc) - datetime(2024, 1, 1, tzinfo=timezone.utc)).days / YEAR_DAYS, places=4)
        self.assertGreater(float(np.nanmedian(los_2027)), float(np.nanmedian(los_2026)))
        exposure_2026, _ = core.read_raster(manifest, "exposure2026")
        exposure_2027, _ = core.read_raster(manifest, "exposure2027")
        self.assertEqual(int(np.count_nonzero(exposure_2026 == 1)), 7)
        self.assertEqual(int(np.count_nonzero(exposure_2027 == 1)), 0)
        self.assertTrue(np.isnan(exposure_2026[1, 1]))
        self.assertIn("geometry2026", manifest["assets"])
        self.assertIn("depth2026", manifest["assets"])
        geometry = json.loads((projection_path.parent / manifest["assets"]["geometry2026"]["path"]).read_text())
        self.assertEqual(geometry["type"], "FeatureCollection")
        self.assertEqual(len(geometry["features"]), 1)
        metrics_2026 = manifest["annualMetrics"]["2026"]
        self.assertAlmostEqual(metrics_2026["exposedAreaKm2"], 7 * 0.0001, places=8)
        self.assertIsNone(metrics_2026["exposedAssetCount"])
        self.assertIsNone(metrics_2026["exposedPopulationCount"])
        comparison = manifest["annualMetrics"]["2027"]["comparisonToBaseline"]
        self.assertEqual(comparison["firstExposedCellCount"], 7)
        self.assertEqual(comparison["secondExposedCellCount"], 0)
        self.assertAlmostEqual(comparison["netExposedAreaChangeKm2"], -7 * 0.0001, places=8)
        self.assertEqual(grid["width"], 4)
        self.assertGreaterEqual(manifest["grid"]["resolutionMetres"], 10)

    def test_inference_requires_explicit_opt_in_and_missing_vertical_evidence_fails(self) -> None:
        motion = self._motion_manifest()
        terrain = self._terrain_manifest(barriers=False, nodata_cell=False)
        config_path = self._scenario(vertical="inference")
        with self.assertRaisesRegex(ValueError, "opt-in"):
            project(EVENT, motion, terrain, config_path, self.output)
        missing_path = self._scenario(vertical="missing")
        with self.assertRaisesRegex(ValueError, "verticalMotion evidence"):
            project(EVENT, motion, terrain, missing_path, self.output)

    def test_inference_geometry_and_reviewed_gate_convert_sign_when_enabled(self) -> None:
        motion = self._motion_manifest(rate_mm_per_year=10)
        terrain = self._terrain_manifest(barriers=False, nodata_cell=False)
        config_path = self._scenario(vertical="inference")
        config = json.loads(config_path.read_text())
        config["allowVerticalOnlyLosInference"] = True
        config_path.write_text(json.dumps(config))
        output = project(EVENT, motion, terrain, config_path, self.output)
        manifest = core.load_manifest(output)
        exposure, _ = core.read_raster(manifest, "exposure2027")
        # Positive-away LOS means downward motion under this reviewed inference.
        self.assertEqual(int(np.count_nonzero(exposure == 1)), 16)
        self.assertIn("verticalOnlyLosInference", manifest["assumptions"]["waterExposure"]["verticalMotion"]["mode"])

    def test_no_rate_pixels_remain_nodata_and_no_zero_baseline_is_invented(self) -> None:
        motion = self._motion_manifest(all_nodata=True)
        config_path = self._scenario(los=True, exposure=False)
        output = project(EVENT, motion, None, config_path, self.output)
        manifest = core.load_manifest(output)
        projected, _ = core.read_raster(manifest, "losMm2026")
        self.assertFalse(np.isfinite(projected).any())
        self.assertIsNone(manifest["annualMetrics"]["2026"]["medianLosMm"])
        self.assertEqual(manifest["annualMetrics"]["2026"]["losValidCellCount"], 0)
        self.assertTrue(any("No valid annual LOS rates" in warning for warning in manifest["warnings"]))

    def test_invalid_year_scenario_mismatch_and_prebaseline_date_are_rejected(self) -> None:
        motion = self._motion_manifest()
        terrain = self._terrain_manifest()
        invalid_year = self._scenario()
        config = json.loads(invalid_year.read_text())
        config["supportedYears"] = [2036]
        invalid_year.write_text(json.dumps(config))
        with self.assertRaisesRegex(ValueError, "2026–2035"):
            project(EVENT, motion, terrain, invalid_year, self.output)

        wrong_scenario = self._scenario()
        terrain_manifest = core.load_manifest(terrain)
        terrain_manifest["waterLevels"][0]["scenario"] = "low"
        # Metadata edits invalidate the immutable manifest only if its assets
        # change; this verifies explicit scenario compatibility validation.
        terrain.write_text(json.dumps(terrain_manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "scenarioId"):
            project(EVENT, motion, terrain, wrong_scenario, self.output)

        before_base = self._scenario(years=[2026])
        config = json.loads(before_base.read_text())
        config["baselineEpoch"] = "2026-07-01"
        before_base.write_text(json.dumps(config))
        with self.assertRaisesRegex(ValueError, "scenario baselineEpoch"):
            project(EVENT, motion, None, before_base, self.output)

    def test_zero_common_exposure_support_reports_null_metrics_and_snapshot_does_not_crop_grid(self) -> None:
        motion = self._motion_manifest()
        terrain = self._terrain_manifest(barriers=False, nodata_cell=False)
        config_path = self._scenario()
        config = json.loads(config_path.read_text())
        config["verticalMotion"]["path"] = "vertical-nodata.tif"
        _write_raster(self.root / "vertical-nodata.tif", np.full((4, 4), -9999, dtype=np.float32), nodata=-9999)
        config["exposureSnapshots"] = {
            "populationCount": {"path": "partial-population.tif", "units": "persons_per_cell",
                                "sourceId": "population-fixture", "sourceDate": "2025-01-01",
                                "provenance": "synthetic partial snapshot"}
        }
        population = np.ones((2, 2), dtype=np.float32)
        _write_raster(self.root / "partial-population.tif", population,
                      transform=from_origin(500000, 1700000, 20, 20))
        config_path.write_text(json.dumps(config))
        output = project(EVENT, motion, terrain, config_path, self.output)
        manifest = core.load_manifest(output)
        metrics = manifest["annualMetrics"]["2026"]
        self.assertEqual(metrics["validExposureCellCount"], 0)
        self.assertIsNone(metrics["exposedCellCount"])
        self.assertIsNone(metrics["exposedAreaKm2"])
        self.assertIsNone(metrics["exposedPopulationCount"])
        self.assertEqual(manifest["grid"]["width"], 4)
        self.assertEqual(manifest["grid"]["height"], 4)

    def test_input_asset_hashes_are_verified_and_lineage_names_source_runs(self) -> None:
        motion = self._motion_manifest()
        terrain = self._terrain_manifest(barriers=False, nodata_cell=False)
        config = self._scenario()
        output = project(EVENT, motion, terrain, config, self.output)
        manifest = core.load_manifest(output)
        self.assertEqual(manifest["sourceManifestHashes"]["groundMotion"], core.digest(motion))
        self.assertEqual(manifest["sourceManifestHashes"]["scenarioInputs"], core.digest(terrain))
        self.assertIn("projectionConfig", manifest["sourceHashes"])
        self.assertIn("verticalRate:vertical-fixture", manifest["sourceHashes"])
        motion_manifest = core.load_manifest(motion)
        rate_path = core.asset_path(motion_manifest, "rateMmPerYear")
        with rasterio.open(rate_path, "r+") as dataset:
            values = dataset.read(1)
            values[0, 0] += 1
            dataset.write(values, 1)
        with self.assertRaisesRegex(ValueError, "Asset hash mismatch"):
            project(EVENT, motion, terrain, config, self.output)


if __name__ == "__main__":
    unittest.main()
