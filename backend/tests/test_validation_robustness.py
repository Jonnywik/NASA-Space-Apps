import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import validation_api


class RobustnessEndpointTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.output = root / "output"
        (self.output / "camanava_2026" / "nisar").mkdir(parents=True)
        self.manifest = self.output / "camanava_2026" / "nisar" / "manifest.json"
        self.manifest.write_text('{"dataKind": "observed"}')
        self.cache = root / "cache" / "validation"
        self.cache.mkdir(parents=True)
        app = FastAPI()
        app.include_router(validation_api.make_router(self.output, lambda: [{"id": "camanava_2026"}]))
        self.client = TestClient(app)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, sha):
        doc = {"area": "camanava_2026", "dataKind": "derived", "productManifestSha256": sha,
               "correlations": [{"label": "x", "rho": -0.77, "pPermutation": 0.008}]}
        (self.cache / "robustness.json").write_text(json.dumps(doc))

    def test_served_when_bound_to_current_product(self):
        self.write(hashlib.sha256(self.manifest.read_bytes()).hexdigest())
        r = self.client.get("/api/v1/validation/robustness")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["correlations"][0]["rho"], -0.77)

    def test_404_when_product_changed(self):
        self.write("0" * 64)
        r = self.client.get("/api/v1/validation/robustness")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["detail"]["code"], "data_unavailable")

    def test_404_when_missing_or_unknown_area(self):
        self.assertEqual(self.client.get("/api/v1/validation/robustness").status_code, 404)
        r = self.client.get("/api/v1/validation/robustness", params={"area": "nope"})
        self.assertEqual(r.json()["detail"]["code"], "unknown_area")


    def test_cross_track_bound_to_product(self):
        doc = {"area": "camanava_2026", "dataKind": "derived", "geometryAgreement": {"shareAscendingNearDescending": 0.99},
               "productManifestSha256": hashlib.sha256(self.manifest.read_bytes()).hexdigest()}
        (self.cache / "cross_track.json").write_text(json.dumps(doc))
        r = self.client.get("/api/v1/validation/cross-track")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["geometryAgreement"]["shareAscendingNearDescending"], 0.99)
        doc["productManifestSha256"] = "f" * 64
        (self.cache / "cross_track.json").write_text(json.dumps(doc))
        self.assertEqual(self.client.get("/api/v1/validation/cross-track").status_code, 404)


if __name__ == "__main__":
    unittest.main()
