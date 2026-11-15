import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.nisar_api import make_router
from processing.nisar_flood import extras as ex


class SpearmanTests(unittest.TestCase):
    def test_perfect_positive_and_negative(self):
        series = np.arange(11, dtype=float)
        stack = np.zeros((11, 1, 2))
        stack[:, 0, 0] = series * 2 + 1      # monotone increasing
        stack[:, 0, 1] = -series ** 3        # monotone decreasing
        rho = ex.spearman_per_cell(stack, series)
        self.assertAlmostEqual(rho[0, 0], 1.0)
        self.assertAlmostEqual(rho[0, 1], -1.0)

    def test_missing_values_stay_nan_not_zero(self):
        series = np.arange(11, dtype=float)
        stack = np.tile(series[:, None, None], (1, 1, 2)).astype(float)
        stack[:7, 0, 1] = np.nan  # only 4 valid steps
        rho = ex.spearman_per_cell(stack, series)
        self.assertAlmostEqual(rho[0, 0], 1.0)
        self.assertTrue(np.isnan(rho[0, 1]))

    def test_constant_cell_is_nan(self):
        rho = ex.spearman_per_cell(np.ones((11, 1, 1)), np.arange(11.0))
        self.assertTrue(np.isnan(rho[0, 0]))


class BlockAndDropTests(unittest.TestCase):
    def test_block_mean_ignores_nan(self):
        a = np.array([[1.0, 3.0], [np.nan, 2.0]])
        self.assertAlmostEqual(ex.block_mean(a, 2)[0, 0], 2.0)

    def test_coherence_drop_is_calm_median_minus_storm(self):
        storm = np.array([[0.2, np.nan]])
        calm = np.array([[[0.6, 0.5]], [[0.8, 0.5]], [[0.7, 0.5]]])
        d = ex.coherence_drop(storm, calm)
        self.assertAlmostEqual(d[0, 0], 0.5)
        self.assertTrue(np.isnan(d[0, 1]))

    def test_ramp_transparent_for_nan_and_small(self):
        rgba = ex.ramp_rgba(np.array([[np.nan, 0.01, 0.6]]), ex.DROP_STOPS, transparent_below=0.05)
        self.assertEqual(rgba[0, 0, 3], 0)
        self.assertEqual(rgba[0, 1, 3], 0)
        self.assertGreater(rgba[0, 2, 3], 0)


class ExtrasApiTests(unittest.TestCase):
    def client(self, write=True):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name) / "output"
        out.mkdir()
        extra = Path(tmp.name) / "cache" / "nisar" / "extra"
        sm = Path(tmp.name) / "cache" / "nisar" / "soil_moisture"
        extra.mkdir(parents=True)
        sm.mkdir(parents=True)
        if write:
            (extra / "rain_response.json").write_text(json.dumps({"dataKind": "derived", "stats": {"medianRho": 0.6}}))
            (extra / "rain_response.png").write_bytes(b"\x89PNG\r\n\x1a\n")
            (sm / "manifest.json").write_text(json.dumps({"dataKind": "observed", "passes": [{"date": "2026-06-23", "overlay": "sm_20260623.png"}]}))
            (sm / "sm_20260623.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        app = FastAPI()
        app.include_router(make_router(out, lambda: [{"id": "camanava_2026"}]))
        return TestClient(app)

    def test_rain_response_served(self):
        r = self.client().get("/api/v1/nisar/rain-response", params={"area": "camanava_2026"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["stats"]["medianRho"], 0.6)

    def test_missing_layer_is_data_unavailable(self):
        r = self.client().get("/api/v1/nisar/coherence-change", params={"area": "camanava_2026"})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["detail"]["code"], "data_unavailable")

    def test_soil_moisture_overlay_urls(self):
        j = self.client().get("/api/v1/nisar/soil-moisture", params={"area": "camanava_2026"}).json()
        self.assertEqual(j["passes"][0]["overlayUrl"], "/api/v1/nisar/extra/sm_20260623.png")

    def test_extra_overlay_whitelist(self):
        c = self.client()
        self.assertEqual(c.get("/api/v1/nisar/extra/rain_response.png").status_code, 200)
        self.assertEqual(c.get("/api/v1/nisar/extra/sm_20260623.png").status_code, 200)
        self.assertEqual(c.get("/api/v1/nisar/extra/..%2Fsecret.png").status_code, 404)
        self.assertEqual(c.get("/api/v1/nisar/extra/manifest.png").status_code, 404)

    def test_unknown_area(self):
        self.assertEqual(self.client().get("/api/v1/nisar/rain-response", params={"area": "x"}).status_code, 404)


if __name__ == "__main__":
    unittest.main()
