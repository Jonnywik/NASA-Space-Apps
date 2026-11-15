"""Exploratory NISAR layers built from data already cached by scripts 20, 24 and 31.

rain_response: per-cell Spearman rank correlation between NISAR HH backscatter (dB) and the 48-hour NASA GPM IMERG
    rain before each pass. Positive = the radar gets brighter after rain (usually wetter soil or vegetation).
coherence_drop: interferometric coherence on the pair spanning a storm, compared with the median of the calm pairs.
    Positive = coherence was lost across the storm. Loss can come from water, vegetation change, construction or noise.
Neither layer is a flood map. Cells with missing inputs stay NaN (never 0).
"""
from __future__ import annotations

import numpy as np

LANDCOVER_NAMES = {10: "Tree cover", 20: "Shrubland", 30: "Grassland", 40: "Cropland", 50: "Built-up",
                   60: "Bare / sparse", 80: "Water", 90: "Herbaceous wetland", 95: "Mangroves"}

RESPONSE_STOPS = [(-1.0, "#2166AC"), (-0.5, "#92C5DE"), (0.0, "#F7F7F7"), (0.5, "#F4A582"), (1.0, "#B35806")]
DROP_STOPS = [(0.05, "#FDE0EF"), (0.2, "#F1B6DA"), (0.35, "#DE77AE"), (0.5, "#C51B7D"), (0.7, "#4D004B")]


def block_mean(a: np.ndarray, k: int) -> np.ndarray:
    """Mean over non-overlapping k x k blocks (NaN-aware; all-NaN blocks stay NaN). Trailing rows/cols are dropped."""
    h, w = (a.shape[-2] // k) * k, (a.shape[-1] // k) * k
    a = a[..., :h, :w]
    shaped = a.reshape(a.shape[:-2] + (h // k, k, w // k, k))
    with np.errstate(invalid="ignore"), np.testing.suppress_warnings() as sup:
        sup.filter(RuntimeWarning)
        return np.nanmean(shaped, axis=(-3, -1))


def _ranks(x: np.ndarray, axis: int = 0) -> np.ndarray:
    """Average ranks along axis (ties share the mean rank)."""
    from scipy.stats import rankdata
    return rankdata(x, axis=axis, method="average")


def spearman_per_cell(stack: np.ndarray, series: np.ndarray, min_n: int = 6) -> np.ndarray:
    """Spearman rho between each cell's values over time (stack: n x H x W) and one series (n,).

    A cell is NaN when fewer than min_n time steps have finite values, or when it doesn't vary.
    """
    stack = np.asarray(stack, dtype="float64")
    series = np.asarray(series, dtype="float64")
    if stack.shape[0] != series.shape[0]:
        raise ValueError("stack and series lengths differ")
    out = np.full(stack.shape[1:], np.nan)
    finite = np.isfinite(stack) & np.isfinite(series)[:, None, None]
    counts = finite.sum(axis=0)
    full = counts == stack.shape[0]
    if full.any() and stack.shape[0] >= min_n:
        rx = _ranks(stack[:, full], axis=0)
        ry = _ranks(series)[:, None]
        rx = rx - rx.mean(axis=0)
        ry = ry - ry.mean()
        den = np.sqrt((rx ** 2).sum(axis=0) * (ry ** 2).sum())
        with np.errstate(invalid="ignore", divide="ignore"):
            out[full] = np.where(den > 0, (rx * ry).sum(axis=0) / den, np.nan)
    # cells with some missing time steps: compute individually (rare)
    partial = (~full) & (counts >= min_n)
    for r, c in zip(*np.nonzero(partial)):
        m = finite[:, r, c]
        x = _ranks(stack[m, r, c])
        y = _ranks(series[m])
        x, y = x - x.mean(), y - y.mean()
        den = np.sqrt((x ** 2).sum() * (y ** 2).sum())
        out[r, c] = (x * y).sum() / den if den > 0 else np.nan
    return out


def coherence_drop(storm: np.ndarray, calm: np.ndarray) -> np.ndarray:
    """median(calm pairs) - storm pair coherence. calm: k x H x W. NaN where inputs are missing."""
    with np.errstate(invalid="ignore"), np.testing.suppress_warnings() as sup:
        sup.filter(RuntimeWarning)
        base = np.nanmedian(np.asarray(calm, dtype="float64"), axis=0)
    return base - np.asarray(storm, dtype="float64")


def ramp_rgba(values: np.ndarray, stops, *, alpha: int = 215, transparent_below: float | None = None) -> np.ndarray:
    """Colour a float array with a piecewise-linear ramp; NaN (and values below transparent_below) are transparent."""
    xs = np.array([s for s, _ in stops], dtype="float64")
    cols = np.array([[int(c[i:i + 2], 16) for i in (1, 3, 5)] for _, c in stops], dtype="float64")
    v = np.clip(np.nan_to_num(values, nan=xs[0]), xs[0], xs[-1])
    rgb = np.stack([np.interp(v, xs, cols[:, i]) for i in range(3)], axis=-1)
    visible = np.isfinite(values)
    if transparent_below is not None:
        visible &= values >= transparent_below
    a = np.where(visible, alpha, 0)
    return np.dstack([rgb, a]).astype("uint8")


def by_landcover(values: np.ndarray, landcover: np.ndarray, *, stat=np.nanmedian, min_cells: int = 20) -> list[dict]:
    rows = []
    for cls, name in LANDCOVER_NAMES.items():
        m = (landcover == cls) & np.isfinite(values)
        n = int(m.sum())
        if n >= min_cells:
            rows.append({"class": cls, "name": name, "cells": n, "median": round(float(stat(values[m])), 3)})
    return rows
