"""Places API: gazetteer search, boundaries, point lookup and exposure under NISAR masks."""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from processing.places import BBOX, PLACES_DIR, STUDY_AREA_ID, gazetteer, path_for

NISAR_DIR = 'nisar'
RHYTHM_FILE = 'rhythm.tif'
PRIORITY_FILE = 'priority_mask.tif'
NISAR_MANIFESTS = ('manifest.json', 'rhythm_manifest.json')
MASKS = ('rhythm_half', 'priority')


def _err(status, code, message):
    return HTTPException(status, detail={'code': code, 'message': message})


@lru_cache(maxsize=8)
def _json(path: str, mtime: float):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _read(path):
    p = Path(path)
    return _json(str(p), p.stat().st_mtime)


def make_router(output_root, read_public_events, places_root=None):
    router = APIRouter(prefix='/api/v1')
    root = Path(places_root) if places_root else PLACES_DIR

    def manifest():
        p = path_for('manifest', root)
        return _read(p) if p.exists() else {}

    def base(dataKind='observed'):
        m = manifest()
        gen = (m.get('inputs', {}).get('boundaries') or {}).get('retrievedAt') or m.get('generatedAt')
        return {'dataKind': dataKind, 'retrievedAt': gen, 'warnings': [], 'limitations': []}

    def need(key):
        p = path_for(key, root)
        if not p.exists():
            raise _err(404, 'data_unavailable', f'{key} data not built; run backend/scripts/40_fetch_places.py')
        return p

    def boundary_source():
        s = (manifest().get('inputs') or {}).get('boundaries') or {}
        return {'name': s.get('name', 'Philippines COD-AB admin boundaries'), 'url': s.get('landingPage', 'https://data.humdata.org/dataset/cod-ab-phl'),
                'version': s.get('datasetDate', 'v03, valid 2025-02-13')}

    @router.get('/places/search')
    def search(q: str = '', limit: str = '10'):
        try:
            n = int(limit)
        except ValueError:
            raise _err(422, 'invalid_request', 'limit must be an integer')
        if not 1 <= n <= 50:
            raise _err(422, 'invalid_request', 'limit must be between 1 and 50')
        if not q.strip():
            raise _err(422, 'invalid_request', 'q is required')
        need('gazetteer')
        res = gazetteer.search(q, n, root=root)
        out = base()
        out.update({'query': q, 'results': res, 'source': boundary_source(), 'nativeResolution': 'administrative boundary (barangay)'})
        return out

    @router.get('/places/boundaries')
    def boundaries(level: str = 'barangay'):
        if level not in ('city', 'barangay'):
            raise _err(422, 'invalid_request', "level must be 'city' or 'barangay'")
        fc = dict(_read(need(level)))
        out = base()
        out.update({k: v for k, v in fc.items() if k not in ('type', 'features')})
        out['source'] = boundary_source()
        out['limitations'] = ['boundaries simplified to about 5 m for display']
        out.update({'type': 'FeatureCollection', 'level': level, 'features': fc['features']})
        return out

    @router.get('/places/locate')
    def locate(lon: str = '', lat: str = ''):
        try:
            x, y = float(lon), float(lat)
        except ValueError:
            raise _err(422, 'invalid_request', 'lon and lat must be numbers')
        if not (math.isfinite(x) and math.isfinite(y)) or not (-180 <= x <= 180 and -90 <= y <= 90):
            raise _err(422, 'invalid_request', 'lon/lat out of range')
        if not (BBOX[0] <= x <= BBOX[2] and BBOX[1] <= y <= BBOX[3]):
            raise _err(404, 'outside_coverage', f'point is outside the study area bbox {list(BBOX)}')
        need('barangay'); need('city')
        res = gazetteer.locate(x, y, root=root)
        out = base()
        out.update(res)
        out['source'] = boundary_source()
        if res['barangay'] is None:
            out['warnings'].append('point is inside the study bbox but not inside any barangay polygon (for example open water)')
        out['limitations'] = ['boundaries simplified to about 5 m; points within a few metres of a border can fall on either side']
        return out

    def nisar_dir():
        return Path(output_root) / STUDY_AREA_ID / NISAR_DIR

    @router.get('/places/exposure')
    def exposure(area: str = STUDY_AREA_ID, mask: str = 'rhythm_half', level: str = 'barangay'):
        if area != STUDY_AREA_ID:
            raise _err(404, 'unknown_area', f'unknown area {area!r}')
        if mask not in MASKS:
            raise _err(422, 'invalid_request', f'mask must be one of {list(MASKS)}')
        if level not in ('city', 'barangay'):
            raise _err(422, 'invalid_request', "level must be 'city' or 'barangay'")
        d = nisar_dir()
        raster = d / (RHYTHM_FILE if mask == 'rhythm_half' else PRIORITY_FILE)
        if not raster.exists():
            raise _err(404, 'data_unavailable', f'{mask} raster not available yet ({raster.name})')
        need(level)
        nm = {}
        for name in NISAR_MANIFESTS:
            if (d / name).exists():
                nm = _read(d / name)
                break
        from processing.places.exposure import exposure_for_mask, rhythm_mask
        try:
            if mask == 'rhythm_half' and (d / 'rhythm_half.tif').exists():
                # NISAR's own mask: flooded on >= half of each pixel's VALID passes
                res = exposure_for_mask(str(d / 'rhythm_half.tif'), level, root=root)
            elif mask == 'rhythm_half':
                arr = rhythm_mask(raster, nm.get('passCount'), 0.5)
                res = exposure_for_mask(arr, level, root=root)
            else:
                res = exposure_for_mask(str(raster), level, root=root)
        except (ValueError, OSError) as exc:
            raise _err(422, 'invalid_request', f'could not read mask: {exc}')
        kind = 'synthetic' if nm.get('dataKind') == 'synthetic' else 'derived'
        out = base(kind)
        out['warnings'] += res['warnings']
        if not nm:
            out['warnings'].append('NISAR manifest not found; data kind could not be verified')
        out['limitations'] = res['limitations']
        m = manifest()
        pop = (m.get('inputs') or {}).get('population') or {}
        bld = (m.get('inputs') or {}).get('buildings') or {}
        out.update({
            'area': area, 'mask': mask, 'level': level,
            'maskDefinition': 'flood rhythm count >= half of valid passes (rounded up); nodata is not exposure' if mask == 'rhythm_half'
                              else 'priority mask raster; nodata is not exposure',
            'passCount': nm.get('passCount'),
            'zones': res['zones'], 'totals': res['totals'],
            'populationSource': {'name': 'WorldPop 2020 constrained 100 m (BSGM)', 'year': 2020, 'url': pop.get('url'), 'license': pop.get('license', 'CC BY 4.0')},
            'buildingSource': {'name': 'OpenStreetMap buildings (HOT export)', 'snapshotDate': '2026-10-12', 'completeness': 'unknown',
                               'url': bld.get('url'), 'license': bld.get('license', 'ODbL')},
            'source': {'name': 'Tanaw exposure from NISAR ' + ('flood rhythm' if mask == 'rhythm_half' else 'priority mask'),
                       'url': 'https://nisar.jpl.nasa.gov/', 'version': nm.get('version', 'unversioned')},
            'units': {'areaKm2': 'km2 (equal-area)', 'population': 'people', 'buildings': 'mapped footprints'},
            'nativeResolution': 'mask grid; population 100 m',
            'populationUnavailableReason': res['populationUnavailableReason'],
            'buildingsUnavailableReason': res['buildingsUnavailableReason'],
        })
        return out

    return router
