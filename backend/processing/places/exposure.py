"""Exposure under a raster mask: area, population and buildings per place.

Method (all done on the mask's own grid, so a 10-30 m mask is not blurred to 100 m):

* mask pixel is "exposed" when it is finite, not the raster nodata value, and
  non-zero (or >= ``threshold`` when given). Nodata and NaN are never exposure.
* place of a pixel: the barangay (or city) polygon containing the pixel centre
  (pixel-centre rule; no polygon means the pixel is "unassigned", e.g. open sea).
* area: pixel area on an equal-area basis. Geographic masks use the exact
  ellipsoid-authalic-sphere area of each pixel (varies with latitude); projected
  masks are assumed to be in metres and to be locally equal-area (UTM error is
  well under 0.1 percent at this latitude and extent).
* population: the WorldPop 100 m cell count is converted to a density (people per
  km2, uniform inside the cell) and resampled onto the mask grid (nearest when the
  mask is finer than the population grid, area-average when it is coarser); each
  exposed pixel then contributes density x pixel area. A cell partly under the mask
  therefore contributes in proportion to the covered area, and a cell split by a
  barangay border is split in proportion to area. This assumes people are spread
  evenly inside a 100 m cell, which is not true; it is a documented approximation.
  Cells with no WorldPop value (constrained product: no built settlement) are zero.
* buildings: OSM footprint centroids whose pixel is exposed (centroid-in-pixel).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from pyproj import CRS, Transformer
from rasterio.features import rasterize
from rasterio.transform import Affine
from rasterio.warp import Resampling, reproject
from shapely.geometry import shape
from shapely.ops import transform as shp_transform

from . import path_for

AUTHALIC_RADIUS_M = 6371007.181
WGS84 = CRS.from_epsg(4326)


def _load_mask(mask, transform, crs, nodata, threshold):
    if isinstance(mask, (tuple, list)):
        arr, transform, *rest = mask
        crs = rest[0] if rest else crs
        mask = arr
    if isinstance(mask, (str, Path)):
        with rasterio.open(mask) as src:
            arr = src.read(1)
            transform, crs = src.transform, src.crs
            nodata = src.nodata if nodata is None else nodata
    else:
        arr = np.asarray(mask)
        if transform is None:
            raise ValueError('an array mask needs a transform')
    if arr.ndim != 2:
        raise ValueError('mask must be 2-D')
    crs = CRS.from_user_input(crs) if crs is not None else WGS84
    valid = np.ones(arr.shape, bool)
    if arr.dtype.kind == 'f':
        valid &= np.isfinite(arr)
    if nodata is not None and not (isinstance(nodata, float) and np.isnan(nodata)):
        valid &= arr != nodata
    exposed = valid & ((arr >= threshold) if threshold is not None else (arr != 0))
    return exposed, Affine(*tuple(transform)[:6]), crs


def pixel_area_km2(shape_hw, transform, crs):
    """Equal-area pixel areas (km2), shape (rows, cols)."""
    rows, cols = shape_hw
    if crs.is_geographic:
        dlon = np.radians(abs(transform.a))
        edges = transform.f + transform.e * np.arange(rows + 1)
        s = np.sin(np.radians(edges))
        per_row = AUTHALIC_RADIUS_M ** 2 * dlon * np.abs(np.diff(s)) / 1e6
        return np.repeat(per_row[:, None], cols, axis=1)
    return np.full(shape_hw, abs(transform.a * transform.e - transform.b * transform.d) / 1e6)


def _read_places(level, root):
    with open(path_for(level, root), encoding='utf-8') as fh:
        return json.load(fh)['features']


def _place_raster(features, shape_hw, transform, crs):
    tf = None if crs == WGS84 else Transformer.from_crs(WGS84, crs, always_xy=True).transform
    items = []
    for i, f in enumerate(features, start=1):
        g = shape(f['geometry'])
        items.append((shp_transform(tf, g) if tf else g, i))
    return rasterize(items, out_shape=shape_hw, transform=transform, fill=0, dtype='int32')


def _population_per_pixel(pop_path, shape_hw, transform, crs):
    """Returns (people per mask pixel, fraction of mask grid covered by the clip)."""
    with rasterio.open(pop_path) as src:
        pop = src.read(1).astype('float64')
        if src.nodata is not None:
            pop[pop == src.nodata] = 0.0
        pop[~np.isfinite(pop)] = 0.0
        pop[pop < 0] = 0.0
        cell = pixel_area_km2(pop.shape, src.transform, src.crs)
        density = (pop / cell).astype('float32')
        cover = np.ones(pop.shape, 'float32')
        out = np.zeros(shape_hw, 'float32')
        seen = np.zeros(shape_hw, 'float32')
        mask_px = abs(transform.a) if crs.is_projected else abs(transform.a) * 111_320.0
        src_px = abs(src.transform.a) * 111_320.0
        method = Resampling.nearest if mask_px <= src_px else Resampling.average
        reproject(density, out, src_transform=src.transform, src_crs=src.crs, dst_transform=transform,
                  dst_crs=crs, resampling=method)
        reproject(cover, seen, src_transform=src.transform, src_crs=src.crs, dst_transform=transform,
                  dst_crs=crs, resampling=Resampling.nearest)
    return out.astype('float64') * pixel_area_km2(shape_hw, transform, crs), seen


def _building_counts(path, shape_hw, transform, crs, exposed, place_idx, n_places):
    import pyarrow.parquet as pq
    t = pq.read_table(path, columns=['lon', 'lat'])
    lon, lat = t['lon'].to_numpy(), t['lat'].to_numpy()
    if crs != WGS84:
        lon, lat = Transformer.from_crs(WGS84, crs, always_xy=True).transform(lon, lat)
    inv = ~transform
    x, y = np.asarray(lon, 'float64'), np.asarray(lat, 'float64')
    col, row = inv.a * x + inv.b * y + inv.c, inv.d * x + inv.e * y + inv.f
    col, row = np.floor(col).astype(np.int64), np.floor(row).astype(np.int64)
    inside = (row >= 0) & (row < shape_hw[0]) & (col >= 0) & (col < shape_hw[1])
    row, col = row[inside], col[inside]
    keep = exposed[row, col] & (place_idx[row, col] > 0)
    return np.bincount(place_idx[row[keep], col[keep]], minlength=n_places + 1)


def exposure_for_mask(mask, level='barangay', *, transform=None, crs=None, nodata=None, threshold=None,
                      root=None, population_path=None, buildings_path=None, include_empty=False):
    """Exposure under ``mask`` (file path, array with ``transform``, or ``(array, transform[, crs])``)."""
    if level not in ('barangay', 'city'):
        raise ValueError("level must be 'barangay' or 'city'")
    exposed, transform, crs = _load_mask(mask, transform, crs, nodata, threshold)
    features = _read_places(level, root)
    n = len(features)
    place_idx = _place_raster(features, exposed.shape, transform, crs)
    area_px = pixel_area_km2(exposed.shape, transform, crs)
    assigned = exposed & (place_idx > 0)
    area = np.bincount(place_idx[assigned], weights=area_px[assigned], minlength=n + 1)
    unassigned_km2 = float(area_px[exposed & (place_idx == 0)].sum())
    warnings, limitations = [], ['exposure, not damage',
                                 'pixel-centre rule at barangay borders; boundaries are simplified (about 5 m)']

    pop = None
    pop_reason = None
    pop_path = Path(population_path) if population_path else path_for('population', root)
    if pop_path.exists():
        ppp, seen = _population_per_pixel(pop_path, exposed.shape, transform, crs)
        pop = np.bincount(place_idx[assigned], weights=ppp[assigned], minlength=n + 1)
        outside = float((exposed & (seen == 0)).sum())
        if outside:
            warnings.append(f'{int(outside)} exposed pixels lie outside the population clip and add no people')
        limitations.append('population assumes people are spread evenly inside each 100 m WorldPop cell')
    else:
        pop_reason = 'population clip not found; run backend/scripts/40_fetch_places.py'
        warnings.append(pop_reason)

    bld = None
    bld_reason = None
    b_path = Path(buildings_path) if buildings_path else path_for('buildings', root)
    if b_path.exists():
        bld = _building_counts(b_path, exposed.shape, transform, crs, exposed, place_idx, n)
        limitations.append('OSM building completeness is unknown; counts are mapped footprints only')
    else:
        bld_reason = 'building snapshot not found; run backend/scripts/40_fetch_places.py'
        warnings.append(bld_reason)

    zones = []
    for i, f in enumerate(features, start=1):
        if area[i] <= 0 and not include_empty:
            continue
        p = f['properties']
        zones.append({'placeId': p['id'], 'name': p['name'], 'city': p.get('city') or p['name'],
                      'areaKm2': round(float(area[i]), 4),
                      'population': None if pop is None else int(round(float(pop[i]))),
                      'buildings': None if bld is None else int(bld[i])})
    zones.sort(key=lambda z: (-(z['population'] or 0), -z['areaKm2'], z['placeId']))
    totals = {'areaKm2': round(float(area.sum()), 4),
              'population': None if pop is None else int(round(float(pop.sum()))),
              'buildings': None if bld is None else int(bld.sum()),
              'unassignedAreaKm2': round(unassigned_km2, 4)}
    return {'level': level, 'zones': zones, 'totals': totals,
            'populationUnavailableReason': pop_reason, 'buildingsUnavailableReason': bld_reason,
            'warnings': warnings, 'limitations': limitations}


def rhythm_mask(path, pass_count=None, min_fraction=0.5):
    """Boolean mask array from a flood-rhythm count raster: count >= ceil(min_fraction * pass_count).

    Returns ``(array, transform, crs)`` ready for :func:`exposure_for_mask`.
    """
    import math
    with rasterio.open(path) as src:
        a = src.read(1)
        nodata = src.nodata
        tf, crs = src.transform, src.crs
    valid = np.isfinite(a.astype('float64')) if a.dtype.kind == 'f' else np.ones(a.shape, bool)
    if nodata is not None:
        valid &= a != nodata
    if not pass_count:
        pass_count = int(a[valid].max()) if valid.any() else 0
    need = max(1, math.ceil(min_fraction * pass_count))
    return (valid & (a >= need)), tf, crs
