"""Tiny synthetic fixtures for the places tests (no network). Names are test labels, not real places."""
import json
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import rasterio
from rasterio.transform import from_origin

W, N, STEP = 120.95, 14.71, 0.0025  # 4 x 4 grid, 0.01 degree square
MID_LON, MID_LAT = W + 2 * STEP, N - 2 * STEP
E, S = W + 4 * STEP, N - 4 * STEP
GRID_TF = from_origin(W, N, STEP, STEP)


def _poly(w, s, e, n):
    return {'type': 'Polygon', 'coordinates': [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}


CITIES = [('T1', 'Test City Alpha', (W, S, MID_LON, N)), ('T2', 'Test City Beta', (MID_LON, S, E, N))]
BARANGAYS = [
    ('T1-1', 'Brgy. Test Niño', 'T1', (W, MID_LAT, MID_LON, N)),
    ('T1-2', 'Test Poblacion', 'T1', (W, S, MID_LON, MID_LAT)),
    ('T2-1', 'Test Poblacion', 'T2', (MID_LON, MID_LAT, E, N)),
    ('T2-2', 'Another Barangay 28', 'T2', (MID_LON, S, E, MID_LAT)),
]


def make_places_root(root, population=True, buildings=True):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    cname = {c[0]: c[1] for c in CITIES}
    cf = [{'type': 'Feature', 'properties': {'id': i, 'name': n, 'city': n, 'province': 'Test Province', 'level': 'city'},
           'geometry': _poly(*b)} for i, n, b in CITIES]
    bf = [{'type': 'Feature', 'properties': {'id': i, 'name': n, 'city': cname[c], 'cityId': c, 'province': 'Test Province', 'level': 'barangay'},
           'geometry': _poly(*b)} for i, n, c, b in BARANGAYS]
    (root / 'boundaries_city.geojson').write_text(json.dumps({'type': 'FeatureCollection', 'features': cf}))
    (root / 'boundaries_barangay.geojson').write_text(json.dumps({'type': 'FeatureCollection', 'features': bf}))
    places = [{'id': f['properties']['id'], 'name': f['properties']['name'], 'level': f['properties']['level'],
               'city': f['properties']['city'], 'province': 'Test Province', 'lon': 120.96, 'lat': 14.7,
               'bbox': [W, S, E, N], 'inStudyArea': True} for f in cf + bf]
    (root / 'gazetteer.json').write_text(json.dumps({'places': places}))
    if population:
        pop = (np.arange(16, dtype='float32').reshape(4, 4) + 1) * 10  # 10..160
        with rasterio.open(root / 'worldpop_phl_2020_constrained_clip.tif', 'w', driver='GTiff', height=4, width=4, count=1,
                           dtype='float32', crs='EPSG:4326', transform=GRID_TF, nodata=-99999.0) as dst:
            dst.write(pop, 1)
    if buildings:
        def centre(r, c):
            return W + (c + 0.5) * STEP, N - (r + 0.5) * STEP
        pts = [centre(0, 0)] * 3 + [centre(1, 2)] + [centre(2, 2)] * 2 + [centre(3, 0)] * 5 + [(121.5, 15.5)]
        pq.write_table(pa.table({'lon': pa.array([p[0] for p in pts], 'float32'), 'lat': pa.array([p[1] for p in pts], 'float32'),
                                 'area_m2': pa.array([50] * len(pts), 'uint16')}), root / 'buildings_osm_centroids.parquet')
    (root / 'manifest.json').write_text(json.dumps({'generatedAt': '2026-11-14T00:00:00Z', 'inputs': {}}))
    return root


def mask_array():
    m = np.zeros((4, 4), 'uint8')
    m[0, 0] = m[0, 1] = m[1, 2] = m[3, 3] = 1
    m[2, 2] = 255  # nodata cell that also holds population and buildings
    return m


def write_raster(path, arr, nodata=255, transform=GRID_TF):
    with rasterio.open(path, 'w', driver='GTiff', height=arr.shape[0], width=arr.shape[1], count=1, dtype=str(arr.dtype),
                       crs='EPSG:4326', transform=transform, nodata=nodata) as dst:
        dst.write(arr, 1)
