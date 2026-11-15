"""NISAR L3 soil moisture (SME2) over the study area.

Reads the study window of the top-level `soilMoisture` layer (m3/m3, 200 m EASE-Grid 2.0) and its quality flag
from each SME2 granule, keeps only retrievals the product marks as recommended (least significant bit of
`retrievalQualityFlag` == 0), and summarises them per pass. Missing or not-recommended pixels are nodata,
never zero. Water bodies are excluded using the product's own `waterbodyFraction` layer.
"""
from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

GRID = "science/LSAR/SME2/grids"
FILL = -9999.0
WATER_FRACTION_MAX = 0.5  # cells more than half water are excluded

# Sequential brown -> teal ramp (dry -> wet), readable by people with colour-vision deficiency.
RAMP = [(0.0, (166, 97, 26)), (0.15, (223, 194, 125)), (0.30, (245, 245, 245)), (0.45, (128, 205, 193)), (0.60, (1, 133, 113))]


def lat_lon_window(lat: np.ndarray, lon: np.ndarray, bbox, pad: int = 2) -> tuple[slice, slice]:
    """Row/column slices of 1-D latitude/longitude axes covering bbox (W, S, E, N), with a small pad."""
    west, south, east, north = bbox
    rows = np.where((lat >= south) & (lat <= north))[0]
    cols = np.where((lon >= west) & (lon <= east))[0]
    if rows.size == 0 or cols.size == 0:
        raise ValueError("study bbox is outside this soil-moisture grid")
    r0, r1 = max(rows.min() - pad, 0), min(rows.max() + pad + 1, lat.size)
    c0, c1 = max(cols.min() - pad, 0), min(cols.max() + pad + 1, lon.size)
    return slice(int(r0), int(r1)), slice(int(c0), int(c1))


def recommended_mask(soil: np.ndarray, flag: np.ndarray, water_fraction: np.ndarray | None) -> np.ndarray:
    """True where the retrieval is valid, recommended by the product, and the cell is mostly land."""
    ok = np.isfinite(soil) & (soil != FILL) & (soil >= 0) & (soil <= 1)
    ok &= (flag != -9999) & ((flag.astype(np.int64) & 1) == 0)
    if water_fraction is not None:
        wf = np.where(water_fraction == FILL, np.nan, water_fraction)
        ok &= ~(np.nan_to_num(wf, nan=0.0) > WATER_FRACTION_MAX)
    return ok


def read_window(handle, bbox) -> dict:
    lat = handle[f"{GRID}/latitude"][...]
    lon = handle[f"{GRID}/longitude"][...]
    rows, cols = lat_lon_window(lat, lon, bbox)
    soil = handle[f"{GRID}/soilMoisture"][rows, cols].astype("float64")
    unc = handle[f"{GRID}/soilMoistureUncertainty"][rows, cols].astype("float64")
    flag = handle[f"{GRID}/retrievalQualityFlag"][rows, cols]
    wf_path = f"{GRID}/ancillaryData/waterbodyFraction"
    wf = handle[wf_path][rows, cols].astype("float64") if wf_path in handle else None
    return {"lat": lat[rows].astype("float64"), "lon": lon[cols].astype("float64"), "soil": soil, "uncertainty": unc,
            "flag": flag, "waterFraction": wf}


def summarise(window: dict, bbox) -> dict:
    """Per-pass statistics over recommended land pixels inside the exact study bbox."""
    west, south, east, north = bbox
    inside = np.outer((window["lat"] >= south) & (window["lat"] <= north), (window["lon"] >= west) & (window["lon"] <= east))
    ok = recommended_mask(window["soil"], window["flag"], window["waterFraction"]) & inside
    n_inside = int(inside.sum())
    if ok.sum() == 0:
        return {"medianM3M3": None, "meanM3M3": None, "p10M3M3": None, "p90M3M3": None, "medianUncertaintyM3M3": None,
                "recommendedPixels": 0, "studyPixels": n_inside, "recommendedFraction": 0.0,
                "missingReason": "no recommended retrievals inside the study area"}
    v = window["soil"][ok]
    u = window["uncertainty"][ok]
    u = u[np.isfinite(u) & (u != FILL)]
    return {
        "medianM3M3": round(float(np.median(v)), 4), "meanM3M3": round(float(np.mean(v)), 4),
        "p10M3M3": round(float(np.percentile(v, 10)), 4), "p90M3M3": round(float(np.percentile(v, 90)), 4),
        "medianUncertaintyM3M3": round(float(np.median(u)), 4) if u.size else None,
        "recommendedPixels": int(ok.sum()), "studyPixels": n_inside,
        "recommendedFraction": round(float(ok.sum()) / n_inside, 4) if n_inside else 0.0,
    }


def colourise(soil: np.ndarray, ok: np.ndarray) -> np.ndarray:
    """RGBA image: ramp colours for recommended pixels, transparent elsewhere."""
    stops = np.array([s for s, _ in RAMP])
    cols = np.array([c for _, c in RAMP], dtype="float64")
    val = np.clip(np.nan_to_num(soil, nan=0.0), stops[0], stops[-1])
    rgb = np.stack([np.interp(val, stops, cols[:, i]) for i in range(3)], axis=-1)
    alpha = np.where(ok, 210, 0)
    return np.dstack([rgb, alpha]).astype("uint8")


def png_bytes(rgba: np.ndarray) -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def bounds_of(window: dict) -> list:
    lat, lon = window["lat"], window["lon"]
    dlat = abs(float(lat[1] - lat[0])) / 2 if lat.size > 1 else 0.0
    dlon = abs(float(lon[1] - lon[0])) / 2 if lon.size > 1 else 0.0
    return [[round(float(lat.min()) - dlat, 6), round(float(lon.min()) - dlon, 6)],
            [round(float(lat.max()) + dlat, 6), round(float(lon.max()) + dlon, 6)]]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1))
