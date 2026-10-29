from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import h5py
import numpy as np
import rasterio
import xarray as xr

from processing.p3 import core
from processing.p3.ingestion import ingest


class IngestionTests(unittest.TestCase):
    def test_historical_observations_cannot_be_relabelled_nisar(self) -> None:
        config = self._base_config()
        config["dataKind"] = "observed"
        config["source"]["acquisitionDates"] = ["2024-01-01T00:00:00Z", "2024-02-01T00:00:00Z"]
        self._write_config(config)
        with self.assertRaisesRegex(ValueError, "predate"):
            ingest("pilot_event", self.config, self.output)

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "fixture_product.h5"
        self.config = self.root / "source.json"
        self.output = self.root / "output"
        self._write_gunw()
        self._write_config()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write_gunw(self) -> None:
        phase = np.arange(42, dtype="float32").reshape(6, 7) / 10.0
        phase[1, 2] = -9999
        coherence = np.full((6, 7), 0.7, dtype="float32")
        components = np.ones((6, 7), dtype="int16")
        components[:, 5:] = 2
        correction = np.full((6, 7), 0.01, dtype="float32")
        incidence = np.full((6, 7), 34.0, dtype="float32")
        quality = np.ones((6, 7), dtype="uint8")
        quality[0, 0] = 0
        with h5py.File(self.source, "w") as product:
            grid = product.create_group("grid")
            grid.create_dataset("x", data=500000 + np.arange(7) * 20)
            grid.create_dataset("y", data=4100000 - np.arange(6) * 20)
            science = product.create_group("science")
            for name, values, units in (
                ("phase", phase, "radian"),
                ("coherence", coherence, "1"),
                ("components", components, "label"),
                ("troposphere", correction, "rad"),
                ("incidence", incidence, "degree"),
                ("quality", quality, "1"),
            ):
                dataset = science.create_dataset(name, data=values)
                dataset.attrs["units"] = units
            science["phase"].attrs["_FillValue"] = -9999.0
            meta = product.create_group("metadata")
            meta.attrs["productId"] = "fixture-GUNW-001"
            meta.attrs["processingVersion"] = "fixture-processor-3"
            meta.attrs["frequency"] = "L"
            meta.attrs["polarization"] = "HH"
            meta.attrs["acquisitionDates"] = np.asarray(
                ["2024-01-02T03:04:05Z", "2024-01-14T03:04:05Z"], dtype=h5py.string_dtype()
            )
            meta.attrs["wavelengthMetres"] = 0.24
            meta.attrs["phaseToAwaySign"] = -1

    def _base_config(self, product_type: str = "GUNW") -> dict:
        common = {
            "productId": f"fixture-{product_type}-001",
            "sensor": "NISAR",
            "frequency": "L",
            "polarization": "HH",
            "orbit": "ascending-001",
            "frame": "frame-042",
            "processingVersion": "fixture-processor-3",
            "maturity": "synthetic-fixture",
            "acquisitionDates": ["2024-01-02T03:04:05Z", "2024-01-14T03:04:05Z"] if product_type == "GUNW" else ["2024-01-14T03:04:05Z"],
            "quality": {"sourceQuality": "fixture-valid"},
        }
        if product_type == "GUNW":
            common.update(
                wavelengthMetres=0.24,
                wavelengthUnits="metre",
                phaseToAwaySign=-1,
                phaseUnits="radian",
                correctionsApplied=["ionosphere"],
                nativeResolution={"x": 20.0, "y": 20.0, "units": "m"},
            )
        return {
            "configVersion": "1.0",
            "event": "pilot_event",
            "productType": product_type,
            "dataKind": "synthetic",
            "source": {"path": self.source.name, "sha256": hashlib.sha256(self.source.read_bytes()).hexdigest(), **common},
            "sourceProfile": {
                "id": "nisar-fixture-v1",
                "version": "1",
                "adapter": "hdf5",
                "status": "needs-review",
                "evidence": [],
                "arrayAxisOrder": "yx",
                "crs": "EPSG:32651",
                "coordinateDatasets": {"x": "/grid/x", "y": "/grid/y"},
                "datasets": {
                    "phase": {"path": "/science/phase", "units": "radian"},
                    "coherence": {"path": "/science/coherence", "units": "1"},
                    "components": {"path": "/science/components", "units": "label"},
                },
                "corrections": {
                    "ionosphere": {
                        "path": "/science/troposphere",
                        "units": "radian",
                        "appliesTo": "phase",
                        "signConvention": "same_as_phase",
                    }
                },
                "geometry": {"incidenceAngle": {"path": "/science/incidence", "units": "degree"}},
                "qualityMask": {
                    "dataset": {"path": "/science/quality", "units": "1"},
                    "validValues": [1],
                    "appliesTo": ["phase", "coherence", "components"],
                },
                "metadataAttributes": {
                    "productId": {"object": "/metadata", "attribute": "productId"},
                    "processingVersion": {"object": "/metadata", "attribute": "processingVersion"},
                    "frequency": {"object": "/metadata", "attribute": "frequency"},
                    "polarization": {"object": "/metadata", "attribute": "polarization"},
                    "acquisitionDates": {"object": "/metadata", "attribute": "acquisitionDates"},
                    "wavelengthMetres": {"object": "/metadata", "attribute": "wavelengthMetres"},
                    "phaseToAwaySign": {"object": "/metadata", "attribute": "phaseToAwaySign"},
                },
            },
        }

    def _write_config(self, config: dict | None = None) -> None:
        self.config.write_text(json.dumps(config or self._base_config()), encoding="utf-8")

    def test_gunw_ingestion_preserves_grid_masks_lineage_and_corrections(self) -> None:
        config = self._base_config()
        config["sourceProfile"]["window"] = {"rowStart": 0, "rowStop": 5, "colStart": 0, "colStop": 6}
        self._write_config(config)
        manifest_path = ingest("pilot_event", self.config, self.output)
        manifest = core.load_manifest(manifest_path)

        self.assertEqual(manifest["product"], "gunw")
        self.assertEqual(manifest["dataKind"], "synthetic")
        self.assertTrue(manifest["syntheticLineage"])
        self.assertEqual(manifest["phaseUnits"], "radian")
        self.assertEqual(manifest["wavelengthUnits"], "metre")
        self.assertEqual(manifest["phaseToAwaySign"], -1)
        self.assertEqual(manifest["correctionsApplied"], ["ionosphere"])
        self.assertEqual(manifest["correctionsAvailable"][0]["name"], "ionosphere")
        self.assertEqual(manifest["sourceProfileStatus"], "needs-review")
        self.assertIn("not tiled", manifest["processingNotes"][0])
        self.assertEqual(manifest["grid"]["width"], 6)
        self.assertEqual(manifest["grid"]["height"], 5)
        self.assertEqual(manifest["grid"]["transform"][:6], [20.0, 0.0, 499990.0, 0.0, -20.0, 4100010.0])
        self.assertEqual(set(manifest["assets"]), {"phase", "coherence", "components", "correction_ionosphere", "geometry_incidenceAngle", "qualityMask"})
        self.assertEqual(manifest["quality"]["validPixelCount"], 28)
        with rasterio.open(core.asset_path(manifest, "phase")) as dataset:
            phase = dataset.read(1)
            self.assertTrue(np.isnan(phase[0, 0]))  # native quality mask
            self.assertTrue(np.isnan(phase[1, 2]))  # source fill value
            self.assertEqual(phase[2, 1], 1.5)

    def _write_gcov(self) -> None:
        with h5py.File(self.source, "w") as product:
            product.create_dataset("grid/x", data=100 + np.arange(4) * 10)
            product.create_dataset("grid/y", data=200 - np.arange(3) * 10)
            product.create_dataset("cov/HHHH", data=np.full((3, 4), 0.6, dtype="float32"))
            product.create_dataset("cov/HVHV", data=np.full((3, 4), 0.08, dtype="float32"))
            for name in ("HHHH", "HVHV"):
                product[f"cov/{name}"].attrs["units"] = "linear_power"

    def test_gcov_requires_explicit_hhhh_and_hvhv_and_publishes_units(self) -> None:
        self._write_gcov()
        config = self._base_config("GCOV")
        config["source"]["path"] = self.source.name
        config["source"]["sha256"] = hashlib.sha256(self.source.read_bytes()).hexdigest()
        config["source"].pop("wavelengthMetres", None)
        config["source"].pop("wavelengthUnits", None)
        config["source"].pop("phaseToAwaySign", None)
        config["source"].pop("phaseUnits", None)
        config["source"].pop("correctionsApplied", None)
        profile = config["sourceProfile"]
        profile["datasets"] = {
            "HHHH": {"path": "/cov/HHHH", "units": "linear_power"},
            "HVHV": {"path": "/cov/HVHV", "units": "linear_power"},
        }
        for optional in ("corrections", "geometry", "qualityMask", "metadataAttributes"):
            profile.pop(optional, None)
        self._write_config(config)
        manifest = core.load_manifest(ingest("pilot_event", self.config, self.output))
        self.assertEqual(manifest["product"], "gcov")
        self.assertEqual(set(manifest["assets"]), {"HHHH", "HVHV"})
        self.assertEqual(manifest["units"]["HHHH"], "linear_power")
        self.assertEqual(manifest["acquisitionDates"], ["2024-01-14T03:04:05Z"])

    def test_zero_phase_without_explicit_fill_metadata_remains_valid(self) -> None:
        with h5py.File(self.source, "w") as product:
            product.create_dataset("grid/x", data=500000 + np.arange(3) * 20)
            product.create_dataset("grid/y", data=4100000 - np.arange(3) * 20)
            phase = product.create_dataset("science/phase", data=np.zeros((3, 3), dtype="float32"))
            phase.attrs["units"] = "radian"
            coherence = product.create_dataset("science/coherence", data=np.zeros((3, 3), dtype="float32"))
            coherence.attrs["units"] = "1"
            components = product.create_dataset("science/components", data=np.zeros((3, 3), dtype="int16"))
            components.attrs["units"] = "label"
        config = self._base_config()
        config["source"]["sha256"] = hashlib.sha256(self.source.read_bytes()).hexdigest()
        profile = config["sourceProfile"]
        profile.pop("metadataAttributes", None)
        profile.pop("corrections", None)
        profile.pop("geometry", None)
        profile.pop("qualityMask", None)
        self._write_config(config)
        manifest = core.load_manifest(ingest("pilot_event", self.config, self.output))
        with rasterio.open(core.asset_path(manifest, "phase")) as dataset:
            normalized = dataset.read(1)
        self.assertTrue(np.all(normalized == 0.0))

    def test_aria_netcdf_adapter_crops_and_flips_axes_from_explicit_coordinates(self) -> None:
        x = np.asarray([104.0, 103.0, 102.0, 101.0])
        y = np.asarray([200.0, 201.0, 202.0])
        phase = np.arange(12, dtype="float32").reshape(3, 4)
        source = xr.Dataset(
            {
                "phase": (("y", "x"), phase, {"units": "radian"}),
                "coherence": (("y", "x"), np.full((3, 4), 0.8, dtype="float32"), {"units": "1"}),
                "components": (("y", "x"), np.ones((3, 4), dtype="int16"), {"units": "label"}),
            },
            coords={"x": (("x",), x), "y": (("y",), y)},
        )
        source.to_netcdf(self.source, engine="netcdf4")
        config = self._base_config()
        config["source"]["path"] = self.source.name
        config["source"]["sha256"] = hashlib.sha256(self.source.read_bytes()).hexdigest()
        config["source"]["nativeResolution"] = {"x": 1.0, "y": 1.0, "units": "m"}
        profile = config["sourceProfile"]
        profile["adapter"] = "aria-netcdf"
        profile["coordinateDatasets"] = {"x": "x", "y": "y"}
        profile["datasets"] = {
            "phase": {"path": "phase", "units": "radian"},
            "coherence": {"path": "coherence", "units": "1"},
            "components": {"path": "components", "units": "label"},
        }
        profile["window"] = {"rowStart": 0, "rowStop": 3, "colStart": 1, "colStop": 4}
        profile.pop("metadataAttributes", None)
        profile.pop("corrections", None)
        profile.pop("geometry", None)
        profile.pop("qualityMask", None)
        self._write_config(config)
        manifest = core.load_manifest(ingest("pilot_event", self.config, self.output))
        self.assertEqual(manifest["sourceProfile"]["adapter"], "aria-netcdf")
        self.assertEqual(manifest["grid"]["width"], 3)
        self.assertEqual(manifest["grid"]["height"], 3)
        self.assertEqual(manifest["grid"]["transform"][:6], [1.0, 0.0, 100.5, 0.0, -1.0, 202.5])
        with rasterio.open(core.asset_path(manifest, "phase")) as dataset:
            self.assertEqual(dataset.read(1).tolist(), [[11.0, 10.0, 9.0], [7.0, 6.0, 5.0], [3.0, 2.0, 1.0]])

    def test_rejects_checksum_mismatch_and_unverified_dataset_path(self) -> None:
        config = self._base_config()
        config["source"]["sha256"] = "0" * 64
        self._write_config(config)
        with self.assertRaisesRegex(ValueError, "sha256"):
            ingest("pilot_event", self.config, self.output)

        config = self._base_config()
        config["sourceProfile"]["datasets"]["phase"]["path"] = "/science/not_a_phase"
        self._write_config(config)
        with self.assertRaisesRegex(ValueError, "does not exist"):
            ingest("pilot_event", self.config, self.output)

    def test_rejects_product_version_that_conflicts_with_embedded_metadata(self) -> None:
        with h5py.File(self.source, "a") as product:
            product["metadata"].attrs["processingVersion"] = "unexpected-version"
        config = self._base_config()
        config["source"]["sha256"] = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self._write_config(config)
        with self.assertRaisesRegex(ValueError, "processingVersion.*conflicts"):
            ingest("pilot_event", self.config, self.output)

    def test_rejects_wrong_units_sign_chronology_and_uncorroborated_profile_claim(self) -> None:
        cases = []
        config = self._base_config()
        config["sourceProfile"]["datasets"]["phase"]["units"] = "degree"
        cases.append((config, "unsupported"))
        config = self._base_config()
        config["source"]["phaseToAwaySign"] = 0
        cases.append((config, "phaseToAwaySign"))
        config = self._base_config()
        config["source"]["acquisitionDates"] = ["2024-01-14T03:04:05Z", "2024-01-02T03:04:05Z"]
        cases.append((config, "chronological"))
        config = self._base_config()
        config["sourceProfile"]["status"] = "verified"
        config["sourceProfile"]["evidence"] = []
        cases.append((config, "evidence"))
        for candidate, message in cases:
            with self.subTest(message=message):
                self._write_config(candidate)
                with self.assertRaisesRegex(ValueError, message):
                    ingest("pilot_event", self.config, self.output)


if __name__ == "__main__":
    unittest.main()
