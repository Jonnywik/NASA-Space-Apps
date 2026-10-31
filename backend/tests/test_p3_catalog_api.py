import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from processing.p3.core import publish, load_manifest, digest
from processing.p3.catalog import select, promote, ProductUnavailable
from app.p3_api import make_router


class CatalogApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        app = FastAPI()
        app.include_router(make_router(self.root, lambda: [{'id': 'pilot'}]))
        self.client = TestClient(app)

    def tearDown(self):
        self.tmp.cleanup()

    def product(self, kind='synthetic', product='ground-motion', review=False, **extra):
        def writer(stage):
            (stage / 'sample.json').write_text('{"valid": true}')
            return {'sample': 'sample.json'}
        return publish('pilot', product, {'dataKind': kind, **extra}, writer, self.root, review=review)

    def test_missing_unknown_and_path_rejection(self):
        self.assertEqual(self.client.get('/api/v1/ground-motion?event=unknown').status_code, 404)
        self.assertEqual(self.client.get('/api/v1/ground-motion?event=pilot').json()['detail']['code'], 'data_unavailable')
        self.assertEqual(self.client.get('/api/v1/ground-motion', params={'event': 'pilot', 'runId': '../bad'}).status_code, 422)

    def test_synthetic_roundtrip_alias_and_hash_check(self):
        path = self.product(review=True)
        response = self.client.get('/api/v1/subsidence?event=pilot')
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['dataStatus'], 'synthetic')
        self.assertNotIn('_directory', body)
        url = body['assets']['sample']['url']
        self.assertEqual(self.client.get(url).json(), {'valid': True})
        (path.parent / 'sample.json').write_text('{}')
        self.assertEqual(self.client.get(url).json()['detail']['code'], 'invalid_product')

    def test_review_gate_receipt_and_exact_manifest_binding(self):
        path = self.product(kind='derived', sourceRunIds=['upstream'])
        with self.assertRaises(ProductUnavailable):
            select('pilot', 'ground-motion', path.parent.name, self.root)
        receipt = {'reviewer': 'qualified-reviewer', 'reviewedAt': '2026-10-29T00:00:00Z', 'status': 'validated',
                   'manifestSha256': digest(path), 'sourceRunIds': ['upstream'], 'evidence': ['review report: sign and reference checked']}
        receipt_path = self.root / 'review.json'
        receipt_path.write_text(json.dumps(receipt))
        promote(path, receipt_path)
        self.assertEqual(select('pilot', 'ground-motion', root=self.root)['dataStatus'], 'validated')
        manifest = json.loads(path.read_text())
        manifest['quality'] = 'changed after review'
        path.write_text(json.dumps(manifest))
        self.assertEqual(self.client.get('/api/v1/ground-motion?event=pilot').json()['detail']['code'], 'review_required')

    def test_synthetic_cannot_be_promoted(self):
        path = self.product()
        receipt = self.root / 'review.json'
        receipt.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'Synthetic'):
            promote(path, receipt)

    def test_failed_stage_keeps_current(self):
        first = self.product(review=True)
        def failed(stage):
            (stage / 'partial').write_text('partial')
            raise RuntimeError('fixture failure')
        with self.assertRaises(RuntimeError):
            publish('pilot', 'ground-motion', {'dataKind': 'synthetic'}, failed, self.root, review=True)
        self.assertEqual(select('pilot', 'ground-motion', root=self.root)['runId'], first.parent.name)
        self.assertEqual(list(first.parent.parent.glob('.stage-*')), [])

    def test_projection_year_and_scenario_validation(self):
        self.product(product='projection', review=True, scenarioId='central', supportedYears=[2026, 2027])
        self.assertEqual(self.client.get('/api/v1/projection?event=pilot&scenarioId=central&year=2028').json()['detail']['code'], 'unsupported_year')
        self.assertEqual(self.client.get('/api/v1/projection?event=pilot&scenarioId=bad&year=2026').status_code, 404)
        self.assertEqual(self.client.get('/api/v1/projection?event=pilot&scenarioId=central&year=2026').json()['selectedYear'], 2026)

    def test_manifest_rejects_traversal_asset(self):
        path = self.product()
        manifest = json.loads(path.read_text())
        outside = self.root / 'outside.json'
        outside.write_text('{}')
        manifest['assets']['bad'] = {'path': str(outside), 'sha256': digest(outside)}
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'Invalid asset path'):
            load_manifest(path)

    def test_existing_flood_routes_keep_response_contract(self):
        from app import main
        events = self.root / 'events.json'
        events.write_text(json.dumps([{'id': 'pilot', 'name': 'Pilot', 'aoi': [1, 2, 3, 4],
                                       'before_date': '2026-01-01', 'after_date': '2026-01-02'}]))
        event_dir = self.root / 'pilot'
        event_dir.mkdir()
        (event_dir / 'flood_extent.json').write_text('{"km2Flood": 0}')
        (event_dir / 'flood.geojson').write_text('{"type": "FeatureCollection", "features": []}')
        with patch.object(main, 'EVENTS_FILE', events), patch.object(main, 'OUTPUT', self.root):
            client = TestClient(main.app)
            self.assertEqual(client.get('/health').json(), {'status': 'ok'})
            entry = client.get('/api/v1/events').json()[0]
            self.assertTrue(entry['ready'])
            self.assertFalse(entry['capabilities']['ground-motion']['available'])
            result = client.get('/api/v1/flood-extent?event=pilot').json()
            self.assertEqual(result['km2Flood'], 0)
            self.assertEqual(result['floodGeojson']['features'], [])
            self.assertIsNone(result['overlays'])
            self.assertEqual(client.get('/api/v1/overlay/pilot/before').status_code, 404)


if __name__ == '__main__':
    unittest.main()
