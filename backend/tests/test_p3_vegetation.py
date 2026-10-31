from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from processing.p3 import core
from processing.p3.vegetation import (
    CalibrationUnavailableError,
    BiomassError,
    aggregate_reference_plots,
    fit_calibration_model,
    fuse_regional_metrics,
    predict_biomass,
    publish_regional_fusion,
    read_gcov_features,
    train_calibration,
)


CONFIG = {
    "splitProvenance": "Plots were assigned by watershed block before feature extraction.",
    "referenceTimingNotes": "Plot campaigns were acquired one day after the GCOV acquisition; date offset retained.",
    "acceptanceLimits": {"maxAbsBiasMgPerHa": 1_000_000.0, "maxRmseMgPerHa": 1_000_000.0},
}


def _known_samples():
    patterns = [(-1.0, -1.0), (-1.0, 1.0), (1.0, -1.0), (1.0, 1.0)]
    rows = []
    for index in range(17):
        x1, x2 = patterns[index % len(patterns)]
        # Twelve training plots contain three balanced repetitions. Five
        # separate spatial groups provide the independent validation set.
        split = "train" if index < 12 else "validation"
        log_agb = 2.0 + 0.5 * x1 - 0.25 * x2
        rows.append({
            "plotId": f"plot-{index:02d}",
            "spatialGroup": f"group-{index:02d}",
            "split": split,
            "featuresDb": {"HHHH_dB": x1, "HVHV_dB": x2},
            "agbMgPerHa": float(np.expm1(log_agb)),
            "referenceDate": "2024-06-02",
        })
    return rows


def _write_gcov(directory: Path, *, include_hvhv=True, zero=False) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    transform = from_origin(500000, 1700000, 30, 30)
    patterns = [(-1.0, -1.0), (-1.0, 1.0), (1.0, -1.0), (1.0, 1.0)]
    db_values = np.asarray([patterns[i % 4] for i in range(15)], dtype="float64").reshape(3, 5, 2)
    hhhh = np.power(10.0, db_values[:, :, 0] / 10.0).astype("float32")
    hvhv = np.power(10.0, db_values[:, :, 1] / 10.0).astype("float32")
    if zero:
        hhhh[:] = 0
        hvhv[:] = 0
    assets = {}
    for name, values in (("HHHH", hhhh), ("HVHV", hvhv)):
        if name == "HVHV" and not include_hvhv:
            continue
        file_name = name.lower() + ".tif"
        path = directory / file_name
        with rasterio.open(
            path, "w", driver="GTiff", width=5, height=3, count=1,
            dtype="float32", crs="EPSG:32651", transform=transform,
            nodata=np.nan,
        ) as dataset:
            dataset.write(values, 1)
        assets[name] = {"path": file_name, "sha256": core.digest(path), "units": "linear_power", "quantity": "power"}
    manifest = {
        "schemaVersion": "1.0", "event": "biomass_fixture", "product": "gcov",
        "runId": "gcov-run-1", "productId": "GCOV-SYNTH-1", "dataKind": "synthetic",
        "syntheticLineage": ["synthetic_gcov_fixture"], "sensor": "NISAR-fixture",
        "frequency": "L", "polarization": "HH", "orbit": "ascending-001", "frame": "frame-042",
        "processingVersion": "fixture-1", "maturity": "synthetic-fixture",
        "sourceProfile": {"id": "fixture-gcov-profile", "version": "1", "adapter": "fixture"},
        "units": {"HHHH": "linear_power", "HVHV": "linear_power"},
        "acquisitionDates": ["2024-06-01"], "nativeResolution": {"x": 30, "y": 30, "units": "m"},
        "assets": assets,
    }
    manifest_path = directory / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


def _polygon(left: float, top: float, right: float, bottom: float) -> dict:
    return {"type": "Polygon", "coordinates": [[[left, top], [right, top], [right, bottom], [left, bottom], [left, top]]]}


def _write_plots(path: Path) -> Path:
    features = []
    samples = _known_samples()
    plot_samples = samples[:10] + samples[12:17]
    for index, row in enumerate(plot_samples):
        r, c = divmod(index, 5)
        left = 500000 + c * 30
        top = 1700000 - r * 30
        features.append({
            "type": "Feature",
            "geometry": _polygon(left, top, left + 30, top - 30),
            "properties": {
                "plotId": row["plotId"], "agbMgPerHa": row["agbMgPerHa"], "agbUnit": "Mg/ha",
                "split": row["split"], "spatialGroup": row["spatialGroup"], "referenceDate": row["referenceDate"],
            },
        })
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")
    return path


def _write_regions(path: Path) -> Path:
    feature = {
        "type": "Feature",
        "geometry": _polygon(500000, 1700000, 500150, 1699910),
        "properties": {"regionId": "fixture-region"},
    }
    path.write_text(json.dumps({
        "type": "FeatureCollection", "crs": {"type": "name", "properties": {"name": "EPSG:32651"}},
        "features": [feature],
    }), encoding="utf-8")
    return path


