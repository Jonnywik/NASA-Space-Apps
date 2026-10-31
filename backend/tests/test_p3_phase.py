from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from processing.p3 import core
from processing.p3.phase import convert, phase_to_los


GRID = {
    "crs": "EPSG:4326",
    "transform": list(from_origin(0, 8, 1, 1))[:6],
    "width": 8,
    "height": 8,
}
REFERENCE_POLYGON = {
    "type": "Polygon",
    "coordinates": [[[0, 5], [0, 8], [3, 8], [3, 5], [0, 5]]],
}


def write_raster(path: Path, array: np.ndarray) -> Path:
    core.write_raster(path, array, GRID)
    return path


def write_input(
    root: Path,
    *,
    phase_units: str = "radians",
    applied: list[str] | None = None,
    include_components: bool = True,
    correction: bool = False,
) -> Path:
    phase = np.full((8, 8), 0.1, dtype=np.float64)
    phase[:3, :3] = np.arange(9, dtype=np.float64).reshape((3, 3)) * 0.01
    phase[7, 7] = np.nan
    coherence = np.full((8, 8), 0.8, dtype=np.float64)
    coherence[2, 2] = 0.2  # below the default reference/output threshold
    coherence[7, 7] = np.nan
    components = np.ones((8, 8), dtype=np.float64)
    components[:, 6:] = 2

    assets: dict[str, dict[str, str]] = {}
    for key, values in (("phase", phase), ("coherence", coherence)):
        path = write_raster(root / f"{key}.tif", values)
        assets[key] = {"path": path.name, "sha256": core.digest(path)}
    if include_components:
        path = write_raster(root / "components.tif", components)
        assets["components"] = {"path": path.name, "sha256": core.digest(path)}

    corrections_available = []
    if correction:
        screen = np.indices((8, 8)).sum(axis=0).astype(np.float64) * 0.001
        path = write_raster(root / "troposphere.tif", screen)
        assets["troposphereScreen"] = {"path": path.name, "sha256": core.digest(path)}
        corrections_available = [{
            "name": "troposphere",
            "assetKey": "troposphereScreen",
            "units": "radians",
            "appliesTo": "phase",
            "signConvention": "same_as_phase",
        }]

    manifest = {
        "schemaVersion": "1.0",
        "event": "test_event",
        "product": "gunw",
        "runId": "gunw-synthetic-fixture",
        "dataKind": "synthetic",
        "syntheticLineage": {"fixture": "p3-phase"},
        "assets": assets,
        "grid": GRID,
        "phaseUnits": phase_units,
        "wavelengthMetres": 0.24,
        "wavelengthUnits": "metres",
        "phaseToAwaySign": 1,
        "acquisitionDates": ["2026-01-01", "2026-01-13"],
        "correctionsApplied": applied or [],
        "correctionsAvailable": corrections_available,
        "sensor": "fixture-sensor",
        "frequency": "L",
        "polarization": "HH",
        "orbit": "ascending-001",
        "frame": "frame-51",
        "maturity": "synthetic-fixture",
        "sourceProfile": "fixture-v1",
        "processingVersion": "fixture-1",
        "nativeResolution": {"x": 30, "y": 30, "units": "metres"},
    }
    manifest_path = root / "gunw.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


def write_config(root: Path, **values: object) -> Path:
    config = {
        "reference": {"polygonWgs84": REFERENCE_POLYGON},
        **values,
    }
    path = root / "phase-config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


