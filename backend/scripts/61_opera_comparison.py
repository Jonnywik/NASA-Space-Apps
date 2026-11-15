"""Prepare three near-date OPERA references and compare an observed NISAR product."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from datetime import date

import numpy as np
import rasterio
from rasterio.warp import transform_bounds
from rasterio.windows import Window, from_bounds

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from processing.nisar_flood.geo import Grid, study_mask, pixel_area_km2
from processing.nisar_flood.pipeline import raster_on_grid
from processing.nisar_flood.water import WaterRule
from processing.validation.metrics import sensitivity
COLLECTION = 'C2949811996-POCLOUD'
MATCHES = [('20260915', 'G4361329706-POCLOUD'), ('20261009', 'G4361778874-POCLOUD'),
           ('20261102', 'G4408674689-POCLOUD')]
BBOX = (120.88, 14.60, 121.04, 14.82)


def digest(path, algorithm='sha256'):
    return hashlib.new(algorithm, path.read_bytes()).hexdigest()


def normalize_reference(source, target, allow_empty=False):
    with rasterio.open(source) as src:
        bounds = transform_bounds('EPSG:4326', src.crs, *BBOX, densify_pts=21)
        window = from_bounds(*bounds, transform=src.transform).round_offsets().round_lengths().intersection(
            Window(0, 0, src.width, src.height))
        values = src.read(1, window=window)
        if not np.isin(values, [0, 1, 250, 251, 255]).all():
            raise ValueError('Unexpected BWTR class')
        normalized = np.full(values.shape, 255, dtype='uint8')
        normalized[values == 0] = 0
        normalized[values == 1] = 1
        if not allow_empty and not (normalized != 255).any():
            raise ValueError('Reference has no valid pixels in study window')
        profile = src.profile.copy()
        profile.update(height=values.shape[0], width=values.shape[1], transform=src.window_transform(window),
                       nodata=255, compress='deflate')
        with rasterio.open(target, 'w', **profile) as dst:
            dst.write(normalized, 1)
        return int((normalized != 255).sum())


def prepare_reference(concept, out, allow_empty=False):
    url = f'https://cmr.earthdata.nasa.gov/search/granules.json?concept_id={concept}'
    entry = json.load(urlopen(url, timeout=30))['feed']['entry'][0]
    if entry['collection_concept_id'] != COLLECTION:
        raise ValueError('Unexpected CMR collection')
    source_url = next(link['href'] for link in entry['links'] if link.get('title', '').endswith('_B02_BWTR.tif'))
    checksum_url = next(link['href'] for link in entry['links'] if link.get('title', '').endswith('_B02_BWTR.tif.md5'))
    expected = urlopen(checksum_url, timeout=30).read().decode().split()[0].lower()
    source = out / source_url.rsplit('/', 1)[-1]
    if not source.exists():
        token = os.environ.get('EARTHDATA_TOKEN', '').strip()
        if not token:
            raise ValueError('Set EARTHDATA_TOKEN to download OPERA data')
        request = Request(source_url, headers={'Authorization': 'Bearer ' + token})
        with urlopen(request, timeout=90) as response:
            data = response.read()
        if hashlib.md5(data).hexdigest() != expected:
            raise ValueError('Downloaded OPERA file failed provider checksum')
        source.write_bytes(data)
    if digest(source, 'md5') != expected:
        raise ValueError('Cached OPERA file failed provider checksum')
    day = entry['time_start'][:10]
    target = out / f'dswx_s1_{concept}_{day.replace("-", "")}_camanava_binary.tif'
    valid_pixels = normalize_reference(source, target, allow_empty=allow_empty)
    return entry, source, target, expected, valid_pixels


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--product-dir', type=Path, default=BACKEND / 'data/output/camanava_2026/nisar')
    parser.add_argument('--out-dir', type=Path, default=BACKEND / 'data/raw/validation')
    parser.add_argument('--permanent-mask', type=Path, default=BACKEND / 'data/cache/places/worldcover_water_mask.tif')
    parser.add_argument('--prepare-only', action='store_true', help='fetch and normalize references without NISAR comparison')
    parser.add_argument('--scan', action='store_true', help='inspect all season references within two calendar days')
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    if args.scan:
        params = urlencode({'collection_concept_id': COLLECTION, 'bounding_box': ','.join(map(str, BBOX)),
                            'temporal': '2026-06-21T00:00:00Z,2026-11-04T23:59:59Z', 'page_size': 200})
        entries = json.load(urlopen('https://cmr.earthdata.nasa.gov/search/granules.json?' + params, timeout=30))['feed']['entry']
        dates = [date.fromisoformat(p['date']) for p in json.loads((BACKEND / 'data/cache/nisar/nisar_manifest_t140_A_f009_m4005.json').read_text())['gcov']]
        entries = [e for e in entries if min(abs((date.fromisoformat(e['time_start'][:10]) - d).days) for d in dates) <= 2]
        scan = []
        for entry in entries:
            ref, source, normalized, md5, count = prepare_reference(entry['id'], args.out_dir, allow_empty=True)
            scan.append({'granuleId': entry['id'], 'acquisitionTime': entry['time_start'], 'validPixels': count,
                         'sourceMd5': md5, 'binarySha256': digest(normalized)})
            print(entry['id'], entry['time_start'], count, flush=True)
        (args.out_dir / 'reference_scan.json').write_text(json.dumps(scan, indent=2) + '\n', encoding='utf-8')
        cache = BACKEND / 'data/cache/validation'
        cache.mkdir(parents=True, exist_ok=True)
        (cache / 'reference_scan.json').write_text(json.dumps(scan, indent=2) + '\n', encoding='utf-8')
        print('Scanned', len(scan), 'references;', sum(x['validPixels'] > 0 for x in scan), 'usable')
        return
    references = [prepare_reference(concept, args.out_dir) for _, concept in MATCHES]
    if args.prepare_only:
        print('Prepared and checksum-verified three OPERA reference rasters')
        return
    product = args.product_dir
    manifest_path = product / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('dataKind') != 'observed' or manifest.get('passCount') != 11:
        raise ValueError('Expected a completed 11-pass observed NISAR product')
    rule = manifest['rule']
    if rule['calibration']['status'] != 'calibrated':
        raise ValueError('Expected a calibrated water rule')
    reports = []
    for (pid, concept), (ref, ref_source, reference, md5, _) in zip(MATCHES, references):
        entry = next(x for x in manifest['passes'] if x['id'] == pid)
        asset = manifest['assets'][entry['assets']['db']]
        db = product / asset['path']
        if digest(db) != asset['sha256']:
            raise ValueError('NISAR db asset checksum mismatch')
        with rasterio.open(db) as src:
            hh = src.read(1, masked=True).filled(np.nan)
            hv = src.read(2, masked=True).filled(np.nan)
            valid = np.isfinite(hh) & np.isfinite(hv)
            if not valid.any():
                raise ValueError('NISAR pass has no valid pixels')
            values = np.full(hh.shape, 255, dtype='uint8')
            values[valid] = ((hh[valid] < rule['hhThresholdDb']) & (hv[valid] < rule['hvThresholdDb'])).astype('uint8')
            profile = src.profile.copy()
            profile.update(count=1, dtype='uint8', nodata=255, compress='deflate')
            normalized = args.out_dir / f'nisar_{pid}_total_open_water.tif'
            with rasterio.open(normalized, 'w', **profile) as dst:
                dst.write(values, 1)
        provenance = {
            'nisar': {'dataKind': 'derived', 'date': entry['date'], 'acquisitionTime': entry['acquisitionTime'],
                      'source': 'NISAR L2 GCOV threshold-derived total open water', 'url': entry['source']['url'],
                      'productId': entry['productId'], 'dbSha256': asset['sha256'], 'binarySha256': digest(normalized),
                      'rule': rule, 'productManifestSha256': digest(manifest_path)},
            'reference': {'dataKind': 'derived', 'date': ref['time_start'][:10], 'acquisitionTime': ref['time_start'],
                          'source': 'OPERA DSWx-S1 BWTR total water', 'url': f'https://cmr.earthdata.nasa.gov/search/concepts/{concept}.html',
                          'granuleId': concept, 'productId': ref['title'], 'sourceMd5': md5,
                          'binarySha256': digest(reference)},
        }
        provenance_path = args.out_dir / f'comparison_{pid}_provenance.json'
        provenance_path.write_text(json.dumps(provenance, indent=2) + '\n', encoding='utf-8')
        report = args.out_dir / f'comparison_{pid}_near_match.json'
        subprocess.run([sys.executable, str(BACKEND / 'scripts/60_validation.py'), '--nisar', str(normalized),
                        '--reference', str(reference), '--provenance', str(provenance_path), '--out', str(report)], check=True)
        reports.append(json.loads(report.read_text(encoding='utf-8')))
        print('Wrote', report)
    grid = Grid.from_dict(manifest['grid'])
    hh_passes, hv_passes = [], []
    for entry in manifest['passes']:
        asset = manifest['assets'][entry['assets']['db']]
        path = product / asset['path']
        if digest(path) != asset['sha256']:
            raise ValueError('NISAR db asset checksum mismatch')
        with rasterio.open(path) as src:
            hh_passes.append(src.read(1, masked=True).filled(np.nan))
            hv_passes.append(src.read(2, masked=True).filled(np.nan))
    permanent = manifest['permanentWater']
    mask_path = args.permanent_mask
    if digest(mask_path) != manifest['provenance']['permanentWaterMaskSha256']:
        raise ValueError('Permanent mask checksum mismatch')
    external = np.nan_to_num(raster_on_grid(mask_path, grid), nan=0.0) > 0
    result = sensitivity(hh_passes, hv_passes, WaterRule(rule['hhThresholdDb'], rule['hvThresholdDb']),
                         study_mask(grid, manifest['studyBbox']), pixel_area_km2(grid),
                         permanent['minValidPasses'], permanent['fraction'], external)
    baseline = manifest['rhythm']['halfOrMoreKm2']
    if abs(result['halfOrMoreKm2']['0'] - baseline) > 0.0001:
        raise ValueError(f'Sensitivity baseline differs from canonical product: {result} vs {baseline}')
    result['permanentMaskSha256'] = digest(mask_path)
    public = dict(reports[0])
    public['comparisons'] = reports
    public['sensitivity'] = result
    public['warnings'] = ['All three comparisons exceed 48 hours; they are near matches, not simultaneous observations.',
                          'Ground-motion comparison is unavailable.']
    public['limitations'].append('Total water includes permanent and coastal water; agreement does not measure flood-only accuracy.')
    cache = BACKEND / 'data/cache/validation'
    cache.mkdir(parents=True, exist_ok=True)
    for report in reports:
        date_id = report['source']['nisar']['date'].replace('-', '')
        (cache / f'comparison_{date_id}_near_match.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    (cache / 'camanava_2026.json').write_text(json.dumps(public, indent=2) + '\n', encoding='utf-8')
    print('Sensitivity:', result)


if __name__ == '__main__':
    main()
