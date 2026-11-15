import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.validation_api import make_router


class ValidationApiTests(unittest.TestCase):
    def test_missing_and_synthetic_cache_not_served(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "output"
            app = FastAPI()
            app.include_router(make_router(root, lambda: [{"id": "camanava_2026"}]))
            client = TestClient(app)
            self.assertEqual(client.get("/api/v1/validation").json()["detail"]["code"], "data_unavailable")
            cache = root.parent / "cache" / "validation"
            cache.mkdir(parents=True)
            (cache / "camanava_2026.json").write_text(json.dumps({"area": "camanava_2026", "dataKind": "synthetic"}))
            self.assertEqual(client.get("/api/v1/validation").json()["detail"]["code"], "data_unavailable")
            (cache / "camanava_2026.json").write_text(json.dumps({"area": "camanava_2026", "dataKind": "derived", "status": "partial", "source": "literature"}))
            self.assertEqual(client.get("/api/v1/validation").json()["detail"]["code"], "data_unavailable")
            self.assertEqual(client.get("/api/v1/validation?area=other").status_code, 404)

    def test_script_rejects_synthetic_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            provenance = Path(directory) / "source.json"
            provenance.write_text(json.dumps({"nisar": {"dataKind": "synthetic", "source": "fixture", "url": "https://example.com"}}))
            script = Path(__file__).resolve().parents[1] / "scripts" / "60_validation.py"
            result = subprocess.run([sys.executable, str(script), "--nisar", "none", "--reference", "none",
                                     "--provenance", str(provenance)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("synthetic is rejected", result.stderr)


if __name__ == "__main__":
    unittest.main()
