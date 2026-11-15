"""Offline composition of published point products and deterministic briefings."""
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import rasterio
from rasterio.warp import transform
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.nisar_api import make_router as nisar_router
from processing.climate import stats
from processing.climate.constants import CACHE_DIR
from processing.climate.power import daily_series, NATIVE_RESOLUTION, POWER_URL
from processing.climate.store import read_cache
from processing.p3 import catalog
from processing.p3.series import sample_point
from processing.places import BBOX, PLACES_DIR, gazetteer
from processing.briefing_place.render import build, csv_text, html_text
from processing.priority.provenance import load_priority

AREA = 'camanava_2026'


def stream(value=None, reason=None, source=None, kind=None, resolution=None, units=None, **extra):
    return {'value': value, 'reason': reason, 'source': source, 'dataKind': kind,
            'nativeResolution': resolution, 'units': units, **extra}


def make_router(output_root, read_public_events, places_root=None, climate_root=None):
    router = APIRouter(prefix='/api/v1')
    root = Path(output_root)
    places = Path(places_root or PLACES_DIR)
    climate = Path(climate_root or CACHE_DIR)
    nisar_point = next(r.endpoint for r in nisar_router(root, read_public_events).routes if r.path.endswith('/nisar/point'))

    def make_spot(lon, lat):
        try:
            x, y = float(lon), float(lat)
        except (ValueError, TypeError):
            raise HTTPException(422, detail={'code': 'invalid_request', 'message': 'lon and lat must be finite numbers'}) from None
        if not math.isfinite(x) or not math.isfinite(y) or not (-180 <= x <= 180 and -90 <= y <= 90):
            raise HTTPException(422, detail={'code': 'invalid_request', 'message': 'lon and lat must be finite WGS84 coordinates'})
        if not (BBOX[0] <= x <= BBOX[2] and BBOX[1] <= y <= BBOX[3]):
            raise HTTPException(404, detail={'code': 'outside_coverage', 'message': 'point is outside the study area'})
        warnings, limits, streams = [], [], {}
        try:
            place = gazetteer.locate(x, y, root=places)
            value = {'barangay': place['barangay'], 'city': place['city']}
            if not place['barangay']:
                value = None
            try:
                inputs = json.loads((places / 'manifest.json').read_text(encoding='utf-8')).get('inputs', {})
            except (OSError, ValueError):
                inputs = {}
            boundary = inputs.get('boundaries') or {}
            streams['place'] = stream(value, None if value else 'no barangay polygon contains this point',
                                      {'name': boundary.get('name', 'HDX COD-AB administrative boundaries'), 'url': boundary.get('landingPage', 'https://data.humdata.org/dataset/cod-ab-phl'), 'version': boundary.get('datasetDate')},
                                      'observed', 'administrative boundaries', retrievedAt=boundary.get('retrievedAt'))
            limits.append('Administrative boundaries are simplified; a point near a border may fall on either side.')
        except (OSError, ValueError, KeyError):
            streams['place'] = stream(reason='administrative boundary data is unavailable')
        point = None
        try:
            point = nisar_point(area=AREA, lon=str(x), lat=str(y))
            streams['nisar'] = stream({k: point[k] for k in ('floodCount', 'floodCountReason', 'validCount', 'permanentWater', 'possibleFloodedVegetationPasses', 'perPass', 'cellCenter')},
                                      source=point['source'], kind=point['dataKind'], resolution=point.get('nativeResolution'), units=point.get('units'), generatedAt=point.get('generatedAt'))
            warnings.extend(point.get('warnings', [])); limits.extend(point.get('limitations', []))
        except HTTPException as exc:
            streams['nisar'] = stream(reason=exc.detail.get('message', 'NISAR point data is unavailable'))
        except (OSError, ValueError, KeyError):
            streams['nisar'] = stream(reason='NISAR point product is missing or unreadable')
        try:
            payload, entry = read_cache('power_daily', cache_dir=climate)
            if not point or not point['perPass']:
                raise ValueError('NISAR pass dates are unavailable')
            if payload is None:
                raise ValueError('NASA POWER cache is unavailable or failed its integrity check')
            rain = stats.pass_rainfall(daily_series(payload), [p['date'] for p in point['perPass']])
            streams['rainfall'] = stream(rain, source={'name': 'NASA POWER PRECTOTCORR', 'url': POWER_URL, 'version': payload.get('apiVersion'), 'dataSources': payload.get('sources')},
                                         kind='synthetic' if point['dataKind'] == 'synthetic' else 'derived', resolution=NATIVE_RESOLUTION, units='mm', retrievedAt=entry.get('retrievedAt'))
            limits.append('NASA POWER rainfall represents a coarse grid cell, not street-level rainfall; prior-day windows exclude the pass day.')
            limits.append('NASA POWER is reanalysis, not a rain-gauge record; dry-season rainfall reads much wetter than ERA5 in this area.')
            if any(c.get('sources') and set(c['sources']) != {'MERRA2'} for c in payload.get('chunks', [])):
                warnings.append('Recent NASA POWER data includes sources other than MERRA-2 and may be revised.')
            if entry.get('lastRefreshError'):
                warnings.append('The latest rainfall cache refresh failed; an older cache is shown.')
        except (OSError, ValueError, KeyError, TypeError) as exc:
            streams['rainfall'] = stream(reason=str(exc))
        try:
            imerg = json.loads((climate / 'imerg_passes.json').read_text(encoding='utf-8'))
            if imerg['area'] != AREA or not isinstance(imerg['passes'], list):
                raise ValueError('IMERG cache does not cover this area')
            rows = imerg['passes']
            if point and point.get('perPass'):
                latest_date = max(p['date'] for p in point['perPass'])
                rows = [row for row in rows if row['date'] == latest_date]
            latest = max(rows, key=lambda row: row['acquisitionTime'])
            value = {k: latest.get(k) for k in ('acquisitionTimeManila', 'last24hMm', 'last48hMm', 'hoursSinceRain')}
            if latest.get('hoursSinceRain') is None:
                value['hoursSinceRainReason'] = latest.get('hoursSinceRainNote') or 'the IMERG value is missing'
            if latest.get('hoursSinceRainNote'):
                value['hoursSinceRainNote'] = latest['hoursSinceRainNote']
            value.update(rainThresholdMmHr=imerg['rainThresholdMmHr'], window24Hours=24, window48Hours=48)
            streams['imerg'] = stream(value, source=imerg['source'], kind=imerg['dataKind'],
                                      resolution=imerg['nativeResolution'], units=imerg['units'], retrievedAt=imerg.get('retrievedAt'))
            limits.extend(imerg.get('limitations', [])); warnings.extend(imerg.get('warnings', []))
        except (OSError, ValueError, KeyError, TypeError):
            streams['imerg'] = stream(reason='IMERG pass data is unavailable')
        try:
            m = catalog.select(AREA, 'ground-motion', root=root)
            motion = sample_point(m, x, y)
            streams['motion'] = stream(motion if motion['status'] == 'ok' else None, motion.get('reason'),
                                       m.get('source') or m.get('sources') or m.get('sourceBasis') or {'runId': m.get('runId')}, m['dataKind'], m.get('nativeResolutionMetres') or m.get('nativeResolution') or m.get('grid'),
                                       'mm', generatedAt=m.get('generatedAt'), dataStatus=m.get('dataStatus'))
            limits.extend(m.get('limitations', [])); warnings.extend(m.get('warnings', []))
        except (catalog.ProductUnavailable, ValueError, OSError, KeyError) as exc:
            streams['motion'] = stream(reason=str(exc) or 'line-of-sight motion is unavailable')
        priority_meta = None
        try:
            folder = root / AREA / 'nisar'
            manifest = load_priority(folder)
            mask_path = folder / 'priority_mask.tif'
            priority_meta = manifest
            with rasterio.open(mask_path) as ds:
                xx, yy = transform('EPSG:4326', ds.crs, [x], [y])
                row, col = ds.index(xx[0], yy[0])
                if not (0 <= row < ds.height and 0 <= col < ds.width):
                    raise ValueError('point is outside priority mask coverage')
                pixel = ds.read(1, window=((row, row + 1), (col, col + 1)), masked=True)[0, 0]
                if bool(getattr(pixel, 'mask', False)) or int(pixel) not in (0, 1):
                    raise ValueError('priority mask has no valid value at this point')
                value = bool(pixel)
                resolution = {'pixelSize': list(ds.res), 'crs': str(ds.crs)}
            streams['priority'] = stream(value, source=manifest.get('source'), kind=manifest['dataKind'], resolution=resolution, generatedAt=manifest.get('generatedAt'))
        except (OSError, ValueError, KeyError, TypeError, AttributeError, rasterio.errors.RasterioError) as exc:
            streams['priority'] = stream(reason=str(exc) if isinstance(exc, ValueError) else 'priority mask or its provenance is unavailable',
                                         source=priority_meta.get('source') if priority_meta else None,
                                         kind=priority_meta.get('dataKind') if priority_meta else None)
        try:
            from processing.places.exposure import exposure_for_mask
            barangay = streams['place']['value']['barangay']
            if not barangay:
                raise ValueError('the point has no containing barangay')
            if streams['priority']['value'] is None:
                raise ValueError(streams['priority']['reason'] or 'priority mask is unavailable')
            result = exposure_for_mask(str(folder / 'priority_mask.tif'), 'barangay', root=places)
            zone = next((z for z in result['zones'] if z['placeId'] == barangay['id']), None)
            if zone is None:
                raise ValueError('no exposed area was reported for this barangay')
            zone = {**zone, 'populationReason': result.get('populationUnavailableReason'), 'buildingsReason': result.get('buildingsUnavailableReason')}
            streams['exposure'] = stream(zone, source={'mask': streams['priority']['source'], 'population': 'WorldPop 2020', 'buildings': 'OpenStreetMap'},
                                         kind=streams['priority']['dataKind'], resolution=streams['priority']['nativeResolution'], units={'areaKm2': 'km2', 'population': 'people', 'buildings': 'footprints'})
            limits.extend(result.get('limitations', [])); warnings.extend(result.get('warnings', []))
        except (ValueError, OSError, KeyError, TypeError, rasterio.errors.RasterioError) as exc:
            streams['exposure'] = stream(reason=str(exc) or 'barangay exposure is unavailable')
        synthetic = any(s['dataKind'] == 'synthetic' for s in streams.values())
        if synthetic:
            warnings.insert(0, 'SYNTHETIC DEMO DATA: one or more streams are synthetic.')
        return {'lon': x, 'lat': y, 'area': AREA, 'streams': streams,
                'dataKind': 'synthetic' if synthetic else 'derived',
                'source': {k: v['source'] for k, v in streams.items()},
                'generatedAt': datetime.now(timezone.utc).isoformat(), 'warnings': warnings, 'limitations': limits}

    @router.get('/spot-check')
    def spot_check(lon: str = '', lat: str = ''):
        return make_spot(lon, lat)

    @router.get('/briefing/place')
    def briefing(lon: str = '', lat: str = '', lang: str = 'en', format: str = 'json'):
        if lang not in ('en', 'fil') or format not in ('json', 'csv', 'html'):
            raise HTTPException(422, detail={'code': 'invalid_request', 'message': 'lang must be en or fil; format must be json, csv or html'})
        data = build(make_spot(lon, lat), lang)
        if format == 'csv':
            return Response(csv_text(data), media_type='text/csv; charset=utf-8')
        if format == 'html':
            return Response(html_text(data), media_type='text/html; charset=utf-8')
        return data

    return router
