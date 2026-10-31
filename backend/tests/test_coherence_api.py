"""Read-only coherence routes expose only hash-checked catalog publications."""
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.coherence_api import make_router
from app.p3_api import make_router as make_product_router
from processing.p3.core import digest, publish
from coherence_fixtures import EVENT_ID, write_geotiff


class CoherenceApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.events = [{'id': EVENT_ID}]
        app = FastAPI()
        read_events = lambda: self.events
        app.include_router(make_router(self.root, read_events))
        app.include_router(make_product_router(self.root, read_events))
        self.client = TestClient(app)

    def tearDown(self):
        self.tmp.cleanup()

    def change(self, *, kind='synthetic', regional_metrics=None):
        metadata = {
            'dataKind': kind,
            'prePair': ['2024-01-01', '2024-01-05'],
            'coPair': ['2024-01-05', '2024-01-15'],
            'parameters': {'preMin': 0.5, 'lossMin': 0.2, 'minPixels': 1},
            'stats': {'km2Changed': 0.0, 'changedPixelCount': 0},
            'coverage': {'commonValidPixelCount': 0, 'eligiblePixelCount': 0},
            'basis': {'sensor': 'fixture', 'polarization': 'VV'},
        }
        if regional_metrics is not None:
            metadata['regionalMetrics'] = regional_metrics

        def writer(stage):
            write_geotiff(stage / 'change_mask.tif', np.zeros((2, 2), dtype=np.uint8), nodata=255)
            (stage / 'change.geojson').write_text(json.dumps({
                'type': 'FeatureCollection', 'features': [],
            }))
            return {'changeMask': 'change_mask.tif', 'changeGeometry': 'change.geojson'}

        return publish(EVENT_ID, 'coherence-change', metadata, writer, self.root, review=kind == 'synthetic')

    def frequency(self):
        def writer(stage):
            for filename in ('frequency.tif', 'detection_count.tif', 'valid_count.tif'):
                write_geotiff(stage / filename, np.zeros((2, 2), dtype=np.float32), nodata=np.nan)
            return {
                'frequency': 'frequency.tif',
                'detectionCount': 'detection_count.tif',
                'validComparisonCount': 'valid_count.tif',
            }

        return publish(EVENT_ID, 'change-frequency', {
            'dataKind': 'synthetic',
            'stats': {'comparisonCount': 0},
            'coverage': {'validPixelCount': 0},
            'basis': {'sensor': 'fixture', 'polarization': 'VV'},
        }, writer, self.root, review=True)

    def exposure(self, hazard_run_id, *, hazard_product='coherence-change', hazard_event=EVENT_ID):
        report = {
            'event': EVENT_ID,
            'product': 'building-exposure',
            'hazardEvent': hazard_event,
            'hazardProduct': hazard_product,
            'hazardRunId': hazard_run_id,
            'snapshotDate': '2026-01-01',
            'snapshotCoverage': {'completeness': 'partial'},
            'scope': 'whole-event',
            'threshold': {'kind': 'frequency', 'minimumFrequency': 0.5},
            'regions': [{'regionId': 'north', 'countStatus': 'partial',
                         'mappedHazardOverlapCount': None, 'partialMappedHazardOverlapCount': 0}],
            'combined': {'countStatus': 'partial', 'mappedHazardOverlapCount': None,
                         'partialMappedHazardOverlapCount': 0},
        }

        def writer(stage):
            (stage / 'exposure.json').write_text(json.dumps(report))
            return {'exposure': 'exposure.json'}

        return publish(EVENT_ID, 'building-exposure', {
            'dataKind': 'synthetic',
            'hazardEvent': hazard_event,
            'hazardProduct': hazard_product,
            'hazardRunId': hazard_run_id,
        }, writer, self.root, review=True)

    def test_ready_empty_change_returns_zero_stats_geojson_and_asset_urls(self):
        manifest_path = self.change()
        response = self.client.get('/api/v1/coherence-loss', params={'event': EVENT_ID})
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body['dataStatus'], 'synthetic')
        self.assertEqual(body['stats']['changedPixelCount'], 0)
        self.assertEqual(body['changeGeojson'], {'type': 'FeatureCollection', 'features': []})
        self.assertEqual(body['assets']['changeMask']['sha256'], digest(
            manifest_path.parent / 'change_mask.tif',
        ))
        self.assertIn('/coherence-change/', body['assets']['changeGeometry']['url'])
        self.assertEqual(body['runId'], manifest_path.parent.name)

    def test_frequency_returns_registered_count_and_frequency_assets(self):
        manifest_path = self.frequency()
        response = self.client.get('/api/v1/coherence-loss', params={
            'event': EVENT_ID, 'product': 'frequency',
        })
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body['product'], 'change-frequency')
        self.assertEqual(body['productView'], 'frequency')
        self.assertEqual(body['runId'], manifest_path.parent.name)
        self.assertEqual(set(body['assets']), {'frequency', 'detectionCount', 'validComparisonCount'})
        self.assertIn('/change-frequency/', body['assets']['validComparisonCount']['url'])

    def test_missing_exposure_is_partial_and_does_not_hide_hazard(self):
        self.change()
        response = self.client.get('/api/v1/coherence-loss', params={'event': EVENT_ID})
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body['exposure'], {'available': False, 'reason': 'data_unavailable'})
        self.assertEqual(body['product'], 'coherence-change')

    def test_matching_exposure_summary_and_explicit_stale_exposure(self):
        hazard_path = self.change()
        hazard_run = hazard_path.parent.name
        exposure_path = self.exposure(hazard_run)
        good = self.client.get('/api/v1/coherence-loss', params={
            'event': EVENT_ID, 'exposureRunId': exposure_path.parent.name,
        })
        self.assertEqual(good.status_code, 200, good.text)
        self.assertTrue(good.json()['exposure']['available'])
        self.assertEqual(good.json()['exposure']['threshold']['minimumFrequency'], 0.5)
        self.assertEqual(good.json()['exposure']['summary']['countStatus'], 'partial')
        self.assertIsNone(good.json()['exposure']['summary']['mappedHazardOverlapCount'])

        stale_path = self.exposure('older-hazard-run')
        stale = self.client.get('/api/v1/coherence-loss', params={
            'event': EVENT_ID, 'exposureRunId': stale_path.parent.name,
        })
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(stale.json()['detail']['code'], 'stale_exposure')

    def test_registered_region_only_and_invalid_product_parameters(self):
        self.change(regional_metrics=[{'regionId': 'north', 'changedPixelCount': 0}])
        good = self.client.get('/api/v1/coherence-loss', params={'event': EVENT_ID, 'regionId': 'north'})
        self.assertEqual(good.status_code, 200, good.text)
        self.assertEqual(good.json()['selectedRegion']['regionId'], 'north')
        unknown_region = self.client.get('/api/v1/coherence-loss', params={
            'event': EVENT_ID, 'regionId': 'arbitrary-aoi',
        })
        self.assertEqual(unknown_region.status_code, 422)
        self.assertEqual(unknown_region.json()['detail']['code'], 'region_unavailable')
        invalid_product = self.client.get('/api/v1/coherence-loss', params={
            'event': EVENT_ID, 'product': 'something-else',
        })
        self.assertEqual(invalid_product.status_code, 422)
        self.assertEqual(invalid_product.json()['detail']['code'], 'unsupported_product')
        invalid_run = self.client.get('/api/v1/coherence-loss', params={
            'event': EVENT_ID, 'runId': '../bad',
        })
        self.assertEqual(invalid_run.status_code, 422)

    def test_hash_checked_geometry_asset_route_and_traversal_are_rejected(self):
        manifest_path = self.change()
        response = self.client.get('/api/v1/coherence-loss', params={'event': EVENT_ID})
        self.assertEqual(response.status_code, 200, response.text)
        geometry_url = response.json()['assets']['changeGeometry']['url']
        self.assertEqual(self.client.get(geometry_url).json()['features'], [])

        (manifest_path.parent / 'change.geojson').write_text('{}')
        tampered = self.client.get('/api/v1/coherence-loss', params={'event': EVENT_ID})
        self.assertEqual(tampered.status_code, 409)
        self.assertEqual(tampered.json()['detail']['code'], 'invalid_product')

        manifest = json.loads(manifest_path.read_text())
        manifest['assets']['changeGeometry']['path'] = '../../../outside.geojson'
        manifest_path.write_text(json.dumps(manifest))
        escaped = self.client.get('/api/v1/coherence-loss', params={'event': EVENT_ID})
        self.assertEqual(escaped.status_code, 409)
        self.assertEqual(escaped.json()['detail']['code'], 'invalid_product')

    def test_review_required_and_unknown_event(self):
        manifest_path = self.change(kind='derived')
        review_required = self.client.get('/api/v1/coherence-loss', params={
            'event': EVENT_ID, 'runId': manifest_path.parent.name,
        })
        self.assertEqual(review_required.status_code, 409)
        self.assertEqual(review_required.json()['detail']['code'], 'review_required')
        unknown_event = self.client.get('/api/v1/coherence-loss', params={'event': 'unknown'})
        self.assertEqual(unknown_event.status_code, 404)
        self.assertEqual(unknown_event.json()['detail']['code'], 'unknown_event')


if __name__ == '__main__':
    unittest.main()
