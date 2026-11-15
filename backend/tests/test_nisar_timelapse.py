import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

SPEC = importlib.util.spec_from_file_location("timelapse", Path(__file__).resolve().parents[1] / "scripts/28_nisar_timelapse.py")
timelapse = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(timelapse)


class TimelapseTests(unittest.TestCase):
    def test_caption_uses_local_date(self):
        self.assertIn("24 Jun 2026 | 05:30 Manila", timelapse.caption("2026-06-23T21:30:35Z"))

    def test_missing_rain_is_not_zero(self):
        self.assertIsNone(timelapse.rain_value(None))
        self.assertIsNone(timelapse.rain_value({"last48hMm": 4, "missingHalfHours": 1}))
        self.assertEqual(timelapse.rain_value({"last48hMm": 0, "missingHalfHours": 0}), 0)

    def test_synthetic_and_tampered_product_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            product = root / "product"
            product.mkdir()
            rain = root / "rain.json"
            rain.write_text(json.dumps({"dataKind": "observed", "area": "camanava_2026", "hoursBeforePass": 48, "passes": []}))
            manifest = {"kind": "nisar-flood-rhythm", "area": "camanava_2026", "dataKind": "synthetic", "passCount": 1,
                        "passes": [{"id": "20260623", "date": "2026-06-23", "acquisitionTime": "2026-06-23T21:30:35Z"}], "assets": {}}
            for name in ("hh_20260623", "pass_20260623"):
                path = product / f"{name}.png"
                Image.new("RGBA", (4, 4)).save(path)
                manifest["assets"][name] = {"path": path.name, "sha256": timelapse.digest(path)}
            manifest_path = product / "manifest.json"
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "not observed"):
                timelapse.build(product, rain, root / "out.gif")
            manifest["dataKind"] = "observed"
            manifest_path.write_text(json.dumps(manifest))
            (product / "pass_20260623.png").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "asset mismatch"):
                timelapse.build(product, rain, root / "out.gif")


if __name__ == "__main__":
    unittest.main()

