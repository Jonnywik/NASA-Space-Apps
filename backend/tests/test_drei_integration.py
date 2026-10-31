"""Actual P2 mapper -> catalog -> frequency -> exposure -> API contract."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid
import numpy as np
from shapely.geometry import box, mapping
from fastapi import FastAPI
from fastapi.testclient import TestClient
from coherence_fixtures import prepared_pair, write_event_catalog, EVENT_ID
from processing import coherence_io, coherence_change
from processing.coherence_publication import import_change
from processing.p3 import core

class DreiIntegrationTests(unittest.TestCase):
    def test_import_preserves_synthetic_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            events = write_event_catalog(root / 'events.json')
            prepared_pair(root/'prepared', np.full((7,7),.8), np.full((7,7),.4))
            with patch.object(coherence_io,'EVENTS_FILE',events):
                coherence_change.create_change_map(EVENT_ID,input_dir=root/'prepared',output_dir=root/'mapped',min_pixels=1,simplify=0)
            path=root/'mapped'/'change_extent.json'
            meta=json.loads(path.read_text())
            meta['dataKind']='observed'
            path.write_text(json.dumps(meta))
            with self.assertRaisesRegex(ValueError,'data kind'):
                import_change(EVENT_ID,path,root/'published')

    def test_mapper_import_frequency_exposure_api(self):
        from processing.change_frequency import build_frequency
        from processing.building_exposure import build_exposure
        from app.coherence_api import make_router
        from app.p3_api import make_router as asset_router
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            events = write_event_catalog(root / 'events.json')
            outputs = root / 'published'
            imports = []
            with patch.object(coherence_io, 'EVENTS_FILE', events):
                for i, coherence in enumerate([.4, .8]):
                    prepared = root / f'prepared{i}'
                    prepared_pair(prepared, np.full((7,7), .8), np.full((7,7), coherence), extraction_id=str(uuid.uuid4()))
                    if i:
                        path = prepared / 'coherence_info.json'
                        meta = json.loads(path.read_text())
                        meta['prePair'] = ['2024-01-02', '2024-01-06']
                        meta['coPair'] = ['2024-01-06', '2024-01-16']
                        for name in ['pre', 'co']:
                            meta['sources'][name]['acquisitionDates'] = meta['prePair' if name=='pre' else 'coPair']
                            meta['sources'][name]['productId'] += '-second'
                            meta['sources'][name]['sceneIds'] = [s+'2' for s in meta['sources'][name]['sceneIds']]
                        path.write_text(json.dumps(meta))
                    mapped = root / f'mapped{i}'
                    coherence_change.create_change_map(EVENT_ID, input_dir=prepared, output_dir=mapped, min_pixels=1, simplify=0)
                    imports.append(import_change(EVENT_ID, mapped / 'change_extent.json', outputs))
            frequency_path = build_frequency(EVENT_ID, imports, output_root=outputs)
            frequency = core.load_manifest(frequency_path)
            array, grid = core.read_raster(frequency, 'frequency')
            np.testing.assert_allclose(array[np.isfinite(array)], .5)
            self.assertTrue(np.isnan(array).any())
            from affine import Affine
            transform = Affine(*grid['transform'])
            x,y = transform * (3,3)
            footprint = box(x+2, y-28, x+28, y-2)
            buildings = root / 'buildings.geojson'
            buildings.write_text(json.dumps({'type':'FeatureCollection', 'crs':{'type':'name','properties':{'name':grid['crs']}}, 'features':[
                {'type':'Feature','properties':{'osmType':'way','osmId':7},'geometry':mapping(footprint)}]*2}))
            left, top = transform*(0,0)
            right,bottom = transform*(grid['width'],grid['height'])
            config = {'schemaVersion':'1.0','dataKind':'synthetic','sourceDate':'2026-01-01','source':'Synthetic OSM fixture',
                      'geojsonPath':str(buildings),'sha256':core.digest(buildings),
                      'coverage':{'geometry':mapping(box(left,bottom,right,top)), 'crs':grid['crs']}}
            snapshot = root / 'snapshot.json'
            snapshot.write_text(json.dumps(config))
            exposure_path = build_exposure(EVENT_ID, imports[0], snapshot, output_root=outputs)
            exposure = core.load_manifest(exposure_path)
            report = json.loads(core.asset_path(exposure,'exposure').read_text())
            self.assertIsNone(report['combined']['mappedHazardOverlapCount'])
            self.assertEqual(report['combined']['partialMappedHazardOverlapCount'],1)
            self.assertEqual(report['combined']['uniqueOsmIds'],['way/7'])
            self.assertEqual(exposure['dataKind'],'synthetic')
            app = FastAPI()
            read_events=lambda:[{'id':EVENT_ID}]
            app.include_router(make_router(outputs, read_events))
            app.include_router(asset_router(outputs, read_events))
            client = TestClient(app)
            response=client.get('/api/v1/coherence-loss',params={'event':EVENT_ID,'runId':core.load_manifest(imports[0])['runId'],'exposureRunId':exposure['runId']})
            self.assertEqual(response.status_code,200,response.text)
            self.assertIn('synthetic',response.text)
            self.assertTrue(response.json()['exposure']['available'])
            self.assertEqual(response.json()['exposure']['summary']['partialMappedHazardOverlapCount'],1)
            response=client.get('/api/v1/coherence-loss',params={'event':EVENT_ID,'product':'frequency','runId':frequency['runId']})
            self.assertEqual(response.status_code,200,response.text)
            # Import must reject altered legacy output bytes.
            (root/'mapped0'/'change.geojson').write_text('{}')
            with self.assertRaisesRegex(ValueError,'hash mismatch'):
                import_change(EVENT_ID,root/'mapped0'/'change_extent.json',outputs)
