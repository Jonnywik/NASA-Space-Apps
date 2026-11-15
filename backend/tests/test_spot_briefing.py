import csv
import hashlib
import io
import json
import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
import numpy as np
import rasterio
from rasterio.transform import from_origin

from app.spot_api import make_router
from processing.briefing_place.render import build, csv_text, html_text


class SpotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def client(self, point=None):
        if point is None:
            def unavailable(**kwargs):
                from fastapi import HTTPException
                raise HTTPException(404, detail={'message': 'product missing'})
            endpoint = unavailable
        else:
            endpoint = lambda **kwargs: point
        fake = SimpleNamespace(routes=[SimpleNamespace(path='/api/v1/nisar/point', endpoint=endpoint)])
        with patch('app.spot_api.nisar_router', return_value=fake):
            app = FastAPI()
            app.include_router(make_router(self.tmp.name, lambda: [{'id': 'camanava_2026'}],
                                           places_root=Path(self.tmp.name), climate_root=Path(self.tmp.name)))
        return TestClient(app)

    def test_missing_and_bounds(self):
        client = self.client()
        body = client.get('/api/v1/spot-check', params={'lon': 120.957, 'lat': 14.665}).json()
        self.assertIsNone(body['streams']['nisar']['value'])
        self.assertEqual(body['streams']['nisar']['reason'], 'product missing')
        self.assertEqual(client.get('/api/v1/spot-check?lon=120&lat=14').status_code, 404)
        self.assertEqual(client.get('/api/v1/spot-check?lon=nan&lat=14').status_code, 422)
        brief = client.get('/api/v1/briefing/place?lon=120.957&lat=14.665').json()
        self.assertTrue(any('not available because product missing' in x for x in brief['sentences']))
        self.assertEqual(client.get('/api/v1/briefing/place?lon=120.957&lat=14.665&lang=fr').status_code, 422)

    def test_synthetic_and_exports(self):
        point = {'floodCount': 2, 'floodCountReason': None, 'validCount': 3, 'permanentWater': False,
                 'possibleFloodedVegetationPasses': 0, 'perPass': [{'date': '2026-06-23', 'state': 'water'}],
                 'cellCenter': {'lon': 120.957, 'lat': 14.665}, 'source': {'name': '<unsafe>'},
                 'dataKind': 'synthetic', 'nativeResolution': '30 m', 'generatedAt': '2026-01-01'}
        client = self.client(point)
        params = {'lon': 120.957, 'lat': 14.665}
        for lang in ('en', 'fil'):
            brief = client.get('/api/v1/briefing/place', params={**params, 'lang': lang}).json()
            self.assertEqual(brief['dataKind'], 'synthetic')
            facts = json.dumps(brief['facts'], ensure_ascii=False)
            for sentence in brief['sentences']:
                for number in re.findall(r'\d+(?:\.\d+)?', sentence):
                    self.assertIn(number, facts)
            if lang == 'fil':
                self.assertEqual(brief['translationStatus'], 'pending native-speaker review')
        html = client.get('/api/v1/briefing/place', params={**params, 'format': 'html'}).text
        self.assertIn('<strong>SYNTHETIC DEMO DATA</strong>', html)
        self.assertIn('&lt;unsafe&gt;', html)
        self.assertNotIn('<unsafe>', html)
        rows = list(csv.DictReader(io.StringIO(client.get('/api/v1/briefing/place', params={**params, 'format': 'csv'}).text)))
        self.assertTrue(any(row['field'] == 'nisar.floodCount' and row['value'] == '2' for row in rows))

    def test_csv_formula_escape(self):
        stream = {'value': '=1+1', 'reason': None, 'source': None, 'dataKind': 'observed', 'nativeResolution': None, 'units': None}
        rows = list(csv.DictReader(io.StringIO(csv_text({'facts': {'streams': {'place': stream}}}))))
        self.assertEqual(rows[-1]['value'], "'=1+1")

    def test_briefing_summarizes_series_and_explains_missing_exposure(self):
        streams = {k: {'value': None, 'reason': 'not published'}
                   for k in ('place', 'nisar', 'rainfall', 'motion', 'priority', 'exposure')}
        streams['rainfall']['value'] = [{'date': '2026-06-23', 'prior7DayMm': 42.5}]
        streams['motion']['value'] = {'epochs': ['2026-06-23', '2026-07-05'], 'displacementMm': [0, 2.5]}
        streams['exposure']['value'] = {'areaKm2': 0.5, 'population': None, 'buildings': 0, 'populationReason': 'population grid absent'}
        facts = {'streams': streams, 'dataKind': 'synthetic', 'source': {}, 'generatedAt': '2026-11-15', 'warnings': [], 'limitations': []}
        for lang in ('en', 'fil'):
            text = ' '.join(build(facts, lang)['sentences'])
            self.assertIn('42.5', text)
            self.assertIn('2.5', text)
            self.assertIn('population grid absent', text)
            self.assertNotIn('None', text)
            self.assertNotIn('{', text)

    def test_priority_mask_integrity_and_nodata(self):
        folder = Path(self.tmp.name) / 'camanava_2026' / 'nisar'
        folder.mkdir(parents=True)
        path = folder / 'priority_mask.tif'
        with rasterio.open(path, 'w', driver='GTiff', width=2, height=1, count=1, dtype='uint8',
                           crs='EPSG:4326', transform=from_origin(120.95, 14.67, .01, .01), nodata=255) as ds:
            ds.write(np.array([[1, 255]], dtype='uint8'), 1)
        (folder / 'rhythm_half.tif').write_bytes(b'fixture rhythm')
        (folder / 'manifest.json').write_text('{}')
        motion = folder.parent / 'p3' / 'ground-motion' / 'fixture'
        motion.mkdir(parents=True)
        (motion / 'displacement.tif').write_bytes(b'fixture displacement')
        (motion / 'manifest.json').write_text(json.dumps({'assets': {'displacementMm': {'path': 'displacement.tif'}}}))
        digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
        metadata = {'area': 'camanava_2026', 'maskSha256': digest(path), 'dataKind': 'synthetic', 'source': {
            'rhythmMaskSha256': digest(folder / 'rhythm_half.tif'),
            'rhythmManifestSha256': digest(folder / 'manifest.json'), 'motionRunId': 'fixture',
            'motionManifestSha256': digest(motion / 'manifest.json'),
            'motionDisplacementSha256': digest(motion / 'displacement.tif')}}
        (folder / 'priority_manifest.json').write_text(json.dumps(metadata))
        client = self.client()
        body = client.get('/api/v1/spot-check?lon=120.957&lat=14.665').json()
        self.assertTrue(body['streams']['priority']['value'])
        self.assertEqual(body['dataKind'], 'synthetic')
        nodata = client.get('/api/v1/spot-check?lon=120.965&lat=14.665').json()
        self.assertIsNone(nodata['streams']['priority']['value'])
        metadata['maskSha256'] = 'bad'
        (folder / 'priority_manifest.json').write_text(json.dumps(metadata))
        self.assertIsNone(client.get('/api/v1/spot-check?lon=120.957&lat=14.665').json()['streams']['priority']['value'])

    def test_real_processing_with_synthetic_product(self):
        try:
            from nisar_fixtures import build_product
        except ImportError:
            from tests.nisar_fixtures import build_product
        root, _, _ = build_product(self.tmp.name)
        app = FastAPI()
        app.include_router(make_router(root, lambda: [{'id': 'camanava_2026'}]))
        client = TestClient(app)
        response = client.get('/api/v1/spot-check?lon=120.945&lat=14.70')
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['dataKind'], 'synthetic')
        self.assertEqual(len(body['streams']['nisar']['value']['perPass']), 4)
        self.assertEqual(len(body['streams']['rainfall']['value']), 4)


if __name__ == '__main__':
    unittest.main()
