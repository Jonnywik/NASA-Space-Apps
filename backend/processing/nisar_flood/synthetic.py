"""SYNTHETIC GCOV-like fixtures. Not NISAR data. Used only for development, demos and tests.

The HDF5 files mimic the layout the reader expects (``/science/LSAR/GCOV/grids/frequencyA/...``) so the real
code path (windowing, dB, rules, exports) is exercised. Every number they contain is generated, never observed,
and every product built from them is labelled ``dataKind: "synthetic"``.
"""
from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np
from pyproj import Transformer

from .constants import DEFAULT_LAYOUT, STUDY_BBOX, GcovLayout

SYNTHETIC_BANNER = "SYNTHETIC FIXTURE - NOT NISAR DATA"


def flood_levels(n: int) -> list[float]:
    """A made-up wet-season wave of 'flood level' per pass (0 = dry, 1 = very high)."""
    base = [0.05, 0.12, 0.30, 0.22, 0.08, 0.42, 0.55, 0.28, 0.14, 0.36, 0.10, 0.20]
    return [base[i % len(base)] for i in range(n)]


def make_axes(bbox=STUDY_BBOX, spacing: float = 30.0, pad_m: float = 3000.0, epsg: int = 32651):
    to_utm = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    west, south, east, north = bbox
    xs, ys = to_utm.transform([west, east, west, east], [south, south, north, north])
    x0 = np.floor((min(xs) - pad_m) / spacing) * spacing + spacing / 2
    x1 = np.ceil((max(xs) + pad_m) / spacing) * spacing
    y_top = np.ceil((max(ys) + pad_m) / spacing) * spacing - spacing / 2
    y_bot = np.floor((min(ys) - pad_m) / spacing) * spacing
    x = np.arange(x0, x1, spacing)
    y = np.arange(y_top, y_bot, -spacing)
    return x, y


def _world(lon: np.ndarray, lat: np.ndarray) -> dict:
    """Deterministic made-up geography (not real land cover)."""
    coast = 120.935 + 0.012 * np.sin((lat - 14.6) * 40.0)
    sea = lon < coast
    elevation = np.clip((lon - coast) / 0.09, 0.0, 1.0) * 0.75 + 0.25 * (0.5 + 0.5 * np.sin(lon * 310.0) * np.cos(lat * 270.0))
    urban = (lon > 120.975) & (lat > 14.63) & (lat < 14.75)
    crops = (lat > 14.76) & (lon > coast + 0.01)
    ponds = (((lon > 120.945) & (lon < 120.965) & (lat > 14.775) & (lat < 14.79))
             | ((lon > 120.99) & (lon < 121.01) & (lat > 14.795) & (lat < 14.81)))
    return {"sea": sea, "elevation": elevation, "urban": urban, "crops": crops, "ponds": ponds}


def build_scene(lon, lat, level: float, rng: np.random.Generator, *, looks: int = 8) -> tuple[np.ndarray, np.ndarray]:
    """Linear-power HH and HV for one synthetic pass."""
    w = _world(lon, lat)
    hh = np.full(lon.shape, -10.0)
    hv = np.full(lon.shape, -17.0)
    hh[w["urban"]], hv[w["urban"]] = -3.0, -12.0
    hh[w["crops"]], hv[w["crops"]] = -10.0, -16.0
    flooded = (w["elevation"] < level) & ~w["sea"] & ~w["ponds"] & ~w["urban"]  # urban floods are invisible by construction
    veg_flood = w["crops"] & (w["elevation"] < level * 1.8) & ~flooded & ~w["ponds"] & (level > 0.15)
    hh[flooded], hv[flooded] = -23.0, -31.0
    hh[veg_flood] += 6.0
    hh[w["sea"] | w["ponds"]], hv[w["sea"] | w["ponds"]] = -23.0, -31.0
    power_hh = 10 ** (hh / 10.0) * rng.gamma(looks, 1.0 / looks, lon.shape)
    power_hv = 10 ** (hv / 10.0) * rng.gamma(looks, 1.0 / looks, lon.shape)
    return power_hh.astype("float32"), power_hv.astype("float32")


def write_synthetic_gcov(path: Path, *, level: float, seed: int, nodata_block: tuple[float, float, float, float] | None = None,
                         layout: GcovLayout = DEFAULT_LAYOUT, bbox=STUDY_BBOX, spacing: float = 30.0, epsg: int = 32651,
                         pad_m: float = 3000.0) -> Path:
    """Write one fake GCOV file. ``nodata_block`` = (west, south, east, north) lon/lat box set to NaN (no swath)."""
    x, y = make_axes(bbox, spacing, pad_m, epsg)
    xx, yy = np.meshgrid(x, y)
    lon, lat = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True).transform(xx, yy)
    rng = np.random.default_rng(seed)
    hh, hv = build_scene(lon, lat, level, rng)
    if nodata_block is not None:
        w, s, e, n = nodata_block
        block = (lon >= w) & (lon <= e) & (lat >= s) & (lat <= n)
        hh[block] = np.nan
        hv[block] = np.nan
    path.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(path, "w") as handle:
        handle.attrs["SYNTHETIC"] = SYNTHETIC_BANNER
        group = handle.create_group(layout.base.strip("/"))
        for name, data in ((layout.hh, hh), (layout.hv, hv)):
            ds = group.create_dataset(name, data=data, chunks=(min(256, data.shape[0]), min(256, data.shape[1])), compression="gzip", compression_opts=4)
            ds.attrs["_FillValue"] = np.float32("nan")
            ds.attrs["description"] = f"{SYNTHETIC_BANNER}: linear power"
        xs = group.create_dataset(layout.x, data=x)
        ys = group.create_dataset(layout.y, data=y)
        xs.attrs["units"] = "m"
        ys.attrs["units"] = "m"
        projection = group.create_dataset(layout.projection, data=np.int32(epsg))
        projection.attrs["epsg_code"] = np.int32(epsg)
    return path
