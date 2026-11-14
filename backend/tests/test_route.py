"""Routing: shortest vs hazard-aware route, API errors, one-way roads."""
import json
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from shapely.geometry import box, mapping

from app.route_api import make_router, _CACHE
from processing import routing

EVENT = 'ev'
N = 7
LON0, LAT0, STEP = 120.0, 14.0, 0.01


def grid_features():
    feats = []

    def seg(a, b):
        for p, q in ((a, b), (b, a)):  # two-way: one edge per direction, like the osmnx export
            feats.append({'type': 'Feature', 'properties': {},
                          'geometry': {'type': 'LineString', 'coordinates': [list(p), list(q)]}})
    pt = lambda r, c: (LON0 + c * STEP, LAT0 + r * STEP)
    for r in range(N):
        for c in range(N):
            if c + 1 < N:
                seg(pt(r, c), pt(r, c + 1))
            if r + 1 < N:
                seg(pt(r, c), pt(r + 1, c))
    return feats


def fc(geoms):
    return {'type': 'FeatureCollection',
            'features': [{'type': 'Feature', 'properties': {}, 'geometry': mapping(g)} for g in geoms]}


class RouteApiTests(unittest.TestCase):
    def setUp(self):
        _CACHE.clear()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / EVENT).mkdir()
        self.events = [{'id': EVENT, 'before_date': '2022-09-19', 'after_date': '2022-10-01'}]
        app = FastAPI()
        app.include_router(make_router(self.root, lambda: self.events))
        self.client = TestClient(app)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, roads=True, flood=None):
        d = self.root / EVENT
        if roads:
            (d / 'roads.geojson').write_text(json.dumps({'type': 'FeatureCollection', 'features': grid_features()}))
        if flood is not None:
            (d / 'flood.geojson').write_text(json.dumps(fc(flood)))

    def get(self, a, b, **kw):
        params = {'event': EVENT, 'fromLon': a[0], 'fromLat': a[1], 'toLon': b[0], 'toLat': b[1], **kw}
        return self.client.get('/api/v1/route', params=params)

    # a block of flood in the middle of the grid: rows 2..4, columns 2..4
    MIDDLE = box(LON0 + 1.5 * STEP, LAT0 + 1.5 * STEP, LON0 + 4.5 * STEP, LAT0 + 4.5 * STEP)

    def test_detour_avoids_flood(self):
        self.write(flood=[self.MIDDLE])
        r = self.get((LON0, LAT0 + 3 * STEP), (LON0 + 6 * STEP, LAT0 + 3 * STEP))
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body['relation'], 'detour')
        self.assertGreater(body['shortest']['hazard']['floodKm'], 0)
        self.assertEqual(body['safe']['hazard']['floodKm'], 0)
        self.assertGreater(body['detourKm'], 0)
        self.assertEqual(body['dataKind'], 'derived')
        self.assertEqual(body['hazardSources'][0]['dates']['after'], '2022-10-01')
        self.assertIn('Hazard-aware does not mean guaranteed safe', body['briefing']['text'])
        self.assertTrue(any('coherence-change' in t for t in body['limitations']))

    def test_identical_when_shortest_already_clear(self):
        self.write(flood=[self.MIDDLE])
        r = self.get((LON0, LAT0), (LON0 + 6 * STEP, LAT0))
        self.assertEqual(r.json()['relation'], 'identical')

    def test_no_safe_route_when_flood_cuts_the_map(self):
        wall = box(LON0 + 2.5 * STEP, LAT0 - 1, LON0 + 3.5 * STEP, LAT0 + 1)
        self.write(flood=[wall])
        r = self.get((LON0, LAT0 + 3 * STEP), (LON0 + 6 * STEP, LAT0 + 3 * STEP))
        body = r.json()
        self.assertEqual(body['relation'], 'no_safe_route')
        self.assertIsNone(body['safe'])
        self.assertIn('as safe', body['briefing']['text'])

    def test_errors(self):
        self.write(roads=False, flood=[self.MIDDLE])
        self.assertEqual(self.get((LON0, LAT0), (LON0 + STEP, LAT0)).json()['detail']['code'], 'roads_unavailable')
        self.write(flood=[self.MIDDLE])
        r = self.get((LON0, LAT0), (LON0 + STEP, LAT0), vehicle='walking')
        self.assertEqual((r.status_code, r.json()['detail']['code']), (422, 'unsupported_vehicle'))
        r = self.get((LON0 + 5, LAT0), (LON0 + STEP, LAT0))
        self.assertEqual((r.status_code, r.json()['detail']['code']), (422, 'point_outside_roads'))
        r = self.client.get('/api/v1/route', params={'event': 'nope', 'fromLon': 0, 'fromLat': 0, 'toLon': 0, 'toLat': 0})
        self.assertEqual(r.json()['detail']['code'], 'unknown_event')

    def test_missing_flood_is_data_unavailable(self):
        self.write(flood=None)
        r = self.get((LON0, LAT0), (LON0 + STEP, LAT0))
        self.assertEqual((r.status_code, r.json()['detail']['code']), (404, 'data_unavailable'))


class RoutingUnitTests(unittest.TestCase):
    def test_one_way_is_respected(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / 'roads.geojson'
            p.write_text(json.dumps({'type': 'FeatureCollection', 'features': [
                {'type': 'Feature', 'properties': {}, 'geometry': {'type': 'LineString', 'coordinates': [[0, 0], [0.01, 0]]}},
                {'type': 'Feature', 'properties': {}, 'geometry': {'type': 'LineString', 'coordinates': [[0.01, 0], [0.02, 0]]}},
                {'type': 'Feature', 'properties': {}, 'geometry': {'type': 'LineString', 'coordinates': [[0.02, 0], [0.02, 0.0001]]}},
                {'type': 'Feature', 'properties': {}, 'geometry': {'type': 'LineString', 'coordinates': [[0.02, 0.0001], [0.02, 0.0002]]}},
            ]}))
            g = routing.load_graph(p)
            routing.classify(g, None, None)
            self.assertEqual(routing.route(g, (0, 0), (0.02, 0.0001))['relation'], 'identical')
            with self.assertRaises(routing.RoutingError) as cm:
                routing.route(g, (0.02, 0.0001), (0, 0))
            self.assertIn(cm.exception.code, ('no_route', 'point_outside_roads'))

    def test_change_area_is_penalised_not_blocked(self):
        # two ways from A to B: short through a change area, longer clear detour; penalty x3 picks the detour
        feats = []

        def seg(a, b):
            feats.append({'type': 'Feature', 'properties': {}, 'geometry': {'type': 'LineString', 'coordinates': [a, b]}})
        A, B, M, D = [0, 0], [0.04, 0], [0.02, 0], [0.02, 0.012]
        seg(A, M); seg(M, B); seg(A, D); seg(D, B)
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / 'r.geojson'
            p.write_text(json.dumps({'type': 'FeatureCollection', 'features': feats}))
            g = routing.load_graph(p)
            routing.classify(g, None, box(0.005, -0.001, 0.035, 0.001))
            r = routing.route(g, tuple(A), tuple(B))
            self.assertGreater(r['shortest']['hazard']['changeKm'], 0)
            self.assertEqual(r['safe']['hazard']['changeKm'], 0)
            self.assertEqual(r['relation'], 'detour')


if __name__ == '__main__':
    unittest.main()
