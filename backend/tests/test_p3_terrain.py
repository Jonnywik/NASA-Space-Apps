from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from processing.p3.terrain import CompatibilityError, prepare_inputs


class TerrainPreparationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.output = self.root / "output"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write(self, name: str, array: np.ndarray, resolution: float, *, nodata=None) -> Path:
        path = self.root / name
        height, width = array.shape
        # All test sources cover the same 40 x 40 m footprint at their native resolution.
        transform = from_origin(0, 40, resolution, resolution)
        with rasterio.open(
            path, "w", driver="GTiff", width=width, height=height, count=1,
            dtype=array.dtype, crs="EPSG:32651", transform=transform, nodata=nodata,
        ) as ds:
            ds.write(array, 1)
        return path

    def _base_config(self, *, dem: str = "dem.tif", seed: str = "seeds.tif") -> dict:
        return {
            "dataKind": "synthetic",
            "verticalDatum": "TEST_DATUM",
            "verticalReferenceEpoch": "2010.0",
            "projectionBaselineEpoch": "2020-01-01",
            "targetCrs": "EPSG:32651",
            "terrain": {
                "path": dem,
                "units": "m",
                "positiveDirection": "up",
                "representation": "ground",
                "verticalDatum": "TEST_DATUM",
                "verticalReferenceEpoch": "2010.0",
                "baselineEpoch": "2020-01-01",
                "sourceDate": "2020-01-01",
                "uncertaintyMetres": 0.15,
            },
            "coastalSeeds": {"path": seed, "trueValues": [1]},
            "waterLevels": [{
                "year": 2030,
                "scenario": "central",
                "mode": "total",
                "source": {
                    "kind": "scalar", "value": 1.25, "units": "m",
                    "positiveDirection": "up",
                    "semantics": "total_water_level", "verticalDatum": "TEST_DATUM",
                    "verticalReferenceEpoch": "2010.0", "sourceDate": "2026-01-01",
                    "provenance": "synthetic scalar water-level fixture",
                    "uncertaintyMetres": 0.3,
                },
            }],
        }

    def _write_base_rasters(self, *, dem_values=None, seed_values=None) -> None:
        dem = np.full((4, 4), 10, dtype=np.float32) if dem_values is None else np.asarray(dem_values, dtype=np.float32)
        seeds = np.ones((4, 4), dtype=np.uint8) if seed_values is None else np.asarray(seed_values, dtype=np.uint8)
        self._write("dem.tif", dem, 10)
        self._write("seeds.tif", seeds, 10, nodata=255)

    def _save_config(self, config: dict, name: str = "inputs.json") -> Path:
        path = self.root / name
        path.write_text(json.dumps(config), encoding="utf-8")
        return path

    def test_datum_mismatch_returns_report_and_publishes_nothing(self) -> None:
        self._write_base_rasters()
        config = self._base_config()
        config["terrain"]["verticalDatum"] = "OTHER_DATUM"
        with self.assertRaises(CompatibilityError) as caught:
            prepare_inputs("fixture_event", self._save_config(config), self.output)
        self.assertEqual(caught.exception.report["status"], "incompatible")
        self.assertEqual(caught.exception.report["issues"][0]["code"], "vertical_reference_mismatch")
        self.assertFalse((self.output / "fixture_event" / "p3" / "scenario-inputs").exists())

    def test_reviewed_vertical_offset_is_applied_and_recorded(self) -> None:
        self._write_base_rasters()
        config = self._base_config()
        config["terrain"].update({
            "verticalDatum": "SOURCE_DATUM",
            "reviewedVerticalAdjustment": {
                "fromVerticalDatum": "SOURCE_DATUM", "toVerticalDatum": "TEST_DATUM",
                "fromReferenceEpoch": "2010.0", "toReferenceEpoch": "2010.0",
                "offsetMetres": 0.75, "reviewed": True,
                "reviewedBy": "fixture reviewer", "evidence": "fixture geoid comparison",
            },
        })
        manifest_path = prepare_inputs("fixture_event", self._save_config(config), self.output)
        manifest = json.loads(manifest_path.read_text())
        elevation_path = manifest_path.parent / manifest["assets"]["elevationMetres"]["path"]
        with rasterio.open(elevation_path) as ds:
            values = ds.read(1)
        self.assertTrue(np.allclose(values, 10.75))
        self.assertEqual(manifest["terrain"]["datumAdjustment"]["offsetMetres"], 0.75)
        self.assertEqual(manifest["verticalDatum"], "TEST_DATUM")

    def test_reviewed_baseline_offset_is_required_and_applied(self) -> None:
        self._write_base_rasters()
        config = self._base_config()
        config["terrain"]["baselineEpoch"] = "2019-01-01"
        config_path = self._save_config(config)
        with self.assertRaises(CompatibilityError) as caught:
            prepare_inputs("fixture_event", config_path, self.output)
        self.assertEqual(caught.exception.report["issues"][0]["code"], "baseline_epoch_mismatch")
        config["terrain"]["reviewedBaselineAdjustment"] = {
            "fromEpoch": "2019-01-01", "toEpoch": "2020-01-01",
            "offsetMetres": -0.25, "reviewed": True,
            "reviewedBy": "fixture reviewer", "evidence": "fixture epoch comparison",
        }
        manifest_path = prepare_inputs("fixture_event", self._save_config(config), self.output)
        manifest = json.loads(manifest_path.read_text())
        elevation_path = manifest_path.parent / manifest["assets"]["elevationMetres"]["path"]
        with rasterio.open(elevation_path) as ds:
            values = ds.read(1)
        self.assertTrue(np.allclose(values, 9.75))
        self.assertEqual(manifest["terrain"]["baselineAdjustment"]["offsetMetres"], -0.25)

    def test_missing_water_model_and_target_epoch_have_structured_reports(self) -> None:
        self._write_base_rasters()
        config = self._base_config()
        config["waterLevels"] = []
        with self.assertRaises(CompatibilityError) as missing_model:
            prepare_inputs("fixture_event", self._save_config(config), self.output)
        self.assertEqual(missing_model.exception.report["issues"][0]["code"], "missing_water_level_model")
        config = self._base_config()
        del config["verticalReferenceEpoch"]
        with self.assertRaises(CompatibilityError) as missing_epoch:
            prepare_inputs("fixture_event", self._save_config(config), self.output)
        self.assertEqual(missing_epoch.exception.report["issues"][0]["code"], "target_vertical_reference_epoch_missing")

    def test_water_nodata_stays_nodata_and_zero_is_not_missing(self) -> None:
        self._write_base_rasters()
        water = np.array([[0.0, 1.0], [2.0, -9999.0]], dtype=np.float32)
        self._write("water.tif", water, 20, nodata=-9999.0)
        config = self._base_config()
        config["waterLevels"][0]["source"] = {
            "kind": "raster", "path": "water.tif", "units": "m",
            "positiveDirection": "up",
            "semantics": "total_water_level", "verticalDatum": "TEST_DATUM",
            "verticalReferenceEpoch": "2010.0", "sourceDate": "2026-01-01",
            "provenance": "synthetic raster water-level fixture",
        }
        manifest_path = prepare_inputs("fixture_event", self._save_config(config), self.output)
        manifest = json.loads(manifest_path.read_text())
        level_path = manifest_path.parent / manifest["assets"]["waterLevel2030"]["path"]
        with rasterio.open(level_path) as ds:
            values = ds.read(1)
        self.assertEqual(manifest["grid"]["resolutionMetres"], 20.0)
        self.assertEqual(manifest["grid"]["width"], 2)
        self.assertEqual(manifest["grid"]["height"], 2)
        self.assertEqual(values[0, 0], 0.0)
        self.assertTrue(np.isfinite(values[0, 1]))
        self.assertTrue(np.isfinite(values[1, 0]))
        self.assertTrue(np.isnan(values[1, 1]))
        self.assertEqual(manifest["resampling"]["continuous"], "bilinear")

    def test_declared_feet_convert_to_metres_without_rescaling_metres_uncertainty(self) -> None:
        self._write("dem.tif", np.full((4, 4), 32.80839895, dtype=np.float32), 10)
        self._write("seeds.tif", np.ones((4, 4), dtype=np.uint8), 10, nodata=255)
        config = self._base_config()
        config["terrain"]["units"] = "ft"
        config["waterLevels"][0]["source"]["value"] = 3.280839895
        config["waterLevels"][0]["source"]["units"] = "ft"
        manifest_path = prepare_inputs("fixture_event", self._save_config(config), self.output)
        manifest = json.loads(manifest_path.read_text())
        elevation_path = manifest_path.parent / manifest["assets"]["elevationMetres"]["path"]
        water_path = manifest_path.parent / manifest["assets"]["waterLevel2030"]["path"]
        with rasterio.open(elevation_path) as ds:
            elevation = ds.read(1)
        with rasterio.open(water_path) as ds:
            water = ds.read(1)
        self.assertTrue(np.allclose(elevation, 10.0, atol=1e-5))
        self.assertTrue(np.allclose(water, 1.0, atol=1e-6))
        self.assertEqual(manifest["terrain"]["uncertaintyMetres"], 0.15)

    def test_positive_down_inputs_are_flipped_to_canonical_positive_up(self) -> None:
        self._write("dem.tif", np.full((4, 4), -10.0, dtype=np.float32), 10)
        self._write("seeds.tif", np.ones((4, 4), dtype=np.uint8), 10, nodata=255)
        config = self._base_config()
        config["terrain"]["positiveDirection"] = "down"
        config["waterLevels"][0]["source"]["value"] = -1.0
        config["waterLevels"][0]["source"]["positiveDirection"] = "down"
        manifest_path = prepare_inputs("fixture_event", self._save_config(config), self.output)
        manifest = json.loads(manifest_path.read_text())
        elevation_path = manifest_path.parent / manifest["assets"]["elevationMetres"]["path"]
        water_path = manifest_path.parent / manifest["assets"]["waterLevel2030"]["path"]
        with rasterio.open(elevation_path) as ds:
            elevation = ds.read(1)
        with rasterio.open(water_path) as ds:
            water = ds.read(1)
        self.assertTrue(np.allclose(elevation, 10.0))
        self.assertTrue(np.allclose(water, 1.0))
        self.assertEqual(manifest["terrain"]["outputPositiveDirection"], "up")

    def test_masks_use_nearest_and_grid_uses_coarsest_native_cell(self) -> None:
        self._write_base_rasters()
        self._write("water_coarse.tif", np.full((2, 2), 2, dtype=np.float32), 20)
        quality = np.ones((4, 4), dtype=np.uint8)
        quality[:, 2:] = 0
        self._write("quality.tif", quality, 10, nodata=255)
        config = self._base_config()
        config["qualityMask"] = {"path": "quality.tif", "validValues": [1]}
        config["waterLevels"][0]["source"] = {
            "kind": "raster", "path": "water_coarse.tif", "units": "m",
            "positiveDirection": "up",
            "semantics": "total_water_level", "verticalDatum": "TEST_DATUM",
            "verticalReferenceEpoch": "2010.0", "sourceDate": "2026-01-01",
            "provenance": "synthetic coarse raster water-level fixture",
        }
        manifest_path = prepare_inputs("fixture_event", self._save_config(config), self.output)
        manifest = json.loads(manifest_path.read_text())
        elevation_path = manifest_path.parent / manifest["assets"]["elevationMetres"]["path"]
        seeds_path = manifest_path.parent / manifest["assets"]["coastalSeeds"]["path"]
        with rasterio.open(elevation_path) as ds:
            elevation = ds.read(1)
        with rasterio.open(seeds_path) as ds:
            seeds = ds.read(1)
        self.assertEqual(manifest["grid"]["resolutionMetres"], 20.0)
        self.assertTrue(np.isfinite(elevation[:, 0]).all())
        self.assertTrue(np.isnan(elevation[:, 1]).all())
        self.assertTrue(np.all(seeds[:, 0] == 1))
        self.assertTrue(np.all(seeds[:, 1] == 255))
        self.assertEqual(manifest["resampling"]["categoricalMasks"], "nearest")

    def test_total_and_components_cannot_be_double_counted(self) -> None:
        self._write_base_rasters()
        config = self._base_config()
        config["waterLevels"][0]["components"] = {"surge": {}}
        with self.assertRaises(CompatibilityError) as caught:
            prepare_inputs("fixture_event", self._save_config(config), self.output)
        self.assertEqual(caught.exception.report["issues"][0]["code"], "water_level_double_counting")

    def test_component_sum_requires_reviewed_disjoint_declaration(self) -> None:
        self._write_base_rasters()
        config = self._base_config()
        config["waterLevels"][0] = {
            "year": 2030, "mode": "components", "combination": "sum",
            "components": {"mean_water_level": {
                "kind": "scalar", "value": 1.0, "units": "m",
                "positiveDirection": "up",
                "semantics": "mean_water_level", "verticalDatum": "TEST_DATUM",
                "verticalReferenceEpoch": "2010.0", "sourceDate": "2026-01-01", "provenance": "fixture model",
            }},
        }
        with self.assertRaises(CompatibilityError) as caught:
            prepare_inputs("fixture_event", self._save_config(config), self.output)
        self.assertEqual(caught.exception.report["issues"][0]["code"], "component_combination_undeclared")

    def test_component_offsets_apply_once_to_absolute_level_not_anomaly(self) -> None:
        self._write_base_rasters()

        def scalar(value: float, name: str, role: str, datum: str = "TEST_DATUM") -> dict:
            return {
                "kind": "scalar", "value": value, "units": "m", "semantics": name,
                "positiveDirection": "up",
                "verticalRole": role, "verticalDatum": datum,
                "verticalReferenceEpoch": "2010.0", "sourceDate": "2026-01-01", "provenance": "fixture model",
            }

        config = self._base_config()
        config["waterLevels"][0] = {
            "year": 2030, "scenario": "central", "mode": "components", "combination": "sum",
            "combinationReview": {
                "componentsAreDisjoint": True, "reviewedBy": "fixture reviewer",
                "evidence": "fixture component definitions",
            },
            "components": {
                "mean_water_level": {
                    **scalar(0.0, "mean_water_level", "absolute_level", "SOURCE_DATUM"),
                    "reviewedVerticalAdjustment": {
                        "fromVerticalDatum": "SOURCE_DATUM", "toVerticalDatum": "TEST_DATUM",
                        "fromReferenceEpoch": "2010.0", "toReferenceEpoch": "2010.0",
                        "offsetMetres": 0.8, "reviewed": True,
                        "reviewedBy": "fixture reviewer", "evidence": "fixture datum offset",
                    },
                },
                "tide": scalar(0.5, "tide", "height_anomaly"),
                "surge": scalar(0.2, "surge", "height_anomaly"),
            },
        }
        manifest_path = prepare_inputs("fixture_event", self._save_config(config), self.output)
        manifest = json.loads(manifest_path.read_text())
        water_path = manifest_path.parent / manifest["assets"]["waterLevel2030"]["path"]
        with rasterio.open(water_path) as ds:
            water = ds.read(1)
        self.assertTrue(np.allclose(water, 1.5))
        components = {item["name"]: item for item in manifest["waterLevels"][0]["components"]}
        self.assertEqual(components["mean_water_level"]["appliedVerticalOffsetMetres"], 0.8)
        self.assertEqual(components["tide"]["appliedVerticalOffsetMetres"], 0.0)
        self.assertEqual(components["surge"]["appliedVerticalOffsetMetres"], 0.0)

    def test_height_anomaly_rejects_absolute_datum_offset(self) -> None:
        self._write_base_rasters()
        config = self._base_config()
        config["waterLevels"][0] = {
            "year": 2030, "mode": "components", "combination": "sum",
            "combinationReview": {
                "componentsAreDisjoint": True, "reviewedBy": "fixture reviewer", "evidence": "fixture components",
            },
            "components": {
                "mean_water_level": {
                    "kind": "scalar", "value": 1, "units": "m", "semantics": "mean_water_level",
                    "positiveDirection": "up",
                    "verticalRole": "absolute_level", "verticalDatum": "TEST_DATUM",
                    "verticalReferenceEpoch": "2010.0", "sourceDate": "2026-01-01", "provenance": "fixture model",
                },
                "surge": {
                    "kind": "scalar", "value": 0.2, "units": "m", "semantics": "surge",
                    "positiveDirection": "up",
                    "verticalRole": "height_anomaly", "verticalDatum": "TEST_DATUM",
                    "verticalReferenceEpoch": "2010.0", "sourceDate": "2026-01-01", "provenance": "fixture model",
                    "reviewedVerticalAdjustment": {"offsetMetres": 0.8},
                },
            },
        }
        with self.assertRaises(CompatibilityError) as caught:
            prepare_inputs("fixture_event", self._save_config(config), self.output)
        self.assertEqual(caught.exception.report["issues"][0]["code"], "anomaly_vertical_adjustment_not_allowed")


if __name__ == "__main__":
    unittest.main()
