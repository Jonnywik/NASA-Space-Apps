"""Independent integration fixture: HDF5 pairs recover a known spatial rate."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
import h5py
import numpy as np
from pyproj import Transformer
from fastapi import FastAPI
from fastapi.testclient import TestClient
from processing.p3 import core
from processing.p3.ingestion import ingest
from processing.p3.phase import convert
from processing.p3.series import build_series, solve_network
from processing.p3.briefing import build_briefing
from processing.p3.terrain import prepare_inputs
from processing.p3.projection import project
from app.p3_api import make_router

class PipelineTests(unittest.TestCase):
    def test_tiled_network_matches_across_tile_sizes(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        dates = [(start + timedelta(days=30*n)).isoformat() for n in range(6)]
        pairs = list(zip(dates[:-1], dates[1:])) + [(dates[0], dates[-1])]
        rate = np.arange(64*64, dtype=float).reshape(64, 64) / 100
        differences = np.stack([rate * (150 if i == 5 else 30) / 365.2425 for i in range(6)])
        differences[1, ::4, ::3] = np.nan
        small = solve_network(pairs, differences, tile_shape=(8, 8))
        large = solve_network(pairs, differences, tile_shape=(32, 32))
        np.testing.assert_allclose(small['displacementMm'], large['displacementMm'], equal_nan=True)
        np.testing.assert_allclose(small['rateMmPerYear'], rate, atol=1e-4)

    def test_hdf5_to_point_api_and_briefing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outputs = root / 'outputs'
            grid = {'crs': 'EPSG:32651', 'width': 6, 'height': 6, 'transform': [20, 0, 500000, 0, -20, 1600000]}
            reference = np.zeros((6, 6))
            reference[:, 0] = 1
            core.write_raster(root / 'reference.tif', reference, grid)
            phase_config = root / 'phase.json'
            phase_config.write_text(json.dumps({'reference': {'maskRaster': 'reference.tif'}}))
            start = datetime(2026, 1, 1, tzinfo=timezone.utc)
            dates = [(start + timedelta(days=30*n)).isoformat().replace('+00:00', 'Z') for n in range(6)]
            pairs = []
            for i in range(5):
                mm = np.full((6, 6), 12 * 30 / 365.2425)
                mm[:, 0] = 0
                source = root / f'pair-{i}.h5'
                with h5py.File(source, 'w') as f:
                    f['/grid/x'] = 500010 + 20*np.arange(6)
                    f['/grid/y'] = 1599990 - 20*np.arange(6)
                    for name, values, unit in [('phase', mm/1000*4*np.pi/.24, 'radian'),
                                              ('coherence', np.ones((6, 6))*.9, '1'),
                                              ('components', np.ones((6, 6)), 'label')]:
                        d = f.create_dataset('/science/'+name, data=values)
                        d.attrs['units'] = unit
                config = {'event': 'pilot', 'productType': 'GUNW', 'dataKind': 'synthetic',
                          'source': {'path': source.name, 'sha256': core.digest(source), 'productId': f'fixture-{i}',
                                     'sensor': 'NISAR', 'frequency': 'L', 'polarization': 'HH', 'orbit': 'ascending-001',
                                     'frame': 'frame-1', 'processingVersion': 'fixture-1', 'maturity': 'synthetic-fixture',
                                     'acquisitionDates': dates[i:i+2], 'quality': {}, 'wavelengthMetres': .24,
                                     'wavelengthUnits': 'metre', 'phaseToAwaySign': 1, 'phaseUnits': 'radian', 'correctionsApplied': []},
                          'sourceProfile': {'id': 'synthetic-h5-v1', 'version': '1', 'adapter': 'hdf5',
                                            'status': 'needs-review', 'evidence': [], 'arrayAxisOrder': 'yx',
                                            'crs': grid['crs'], 'coordinateDatasets': {'x': '/grid/x', 'y': '/grid/y'},
                                            'datasets': {name: {'path': '/science/'+name, 'units': unit}
                                                         for name, unit in [('phase', 'radian'), ('coherence', '1'), ('components', 'label')]}}}
                source_config = root / f'input-{i}.json'
                source_config.write_text(json.dumps(config))
                normalized = ingest('pilot', source_config, output_root=outputs)
                pairs.append(convert('pilot', normalized, phase_config, output_root=outputs))
            series_path = build_series('pilot', pairs, output_root=outputs)
            manifest = core.load_manifest(series_path)
            rate, _ = core.read_raster(manifest, 'rateMmPerYear')
            np.testing.assert_allclose(rate[:, 1:], 12, atol=1e-5)
            np.testing.assert_allclose(rate[:, 0], 0, atol=1e-5)
            self.assertEqual(manifest['dataKind'], 'synthetic')
            self.assertEqual(len(manifest['sourceRunIds']), 5)
            brief = build_briefing(manifest)
            self.assertEqual(brief, build_briefing(manifest))
            self.assertEqual(brief['dataKind'], 'synthetic')
            app = FastAPI()
            app.include_router(make_router(outputs, lambda: [{'id': 'pilot'}]))
            client = TestClient(app)
            lon, lat = Transformer.from_crs(grid['crs'], 4326, always_xy=True).transform(500030, 1599970)
            response = client.get('/api/v1/ground-motion/point', params={'event': 'pilot', 'runId': manifest['runId'], 'lon': lon, 'lat': lat})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['dataKind'], 'synthetic')
            response = client.get('/api/v1/briefing', params={'event': 'pilot', 'runId': manifest['runId']})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['dataKind'], 'synthetic')
            # Continue the actual published chain through terrain and projections.
            core.write_raster(root / 'elevation.tif', np.zeros((6, 6)), grid)
            terrain_config = {
                'dataKind': 'synthetic', 'verticalDatum': 'FIXTURE_DATUM', 'verticalReferenceEpoch': '2026.0',
                'projectionBaselineEpoch': '2026-01-01', 'targetCrs': grid['crs'],
                'terrain': {'path': 'elevation.tif', 'units': 'm', 'positiveDirection': 'up', 'representation': 'ground',
                            'verticalDatum': 'FIXTURE_DATUM', 'verticalReferenceEpoch': '2026.0',
                            'baselineEpoch': '2026-01-01', 'sourceDate': '2026-01-01'},
                'coastalSeeds': {'path': 'reference.tif', 'trueValues': [1]},
                'waterLevels': [{'year': year, 'scenario': 'central', 'mode': 'total',
                                 'source': {'kind': 'scalar', 'value': .25, 'units': 'm', 'positiveDirection': 'up',
                                            'semantics': 'total_water_level', 'verticalDatum': 'FIXTURE_DATUM',
                                            'verticalReferenceEpoch': '2026.0', 'sourceDate': '2026-01-01',
                                            'provenance': 'Synthetic integration fixture; not a measured water level'}}
                                for year in [2026, 2030]]}
            terrain_config_path = root / 'terrain.json'
            terrain_config_path.write_text(json.dumps(terrain_config))
            terrain_path = prepare_inputs('pilot', terrain_config_path, output_root=outputs)
            review = {'reviewedBy': 'synthetic-fixture', 'evidence': 'Analytic fixture, no real-data assertion'}
            scenario = {'schemaVersion': '1.0', 'dataKind': 'synthetic', 'scenarioId': 'central',
                        'baselineEpoch': '2026-01-01', 'horizon': {'startYear': 2026, 'endYear': 2030},
                        'supportedYears': [2026, 2030], 'review': review,
                        'losProjection': {'enabled': True}, 'waterExposure': {'enabled': True},
                        'allowVerticalOnlyLosInference': True,
                        'verticalMotion': {'mode': 'verticalOnlyLosInference', 'horizontalMotionNegligible': True,
                                           'review': review, 'incidenceAngle': {'kind': 'scalar', 'valueDegrees': 30,
                                           'angleConvention': 'from_vertical', 'sourceId': 'fixture-incidence', 'review': review}}}
            scenario_path = root / 'scenario.json'
            scenario_path.write_text(json.dumps(scenario))
            projection_path = project('pilot', series_path, terrain_path, scenario_path, output_root=outputs)
            projection = core.load_manifest(projection_path)
            self.assertEqual(projection['dataKind'], 'synthetic')
            self.assertIn(manifest['runId'], projection['sourceRunIds'])
            self.assertAlmostEqual(projection['annualMetrics']['2030']['exposedAreaKm2'], .0144, places=7)
            self.assertIsNone(projection['annualMetrics']['2030']['exposedPopulationCount'])
            annual_brief = build_briefing(projection, year=2030)
            self.assertEqual(annual_brief['dataKind'], 'synthetic')
            self.assertAlmostEqual(annual_brief['facts']['metrics']['scenarioExposureAreaKm2'], .0144, places=7)
            response = client.get('/api/v1/projection', params={'event': 'pilot', 'runId': projection['runId'],
                                                                'scenarioId': 'central', 'year': 2030})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertIn('exposure2030', response.json()['assets'])
            self.assertNotIn('exposure2026', response.json()['assets'])
            response = client.get('/api/v1/briefing', params={'event': 'pilot', 'product': 'projection',
                                                             'runId': projection['runId'], 'year': 2030})
            self.assertEqual(response.status_code, 200, response.text)

if __name__ == '__main__':
    unittest.main()
