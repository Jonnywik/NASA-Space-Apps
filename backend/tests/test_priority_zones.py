import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import rasterio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from rasterio.transform import from_origin
from rasterio.warp import transform_bounds

from app.places_api import make_router
from processing.p3 import core
from processing.priority.zones import build_priority
from test_places_support import make_places_root, write_raster, GRID_TF, W, N, STEP


class PriorityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.out = self.base / 'output'
        self.places = make_places_root(self.base / 'places')
        self.nisar = self.out / 'camanava_2026' / 'nisar'
        self.nisar.mkdir(parents=True)
        self.rhythm = np.array([[1, 1, 1, 1], [0, 1, 255, 1], [1, 1, 1, 1], [1, 1, 1, 1]], dtype='uint8')
        write_raster(self.nisar / 'rhythm_half.tif', self.rhythm)
        (self.nisar / 'manifest.json').write_text(json.dumps({'dataKind': 'synthetic', 'passCount': 4}))
        self.motion = np.array([[-1, 1, 2, 4], [10, 3, 9, np.nan], [0, -3, 1.5, 5], [0, 0, 0, 0]], dtype='float32')
        pair_dir = self.out / 'camanava_2026' / 'p3' / 'los-pair' / 'pair1'
        pair_dir.mkdir(parents=True)
        geometry = {'type': 'Polygon', 'coordinates': [[[W, N], [W + 2 * STEP, N],
                     [W + 2 * STEP, N - STEP], [W, N - STEP], [W, N]]]}
        pair = {'referenceRegion': {'geometry': geometry, 'hash': 'ref-hash'}}
        pair_path = pair_dir / 'manifest.json'
        pair_path.write_text(json.dumps(pair))
        metadata = {'dataKind': 'synthetic', 'sourceRunIds': ['pair1'],
                    'sourceManifestHashes': {'pair1': core.digest(pair_path)}, 'spatialReferenceHash': 'ref-hash',
                    'displacementConvention': 'positive_away_from_satellite', 'units': {'displacementMm': 'mm'}}

        def writer(stage):
            write_raster(stage / 'displacement.tif', self.motion, nodata=np.nan)
            return {'displacementMm': 'displacement.tif'}

        self.motion_path = core.publish('camanava_2026', 'ground-motion', metadata, writer, output_root=self.out, review=True)
        self.run_id = self.motion_path.parent.name

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, **kwargs):
        return build_priority(self.out, places_root=self.places, **kwargs)

    def test_and_nodata_noise_threshold_sensitivity_and_exposure(self):
        result = self.build()
        self.assertEqual(result['dataKind'], 'synthetic')
        self.assertEqual(result['threshold']['valueMm'], 2.0)  # std([-1, 1]) == 1
        self.assertEqual(result['threshold']['referencePixelCount'], 2)
        with rasterio.open(self.nisar / 'priority_mask.tif') as ds:
            expected = np.array([[0, 0, 0, 1], [0, 1, 255, 255], [0, 0, 0, 1], [0, 0, 0, 0]], dtype='uint8')
            np.testing.assert_array_equal(ds.read(1), expected)
            self.assertEqual(ds.transform, GRID_TF)
            self.assertEqual(ds.nodata, 255)
        self.assertEqual(result['exposure']['totals']['population'], 40 + 60 + 120)
        sensitivity = result['sensitivity']
        self.assertEqual([sensitivity[k]['thresholdMm'] for k in ('half', 'base', 'double')], [1, 2, 4])
        self.assertEqual([sensitivity[k]['totals']['population'] for k in ('half', 'base', 'double')], [360, 220, 120])
        self.assertEqual(result['maskSha256'], core.digest(self.nisar / 'priority_mask.tif'))

    def test_explicit_threshold_reprojects_fine_categorical_mask_to_motion_grid(self):
        fine = np.repeat(np.repeat(self.rhythm, 2, axis=0), 2, axis=1)
        write_raster(self.nisar / 'rhythm_half.tif', fine, transform=from_origin(W, N, STEP / 2, STEP / 2))
        result = self.build(threshold_mm=2)
        self.assertEqual(result['threshold'], {'valueMm': 2.0, 'method': 'explicit'})
        with rasterio.open(self.nisar / 'priority_mask.tif') as ds:
            self.assertEqual((ds.width, ds.height), (4, 4))
            np.testing.assert_array_equal(ds.read(1)[0], [0, 0, 0, 1])
            self.assertEqual(ds.read(1)[1, 2], 255)

    def test_synthetic_motion_propagates_over_observed_rhythm_and_api(self):
        (self.nisar / 'manifest.json').write_text(json.dumps({'dataKind': 'observed', 'passCount': 4}))
        self.assertEqual(self.build(threshold_mm=2)['dataKind'], 'synthetic')
        app = FastAPI()
        app.include_router(make_router(self.out, lambda: [], places_root=self.places))
        response = TestClient(app).get('/api/v1/places/exposure?mask=priority')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['dataKind'], 'synthetic')

    def test_flood_synthetic_and_both_derived_provenance(self):
        motion = core.load_manifest(self.motion_path)
        motion['dataKind'] = 'derived'
        with patch('processing.priority.zones.catalog.select', return_value=motion):
            self.assertEqual(self.build(threshold_mm=2)['dataKind'], 'synthetic')
            (self.nisar / 'manifest.json').write_text(json.dumps({'dataKind': 'observed', 'passCount': 4}))
            self.assertEqual(self.build(threshold_mm=2)['dataKind'], 'derived')

    def test_api_rejects_missing_invalid_or_tampered_priority_manifest(self):
        self.build(threshold_mm=2)
        manifest_path = self.nisar / 'priority_manifest.json'
        original = manifest_path.read_text()
        app = FastAPI()
        app.include_router(make_router(self.out, lambda: [], places_root=self.places))
        client = TestClient(app)

        def unavailable():
            response = client.get('/api/v1/places/exposure?mask=priority')
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.json()['detail']['code'], 'data_unavailable')

        manifest_path.unlink()
        unavailable()
        manifest_path.write_text('{invalid')
        unavailable()
        bad = json.loads(original)
        bad['dataKind'] = 'unknown'
        manifest_path.write_text(json.dumps(bad))
        unavailable()
        manifest_path.write_text(original)
        with (self.nisar / 'priority_mask.tif').open('ab') as mask:
            mask.write(b'tampered')
        unavailable()

    def test_unverified_reference_cannot_derive_noise(self):
        path = self.out / 'camanava_2026' / 'p3' / 'los-pair' / 'pair1' / 'manifest.json'
        path.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'Cannot verify upstream LOS pair'):
            self.build()
        self.assertFalse((self.nisar / 'priority_mask.tif').exists())

    def test_rhythm_reprojects_from_another_crs(self):
        west, south, east, north = transform_bounds('EPSG:4326', 'EPSG:3857', W, N - 4 * STEP, W + 4 * STEP, N)
        with rasterio.open(self.nisar / 'rhythm_half.tif', 'w', driver='GTiff', height=8, width=8,
                           count=1, dtype='uint8', crs='EPSG:3857',
                           transform=from_origin(west, north, (east - west) / 8, (north - south) / 8), nodata=255) as dst:
            dst.write(np.ones((8, 8), dtype='uint8'), 1)
        self.build(threshold_mm=2)
        with rasterio.open(self.nisar / 'priority_mask.tif') as ds:
            self.assertEqual(ds.crs.to_epsg(), 4326)
            np.testing.assert_array_equal(ds.read(1)[0], [0, 0, 0, 1])
            self.assertEqual(ds.read(1)[1, 0], 1)

    def test_coarser_rhythm_cannot_be_upsampled(self):
        write_raster(self.nisar / 'rhythm_half.tif', np.ones((2, 2), dtype='uint8'),
                     transform=from_origin(W, N, STEP * 2, STEP * 2))
        with self.assertRaisesRegex(ValueError, 'Rhythm grid is coarser'):
            self.build(threshold_mm=2)
        self.assertFalse((self.nisar / 'priority_mask.tif').exists())

    def test_registered_rhythm_hash_is_verified(self):
        manifest_path = self.nisar / 'manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['assets'] = {'rhythm_half_tif': {'path': 'rhythm_half.tif', 'sha256': core.digest(self.nisar / 'rhythm_half.tif')}}
        manifest_path.write_text(json.dumps(manifest))
        self.build(threshold_mm=2)
        with (self.nisar / 'rhythm_half.tif').open('ab') as mask:
            mask.write(b'tampered')
        with self.assertRaisesRegex(ValueError, 'SHA-256 check'):
            self.build(threshold_mm=2)

    def test_script_runs_on_synthetic_fixture(self):
        script = Path(__file__).resolve().parents[1] / 'scripts' / '50_priority_zones.py'
        run = subprocess.run([sys.executable, str(script), '--output-root', str(self.out), '--threshold-mm', '2'],
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        result = json.loads((self.nisar / 'priority_manifest.json').read_text())
        self.assertEqual(result['dataKind'], 'synthetic')
        self.assertEqual(result['source']['motionRunId'], self.run_id)

    def test_api_rejects_changed_priority_inputs(self):
        self.build(threshold_mm=2)
        app = FastAPI()
        app.include_router(make_router(self.out, lambda: [], places_root=self.places))
        client = TestClient(app)
        self.assertEqual(client.get('/api/v1/places/exposure?mask=priority').status_code, 200)
        for path in (self.nisar / 'rhythm_half.tif', self.nisar / 'manifest.json', self.motion_path):
            original = path.read_bytes()
            try:
                path.write_bytes(original + b' ')
                response = client.get('/api/v1/places/exposure?mask=priority')
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json()['detail']['code'], 'data_unavailable')
            finally:
                path.write_bytes(original)

    def test_missing_motion_and_invalid_threshold_do_not_publish(self):
        (self.motion_path.parent.parent / 'current.json').unlink()
        with self.assertRaisesRegex(ValueError, 'Ground-motion product unavailable'):
            self.build()
        with self.assertRaisesRegex(ValueError, 'finite non-negative'):
            self.build(run_id=self.run_id, threshold_mm=-1)
        self.assertFalse((self.nisar / 'priority_mask.tif').exists())

    def test_script_fails_clearly_without_motion(self):
        (self.motion_path.parent.parent / 'current.json').unlink()
        script = Path(__file__).resolve().parents[1] / 'scripts' / '50_priority_zones.py'
        run = subprocess.run([sys.executable, str(script), '--output-root', str(self.out)], capture_output=True, text=True)
        self.assertEqual(run.returncode, 2)
        self.assertIn('Ground-motion product unavailable', run.stderr)


if __name__ == '__main__':
    unittest.main()