class P3PhaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="p3-phase-")
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_pure_conversion_uses_radian_wavelength_sign_and_metres(self):
        self.assertAlmostEqual(float(phase_to_los(2 * np.pi, 0.24, 1)), 0.12)
        self.assertAlmostEqual(float(phase_to_los(2 * np.pi, 0.24, -1)), -0.12)
        self.assertAlmostEqual(float(phase_to_los(0.0, 0.24, 1)), 0.0)
        with self.assertRaisesRegex(ValueError, r"exactly \+1 or -1"):
            phase_to_los(np.array([1.0]), 0.24, 0)

    def test_reference_component_mask_and_zero_phase_are_preserved(self):
        manifest_path = write_input(self.root)
        config_path = write_config(self.root)
        output_manifest_path = convert(
            "test_event", manifest_path, config_path, output_root=self.root / "output"
        )
        output_manifest = core.load_manifest(output_manifest_path)

        self.assertEqual(output_manifest["product"], "los-pair")
        self.assertEqual(output_manifest["acquisitionDates"], ["2026-01-01", "2026-01-13"])
        self.assertEqual(output_manifest["units"]["displacement"], "mm")
        self.assertEqual(output_manifest["displacementConvention"], "positive_away_from_satellite")
        self.assertEqual(output_manifest["spatialReferenceId"], "ref-" + output_manifest["spatialReferenceHash"][:16])
        self.assertEqual(output_manifest["sourceBasis"]["phaseToAwaySign"], 1)
        self.assertEqual(output_manifest["sourceBasis"]["orbit"], "ascending-001")
        self.assertEqual(output_manifest["sourceBasis"]["frame"], "frame-51")
        self.assertEqual(output_manifest["sourceBasis"]["maturity"], "synthetic-fixture")
        self.assertEqual(output_manifest["nativeResolutionMetres"], {"x": 30.0, "y": 30.0})
        self.assertEqual(output_manifest["sourceRunIds"], ["gunw-synthetic-fixture"])
        self.assertEqual(output_manifest["dataKind"], "synthetic")
        self.assertTrue(output_manifest["syntheticLineage"])
        self.assertEqual(set(output_manifest["assets"]), {"displacementMm", "quality", "validMask"})

        with rasterio.open(core.asset_path(output_manifest, "displacementMm")) as ds:
            displacement = ds.read(1, masked=True).filled(np.nan)
        with rasterio.open(core.asset_path(output_manifest, "validMask")) as ds:
            mask = ds.read(1, masked=True).filled(np.nan)
        with rasterio.open(core.asset_path(output_manifest, "quality")) as ds:
            quality = ds.read(1, masked=True).filled(np.nan)

        # A source phase of zero is valid and is referenced relative to the
        # reference median; low-coherence, other-component, and nodata cells
        # are excluded with distinct 0/NaN mask behavior.
        self.assertTrue(np.isfinite(displacement[0, 0]))
        self.assertEqual(mask[0, 0], 1)
        self.assertEqual(mask[2, 2], 0)
        self.assertTrue(np.isnan(displacement[2, 2]))
        self.assertEqual(mask[0, 6], 0)
        self.assertTrue(np.isnan(displacement[0, 6]))
        self.assertTrue(np.isnan(mask[7, 7]))
        self.assertTrue(np.isnan(quality[2, 2]))
        self.assertTrue(np.isfinite(displacement[5, 0]))  # same component beyond the reference polygon
        self.assertAlmostEqual(displacement[5, 0], (0.1 - 0.035) * 0.24 / (4 * np.pi) * 1000, places=5)
        self.assertEqual(output_manifest["reference"]["validPixels"], 8)
        self.assertEqual(output_manifest["reference"]["component"]["label"], 1.0)
        self.assertEqual(output_manifest["quality"]["validPixelCount"], 47)

    def test_local_boolean_mask_can_define_reference_and_hash_is_stable(self):
        manifest_path = write_input(self.root)
        mask = np.zeros((8, 8), dtype=np.float64)
        mask[:3, :3] = 1
        write_raster(self.root / "reference-mask.tif", mask)
        config_path = write_config(self.root, reference={"maskRaster": "reference-mask.tif"})

        result = convert("test_event", manifest_path, config_path, output_root=self.root / "out")
        loaded = core.load_manifest(result)
        self.assertEqual(loaded["referenceRegion"]["type"], "maskRaster")
        self.assertEqual(loaded["spatialReferenceHash"], loaded["referenceRegion"]["hash"])

    def test_degrees_and_insufficient_reference_are_rejected_before_publication(self):
        degree_manifest = write_input(self.root, phase_units="degrees")
        config_path = write_config(self.root)
        output_root = self.root / "degrees-output"
        with self.assertRaisesRegex(ValueError, "degrees"):
            convert("test_event", degree_manifest, config_path, output_root=output_root)
        self.assertFalse(output_root.exists())

        # Reuse a valid source but select fewer than five reference cells.
        manifest_path = write_input(self.root)
        small_mask = np.zeros((8, 8), dtype=np.float64)
        small_mask[0, :4] = 1
        write_raster(self.root / "small-mask.tif", small_mask)
        small_config = write_config(self.root, reference={"maskRaster": "small-mask.tif"})
        with self.assertRaisesRegex(ValueError, "at least 5"):
            convert("test_event", manifest_path, small_config, output_root=output_root)
        self.assertFalse(output_root.exists())

    def test_ambiguous_dominant_component_is_rejected(self):
        manifest_path = write_input(self.root)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        components_path = self.root / "components.tif"
        components = np.ones((8, 8), dtype=np.float64)
        components[:3, :3] = np.array([[1, 1, 1], [1, 2, 2], [2, 2, 1]])
        write_raster(components_path, components)
        manifest["assets"]["components"]["sha256"] = core.digest(components_path)
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        config_path = write_config(self.root)

        with self.assertRaisesRegex(ValueError, "ambiguous"):
            convert("test_event", manifest_path, config_path, output_root=self.root / "ambiguous-output")

    def test_zero_and_negative_component_labels_cannot_support_the_reference(self):
        config_path = write_config(self.root)
        for label in (0, -1):
            with self.subTest(label=label):
                case_root = self.root / f"component-{label}"
                case_root.mkdir()
                manifest_path = write_input(case_root)
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                components_path = case_root / "components.tif"
                components = np.ones((8, 8), dtype=np.float64)
                components[:3, :3] = label
                write_raster(components_path, components)
                manifest["assets"]["components"]["sha256"] = core.digest(components_path)
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                local_config = write_config(case_root)

                with self.assertRaisesRegex(ValueError, "coherent valid pixels"):
                    convert("test_event", manifest_path, local_config, output_root=case_root / "out")

    def test_missing_components_are_blocked_for_observed_data_but_flagged_for_synthetic(self):
        observed_root = self.root / "observed"
        observed_root.mkdir()
        manifest_path = write_input(observed_root, include_components=False)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["dataKind"] = "observed"
        manifest.pop("syntheticLineage", None)
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        config_path = write_config(observed_root)
        with self.assertRaisesRegex(ValueError, "requires connected-component labels"):
            convert("test_event", manifest_path, config_path, output_root=observed_root / "blocked")

        synthetic_root = self.root / "synthetic-no-components"
        synthetic_root.mkdir()
        synthetic_manifest = write_input(synthetic_root, include_components=False)
        synthetic_config = write_config(synthetic_root)
        result = convert("test_event", synthetic_manifest, synthetic_config, output_root=synthetic_root / "out")
        published = core.load_manifest(result)
        self.assertFalse(published["quality"]["componentLabelsAvailable"])
        self.assertTrue(any("ambiguity could not be assessed" in warning for warning in published["warnings"]))

    def test_requested_correction_is_subtracted_and_recorded(self):
        manifest_path = write_input(self.root, correction=True)
        config_path = write_config(self.root, correctionsToSubtract=["troposphere"])

        result = convert("test_event", manifest_path, config_path, output_root=self.root / "corrected")
        loaded = core.load_manifest(result)
        self.assertEqual(loaded["correctionsApplied"], ["troposphere"])
        self.assertEqual(loaded["correctionState"]["subtractedByThisRun"], ["troposphere"])
        self.assertEqual(loaded["correctionState"]["availableUnapplied"], [])

        with rasterio.open(core.asset_path(loaded, "displacementMm")) as ds:
            displacement = ds.read(1, masked=True).filled(np.nan)
        phase = np.full((8, 8), 0.1, dtype=np.float64)
        phase[:3, :3] = np.arange(9, dtype=np.float64).reshape((3, 3)) * 0.01
        screen = np.indices((8, 8)).sum(axis=0).astype(np.float64) * 0.001
        corrected = phase - screen
        reference_pixels = corrected[:3, :3].ravel()[:-1]  # bottom-right is below the coherence threshold
        expected = (corrected[5, 0] - np.median(reference_pixels)) * 0.24 / (4 * np.pi) * 1000
        self.assertAlmostEqual(displacement[5, 0], expected, places=5)

    def test_double_correction_is_rejected_and_unapplied_layers_are_warned(self):
        applied_manifest = write_input(self.root, correction=True, applied=["troposphere"])
        correction_config = write_config(self.root, correctionsToSubtract=["troposphere"])
        output_root = self.root / "double-output"
        with self.assertRaisesRegex(ValueError, "double application"):
            convert("test_event", applied_manifest, correction_config, output_root=output_root)
        self.assertFalse(output_root.exists())

        # Build a second independent fixture directory so source assets do not collide.
        second_root = self.root / "unapplied"
        second_root.mkdir()
        unapplied_manifest = write_input(second_root, correction=True)
        no_correction_config = write_config(second_root)
        result = convert("test_event", unapplied_manifest, no_correction_config, output_root=second_root / "out")
        loaded = core.load_manifest(result)
        self.assertIn("troposphere", loaded["correctionState"]["availableUnapplied"])
        self.assertTrue(any("available but unapplied" in warning for warning in loaded["warnings"]))


if __name__ == "__main__":
    unittest.main()
