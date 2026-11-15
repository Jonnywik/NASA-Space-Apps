import json
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.climate_api import make_router

DOC = {
    "schemaVersion": "1.0", "area": "camanava_2026", "dataKind": "observed",
    "source": {"name": "NASA GPM IMERG Late Run half-hourly V07 (GPM_3IMERGHHL)"},
    "passes": [{"date": "2026-08-10", "last24hMm": None, "last48hMm": 12.5, "hoursSinceRain": 30.0,
                "series": [{"start": "2026-08-09T00:00:00Z", "end": "2026-08-09T00:29:59Z", "meanMmHr": None}]}],
    "limitations": ["satellite estimate"], "warnings": [],
}


class ImergApiTests(unittest.TestCase):
    def client(self, write=True):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        if write:
            (Path(tmp.name) / "imerg_passes.json").write_text(json.dumps(DOC))
        app = FastAPI()
        app.include_router(make_router(Path(tmp.name), lambda: [], cache_dir=Path(tmp.name)))
        return TestClient(app)

    def test_serves_cached_file_with_nulls_kept(self):
        r = self.client().get("/api/v1/climate/imerg/passes", params={"area": "camanava_2026"})
        self.assertEqual(r.status_code, 200)
        p = r.json()["passes"][0]
        self.assertIsNone(p["last24hMm"])  # missing stays null, never zero
        self.assertEqual(p["series"][0]["meanMmHr"], None)

    def test_series_can_be_omitted(self):
        r = self.client().get("/api/v1/climate/imerg/passes", params={"area": "camanava_2026", "series": "false"})
        self.assertNotIn("series", r.json()["passes"][0])

    def test_series_flag_errors_use_the_detail_object_shape(self):
        r = self.client().get("/api/v1/climate/imerg/passes", params={"area": "camanava_2026", "series": "maybe"})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"]["code"], "invalid_request")
        for value, kept in (("1", True), ("no", False), ("FALSE", False), ("yes", True)):
            r = self.client().get("/api/v1/climate/imerg/passes", params={"area": "camanava_2026", "series": value})
            self.assertEqual(r.status_code, 200, value)
            self.assertEqual("series" in r.json()["passes"][0], kept, value)

    def test_missing_cache_is_data_unavailable(self):
        r = self.client(write=False).get("/api/v1/climate/imerg/passes", params={"area": "camanava_2026"})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["detail"]["code"], "data_unavailable")

    def test_unknown_area_rejected(self):
        r = self.client().get("/api/v1/climate/imerg/passes", params={"area": "elsewhere"})
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main()
