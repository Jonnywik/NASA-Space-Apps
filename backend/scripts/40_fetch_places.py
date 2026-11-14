#!/usr/bin/env python
"""Fetch and build the Tanaw places data (boundaries, gazetteer, buildings, WorldPop, WorldCover).

Idempotent: raw downloads in backend/data/raw/places/ are reused when present (size checked);
small clipped products are rebuilt into backend/data/cache/places/ with a manifest.json that
records URL, licence, dataset date, retrieval time and sha256 for every input and product.

Sources (all open and licensed):
  boundaries  HDX Philippines COD-AB (PSA/NAMRIA via OCHA), CC BY-IGO
  buildings   OpenStreetMap buildings, HOT export on HDX (ODbL) -- used because overpass-api.de
              refused connections from this environment
  population  WorldPop 2020 constrained 100 m, CC BY 4.0
  landcover   ESA WorldCover 2021 v200 10 m, CC BY 4.0

Usage: python scripts/40_fetch_places.py [--skip-buildings] [--force-download]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402
import rasterio  # noqa: E402
from rasterio.windows import from_bounds  # noqa: E402
from shapely import wkb  # noqa: E402
from shapely.geometry import box, mapping, shape  # noqa: E402
from pyproj import Transformer  # noqa: E402
from shapely.ops import transform as shp_transform  # noqa: E402

from processing.places import BBOX, FILES, PLACES_DIR, RAW_DIR, STUDY_CITY_CODES, path_for  # noqa: E402

SIMPLIFY_DEG = 5e-5  # about 5 m
HDX_BOUNDARIES = ('https://data.humdata.org/dataset/caf116df-f984-4deb-85ca-41b349d3f313/resource/'
                  '3fa0dbcf-e07d-4506-9821-ba15baa6da07/download/phl_admin_boundaries.gdb.zip')
SOURCES = {
    'boundaries': {
        'name': 'Philippines - Subnational Administrative Boundaries (COD-AB), admin3 + admin4',
        'url': HDX_BOUNDARIES, 'landingPage': 'https://data.humdata.org/dataset/cod-ab-phl',
        'license': 'CC BY-IGO', 'datasetDate': 'boundaries valid_on 2025-02-13 (version v03); HDX metadata modified 2026-05-28',
        'raw': 'phl_admin_boundaries.gdb.zip'},
    'buildings': {
        'name': 'OpenStreetMap buildings of the Philippines (HOT export, GeoParquet)',
        'url': 'https://production-raw-data-api.s3.amazonaws.com/ISO3/PHL/_layers/osm/buildings.parquet',
        'landingPage': 'https://data.humdata.org/dataset/hotosm_phl_buildings',
        'license': 'ODbL 1.0 (c) OpenStreetMap contributors', 'datasetDate': '2026-10-12 (HDX dataset date); resource modified 2026-10-13',
        'raw': 'hotosm_phl_buildings.parquet'},
    'population': {
        'name': 'WorldPop 2020 Philippines, constrained individual countries 100 m (BSGM), people per pixel',
        'url': 'https://data.worldpop.org/GIS/Population/Global_2000_2020_Constrained/2020/BSGM/PHL/phl_ppp_2020_constrained.tif',
        'landingPage': 'https://hub.worldpop.org/geodata/summary?id=36130',
        'license': 'CC BY 4.0', 'datasetDate': '2020 (file last modified 2020-09-20)', 'raw': 'phl_ppp_2020_constrained.tif'},
    'landcover': {
        'name': 'ESA WorldCover 2021 v200 10 m, tile N12E120',
        'url': 'https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N12E120_Map.tif',
        'landingPage': 'https://esa-worldcover.org/en/data-access',
        'license': 'CC BY 4.0', 'datasetDate': '2021 (file last modified 2022-10-26)',
        'raw': 'ESA_WorldCover_10m_2021_v200_N12E120_Map.tif'},
}
WORLDCOVER_CLASSES = {10: 'Tree cover', 20: 'Shrubland', 30: 'Grassland', 40: 'Cropland', 50: 'Built-up',
                      60: 'Bare / sparse vegetation', 70: 'Snow and ice', 80: 'Permanent water bodies',
                      90: 'Herbaceous wetland', 95: 'Mangroves', 100: 'Moss and lichen'}
PROVINCE_NCR = 'Metro Manila'


def now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b''):
            h.update(chunk)
    return h.hexdigest()


def remote_size(url):
    r = subprocess.run(['curl', '-sSIL', '-m', '60', url], capture_output=True, text=True)
    sizes = [int(l.split(':')[1]) for l in r.stdout.splitlines() if l.lower().startswith('content-length:')]
    return sizes[-1] if sizes else None


def download(key, force=False):
    s = SOURCES[key]
    dest = RAW_DIR / s['raw']
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not force:
        want = remote_size(s['url'])
        if want is None or want == dest.stat().st_size:
            print(f'[raw] {dest.name} present ({dest.stat().st_size} bytes), reused')
            return dest
        print(f'[raw] {dest.name} size differs from server ({want}); downloading again')
    for attempt in (1, 2):
        r = subprocess.run(['curl', '-sS', '-L', '-m', '3000', '-o', str(dest), '-w', '%{http_code}', s['url']],
                           capture_output=True, text=True)
        if r.stdout.strip() == '200':
            print(f'[raw] downloaded {dest.name} ({dest.stat().st_size} bytes)')
            return dest
        print(f'[raw] attempt {attempt} failed: {r.stdout} {r.stderr[:200]}')
        time.sleep(30)
    raise SystemExit(f'download failed for {key}: {s["url"]}')


def round_coords(obj, nd=5):
    if isinstance(obj, (list, tuple)):
        return [round_coords(o, nd) for o in obj] if obj and isinstance(obj[0], (list, tuple)) else [round(float(v), nd) for v in obj]
    return obj


def feature(geom, props):
    g = geom.simplify(SIMPLIFY_DEG, preserve_topology=True)
    if g.is_empty:
        g = geom
    m = mapping(g)
    return {'type': 'Feature', 'properties': props,
            'geometry': {'type': m['type'], 'coordinates': round_coords(m['coordinates'])}}


def build_boundaries(gdb):
    import pyogrio
    b3 = pyogrio.read_dataframe(gdb, layer='phl_admin3', bbox=BBOX)
    b4 = pyogrio.read_dataframe(gdb, layer='phl_admin4', bbox=BBOX)
    area_box = box(*BBOX)
    b3 = b3[b3.intersects(area_box)]
    b4 = b4[b4.intersects(area_box)]
    cities, city_info = [], {}
    for r in b3.itertuples():
        ncr = r.adm1_pcode == 'PH13'
        province = PROVINCE_NCR if ncr else r.adm2_name
        city_info[r.adm3_pcode] = {'name': r.adm3_name, 'province': province}
        cities.append(feature(r.geometry, {
            'id': r.adm3_pcode, 'name': r.adm3_name, 'level': 'city', 'city': r.adm3_name, 'province': province,
            'region': r.adm1_name, 'inStudyArea': r.adm3_pcode in STUDY_CITY_CODES}))
    brgys, missing_city = [], 0
    for r in b4.itertuples():
        ci = city_info.get(r.adm3_pcode)
        if ci is None:
            missing_city += 1
            ci = {'name': r.adm3_name, 'province': PROVINCE_NCR if r.adm1_pcode == 'PH13' else r.adm2_name}
        brgys.append(feature(r.geometry, {
            'id': r.adm4_pcode, 'name': r.adm4_name, 'level': 'barangay', 'city': ci['name'], 'cityId': r.adm3_pcode,
            'province': ci['province'], 'region': r.adm1_name, 'inStudyArea': r.adm3_pcode in STUDY_CITY_CODES}))
    cities.sort(key=lambda f: f['properties']['id'])
    brgys.sort(key=lambda f: f['properties']['id'])
    meta = {'source': {'name': SOURCES['boundaries']['name'], 'url': SOURCES['boundaries']['landingPage']},
            'license': 'CC BY-IGO (OCHA/HDX COD-AB; data from PSA and NAMRIA)',
            'simplifyToleranceDeg': SIMPLIFY_DEG, 'bbox': list(BBOX)}
    for level, feats in (('city', cities), ('barangay', brgys)):
        fc = {'type': 'FeatureCollection', **meta, 'features': feats}
        path_for(level, PLACES_DIR).write_text(json.dumps(fc, separators=(',', ':'), ensure_ascii=False), encoding='utf-8')
    # gazetteer
    places = []
    for f in cities + brgys:
        g = shape(f['geometry'])
        c = g.centroid if g.centroid.within(g) else g.representative_point()
        p = f['properties']
        places.append({'id': p['id'], 'name': p['name'], 'level': p['level'], 'city': p['city'], 'province': p['province'],
                       'lon': round(c.x, 5), 'lat': round(c.y, 5), 'bbox': [round(v, 5) for v in g.bounds],
                       'inStudyArea': p['inStudyArea']})
    gz = {'source': meta['source'], 'license': meta['license'], 'generatedAt': now(), 'places': places}
    path_for('gazetteer', PLACES_DIR).write_text(json.dumps(gz, separators=(',', ':'), ensure_ascii=False), encoding='utf-8')
    study = [f['properties'] for f in cities if f['properties']['inStudyArea']]
    study_b = [f for f in brgys if f['properties']['inStudyArea']]
    return {'cities': len(cities), 'barangays': len(brgys), 'studyCities': sorted(p['name'] for p in study),
            'studyCityCount': len(study), 'studyBarangays': len(study_b), 'barangaysWithoutCityPolygon': missing_city}


def build_buildings(parquet_path):
    pf = pq.ParquetFile(parquet_path)
    to_utm = Transformer.from_crs(4326, 32651, always_xy=True).transform
    lons, lats, areas = [], [], []
    scanned = 0
    for rg in range(pf.num_row_groups):
        t = pf.read_row_group(rg, columns=['bbox', 'geom'])
        scanned += t.num_rows
        bb = t['bbox'].combine_chunks()
        xmin, xmax = bb.field('xmin').to_numpy(zero_copy_only=False), bb.field('xmax').to_numpy(zero_copy_only=False)
        ymin, ymax = bb.field('ymin').to_numpy(zero_copy_only=False), bb.field('ymax').to_numpy(zero_copy_only=False)
        sel = np.nonzero((xmax >= BBOX[0]) & (xmin <= BBOX[2]) & (ymax >= BBOX[1]) & (ymin <= BBOX[3]))[0]
        if not len(sel):
            continue
        geoms = t['geom'].take(pa.array(sel)).to_pylist()
        for raw in geoms:
            g = wkb.loads(raw)
            if g.geom_type not in ('Polygon', 'MultiPolygon') or g.is_empty:
                continue
            c = g.centroid
            if not (BBOX[0] <= c.x <= BBOX[2] and BBOX[1] <= c.y <= BBOX[3]):
                continue
            lons.append(c.x)
            lats.append(c.y)
            areas.append(shp_transform(to_utm, g).area)
    table = pa.table({'lon': pa.array(np.asarray(lons, 'float32')), 'lat': pa.array(np.asarray(lats, 'float32')),
                      'area_m2': pa.array(np.clip(np.round(areas), 0, 65535).astype('uint16'))})
    out = path_for('buildings', PLACES_DIR)
    pq.write_table(table, out, compression='zstd', compression_level=9)
    return {'rowsScanned': scanned, 'buildings': table.num_rows, 'totalFootprintKm2': round(float(np.sum(areas)) / 1e6, 3)}


def clip_raster(src_path, out_path, dtype=None, nodata=None, predictor=None):
    with rasterio.open(src_path) as src:
        win = from_bounds(*BBOX, transform=src.transform).round_offsets().round_lengths()
        data = src.read(1, window=win)
        tf = src.window_transform(win)
        prof = {'driver': 'GTiff', 'height': data.shape[0], 'width': data.shape[1], 'count': 1, 'dtype': data.dtype,
                'crs': src.crs, 'transform': tf, 'nodata': src.nodata if nodata is None else nodata, 'compress': 'deflate',
                'tiled': True, 'blockxsize': 256, 'blockysize': 256}
        if predictor:
            prof['predictor'] = predictor
        with rasterio.open(out_path, 'w', **prof) as dst:
            dst.write(data, 1)
        return data, src.nodata, tf


def build_population(raw):
    data, nodata, _ = clip_raster(raw, path_for('population', PLACES_DIR), predictor=3)
    valid = data[data != nodata] if nodata is not None else data
    valid = valid[np.isfinite(valid) & (valid > 0)]
    return {'totalPeopleInBboxClip': round(float(valid.sum())), 'cellsWithPeople': int(valid.size), 'shape': list(data.shape)}


def build_landcover(raw):
    data, _, _ = clip_raster(raw, path_for('landcover', PLACES_DIR), predictor=2)
    vals, cnt = np.unique(data, return_counts=True)
    return {'shape': list(data.shape), 'classShare': {f'{int(v)} {WORLDCOVER_CLASSES.get(int(v), "?")}': round(c / data.size, 4) for v, c in zip(vals, cnt)}}


def file_info(path):
    return {'path': str(Path(path).relative_to(ROOT)), 'bytes': Path(path).stat().st_size, 'sha256': sha256(path)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--skip-buildings', action='store_true')
    ap.add_argument('--force-download', action='store_true')
    args = ap.parse_args()
    PLACES_DIR.mkdir(parents=True, exist_ok=True)
    old = {}
    mpath = path_for('manifest', PLACES_DIR)
    if mpath.exists():
        old = json.loads(mpath.read_text()).get('inputs', {})
    raws = {}
    for key in ('boundaries', 'population', 'landcover') + (() if args.skip_buildings else ('buildings',)):
        raws[key] = download(key, args.force_download)
    inputs, products, stats = {}, {}, {}
    for key, raw in raws.items():
        digest = sha256(raw)
        prev = old.get(key, {})
        retrieved = prev.get('retrievedAt') if prev.get('sha256') == digest else None
        retrieved = retrieved or datetime.fromtimestamp(raw.stat().st_mtime, timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        s = SOURCES[key]
        inputs[key] = {'name': s['name'], 'url': s['url'], 'landingPage': s['landingPage'], 'license': s['license'],
                       'datasetDate': s['datasetDate'], 'retrievedAt': retrieved, 'rawFile': f'data/raw/places/{raw.name}',
                       'bytes': raw.stat().st_size, 'sha256': digest}
    stats['boundaries'] = build_boundaries(raws['boundaries'])
    stats['population'] = build_population(raws['population'])
    stats['landcover'] = build_landcover(raws['landcover'])
    if 'buildings' in raws:
        stats['buildings'] = build_buildings(raws['buildings'])
        stats['buildings']['completeness'] = 'unknown'
        stats['buildings']['snapshotDate'] = '2026-10-12'
    for k in ('city', 'barangay', 'gazetteer', 'population', 'landcover', 'buildings'):
        if path_for(k, PLACES_DIR).exists():
            products[k] = file_info(path_for(k, PLACES_DIR))
    manifest = {'schemaVersion': '1.0', 'area': 'camanava_2026', 'bbox': list(BBOX), 'generatedAt': now(),
                'inputs': inputs, 'products': products, 'stats': stats,
                'notes': ['Overpass (overpass-api.de) refused connections from the build environment; buildings come from the '
                          'HOT OSM export on HDX (same ODbL OpenStreetMap data, snapshot 2026-10-12).',
                          'OSM building completeness is unknown.',
                          'WorldPop constrained: cells without built settlement carry no value and count as zero people.',
                          f'WorldCover classes: {WORLDCOVER_CLASSES}'],
                'populationProduct': 'constrained individual-country 100 m, BSGM, 2020'}
    mpath.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    total = sum(p['bytes'] for p in products.values())
    print({k: v['bytes'] for k, v in products.items()}, 'cache total bytes', total)


if __name__ == '__main__':
    main()
