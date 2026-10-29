"""Read-only P3 product API; processing stays in the operator CLIs."""
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from processing.p3 import catalog
from processing.p3.core import asset_path


def make_router(output_root, read_events):
    router = APIRouter(prefix='/api/v1')

    def get(event, product, run_id=None):
        if event not in {e['id'] for e in read_events()}:
            raise HTTPException(404, detail={'code': 'unknown_event'})
        try:
            return catalog.select(event, product, run_id, root=output_root)
        except catalog.ProductUnavailable as exc:
            raise HTTPException(exc.status, detail={'code': exc.code, 'message': str(exc)}) from exc
        except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
            raise HTTPException(422, detail={'code': 'invalid_identifier_or_catalog'}) from exc

    def public(manifest):
        result = {k: v for k, v in manifest.items() if not k.startswith('_')}
        # All downloadable assets come from the selected, hash-checked manifest.
        result['assets'] = {key: {'sha256': info['sha256'], 'url':
            f"/api/v1/products/{manifest['event']}/{manifest['product']}/{manifest['runId']}/assets/{key}"}
            for key, info in manifest['assets'].items()}
        return result

    @router.get('/ground-motion')
    @router.get('/subsidence')
    def ground_motion(event: str, runId: str | None = None):
        return public(get(event, 'ground-motion', runId))

    @router.get('/ground-motion/point')
    def point(event: str, lon: float = Query(ge=-180, le=180), lat: float = Query(ge=-90, le=90), runId: str | None = None):
        from processing.p3.series import sample_point
        manifest = get(event, 'ground-motion', runId)
        try:
            result = sample_point(manifest, lon, lat)
        except ValueError as exc:
            raise HTTPException(422, detail={'code': 'invalid_point_or_product', 'message': str(exc)}) from exc
        return {'event': event, 'runId': manifest['runId'], 'dataKind': manifest['dataKind'],
                'dataStatus': manifest['dataStatus'], 'point': result}

    @router.get('/vegetation')
    def vegetation(event: str, runId: str | None = None):
        return public(get(event, 'biomass', runId))

    @router.get('/scenario-inputs')
    def inputs(event: str, runId: str | None = None):
        return public(get(event, 'scenario-inputs', runId))

    @router.get('/projection')
    def projection(event: str, scenarioId: str, year: int, runId: str | None = None):
        manifest = get(event, 'projection', runId)
        if manifest.get('scenarioId') != scenarioId:
            raise HTTPException(404, detail={'code': 'unknown_scenario'})
        if year not in manifest.get('supportedYears', []):
            raise HTTPException(422, detail={'code': 'unsupported_year', 'supportedYears': manifest.get('supportedYears', [])})
        result = public(manifest)
        result['selectedYear'] = year
        result['annualMetric'] = manifest.get('annualMetrics', {}).get(str(year))
        result['assets'] = {key: value for key, value in result['assets'].items()
                            if not (len(key) >= 4 and key[-4:].isdigit()) or key.endswith(str(year))}
        return result

    @router.get('/briefing')
    def briefing(event: str, product: str = 'ground-motion', runId: str | None = None, regionId: str = 'whole-event', year: int | None = None):
        from processing.p3.briefing import build_briefing
        manifest = get(event, product, runId)
        if product not in ('ground-motion', 'biomass', 'projection', 'los-pair'):
            raise HTTPException(422, detail={'code': 'unsupported_product'})
        if product == 'projection':
            years = manifest.get('supportedYears', [])
            if year is None and len(years) > 1:
                raise HTTPException(422, detail={'code': 'year_required', 'supportedYears': years})
            if year is not None and year not in years:
                raise HTTPException(422, detail={'code': 'unsupported_year', 'supportedYears': years})
        try:
            result = build_briefing(manifest, region_id=regionId, year=year)
        except (ValueError, KeyError) as exc:
            raise HTTPException(422, detail={'code': 'invalid_region_or_facts', 'message': str(exc)}) from exc
        return result

    @router.get('/products/{event}/{product}/{run_id}/assets/{key}')
    def asset(event: str, product: str, run_id: str, key: str):
        manifest = get(event, product, run_id)
        if key not in manifest['assets']:
            raise HTTPException(404, detail={'code': 'unknown_asset'})
        return FileResponse(asset_path(manifest, key))

    return router
