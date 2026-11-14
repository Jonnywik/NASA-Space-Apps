import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.places_api import make_router
from test_places_support import make_places_root, write_raster, W, N, MID_LAT, MID_LON


def code(r):
    return r.json()['detail']['code']


class PlacesApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.places = make_places_root(base / 'places')
        self.out = base / 'output'
        app = FastAPI()
        app.include_router(make_router(self.out, lambda: [], places_root=self.places))
        self.c = TestClient(app)

    def tearDown(self):
        self.tmp.cleanup()

    def nisar(self, kind='derived'):
        d = self.out / 'camanava_2026' / 'nisar'
        d.mkdir(parents=True)
        counts = np.array([[0, 1, 2, 3], [4, 4, 255, 2], [0, 0, 0, 0], [0, 0, 0, 4]], 'uint8')
        write_raster(d / 'rhythm.tif', counts, nodata=255)
        (d / 'manifest.json').write_text(json.dumps({'passCount': 4, 'dataKind': kind}))

    def test_search(self):
        r = self.c.get('/api/v1/places/search', params={'q': 'brgy nino'})
        self.assertEqual(r.status_code, 200)
        b = r.json()
        self.assertEqual(b['results'][0]['id'], 'T1-1')
        for k in ('dataKind', 'source', 'retrievedAt', 'warnings', 'limitations'):
            self.assertIn(k, b)
        self.assertEqual(self.c.get('/api/v1/places/search').status_code, 422)
        self.assertEqual(code(self.c.get('/api/v1/places/search?q=x&limit=0')), 'invalid_request')
        self.assertEqual(code(self.c.get('/api/v1/places/search?q=x&limit=abc')), 'invalid_request')

    def test_boundaries(self):
        r = self.c.get('/api/v1/places/boundaries?level=city')
        self.assertEqual(r.status_code, 200)
        b = r.json()
        self.assertEqual(b['type'], 'FeatureCollection')
        self.assertEqual(len(b['features']), 2)
        self.assertIn('source', b)
        self.assertEqual(len(self.c.get('/api/v1/places/boundaries').json()['features']), 4)
        self.assertEqual(code(self.c.get('/api/v1/places/boundaries?level=street')), 'invalid_request')

    def test_locate(self):
        r = self.c.get('/api/v1/places/locate', params={'lon': W + 0.001, 'lat': N - 0.001})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['barangay']['id'], 'T1-1')
        self.assertEqual(r.json()['city']['id'], 'T1')
        self.assertEqual(code(self.c.get('/api/v1/places/locate?lon=100&lat=10')), 'outside_coverage')
        self.assertEqual(code(self.c.get('/api/v1/places/locate?lon=abc&lat=10')), 'invalid_request')
        self.assertEqual(code(self.c.get('/api/v1/places/locate')), 'invalid_request')
        # inside the study bbox but in no polygon: 200 with nulls and a warning
        r = self.c.get('/api/v1/places/locate', params={'lon': 120.9, 'lat': 14.62})
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.json()['barangay'])
        self.assertTrue(r.json()['warnings'])

    def test_exposure_unavailable_until_rhythm_exists(self):
        r = self.c.get('/api/v1/places/exposure?area=camanava_2026&mask=rhythm_half')
        self.assertEqual((r.status_code, code(r)), (404, 'data_unavailable'))
        self.assertEqual(self.c.get('/api/v1/places/exposure?mask=priority').status_code, 404)

    def test_exposure_errors(self):
        self.assertEqual((self.c.get('/api/v1/places/exposure?area=nowhere').status_code), 404)
        self.assertEqual(code(self.c.get('/api/v1/places/exposure?area=nowhere')), 'unknown_area')
        self.assertEqual(code(self.c.get('/api/v1/places/exposure?mask=bogus')), 'invalid_request')
        self.assertEqual(code(self.c.get('/api/v1/places/exposure?level=bogus')), 'invalid_request')

    def test_exposure_rhythm_half(self):
        self.nisar()
        r = self.c.get('/api/v1/places/exposure?area=camanava_2026&mask=rhythm_half')
        self.assertEqual(r.status_code, 200)
        b = r.json()
        self.assertEqual(b['dataKind'], 'derived')
        # need >= 2 of 4 passes: cells (0,2)=2,(0,3)=3,(1,0)=4,(1,1)=4,(1,3)=2,(3,3)=4; (1,2) is nodata
        # pops: 30,40,50,60,80,160 (ids T1-1 for cols 0-1 north, T2-1 for cols 2-3 north, T2-2 south)
        z = {x['placeId']: x for x in b['zones']}
        self.assertEqual(z['T1-1']['population'], 50 + 60)
        self.assertEqual(z['T2-1']['population'], 30 + 40 + 80)
        self.assertEqual(z['T2-2']['population'], 160)
        self.assertEqual(b['totals']['population'], 420)
        self.assertEqual(b['totals']['buildings'], 0 + 0 + 0)
        for k in ('populationSource', 'buildingSource', 'limitations', 'source', 'totals', 'zones'):
            self.assertIn(k, b)
        self.assertEqual(b['buildingSource']['completeness'], 'unknown')
        self.assertIn('exposure, not damage', b['limitations'])

    def test_exposure_propagates_synthetic(self):
        self.nisar('synthetic')
        r = self.c.get('/api/v1/places/exposure')
        self.assertEqual(r.json()['dataKind'], 'synthetic')

    def test_exposure_city_level(self):
        self.nisar()
        r = self.c.get('/api/v1/places/exposure?level=city')
        self.assertEqual({z['placeId'] for z in r.json()['zones']}, {'T1', 'T2'})

    def test_missing_cache_is_data_unavailable(self):
        app = FastAPI()
        empty = Path(self.tmp.name) / 'empty'
        empty.mkdir()
        app.include_router(make_router(self.out, lambda: [], places_root=empty))
        c = TestClient(app)
        self.assertEqual(code(c.get('/api/v1/places/search?q=a')), 'data_unavailable')
        self.assertEqual(code(c.get('/api/v1/places/boundaries')), 'data_unavailable')


if __name__ == '__main__':
    unittest.main()
