import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from app.product_binding import bound_to_imerg, bound_to_product, imerg_fingerprint, product_fingerprint

MANIFEST = {"area": "camanava_2026", "dataKind": "observed", "generatedAt": "2026-11-15T05:00:00Z",
            "rule": {"hhThresholdDb": -12.5, "hvThresholdDb": -22.5}, "rhythm": {"halfOrMoreKm2": 0.3721},
            "passes": [{"id": "20260623", "productId": "P1", "floodedKm2": 0.5339, "permanentWaterKm2": 68.5409, "validKm2": 419.4374}]}


class ProductBindingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "manifest.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_regenerated_product_with_same_science_still_matches(self):
        self.path.write_text(json.dumps(MANIFEST))
        recorded = {"productManifestSha256": "0" * 64, "productFingerprint": product_fingerprint(MANIFEST)}
        regenerated = {**MANIFEST, "generatedAt": "2026-11-15T09:00:00Z", "warnings": ["layout not verified"]}
        self.path.write_text(json.dumps(regenerated, indent=3))
        self.assertTrue(bound_to_product(recorded, self.path))

    def test_changed_science_does_not_match(self):
        recorded = {"productFingerprint": product_fingerprint(MANIFEST)}
        changed = json.loads(json.dumps(MANIFEST))
        changed["rule"]["hhThresholdDb"] = -13.0
        self.path.write_text(json.dumps(changed))
        self.assertFalse(bound_to_product(recorded, self.path))
        changed = json.loads(json.dumps(MANIFEST))
        changed["passes"][0]["floodedKm2"] = 0.6
        self.path.write_text(json.dumps(changed))
        self.assertFalse(bound_to_product(recorded, self.path))

    def test_raw_hash_still_accepted_and_missing_rejected(self):
        self.path.write_text(json.dumps(MANIFEST))
        self.assertTrue(bound_to_product({"productManifestSha256": hashlib.sha256(self.path.read_bytes()).hexdigest()}, self.path))
        self.assertFalse(bound_to_product({}, self.path))
        self.assertFalse(bound_to_product({"productFingerprint": "x"}, Path(self.tmp.name) / "missing.json"))

    def test_imerg_fingerprint_ignores_retrieval_metadata(self):
        doc = {"retrievedAt": "a", "passes": [{"date": "2026-08-10", "last48hMm": 96.55, "last24hMm": 3.0, "last6hMm": 0.0}]}
        p = Path(self.tmp.name) / "imerg.json"
        p.write_text(json.dumps({**doc, "retrievedAt": "b"}))
        self.assertTrue(bound_to_imerg({"imergFingerprint": imerg_fingerprint(doc)}, p))


if __name__ == "__main__":
    unittest.main()
