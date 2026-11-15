"""N5: HH / HV / HH-over-HV polarization composite.

R = HH (dB), G = HV (dB), B = HH minus HV (dB, i.e. the HH/HV ratio). Fixed stretches (constants.RGB_STRETCH_DB)
so every date has the same colour meaning. Nodata is transparent.
"""
from __future__ import annotations

import numpy as np

from .constants import RGB_STRETCH_DB

CHANNELS = {"r": "HH", "g": "HV", "b": "HH/HV"}

EXPLANATION = [
    "Red is HH, green is HV and blue is HH divided by HV (a difference in dB). Each date uses the same fixed colour scale.",
    "Open water is dark in all three channels because a smooth surface reflects radar away from the satellite.",
    "Bright red or magenta means strong HH, typical of buildings and of water under plants (double-bounce). "
    "Green means strong HV, typical of leafy vegetation that scatters radar in many directions.",
]


def stretch(db: np.ndarray, lo: float, hi: float) -> np.ndarray:
    return np.clip((db - lo) / (hi - lo), 0.0, 1.0)


def polarization_rgba(hh_db: np.ndarray, hv_db: np.ndarray) -> np.ndarray:
    """Return a uint8 RGBA array (alpha 0 where HH or HV is nodata)."""
    valid = np.isfinite(hh_db) & np.isfinite(hv_db)
    ratio = hh_db - hv_db
    rgba = np.zeros(hh_db.shape + (4,), dtype="uint8")
    for index, (name, values) in enumerate((("r", hh_db), ("g", hv_db), ("b", ratio))):
        lo, hi = RGB_STRETCH_DB[name]
        rgba[..., index] = np.where(valid, stretch(np.nan_to_num(values, nan=lo), lo, hi) * 255.0, 0).astype("uint8")
    rgba[..., 3] = np.where(valid, 255, 0).astype("uint8")
    return rgba
