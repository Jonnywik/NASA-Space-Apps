"""N4: possible flooded vegetation (L-band HH double-bounce), kept apart from open water.

Idea: standing water under emergent vegetation or crops (rice, fishpond margins, mangrove, marsh) makes a
water-surface/stem double-bounce, so HH becomes BRIGHTER than the same pixel's own dry-season-state backscatter.
The class is "HH brightening above a per-pixel reference by at least ``margin_db``", on pixels that are not open
water and not permanent water. The reference is the per-pixel median HH (dB) over the season's valid passes
that were not open water on that pixel.

Why a per-pixel reference: urban double-bounce is bright on every date, so it does not brighten relative to its own
reference and is not flagged. Only change is flagged.

Limits (stated in the product): soil moisture, crop growth and rain on vegetation also brighten HH, so this is
"possible flooded vegetation", not a confirmed flood. A pixel flooded on most passes has a contaminated reference.
Without a land-cover mask the class can include non-vegetated change; pass a WorldCover raster to restrict it.
"""
from __future__ import annotations

import warnings

import numpy as np

from .constants import DEFAULT_VEGETATION_LANDCOVER_CLASSES, DEFAULT_VEGETATION_MARGIN_DB


def dry_reference_db(hh_db: list[np.ndarray], water: list[np.ndarray], *, min_reference_passes: int = 3,
                     band_rows: int = 256) -> np.ndarray:
    """Per-pixel median HH dB over passes that are valid and not open water. NaN if fewer than the minimum."""
    stack_shape = hh_db[0].shape
    reference = np.full(stack_shape, np.nan, dtype="float32")
    for r0 in range(0, stack_shape[0], band_rows):
        r1 = min(r0 + band_rows, stack_shape[0])
        band = np.stack([np.where(np.isfinite(h[r0:r1]) & ~w[r0:r1], h[r0:r1], np.nan) for h, w in zip(hh_db, water)])
        count = np.isfinite(band).sum(axis=0)
        with np.errstate(all="ignore"), warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN columns are expected (never valid)
            med = np.nanmedian(band, axis=0)
        med[count < min_reference_passes] = np.nan
        reference[r0:r1] = med.astype("float32")
    return reference


def landcover_candidate_mask(landcover: np.ndarray | None, classes=DEFAULT_VEGETATION_LANDCOVER_CLASSES) -> np.ndarray | None:
    if landcover is None:
        return None
    return np.isin(landcover, list(classes))


def flooded_vegetation(hh_db: np.ndarray, reference_db: np.ndarray, water: np.ndarray, permanent: np.ndarray,
                       in_area: np.ndarray, *, margin_db: float = DEFAULT_VEGETATION_MARGIN_DB,
                       candidate: np.ndarray | None = None) -> np.ndarray:
    """Boolean mask of possible flooded vegetation for one pass. Never overlaps open water or permanent water."""
    with np.errstate(invalid="ignore"):
        brightened = (hh_db - reference_db) >= margin_db
    mask = brightened & np.isfinite(hh_db) & np.isfinite(reference_db) & ~water & ~permanent & in_area
    if candidate is not None:
        mask &= candidate
    return mask
