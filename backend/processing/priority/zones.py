"""Combine flood rhythm and cumulative positive-away LOS displacement."""
import json
import math
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Geod, Transformer
from rasterio.features import geometry_mask
from rasterio.warp import Resampling, reproject, transform_geom

from processing.p3 import catalog, core
from processing.places.exposure import exposure_for_mask


def _check_resolution(motion, rhythm):
    """Reject grids that would upsample the categorical flood data."""
    geod = Geod(ellps='WGS84')
    to_rhythm = Transformer.from_crs(motion.crs, rhythm.crs, always_xy=True)
    to_ll_motion = Transformer.from_crs(motion.crs, 'EPSG:4326', always_xy=True)
    to_ll_rhythm = Transformer.from_crs(rhythm.crs, 'EPSG:4326', always_xy=True)

    def dimensions(x, y, transform, to_ll):
        lon, lat = to_ll.transform(x, y)
        lengths = []
        for dx, dy in ((transform.a, transform.d), (transform.b, transform.e)):
            lon2, lat2 = to_ll.transform(x + dx, y + dy)
            lengths.append(abs(geod.inv(lon, lat, lon2, lat2)[2]))
        return lengths

    for col, row in ((0, 0), (motion.width, 0), (0, motion.height),
                     (motion.width, motion.height), (motion.width / 2, motion.height / 2)):
        x = motion.transform.a * col + motion.transform.b * row + motion.transform.c
        y = motion.transform.d * col + motion.transform.e * row + motion.transform.f
        rx, ry = to_rhythm.transform(x, y)
        target = dimensions(x, y, motion.transform, to_ll_motion)
        source = dimensions(rx, ry, rhythm.transform, to_ll_rhythm)
        if not all(math.isfinite(v) and v > 0 for v in target + source):
            raise ValueError('Cannot compare rhythm and motion grid resolution')
        if any(dst < src * (1 - 1e-6) for dst, src in zip(target, source)):
            raise ValueError('Rhythm grid is coarser than the motion grid; a coarser common grid is required (not supported)')


def _reference(motion, output_root, event):
    """Recover the reference region from a hash-bound upstream LOS pair."""
    runs = motion.get('sourceRunIds') or []
    hashes = motion.get('sourceManifestHashes') or {}
    if not runs:
        raise ValueError('Motion product has no upstream LOS pair; use --threshold-mm')
    run = core.safe_name(runs[0])
    path = Path(output_root) / event / 'p3' / 'los-pair' / run / 'manifest.json'
    if not path.is_file() or hashes.get(run) != core.digest(path):
        raise ValueError('Cannot verify upstream LOS pair reference; use --threshold-mm')
    pair = core.load_manifest(path)
    region = pair.get('referenceRegion') or {}
    if region.get('hash') != motion.get('spatialReferenceHash') or not region.get('hash'):
        raise ValueError('LOS pair reference does not match the motion product')
    return region


def _threshold(motion, data, grid, output_root, event, explicit, reference_mask):
    if explicit is not None:
        if not math.isfinite(explicit) or explicit < 0:
            raise ValueError('Threshold must be a finite non-negative number of mm')
        return {'valueMm': float(explicit), 'method': 'explicit'}
    region = _reference(motion, output_root, event)
    if region.get('geometry'):
        geom = transform_geom('EPSG:4326', grid.crs, region['geometry'])
        selected = geometry_mask([geom], data.shape, grid.transform, invert=True)
    elif region.get('type') == 'maskRaster' and reference_mask:
        if core.digest(reference_mask) != region.get('maskSourceSha256'):
            raise ValueError('Reference mask hash does not match the LOS-pair reference')
        with rasterio.open(reference_mask) as ref:
            if (ref.crs != grid.crs or ref.transform != grid.transform or
                    ref.width != grid.width or ref.height != grid.height):
                raise ValueError('Reference mask grid does not match motion grid')
            selected = ref.read(1, masked=True).filled(0) > 0
    else:
        raise ValueError('Reference geometry is unavailable; provide --reference-mask or --threshold-mm')
    values = data[selected & np.isfinite(data)]
    if values.size < 2:
        raise ValueError('At least two valid motion pixels in the reference area are required; use --threshold-mm')
    std = float(np.std(values))
    return {'valueMm': 2 * std, 'method': '2 x population standard deviation of cumulative LOS displacement in reference area',
            'standardDeviationMm': std, 'referencePixelCount': int(values.size), 'referenceHash': region['hash']}


