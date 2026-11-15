import json
import hashlib
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import numpy as np
import rasterio
from rasterio.transform import from_origin
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.validation_api import make_router


class ValidationApiTests(unittest.TestCase):
    def test_cache_requires_matching_canonical_product(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'output'
            cache = root.parent / 'cache' / 'validation'
            cache.mkdir(parents=True)
            manifest = root / 'camanava_2026' / 'nisar' / 'manifest.json'
            manifest.parent.mkdir(parents=True)
            manifest.write_text('{"version": 1}')
            digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
            result = {'area': 'camanava_2026', 'dataKind': 'derived', 'status': 'partial',
                      'source': {'nisar': {'dataKind': 'derived', 'productManifestSha256': digest},
                                 'reference': {'dataKind': 'derived'}}, 'agreement': {}}
            (cache / 'camanava_2026.json').write_text(json.dumps(result))
            app = FastAPI()
            app.include_router(make_router(root, lambda: [{'id': 'camanava_2026'}]))
            client = TestClient(app)
            self.assertEqual(client.get('/api/v1/validation').status_code, 200)
            manifest.write_text('{"version": 2}')
            self.assertEqual(client.get('/api/v1/validation').status_code, 404)
            manifest.unlink()
            self.assertEqual(client.get('/api/v1/validation').status_code, 404)

    def test_opera_normalization_excludes_masks_and_fill(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "61_opera_comparison.py"
        spec = importlib.util.spec_from_file_location("opera_comparison", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / "source.tif", Path(directory) / "binary.tif"
            with rasterio.open(source, "w", driver="GTiff", width=5, height=1, count=1, dtype="uint8",
                               crs="EPSG:4326", nodata=255,
                               transform=from_origin(120.88, 14.82, 0.032, 0.22)) as dst:
                dst.write(np.array([[0, 1, 250, 251, 255]], dtype="uint8"), 1)
            module.normalize_reference(source, target)
            with rasterio.open(target) as result:
                self.assertEqual(result.nodata, 255)
                self.assertEqual(result.read(1).tolist(), [[0, 1, 255, 255, 255]])

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

    def test_script_reports_elapsed_time_and_excludes_nodata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = [root / "nisar.tif", root / "reference.tif"]
            for path, values in zip(paths, ([[1, 0, 255]], [[1, 1, 0]])):
                with rasterio.open(path, "w", driver="GTiff", width=3, height=1, count=1,
                                   dtype="uint8", crs="EPSG:32651", nodata=255,
                                   transform=from_origin(0, 30, 30, 30)) as dst:
                    dst.write(np.array(values, dtype="uint8"), 1)
            provenance = root / "source.json"
            provenance.write_text(json.dumps({
                "nisar": {"dataKind": "observed", "source": "NISAR", "url": "https://example.com/n",
                          "date": "2026-09-15", "acquisitionTime": "2026-09-15T21:30:31Z"},
                "reference": {"dataKind": "derived", "source": "DSWx", "url": "https://example.com/r",
                              "date": "2026-09-17", "acquisitionTime": "2026-09-17T21:46:11Z"}}))
            output = root / "result.json"
            script = Path(__file__).resolve().parents[1] / "scripts" / "60_validation.py"
            subprocess.run([sys.executable, str(script), "--nisar", str(paths[0]), "--reference", str(paths[1]),
                            "--provenance", str(provenance), "--out", str(output)], check=True)
            report = json.loads(output.read_text())
            self.assertEqual(report["temporalMatch"]["calendarDays"], 2)
            self.assertAlmostEqual(report["temporalMatch"]["elapsedHours"], 48 + 940 / 3600)
            self.assertFalse(report["temporalMatch"]["within48Hours"])
            self.assertTrue(any("NEAR MATCH" in warning for warning in report["warnings"]))
            self.assertEqual(report["agreement"]["validPixels"], 2)
            self.assertEqual(report["agreement"]["confusionMatrix"], {"tp": 1, "tn": 0, "fp": 0, "fn": 1})


if __name__ == "__main__":
    unittest.main()
