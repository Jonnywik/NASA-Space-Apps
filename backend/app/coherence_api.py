"""Read-only API for published paired-coherence change and frequency products."""
import json

from fastapi import APIRouter, HTTPException, Query

from processing.p3 import catalog
from processing.p3.core import asset_path


_PRODUCTS = {
    'change': 'coherence-change',
    'frequency': 'change-frequency',
}


def make_router(output_root, read_events):
    """Build routes over immutable catalog products; this module never processes data."""
    router = APIRouter(prefix='/api/v1')

    def select(event, product, run_id=None):
        if event not in {entry['id'] for entry in read_events()}:
            raise HTTPException(404, detail={'code': 'unknown_event'})
        try:
            return catalog.select(event, product, run_id, root=output_root)
        except catalog.ProductUnavailable as exc:
            raise HTTPException(exc.status, detail={'code': exc.code, 'message': str(exc)}) from exc
        except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
            raise HTTPException(422, detail={'code': 'invalid_identifier_or_catalog'}) from exc

    def public(manifest):
        result = {key: value for key, value in manifest.items() if not key.startswith('_')}
        # URLs always identify assets in the exact selected, hash-checked run.
        result['assets'] = {
            key: {
                'sha256': info['sha256'],
                'url': f"/api/v1/products/{manifest['event']}/{manifest['product']}/{manifest['runId']}/assets/{key}",
            }
            for key, info in manifest.get('assets', {}).items()
        }
        return result

    def regional_metric(manifest, region_id):
        rows = manifest.get('regionalMetrics')
        if isinstance(rows, dict):
            row = rows.get(region_id)
            if isinstance(row, dict):
                return {**row, 'regionId': region_id}
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict) and row.get('regionId') == region_id:
                    return row
        return None

    def exposure_summary(event, hazard, region_id, exposure_run_id):
        """Return matching published exposure facts, or a visible partial-unavailable state."""
        explicit = exposure_run_id is not None
        try:
            exposure = catalog.select(
                event, 'building-exposure', exposure_run_id, root=output_root,
            )
        except catalog.ProductUnavailable as exc:
            return {'available': False, 'reason': exc.code}
        except ValueError as exc:
            # Invalid explicit run IDs are caller errors; a valid but absent run is
            # represented by ProductUnavailable above as a partial exposure result.
            raise HTTPException(422, detail={'code': 'invalid_identifier_or_catalog'}) from exc
        except (KeyError, OSError, json.JSONDecodeError):
            return {'available': False, 'reason': 'invalid_product'}

        try:
            report_key = 'exposure'
            if report_key not in exposure.get('assets', {}):
                return {'available': False, 'reason': 'exposure_summary_missing'}
            report = json.loads(asset_path(exposure, report_key).read_text(encoding='utf-8'))
        except (ValueError, KeyError, OSError, json.JSONDecodeError):
            return {'available': False, 'reason': 'invalid_product'}
        if not isinstance(report, dict):
            return {'available': False, 'reason': 'invalid_product'}

        expected = {
            'hazardRunId': hazard.get('runId'),
            'hazardProduct': hazard.get('product'),
            'hazardEvent': event,
        }
        observed = {
            field: exposure.get(field, report.get(field))
            for field in ('hazardRunId', 'hazardProduct')
        }
        # The catalog's event identity also serves as the exposure's hazard event
        # when older valid manifests omit a separate hazardEvent field.
        observed['hazardEvent'] = exposure.get(
            'hazardEvent', report.get('hazardEvent', exposure.get('event', report.get('event'))),
        )
        # A valid, hash-checked exposure can still describe a different hazard.
        mismatch = any(observed[field] != value for field, value in expected.items())
        report_mismatch = any(
            report.get(field) is not None and report.get(field) != value
            for field, value in expected.items() if field != 'hazardEvent'
        )
        report_mismatch = report_mismatch or report.get('hazardEvent', report.get('event')) != event
        report_mismatch = report_mismatch or report.get('event') not in (None, event)
        report_mismatch = report_mismatch or report.get('product') not in (None, 'building-exposure')
        if mismatch or report_mismatch:
            if explicit:
                raise HTTPException(409, detail={'code': 'stale_exposure'})
            return {'available': False, 'reason': 'stale_exposure'}

        if region_id is None:
            summary = report.get('combined')
        else:
            regions = report.get('regions')
            summary = next((row for row in regions or []
                            if isinstance(row, dict) and row.get('regionId') == region_id), None)
        if not isinstance(summary, dict):
            return {
                'available': False,
                'reason': 'region_unavailable' if region_id is not None else 'exposure_summary_missing',
                'runId': exposure.get('runId'),
                'dataKind': exposure.get('dataKind'),
                'dataStatus': exposure.get('dataStatus'),
            }

        return {
            'available': True,
            'runId': exposure.get('runId'),
            'dataKind': exposure.get('dataKind'),
            'dataStatus': exposure.get('dataStatus'),
            'hazardRunId': observed['hazardRunId'],
            'hazardProduct': observed['hazardProduct'],
            'hazardEvent': observed['hazardEvent'],
            'snapshotDate': report.get('snapshotDate', exposure.get('snapshotDate')),
            'snapshotCoverage': report.get('snapshotCoverage', exposure.get('snapshotCoverage')),
            'scope': report.get('scope', exposure.get('scope')),
            'threshold': report.get('threshold', exposure.get('threshold')),
            'summary': summary,
            'assets': public(exposure)['assets'],
        }

    @router.get('/coherence-loss')
    def coherence_loss(
        event: str,
        product: str = 'change',
        runId: str | None = None,
        exposureRunId: str | None = None,
        regionId: str | None = Query(default=None, min_length=1),
    ):
        if product not in _PRODUCTS:
            raise HTTPException(422, detail={'code': 'unsupported_product', 'allowed': list(_PRODUCTS)})
        selected_product = _PRODUCTS[product]
        manifest = select(event, selected_product, runId)

        selected_region = None
        if regionId is not None:
            selected_region = regional_metric(manifest, regionId)
            if selected_region is None:
                raise HTTPException(422, detail={'code': 'region_unavailable'})

        result = public(manifest)
        result['productView'] = product
        if selected_region is not None:
            result['selectedRegion'] = selected_region

        # Change geometry is both available by asset URL and convenient as GeoJSON for
        # the map view. The catalog has already verified its hash during selection.
        if product == 'change' and 'changeGeometry' in manifest.get('assets', {}):
            try:
                result['changeGeojson'] = json.loads(
                    asset_path(manifest, 'changeGeometry').read_text(encoding='utf-8')
                )
            except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
                raise HTTPException(409, detail={'code': 'invalid_product'}) from exc

        result['exposure'] = exposure_summary(event, manifest, regionId, exposureRunId)
        return result

    return router