class P3VegetationTests(unittest.TestCase):
    def test_known_ridge_calibration_uses_standardized_features_and_unpenalized_intercept(self):
        model = fit_calibration_model(_known_samples(), config=CONFIG)

        self.assertTrue(model["accepted"])
        self.assertEqual(model["ridgeAlpha"], 1.0)
        self.assertTrue(model["interceptUnpenalized"])
        self.assertEqual(model["features"], ["HHHH_dB", "HVHV_dB"])
        self.assertAlmostEqual(model["interceptLog1pAgb"], 2.0, places=10)
        self.assertAlmostEqual(model["coefficients"][0], 6.0 / 13.0, places=10)
        self.assertAlmostEqual(model["coefficients"][1], -3.0 / 13.0, places=10)
        self.assertAlmostEqual(model["validationMetrics"]["validation"]["plotCount"], 5)
        self.assertEqual(model["referenceTiming"]["notes"], CONFIG["referenceTimingNotes"])

    def test_polygon_aggregation_train_publish_predict_and_report_finite_regions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            gcov_path = _write_gcov(root / "gcov")
            plots_path = _write_plots(root / "plots.geojson")
            config_path = root / "config.json"
            config_path.write_text(json.dumps({**CONFIG, "plotCrs": "EPSG:32651"}), encoding="utf-8")

            gcov = read_gcov_features(gcov_path)
            samples, sampling = aggregate_reference_plots(gcov, plots_path, {**CONFIG, "plotCrs": "EPSG:32651"})
            self.assertEqual(len(samples), 15)
            self.assertEqual(samples[0]["validPixelCount"], 1)
            self.assertAlmostEqual(samples[0]["featuresDb"]["HHHH_dB"], -1.0, places=5)
            self.assertEqual(sampling["aggregation"].split(";")[0], "mean_positive_linear_power_then_10log10")

            calibration_path = train_calibration(gcov_path, plots_path, config_path, output_root=root / "output")
            calibration = core.load_manifest(calibration_path)
            self.assertEqual(calibration["dataKind"], "synthetic")
            self.assertTrue(calibration["modelAccepted"])
            self.assertIn(calibration["implementationStatus"], {"pending", "verified"})
            model = json.loads(core.asset_path(calibration, "model").read_text(encoding="utf-8"))
            self.assertEqual(model["referenceTiming"]["maxAbsoluteDateOffsetDays"], 1)

            regions_path = _write_regions(root / "regions.geojson")
            biomass_path = predict_biomass(gcov_path, calibration_path, output_root=root / "output", regions_path=regions_path)
            biomass_manifest = core.load_manifest(biomass_path)
            self.assertEqual(biomass_manifest["dataKind"], "synthetic")
            self.assertIn("biomassMgPerHa", biomass_manifest["assets"])
            self.assertIn("applicabilityMask", biomass_manifest["assets"])
            self.assertGreater(biomass_manifest["statistics"]["validPixelCount"], 0)
            self.assertTrue(np.isfinite(biomass_manifest["statistics"]["medianMgPerHa"]))
            self.assertEqual(len(biomass_manifest["regionalMetrics"]), 1)
            region = biomass_manifest["regionalMetrics"][0]
            self.assertEqual(region["regionId"], "fixture-region")
            self.assertEqual(region["validPixelCount"], 15)
            self.assertTrue(np.isfinite(region["medianMgPerHa"]))
            self.assertEqual(region["resolutionMetres"], {"x": 30, "y": 30})
            raster, _ = core.read_raster(biomass_manifest, "biomassMgPerHa")
            self.assertEqual(np.count_nonzero(np.isfinite(raster)), 15)

            motion_path = root / "ground_motion_regions.json"
            motion_path.write_text(json.dumps({
                "event": "biomass_fixture", "product": "ground-motion",
                "runId": "motion-run-1", "dataKind": "synthetic",
                "syntheticLineage": True, "sourceHashes": {"series": "fixture-hash"},
                "nativeResolutionMetres": {"x": 30, "y": 30},
                "regions": [{
                    "regionId": "fixture-region", "rateMmPerYear": -2.5,
                    "validRateCellCount": 12, "selectedCellCount": 14,
                    "epochs": ["2023-01-01", "2024-01-01"],
                }],
            }), encoding="utf-8")
            fusion_path = publish_regional_fusion(
                "biomass_fixture", biomass_path, motion_path, output_root=root / "output",
            )
            fusion_manifest = core.load_manifest(fusion_path)
            self.assertEqual(fusion_manifest["dataKind"], "synthetic")
            fusion_row = fusion_manifest["regionalFusion"]["regions"][0]
            self.assertEqual(fusion_row["groundMotionLOS"]["medianLosRateMmPerYear"], -2.5)
            self.assertEqual(fusion_row["groundMotionLOS"]["observationStartDate"], "2023-01-01")

    def test_spatially_overlapping_train_and_validation_groups_are_rejected(self):
        samples = _known_samples()
        samples[-1]["spatialGroup"] = samples[0]["spatialGroup"]
        with self.assertRaisesRegex(BiomassError, "spatial groups overlap"):
            fit_calibration_model(samples, config=CONFIG)

    def test_missing_hvhv_term_is_an_explicit_input_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            manifest_path = _write_gcov(Path(temporary) / "gcov", include_hvhv=False)
            with self.assertRaisesRegex(BiomassError, "missing required HVHV"):
                read_gcov_features(manifest_path)

    def test_prediction_rejects_a_different_event_or_source_basis(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            gcov_path = _write_gcov(root / "gcov")
            plots_path = _write_plots(root / "plots.geojson")
            config_path = root / "config.json"
            config_path.write_text(json.dumps({**CONFIG, "plotCrs": "EPSG:32651"}), encoding="utf-8")
            calibration_path = train_calibration(gcov_path, plots_path, config_path, output_root=root / "output")

            changed_manifest = json.loads(gcov_path.read_text(encoding="utf-8"))
            changed_manifest["frequency"] = "C"
            changed_path = root / "gcov" / "different-frequency.json"
            changed_path.write_text(json.dumps(changed_manifest), encoding="utf-8")
            with self.assertRaisesRegex(CalibrationUnavailableError, "source basis differs.*frequency"):
                predict_biomass(changed_path, calibration_path, output_root=root / "output")

            changed_manifest["frequency"] = "L"
            changed_manifest["event"] = "another_event"
            changed_path.write_text(json.dumps(changed_manifest), encoding="utf-8")
            with self.assertRaisesRegex(CalibrationUnavailableError, "event does not match"):
                predict_biomass(changed_path, calibration_path, output_root=root / "output")

    def test_nonpositive_power_is_masked_instead_of_becoming_zero_biomass(self):
        with tempfile.TemporaryDirectory() as temporary:
            manifest_path = _write_gcov(Path(temporary) / "gcov", zero=True)
            gcov = read_gcov_features(manifest_path)
            self.assertFalse(gcov.valid_mask.any())
            self.assertTrue(np.isnan(gcov.features_db["HHHH_dB"]).all())
            self.assertTrue(np.isnan(gcov.features_db["HVHV_dB"]).all())

    def test_acceptance_failure_never_produces_quantitative_biomass(self):
        failed_config = {
            **CONFIG,
            "acceptanceLimits": {"maxAbsBiasMgPerHa": 0.0, "maxRmseMgPerHa": 0.0},
        }
        model = fit_calibration_model(_known_samples(), config=failed_config)
        self.assertFalse(model["accepted"])
        self.assertIn("validation_rmse_exceeds_limit", model["acceptanceFailureReasons"])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            gcov_path = _write_gcov(root / "gcov")

            def writer(stage: Path):
                (stage / "model.json").write_text(json.dumps(model), encoding="utf-8")
                return {"model": "model.json"}

            failed_manifest = core.publish(
                "biomass_fixture", "biomass_calibration",
                {"event": "biomass_fixture", "dataKind": "synthetic", "syntheticLineage": ["fixture"]},
                writer, output_root=root / "output",
            )
            with self.assertRaisesRegex(CalibrationUnavailableError, "did not pass"):
                predict_biomass(gcov_path, failed_manifest, output_root=root / "output")
            with self.assertRaisesRegex(CalibrationUnavailableError, "manifest not found"):
                predict_biomass(gcov_path, root / "absent.json", output_root=root / "output")

    def test_fusion_joins_independent_dates_without_a_combined_risk_score(self):
        result = fuse_regional_metrics(
            [{
                "regionId": "r1", "medianMgPerHa": 42.0, "validPixelCount": 9,
                "observationStartDate": "2024-06-01", "observationEndDate": "2024-06-03", "resolutionMetres": 30,
            }],
            [{
                "regionId": "r1", "medianLosRateMmPerYear": -3.5, "validPixelCount": 12,
                "observationStartDate": "2023-01-01", "observationEndDate": "2024-01-01", "resolutionMetres": 30,
            }],
        )
        self.assertEqual(result["regions"][0]["biomass"]["observationStartDate"], "2024-06-01")
        self.assertEqual(result["regions"][0]["groundMotionLOS"]["observationStartDate"], "2023-01-01")
        self.assertIn("no causal attribution", result["interpretation"])
        self.assertNotIn("riskScore", result["regions"][0])


if __name__ == "__main__":
    unittest.main()
