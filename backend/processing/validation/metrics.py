"""Comparison of normalized binary water rasters and threshold sensitivity."""
import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling
from processing.nisar_flood import water


def agreement(predicted, reference):
    """0=dry, 1=water, 255=nodata; undefined ratios are null."""
    predicted, reference = np.asarray(predicted), np.asarray(reference)
    if predicted.shape != reference.shape:
        raise ValueError("Arrays must share a grid")
    if not np.isin(predicted, [0, 1, 255]).all() or not np.isin(reference, [0, 1, 255]).all():
        raise ValueError("Only normalized binary classes 0, 1 and 255 are supported")
    valid = (predicted != 255) & (reference != 255)
    tp = int((valid & (predicted == 1) & (reference == 1)).sum())
    tn = int((valid & (predicted == 0) & (reference == 0)).sum())
    fp = int((valid & (predicted == 1) & (reference == 0)).sum())
    fn = int((valid & (predicted == 0) & (reference == 1)).sum())
    def ratio(a, b):
        return a / b if b else None
    return {"confusionMatrix": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
            "validPixels": tp + tn + fp + fn,
            "overallAgreement": ratio(tp + tn, tp + tn + fp + fn),
            "f1": ratio(2 * tp, 2 * tp + fp + fn), "iou": ratio(tp, tp + fp + fn)}


def compare_rasters(predicted_path, reference_path):
    """Nearest-neighbour onto an existing coarser grid, restricted to its footprint."""
    with rasterio.open(predicted_path) as p, rasterio.open(reference_path) as r:
        if not p.crs or p.crs != r.crs or p.transform.b or p.transform.d or r.transform.b or r.transform.d:
            raise ValueError("Rasters must use the same CRS and north-up grids")
        ps, rs = (abs(p.transform.a), abs(p.transform.e)), (abs(r.transform.a), abs(r.transform.e))
        if ps[0] >= rs[0] and ps[1] >= rs[1]:
            coarse = p
        elif rs[0] >= ps[0] and rs[1] >= ps[1]:
            coarse = r
        else:
            raise ValueError("Neither grid is coarser in both dimensions")
        arrays = []
        for src in (p, r):
            data = src.read(1, masked=True)
            values = data.compressed()
            if not np.isin(values, [0, 1]).all():
                raise ValueError("Normalize raster classes to 0=dry and 1=water first")
            target = np.full((coarse.height, coarse.width), 255, dtype="uint8")
            reproject(np.asarray(data.filled(255), dtype="uint8"), target,
                      src_transform=src.transform, src_crs=src.crs, src_nodata=255,
                      dst_transform=coarse.transform, dst_crs=coarse.crs, dst_nodata=255,
                      resampling=Resampling.nearest)
            arrays.append(target)
        return agreement(*arrays)


def sensitivity(hh, hv, rule, in_area, area_km2, min_valid_passes, permanent_fraction, external=None):
    """Reclassify pipeline dB passes in memory, with invalid samples represented by NaN."""
    if not hh or len(hh) != len(hv):
        raise ValueError("HH and HV pass lists must be nonempty and equal")
    result = {}
    for delta in (-1, 0, 1):
        adjusted = water.WaterRule(rule.hh_db + delta, rule.hv_db + delta)
        classified = [water.classify(h, v, adjusted) for h, v in zip(hh, hv)]
        masks, valid = map(list, zip(*classified))
        permanent, _ = water.permanent_water(masks, valid, fraction=permanent_fraction,
                                             min_valid_passes=min_valid_passes, external=external)
        permanent &= in_area
        flooded = [water.flooded_from(m, v, permanent) for m, v in classified]
        rhythm = water.compute_rhythm(flooded, valid, permanent, in_area, min_valid_passes=min_valid_passes)
        result[str(delta)] = water.rhythm_stats(rhythm, area_km2)["halfOrMoreKm2"]
    return {"halfOrMoreKm2": result, "changeKm2": {k: round(v - result['0'], 4) for k, v in result.items()}}
