"""Export the drivable road network for one event as roads.geojson (directed edges).

    python scripts/18_export_roads.py karding_2022
    python scripts/18_export_roads.py karding_2022 --bbox 120.6 14.8 121.0 15.2

The area defaults to the bounds of the event's flood.geojson plus a margin. Needs internet and the
packages in requirements-data.txt (osmnx >= 2). Do NOT commit the output: data/ stays out of git.
Roads are (c) OpenStreetMap contributors, ODbL.
"""
import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


def _bounds_from_flood(folder: Path, margin: float):
    from shapely.geometry import shape
    data = json.loads((folder / 'flood.geojson').read_text(encoding='utf-8'))
    geoms = [shape(f['geometry']) for f in data['features'] if f.get('geometry')]
    if not geoms:
        sys.exit('flood.geojson has no shapes; pass --bbox W S E N')
    xs = [g.bounds for g in geoms]
    return (min(b[0] for b in xs) - margin, min(b[1] for b in xs) - margin,
            max(b[2] for b in xs) + margin, max(b[3] for b in xs) + margin)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('event')
    ap.add_argument('--bbox', nargs=4, type=float, metavar=('W', 'S', 'E', 'N'))
    ap.add_argument('--margin', type=float, default=0.05, help='degrees added around the flood shapes')
    ap.add_argument('--output-root', default=str(BACKEND / 'data' / 'output'))
    a = ap.parse_args(argv)

    import osmnx as ox
    folder = Path(a.output_root) / a.event
    west, south, east, north = a.bbox or _bounds_from_flood(folder, a.margin)
    print(f'Downloading drivable roads for bbox W{west:.3f} S{south:.3f} E{east:.3f} N{north:.3f} ...')
    graph = ox.graph_from_bbox((west, south, east, north), network_type='drive')
    to_gdfs = getattr(ox, 'graph_to_gdfs', None) or ox.convert.graph_to_gdfs
    edges = to_gdfs(graph, nodes=False)  # two-way roads appear once per direction

    features = []
    for _, row in edges.iterrows():
        if row.geometry is None or row.geometry.geom_type != 'LineString':
            continue
        hw = row.get('highway')
        features.append({
            'type': 'Feature',
            'geometry': {'type': 'LineString', 'coordinates': [list(c) for c in row.geometry.coords]},
            'properties': {'highway': hw if isinstance(hw, str) else (hw[0] if hw else None),
                           'oneway': bool(row.get('oneway', False))},
        })
    out = folder / 'roads.geojson'
    out.write_text(json.dumps({'type': 'FeatureCollection', 'features': features}), encoding='utf-8')
    sha = hashlib.sha256(out.read_bytes()).hexdigest()
    (folder / 'roads.json').write_text(json.dumps({
        'source': 'OpenStreetMap via osmnx', 'osmnxVersion': getattr(ox, '__version__', None),
        'downloaded': date.today().isoformat(), 'bbox': [west, south, east, north],
        'edgeCount': len(features), 'sha256': sha, 'license': 'ODbL, (c) OpenStreetMap contributors',
    }, indent=2), encoding='utf-8')
    print(f'Wrote {out} ({len(features)} road segments). Do not commit it.')


if __name__ == '__main__':
    main()
