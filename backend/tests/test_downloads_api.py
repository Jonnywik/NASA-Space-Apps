import csv
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.downloads_api import make_router


class DownloadsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / 'output'
        self.product = self.root / 'camanava_2026' / 'nisar'
        self.product.mkdir(parents=True)
        self.cache = self.base / 'cache'
        app = FastAPI()
        app.include_router(make_router(self.root, lambda: [{'id': 'camanava_2026'}]))
        self.client = TestClient(app)

    def write_json(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding='utf-8')

    def test_listing_csv_and_downloads_are_real_only(self):
        manifest = {'kind': 'nisar-flood-rhythm', 'area': 'camanava_2026', 'dataKind': 'observed',
                    'passes': [{'date': '2026-06-23', 'floodedKm2': 0.3, 'validKm2': 2, 'validFraction': 0.9,
                                'maturity': 'provisional', 'productId': 'NISAR-example'},
                               {'date': '2026-07-05', 'floodedKm2': 0, 'validKm2': 0, 'validFraction': 0,
                                'maturity': 'provisional', 'productId': 'NISAR-example-2'}], 'assets': {}}
        for key, name in [('rhythm_tif', 'rhythm.tif'), ('rhythm_half_tif', 'rhythm_half.tif')]:
            data = name.encode()
            (self.product / name).write_bytes(data)
            manifest['assets'][key] = {'path': name, 'kind': 'geotiff', 'sha256': hashlib.sha256(data).hexdigest()}
        self.write_json(self.product / 'manifest.json', manifest)
        self.write_json(self.cache / 'climate' / 'imerg_passes.json', {'area': 'camanava_2026', 'dataKind': 'observed', 'passes': [{'date': '2026-06-23', 'last48hMm': 5.2}]})
        self.write_json(self.cache / 'nisar' / 'soil_moisture' / 'manifest.json', {'area': 'camanava_2026', 'dataKind': 'observed', 'passes': [{'date': '2026-06-23', 'meanM3M3': 0.3}]})
        listing = self.client.get('/api/v1/downloads').json()
        self.assertEqual({x['id'] for x in listing}, {'rhythm', 'rhythm-half', 'open-water-passes', 'imerg-passes', 'soil-moisture-passes'})
        for entry in listing:
            response = self.client.get(entry['url'])
            self.assertEqual(response.status_code, 200)
            self.assertEqual(entry['sizeBytes'], len(response.content))
            self.assertEqual(entry['licence'], 'CC-BY-4.0')
            self.assertTrue(entry['attribution'])
            self.assertIn('attachment;', response.headers['content-disposition'])
        rows = list(csv.DictReader(io.StringIO(self.client.get('/api/v1/downloads/open-water-passes').text)))
        self.assertEqual(rows[0]['openWaterKm2'], '0.3')
        self.assertEqual(rows[0]['productId'], 'NISAR-example')
        self.assertEqual(rows[1]['openWaterKm2'], '')
        manifest['dataKind'] = 'synthetic'
        self.write_json(self.product / 'manifest.json', manifest)
        self.assertNotIn('rhythm', {x['id'] for x in self.client.get('/api/v1/downloads').json()})
        self.assertEqual(self.client.get('/api/v1/downloads/rhythm').status_code, 404)

    def test_stale_validation_and_timelapse_are_rejected(self):
        manifest = {'kind': 'nisar-flood-rhythm', 'area': 'camanava_2026', 'dataKind': 'observed'}
        manifest_path = self.product / 'manifest.json'
        self.write_json(manifest_path, manifest)
        digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        validation = {'area': 'camanava_2026', 'dataKind': 'derived', 'status': 'partial', 'agreement': {},
                      'source': {'nisar': {'dataKind': 'derived', 'productManifestSha256': digest}, 'reference': {'dataKind': 'derived'}}}
        self.write_json(self.cache / 'validation' / 'camanava_2026.json', validation)
        imerg = self.cache / 'climate' / 'imerg_passes.json'
        self.write_json(imerg, {'area': 'camanava_2026', 'dataKind': 'observed', 'passes': [{'date': '2026-06-23'}]})
        gif = self.cache / 'nisar' / 'timelapse.gif'
        gif.parent.mkdir(parents=True)
        gif.write_bytes(b'GIF89a')
        self.write_json(gif.with_suffix('.json'), {'dataKind': 'derived', 'productManifestSha256': digest,
                         'gifSha256': hashlib.sha256(gif.read_bytes()).hexdigest(), 'imergCacheSha256': hashlib.sha256(imerg.read_bytes()).hexdigest()})
        self.assertEqual(self.client.get('/api/v1/downloads/validation').status_code, 200)
        self.assertEqual(self.client.get('/api/v1/nisar/timelapse.gif').content, b'GIF89a')
        manifest_path.write_text('{}')
        self.assertEqual(self.client.get('/api/v1/downloads/validation').status_code, 404)
        self.assertEqual(self.client.get('/api/v1/nisar/timelapse.gif').status_code, 404)

    def test_traversal_and_missing_assets_are_rejected(self):
        secret = self.base / 'rhythm.tif'
        secret.write_bytes(b'secret')
        self.write_json(self.product / 'manifest.json', {'kind': 'nisar-flood-rhythm', 'area': 'camanava_2026', 'dataKind': 'derived',
                        'assets': {'rhythm_tif': {'path': '../../../rhythm.tif', 'kind': 'geotiff', 'sha256': hashlib.sha256(b'secret').hexdigest()}}})
        self.assertEqual(self.client.get('/api/v1/downloads/rhythm').status_code, 404)
        self.assertEqual(self.client.get('/api/v1/downloads?area=../cache').status_code, 404)
        self.assertEqual(self.client.get('/api/v1/downloads/manifest.json').status_code, 404)


if __name__ == '__main__':
    unittest.main()