def build_priority(output_root=core.OUTPUT_ROOT, event='camanava_2026', *, run_id=None,
                   threshold_mm=None, reference_mask=None, places_root=None):
    """Write a mask and exposure manifest from verified input products."""
    core.safe_name(event)
    output_root = Path(output_root)
    folder = output_root / event / 'nisar'
    rhythm_path = folder / 'rhythm_half.tif'
    rhythm_manifest_path = folder / 'manifest.json'
    if not rhythm_path.is_file() or not rhythm_manifest_path.is_file():
        raise ValueError('Flood rhythm mask or NISAR manifest is unavailable')
    rhythm_manifest = json.loads(rhythm_manifest_path.read_text(encoding='utf-8'))
    if rhythm_manifest.get('dataKind') not in ('observed', 'derived', 'synthetic'):
        raise ValueError('NISAR manifest must declare its dataKind')
    if (isinstance(rhythm_manifest.get('passCount'), bool) or
            not isinstance(rhythm_manifest.get('passCount'), int) or rhythm_manifest['passCount'] < 1):
        raise ValueError('NISAR manifest must declare a positive passCount')
    registered = (rhythm_manifest.get('assets') or {}).get('rhythm_half_tif')
    if registered is not None:
        if (not isinstance(registered, dict) or registered.get('path') != 'rhythm_half.tif' or
                registered.get('sha256') != core.digest(rhythm_path)):
            raise ValueError('Flood rhythm mask failed its registered path or SHA-256 check')
    try:
        motion = catalog.select(event, 'ground-motion', run_id, root=output_root)
    except catalog.ProductUnavailable as exc:
        raise ValueError(f'Ground-motion product unavailable: {exc} ({exc.code})') from exc
    if motion.get('displacementConvention') != 'positive_away_from_satellite':
        raise ValueError('Motion displacement must declare the positive-away-from-satellite convention')
    if (motion.get('units') or {}).get('displacementMm') != 'mm':
        raise ValueError('Motion displacement must be in millimetres')
    motion_path = core.asset_path(motion, 'displacementMm')
    with rasterio.open(motion_path) as grid:
        if not grid.crs:
            raise ValueError('Motion raster has no CRS')
        if grid.transform.b or grid.transform.d:
            raise ValueError('Exposure calculation requires a north-up motion grid')
        if grid.crs.is_projected and grid.crs.linear_units != 'metre':
            raise ValueError('Exposure calculation requires projected coordinates in metres')
        data = grid.read(1, masked=True).astype('float64').filled(np.nan)
        threshold = _threshold(motion, data, grid, output_root, event, threshold_mm, reference_mask)
        profile = grid.profile.copy()
        profile.update(driver='GTiff', count=1, dtype='uint8', nodata=255, compress='lzw')
        aligned = np.full(data.shape, 255, dtype='uint8')
        with rasterio.open(rhythm_path) as rhythm:
            if not rhythm.crs:
                raise ValueError('Rhythm raster has no CRS')
            _check_resolution(grid, rhythm)
            source = rhythm.read(1, masked=True)
            values = source.compressed()
            if not np.isin(values, [0, 1]).all():
                raise ValueError('Rhythm mask must contain only 0, 1 and declared nodata')
            reproject(source.filled(255).astype('uint8'), aligned,
                      src_transform=rhythm.transform, src_crs=rhythm.crs, src_nodata=255,
                      dst_transform=grid.transform, dst_crs=grid.crs, dst_nodata=255,
                      resampling=Resampling.nearest)
    valid = (aligned != 255) & np.isfinite(data)
    if not valid.any():
        raise ValueError('Flood rhythm and motion have no valid overlapping pixels')
    kind = 'synthetic' if (rhythm_manifest['dataKind'] == 'synthetic' or rhythm_manifest.get('syntheticLineage') or
                           motion['dataKind'] == 'synthetic' or motion.get('syntheticLineage')) else 'derived'
    with tempfile.TemporaryDirectory(prefix='.priority-', dir=folder) as tmp:
        tmp = Path(tmp)
        outputs = {}
        for label, factor in (('half', 0.5), ('base', 1.0), ('double', 2.0)):
            mask = np.where(valid, ((aligned == 1) & (data > threshold['valueMm'] * factor)).astype('uint8'), 255).astype('uint8')
            path = tmp / f'{label}.tif'
            with rasterio.open(path, 'w', **profile) as dst:
                dst.write(mask, 1)
            outputs[label] = exposure_for_mask(path, level='barangay', root=places_root)
        manifest = {
            'area': event, 'dataKind': kind, 'generatedAt': datetime.now(timezone.utc).isoformat(),
            'passCount': rhythm_manifest.get('passCount'), 'threshold': threshold,
            'grid': {'crs': profile['crs'].to_string(), 'transform': list(profile['transform'])[:6],
                     'width': profile['width'], 'height': profile['height']},
            'sensitivity': {label: {'thresholdMm': threshold['valueMm'] * factor, 'totals': outputs[label]['totals']}
                            for label, factor in (('half', 0.5), ('base', 1.0), ('double', 2.0))},
            'exposure': outputs['base'],
            'source': {'rhythmMaskSha256': core.digest(rhythm_path),
                       'rhythmManifestSha256': core.digest(rhythm_manifest_path),
                       'motionRunId': motion['runId'], 'motionManifestSha256': core.digest(Path(motion['_directory']) / 'manifest.json'),
                       'motionDisplacementSha256': core.digest(motion_path)},
            'maskSha256': core.digest(tmp / 'base.tif'),
            'method': 'Flooded on at least half of valid passes AND cumulative LOS displacement strictly greater than threshold, positive away from satellite. Nearest-neighbour rhythm on motion grid; either input nodata remains nodata.',
            'warnings': ['SYNTHETIC DEMO DATA; not observations'] if kind == 'synthetic' else [],
            'limitations': ['Exposure, not damage. LOS displacement is not necessarily vertical motion.',
                            'Sensitivity varies the motion threshold only; flood classification uncertainty is not assessed.'],
        }
        manifest_path = tmp / 'priority_manifest.json'
        manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        os.replace(tmp / 'base.tif', folder / 'priority_mask.tif')
        os.replace(manifest_path, folder / 'priority_manifest.json')
    return manifest
