"""Exports: PNG overlays (Web Mercator, with bounds), GeoTIFFs, rhythm legend, hashed manifest."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.transform import array_bounds
from rasterio.warp import Resampling, calculate_default_transform, reproject, transform_bounds

from .constants import COLOR_PERMANENT, COLOR_VEGETATION, COLOR_WATER
from .geo import Grid

MAX_SIDE = 2000


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def rhythm_colors(pass_count: int) -> list[str]:
    """Colour-blind-safe sequential palette (viridis, reversed so more floods = darker) for counts 1..N."""
    from matplotlib import colormaps
    cmap = colormaps["viridis_r"]
    n = max(pass_count, 1)
    return ["#%02x%02x%02x" % tuple(int(round(c * 255)) for c in cmap(0.08 + 0.9 * (k - 1) / max(n - 1, 1))[:3]) for k in range(1, n + 1)]


def write_png_overlay(rgba: np.ndarray, grid: Grid, path: Path, *, max_side: int = MAX_SIDE) -> list[list[float]]:
    """Reproject a north-up RGBA array to EPSG:3857 and save a transparent PNG.

    Returns Leaflet bounds [[south, west], [north, east]] (WGS84).
    """
    if rgba.shape[:2] != (grid.height, grid.width) or rgba.dtype != np.uint8 or rgba.shape[2] != 4:
        raise ValueError("RGBA array must be uint8 (H, W, 4) on the grid")
    left = grid.transform[2]
    top = grid.transform[5]
    right = left + grid.transform[0] * grid.width
    bottom = top + grid.transform[4] * grid.height
    dst_crs = "EPSG:3857"
    transform, width, height = calculate_default_transform(grid.crs, dst_crs, grid.width, grid.height, left, bottom, right, top)
    scale = max(width, height) / max_side
    if scale > 1:
        transform, width, height = calculate_default_transform(
            grid.crs, dst_crs, grid.width, grid.height, left, bottom, right, top,
            dst_width=int(width / scale), dst_height=int(height / scale))
    out = np.zeros((4, height, width), dtype="uint8")
    for band in range(4):
        reproject(source=np.ascontiguousarray(rgba[..., band]), destination=out[band], src_transform=grid.affine,
                  src_crs=grid.crs, dst_transform=transform, dst_crs=dst_crs, resampling=Resampling.nearest)
    Image.fromarray(np.moveaxis(out, 0, -1)).save(path, optimize=True)
    west, south, east, north = array_bounds(height, width, transform)
    w, s, e, n = transform_bounds(dst_crs, "EPSG:4326", west, south, east, north)
    return [[round(s, 6), round(w, 6)], [round(n, 6), round(e, 6)]]


def mask_rgba(mask: np.ndarray, color: str, alpha: int = 200) -> np.ndarray:
    rgba = np.zeros(mask.shape + (4,), dtype="uint8")
    rgba[mask] = (*hex_to_rgb(color), alpha)
    return rgba


def backscatter_rgba(db: np.ndarray, lo: float = -25.0, hi: float = 0.0) -> np.ndarray:
    """Greyscale dB image (dark = low backscatter). Nodata is transparent."""
    valid = np.isfinite(db)
    grey = np.clip((np.nan_to_num(db, nan=lo) - lo) / (hi - lo), 0, 1) * 255
    rgba = np.zeros(db.shape + (4,), dtype="uint8")
    rgba[..., :3] = grey.astype("uint8")[..., None]
    rgba[..., 3] = np.where(valid, 255, 0)
    return rgba


def rhythm_rgba(counts: np.ndarray, countable: np.ndarray, permanent: np.ndarray, pass_count: int) -> np.ndarray:
    rgba = np.zeros(counts.shape + (4,), dtype="uint8")
    rgba[permanent] = (*hex_to_rgb(COLOR_PERMANENT), 110)
    for count, color in enumerate(rhythm_colors(pass_count), start=1):
        rgba[countable & (counts == count)] = (*hex_to_rgb(color), 215)
    return rgba


def write_rhythm_legend(path: Path, pass_count: int, half_threshold_text: str, data_kind: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    colors = rhythm_colors(pass_count)
    handles = [Patch(facecolor=c, edgecolor="#333", label=f"flooded on {k} pass{'es' if k != 1 else ''}") for k, c in enumerate(colors, start=1)]
    handles.append(Patch(facecolor=COLOR_PERMANENT, edgecolor="#333", alpha=0.6, label="permanent water (masked)"))
    fig, ax = plt.subplots(figsize=(3.4, 0.32 * (len(handles) + 3)))
    ax.axis("off")
    ax.legend(handles=handles, loc="upper left", frameon=False, fontsize=8, title="Flood rhythm (NISAR passes)", title_fontsize=9)
    note = half_threshold_text + ("\nSYNTHETIC DEMO DATA, not NISAR observations" if data_kind == "synthetic" else "")
    ax.text(0.0, 0.0, note, fontsize=7, va="bottom", ha="left", transform=ax.transAxes, color="#8a1f11" if data_kind == "synthetic" else "#333")
    fig.savefig(path, dpi=140, bbox_inches="tight", transparent=False, facecolor="white")
    plt.close(fig)


def write_gtiff(path: Path, array: np.ndarray, grid: Grid, *, nodata, dtype: str | None = None, descriptions: list[str] | None = None) -> None:
    data = array if array.ndim == 3 else array[None, ...]
    dtype = dtype or str(data.dtype)
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", driver="GTiff", width=grid.width, height=grid.height, count=data.shape[0], dtype=dtype,
                       crs=grid.crs, transform=grid.affine, nodata=nodata, compress="deflate", predictor=2 if "float" in dtype else 1) as ds:
        ds.write(data.astype(dtype))
        for index, name in enumerate(descriptions or [], start=1):
            ds.set_band_description(index, name)


def register(assets: dict, root: Path, key: str, relative: str, kind: str, **extra) -> None:
    path = root / relative
    assets[key] = {"path": relative, "sha256": sha256_path(path), "bytes": path.stat().st_size, "kind": kind, **extra}


def swap_directory(stage: Path, final: Path) -> None:
    """Replace ``final`` with ``stage`` (rename-based; the old product is removed only after the new one is in place)."""
    backup = None
    if final.exists():
        backup = final.with_name(f".{final.name}-old-{uuid.uuid4().hex[:8]}")
        os.replace(final, backup)
    try:
        os.replace(stage, final)
    except OSError:
        if backup is not None:
            os.replace(backup, final)
        raise
    if backup is not None:
        shutil.rmtree(backup, ignore_errors=True)


def write_manifest(path: Path, manifest: dict) -> None:
    path.write_text(json.dumps(manifest, indent=1, allow_nan=False) + "\n")
