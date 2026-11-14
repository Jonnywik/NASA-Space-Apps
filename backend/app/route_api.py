"""Read-only vehicle routing API: shortest vs hazard-aware route between two points."""
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from processing import routing
from processing.p3 import catalog
from processing.p3.core import asset_path

_CACHE: dict = {}


def make_router(output_root, read_events):
    router = APIRouter(prefix='/api/v1')
    root = Path(output_root)

    def _hazards(event):
        """Flood polygons (Tier 1) plus reviewed change polygons (Tier 2), with their descriptions."""
        folder = root / event
        flood_path = folder / 'flood.geojson'
        if not flood_path.exists():
            raise HTTPException(404, detail={'code': 'data_unavailable',
                                             'message': 'No flood result for this event yet.'})
        sources = [{'id': 'flood-extent', 'label': 'Tier 1 flood extent (Sentinel-1 radar)',
                    'dataStatus': 'derived'}]
        limitations = []
        change_geojson, change_run = None, None
        try:
            manifest = catalog.select(event, 'coherence-change', None, root=root)
            change_geojson = json.loads(asset_path(manifest, 'changeGeometry').read_text(encoding='utf-8'))
            change_run = manifest['runId']
            sources.append({'id': 'coherence-change', 'label': 'Tier 2 coherence change (reviewed)',
                            'runId': change_run, 'dataStatus': manifest.get('dataStatus')})
        except (catalog.ProductUnavailable, KeyError, OSError, ValueError):
            limitations.append('No reviewed coherence-change product, so change areas were not used.')
        return flood_path, change_geojson, change_run, sources, limitations

    def _graph(event, flood_path, change_geojson, change_run):
        roads = root / event / 'roads.geojson'
        if not roads.exists():
            raise HTTPException(404, detail={'code': 'roads_unavailable',
                                             'message': 'No road network exported for this event yet (script 18).'})
        key = (event, roads.stat().st_mtime_ns, flood_path.stat().st_mtime_ns, change_run)
        if key not in _CACHE:
            try:
                graph = routing.load_graph(roads)
            except routing.RoutingError as exc:
                raise HTTPException(exc.status, detail={'code': exc.code, 'message': str(exc)}) from exc
            flood = routing.union_of(json.loads(flood_path.read_text(encoding='utf-8')))
            change = routing.union_of(change_geojson)
            routing.classify(graph, flood, change)
            _CACHE.clear()  # keep one classified graph: they are large
            _CACHE[key] = graph
        return _CACHE[key]

    @router.get('/route')
    def route(event: str,
              fromLon: float = Query(ge=-180, le=180), fromLat: float = Query(ge=-90, le=90),
              toLon: float = Query(ge=-180, le=180), toLat: float = Query(ge=-90, le=90),
              vehicle: str = 'car'):
        events = {e['id']: e for e in read_events()}
        if event not in events:
            raise HTTPException(404, detail={'code': 'unknown_event'})
        if vehicle != 'car':
            raise HTTPException(422, detail={'code': 'unsupported_vehicle',
                                             'message': 'Only vehicle routing (car) is available.'})
        flood_path, change_geojson, change_run, sources, limitations = _hazards(event)
        graph = _graph(event, flood_path, change_geojson, change_run)
        try:
            result = routing.route(graph, (fromLon, fromLat), (toLon, toLat))
        except routing.RoutingError as exc:
            raise HTTPException(exc.status, detail={'code': exc.code, 'message': str(exc)}) from exc
        ev = events[event]
        sources[0]['dates'] = {'before': ev.get('before_date'), 'after': ev.get('after_date')}
        return {
            'event': event, 'mode': 'observed', 'vehicle': 'car',
            'dataKind': 'derived', 'dataStatus': 'derived',
            'hazardSources': sources,
            **result,
            'limitations': limitations + [
                'Hazard-aware does not mean guaranteed safe: it only avoids what was mapped, on the dates shown.',
                'Hazards are matched per road segment. Flood extents are minimums (the radar after-date is days after the peak).',
                'No live traffic, closures or water depth. Roads: © OpenStreetMap contributors (ODbL).',
            ],
        }

    return router
