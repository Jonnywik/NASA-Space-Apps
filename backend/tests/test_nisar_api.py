import json
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.nisar_api import make_router
from processing.nisar_flood.constants import COLOR_VEGETATION, COLOR_WATER
from processing.nisar_flood import pipeline
from nisar_fixtures import build_product


class NisarApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root, cls.out, cls.analysis = build_product(cls.tmp.name)
        cls.client = cls.make_client(cls.root)

    @classmethod
    def make_client(cls, root, events=None):
        app = FastAPI()
        app.include_router(make_router(root, lambda: events if events is not None else [{"id": "camanava_2026"}]))
        return TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def code(self, response):
        return response.json()["detail"]["code"]

    # -- passes ---------------------------------------------------------------
    def test_passes_contract_fields_and_synthetic_label(self):
        r = self.client.get("/api/v1/nisar/passes?area=camanava_2026")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["dataKind"], "synthetic")
        for key in ("area", "sensor", "product", "track", "direction", "frame", "polarizations", "rule", "passes", "bounds",
                    "source", "generatedAt", "warnings", "limitations", "units", "nativeResolution"):
            self.assertIn(key, body)
        self.assertEqual(body["legend"], [
            {"id": "flood_water", "label": "Flood water", "color": COLOR_WATER},
            {"id": "possible_flooded_vegetation", "label": "Possible flooded vegetation", "color": COLOR_VEGETATION},
        ])
        self.assertEqual(body["direction"], "descending")
        self.assertEqual(body["polarizations"], ["HH", "HV"])
        self.assertEqual(set(body["rule"]), {"description", "hhThresholdDb", "hvThresholdDb", "calibration"})
        self.assertIn("SYNTHETIC", body["warnings"][0])
        first = body["passes"][0]
        for key in ("id", "date", "acquisitionTime", "productId", "maturity", "floodedKm2", "permanentWaterKm2", "floodedVegetationKm2",
                    "validKm2", "validFraction", "overlayUrl", "backscatterUrl"):
            self.assertIn(key, first)
        self.assertEqual(first["overlayUrl"], f"/api/v1/nisar/overlay/camanava_2026/pass_{first['id']}.png")
        self.assertTrue(first["productId"].startswith("SYNTHETIC"))
        self.assertEqual(len(body["passes"]), 4)

    def test_area_defaults_and_unknown_area(self):
        self.assertEqual(self.client.get("/api/v1/nisar/passes").status_code, 200)
        r = self.client.get("/api/v1/nisar/passes?area=nowhere")
        self.assertEqual((r.status_code, self.code(r)), (404, "unknown_area"))
        for path in ("flood-rhythm", "polarization?date=2026-07-01", "point?lon=120.95&lat=14.7"):
            sep = "&" if "?" in path else "?"
            self.assertEqual(self.code(self.client.get(f"/api/v1/nisar/{path}{sep}area=nowhere")), "unknown_area", path)

    def test_no_product_is_data_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = self.make_client(Path(tmp))
            for path in ("passes", "flood-rhythm", "point?lon=120.95&lat=14.7", "polarization?date=2026-07-01",
                         "overlay/camanava_2026/rhythm.png"):
                r = client.get(f"/api/v1/nisar/{path}")
                self.assertEqual((r.status_code, self.code(r)), (404, "data_unavailable"), path)

    def test_observed_product_is_labelled_observed_and_derived(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "camanava_2026" / "nisar"
            pipeline.export_product(self.analysis, out, data_kind="observed", source={"name": "n", "url": None, "version": "v"},
                                    track={"track": 32, "direction": "D", "frame": 81, "mode": "4005"})
            client = self.make_client(Path(tmp))
            self.assertEqual(client.get("/api/v1/nisar/passes").json()["dataKind"], "observed")
            self.assertEqual(client.get("/api/v1/nisar/flood-rhythm").json()["dataKind"], "derived")
            self.assertEqual(client.get("/api/v1/nisar/point?lon=120.95&lat=14.7").json()["dataKind"], "derived")

    # -- rhythm ---------------------------------------------------------------
    def test_flood_rhythm(self):
        r = self.client.get("/api/v1/nisar/flood-rhythm?area=camanava_2026")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["dataKind"], "synthetic")
        self.assertEqual(body["passCount"], 4)
        self.assertEqual(len(body["legend"]), 4)
        self.assertTrue(all(item["color"].startswith("#") for item in body["legend"]))
        self.assertEqual([i["count"] for i in body["km2ByCount"]], [1, 2, 3, 4])
        self.assertTrue(body["permanentWaterMasked"])
        self.assertIn("valid passes", body["method"])
        self.assertEqual(body["overlayUrl"], "/api/v1/nisar/overlay/camanava_2026/rhythm.png")
        self.assertEqual(len(body["bounds"]), 2)
        self.assertIn("byValidPasses", body)
        self.assertTrue(any("Urban" in x for x in body["limitations"]))

    # -- point ----------------------------------------------------------------
    def test_point_in_land_and_in_permanent_water_and_in_nodata_block(self):
        land = self.client.get("/api/v1/nisar/point?area=camanava_2026&lon=120.945&lat=14.70").json()
        self.assertEqual(len(land["perPass"]), 4)
        self.assertEqual(land["validCount"], 4)
        self.assertIsInstance(land["floodCount"], int)
        self.assertFalse(land["permanentWater"])
        self.assertTrue(all(p["state"] in ("water", "dry", "nodata") for p in land["perPass"]))
        self.assertIn("cellCenter", land)

        bay = self.client.get("/api/v1/nisar/point?lon=120.89&lat=14.65").json()
        self.assertTrue(bay["permanentWater"])
        self.assertIsNone(bay["floodCount"])  # null with a reason, never 0
        self.assertIn("permanent water", bay["floodCountReason"])

        # the synthetic third pass has no data in this block: nodata, not dry; denominator is 3
        gap = self.client.get("/api/v1/nisar/point?lon=121.0&lat=14.69").json()
        self.assertEqual(gap["perPass"][2]["state"], "nodata")
        self.assertIsNone(gap["perPass"][2]["hhDb"])
        self.assertEqual(gap["validCount"], 3)

    def test_point_errors(self):
        for query in ("", "?lon=120.9", "?lat=14.7", "?lon=abc&lat=14.7", "?lon=500&lat=14.7", "?lon=120.9&lat=-91", "?lon=nan&lat=14.7"):
            r = self.client.get("/api/v1/nisar/point" + query)
            self.assertEqual((r.status_code, self.code(r)), (422, "invalid_request"), query)
        for query in ("?lon=0&lat=0", "?lon=121.5&lat=14.7", "?lon=120.95&lat=15.5"):
            r = self.client.get("/api/v1/nisar/point" + query)
            self.assertEqual((r.status_code, self.code(r)), (404, "outside_coverage"), query)

    # -- overlays -------------------------------------------------------------
    def test_registered_overlays_are_served_as_png(self):
        for name in ("rhythm", "rhythm_legend", "pass_20260702", "hh_20260702", "veg_20260702", "pol_20260702"):
            r = self.client.get(f"/api/v1/nisar/overlay/camanava_2026/{name}.png")
            self.assertEqual(r.status_code, 200, name)
            self.assertEqual(r.headers["content-type"], "image/png")
            self.assertTrue(r.content.startswith(b"\x89PNG"))
            self.assertEqual(r.headers["x-tanaw-data-kind"], "synthetic")

    def test_overlay_refuses_names_not_in_manifest(self):
        for name in ("pass_20990101.png", "manifest.png", "nope.png", "state_20260702.png", "db_20260702.png"):
            r = self.client.get(f"/api/v1/nisar/overlay/camanava_2026/{name}")
            self.assertEqual((r.status_code, self.code(r)), (404, "data_unavailable"), name)

    def test_overlay_refuses_malformed_names_and_other_files(self):
        for name in ("manifest.json", "rhythm", "rhythm.png.json", "rhythm.tif", ".png", "a%20b.png", "..%5Cmanifest.png"):
            r = self.client.get(f"/api/v1/nisar/overlay/camanava_2026/{name}")
            self.assertIn(r.status_code, (404, 422), name)
            self.assertNotEqual(r.status_code, 200)
        for name in ("..%2Fmanifest.json", "%2E%2E%2F%2E%2E%2Fetc%2Fpasswd", "tif%2Fpermanent_water.png"):
            r = self.client.get(f"/api/v1/nisar/overlay/camanava_2026/{name}")
            self.assertEqual(r.status_code, 404, name)
        self.assertEqual(self.client.get("/api/v1/nisar/overlay/other/rhythm.png").status_code, 404)

    def test_overlay_that_fails_its_manifest_hash_is_not_served(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "camanava_2026" / "nisar"
            pipeline.export_product(self.analysis, out, data_kind="synthetic", source={"name": "n"})
            client = self.make_client(Path(tmp))
            self.assertEqual(client.get("/api/v1/nisar/overlay/camanava_2026/rhythm.png").status_code, 200)
            (out / "rhythm.png").write_bytes(b"\x89PNG tampered")
            r = client.get("/api/v1/nisar/overlay/camanava_2026/rhythm.png")
            self.assertEqual((r.status_code, self.code(r)), (404, "data_unavailable"))
            self.assertIn("integrity", r.json()["detail"]["message"])

    def test_png_file_missing_from_disk_is_not_a_server_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "camanava_2026" / "nisar"
            pipeline.export_product(self.analysis, out, data_kind="synthetic", source={"name": "n"})
            (out / "rhythm.png").unlink()
            r = self.make_client(Path(tmp)).get("/api/v1/nisar/overlay/camanava_2026/rhythm.png")
            self.assertEqual((r.status_code, self.code(r)), (404, "data_unavailable"))

    # -- polarization ---------------------------------------------------------
    def test_polarization(self):
        r = self.client.get("/api/v1/nisar/polarization?area=camanava_2026&date=2026-07-02")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["channels"], {"r": "HH", "g": "HV", "b": "HH/HV"})
        self.assertEqual(len(body["explanation"]), 3)
        self.assertEqual(body["rgbUrl"], "/api/v1/nisar/overlay/camanava_2026/pol_20260702.png")
        self.assertEqual(body["dataKind"], "synthetic")
        self.assertEqual(len(body["bounds"]), 2)

    def test_polarization_errors(self):
        for query in ("", "?date=", "?date=2026-7-2", "?date=20260702", "?date=notadate", "?date=2026-13-01"):
            r = self.client.get("/api/v1/nisar/polarization" + query)
            self.assertEqual((r.status_code, self.code(r)), (422, "invalid_request"), query)
        r = self.client.get("/api/v1/nisar/polarization?date=2026-07-30")
        self.assertEqual((r.status_code, self.code(r)), (404, "data_unavailable"))
        self.assertIn("2026-07-02", r.json()["detail"]["availableDates"])

    def test_only_get_is_allowed(self):
        self.assertEqual(self.client.post("/api/v1/nisar/passes").status_code, 405)


if __name__ == "__main__":
    unittest.main()
