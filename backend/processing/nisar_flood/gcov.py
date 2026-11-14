"""Windowed reader for NISAR L2 GCOV products (HHHH / HVHV backscatter on a projected grid).

Only the study-area window of the two datasets is read. The source can be a local file, an
https URL (HTTP range requests; needs EARTHDATA_TOKEN) or, as a fallback, a full download into
``backend/data/raw/``. Dataset paths are configuration (``constants.GcovLayout``), verified on
the first real file. Nothing here guesses a layout: a missing path is an error that names the path.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import h5py
import numpy as np
from pyproj import CRS
from scipy.ndimage import uniform_filter

from . import remote
from .constants import BACKEND_DIR, DEFAULT_LAYOUT, STUDY_BBOX, GcovLayout
from .geo import Grid, OutsideGrid, window_for_bbox

RAW_DIR = BACKEND_DIR / "data" / "raw" / "nisar"


class LayoutError(ValueError):
    """The file does not have the dataset the layout names; check docs/NISAR_RUNBOOK.md."""


@dataclass
class GcovWindow:
    hh_db: np.ndarray  # float32, NaN = nodata
    hv_db: np.ndarray
    grid: Grid
    meta: dict = field(default_factory=dict)

    @property
    def valid(self) -> np.ndarray:
        return np.isfinite(self.hh_db) & np.isfinite(self.hv_db)


def power_to_db(power: np.ndarray) -> np.ndarray:
    """10*log10 of linear power. NaN, zero and negative inputs become NaN (nodata), never a dB value."""
    p = np.asarray(power, dtype="float32")
    out = np.full(p.shape, np.nan, dtype="float32")
    ok = np.isfinite(p) & (p > 0)
    out[ok] = 10.0 * np.log10(p[ok])
    return out


def boxcar_power(power: np.ndarray, size: int) -> np.ndarray:
    """Mean of linear power over a size x size window using valid pixels only (speckle reduction).

    Nodata pixels stay nodata. They are never treated as zero power, and they do not pull neighbours down.
    """
    if size <= 1:
        return power
    p = np.asarray(power, dtype="float32")
    valid = np.isfinite(p) & (p > 0)
    num = uniform_filter(np.where(valid, p, 0.0).astype("float64"), size=size, mode="constant")
    den = uniform_filter(valid.astype("float64"), size=size, mode="constant")
    out = np.full(p.shape, np.nan, dtype="float32")
    ok = valid & (den > 0)
    out[ok] = (num[ok] / den[ok]).astype("float32")
    return out


def _require(handle: h5py.File, path: str) -> h5py.Dataset:
    if path not in handle:
        raise LayoutError(f"HDF5 path {path!r} is not in this file. Fix GcovLayout / --layout-* after inspecting the file "
                          "(see docs/NISAR_RUNBOOK.md, 'First real file').")
    obj = handle[path]
    if not isinstance(obj, h5py.Dataset):
        raise LayoutError(f"HDF5 path {path!r} is not a dataset")
    return obj


def _scalar_attr(dataset: h5py.Dataset | None, *names: str):
    if dataset is None:
        return None
    for name in names:
        if name in dataset.attrs:
            value = dataset.attrs[name]
            value = np.asarray(value).reshape(-1)[0] if np.asarray(value).size else None
            return value.decode() if isinstance(value, bytes) else (value.item() if hasattr(value, "item") else value)
    return None


def _read_crs(handle: h5py.File, layout: GcovLayout) -> tuple[str, str]:
    """Return (crs string, how it was determined). Never silently assumes a UTM zone."""
    path = layout.path(layout.projection)
    if path in handle:
        dataset = handle[path]
        epsg = _scalar_attr(dataset, "epsg_code", "epsg", "EPSG")
        if epsg is None and getattr(dataset, "shape", None) == () and np.issubdtype(dataset.dtype, np.integer):
            epsg = int(dataset[()])  # some products store the EPSG code as the scalar value itself
        if epsg is not None and int(epsg) > 0:
            return f"EPSG:{int(epsg)}", f"projection dataset ({path})"
        wkt = _scalar_attr(dataset, "spatial_ref", "crs_wkt", "wkt")
        if wkt:
            return CRS.from_user_input(str(wkt)).to_string(), f"projection WKT attribute ({path})"
    if layout.crs_fallback:
        return CRS.from_user_input(layout.crs_fallback).to_string(), "configured fallback (not read from the file)"
    raise LayoutError(f"Cannot determine the grid CRS from {path!r}; pass a crs fallback after checking the file.")


def read_gcov_window(handle: h5py.File, bbox=STUDY_BBOX, layout: GcovLayout = DEFAULT_LAYOUT, *,
                     speckle_window: int = 3, pad: int = 2) -> GcovWindow:
    """Read the study-area window of HHHH and HVHV from an open GCOV HDF5 file and convert to dB."""
    hh_ds = _require(handle, layout.path(layout.hh))
    hv_ds = _require(handle, layout.path(layout.hv))
    x_ds = _require(handle, layout.path(layout.x))
    y_ds = _require(handle, layout.path(layout.y))
    if hh_ds.shape != hv_ds.shape or hh_ds.ndim != 2:
        raise LayoutError(f"HH {hh_ds.shape} and HV {hv_ds.shape} must be matching 2-D rasters")
    if np.issubdtype(hh_ds.dtype, np.complexfloating) or np.issubdtype(hv_ds.dtype, np.complexfloating):
        raise LayoutError("HHHH/HVHV are complex; expected real covariance power on the diagonal")
    for ds in (hh_ds, hv_ds):
        units = _scalar_attr(ds, "units")
        if isinstance(units, str) and units.strip().lower() in {"db", "decibel", "decibels"}:
            raise LayoutError(f"{ds.name} is already in dB (units attribute); this reader expects linear power")
    x = np.asarray(x_ds[...], dtype="float64")
    y = np.asarray(y_ds[...], dtype="float64")
    if (y.size, x.size) != hh_ds.shape:
        raise LayoutError(f"Coordinate lengths (y={y.size}, x={x.size}) do not match the raster shape {hh_ds.shape}")
    crs, crs_how = _read_crs(handle, layout)
    rows, cols, grid, window_info = window_for_bbox(x, y, crs, bbox, coordinates_are=layout.coordinates_are, pad=pad + speckle_window // 2)

    def read_power(dataset: h5py.Dataset) -> np.ndarray:
        raw = np.asarray(dataset[rows, cols], dtype="float32")
        fill = dataset.attrs.get("_FillValue")
        if fill is not None:
            fill_value = float(np.asarray(fill).reshape(-1)[0])
            if np.isfinite(fill_value):
                raw = np.where(raw == fill_value, np.nan, raw)
        return raw

    hh_power, hv_power = read_power(hh_ds), read_power(hv_ds)
    mask_note = None
    if layout.mask:
        mask_ds = _require(handle, layout.path(layout.mask))
        mask = np.asarray(mask_ds[rows, cols])
        bad = ~(mask > 0)
        hh_power[bad] = np.nan
        hv_power[bad] = np.nan
        mask_note = f"validity mask {mask_ds.name} applied (value > 0 is valid)"
    hh_db = power_to_db(boxcar_power(hh_power, speckle_window))
    hv_db = power_to_db(boxcar_power(hv_power, speckle_window))
    if hh_db.shape != (grid.height, grid.width):
        raise LayoutError("Window shape does not match its grid; refusing to continue")

    both = np.isfinite(hh_db) & np.isfinite(hv_db)
    meta = {
        "window": window_info,
        "crs": crs, "crsSource": crs_how,
        "datasets": {"hh": hh_ds.name, "hv": hv_ds.name, "x": x_ds.name, "y": y_ds.name},
        "datasetAttrs": {"hh": {k: _attr_text(v) for k, v in hh_ds.attrs.items() if k in ("units", "description", "long_name", "grid_mapping", "_FillValue")},
                         "hv": {k: _attr_text(v) for k, v in hv_ds.attrs.items() if k in ("units", "description", "long_name", "grid_mapping", "_FillValue")}},
        "dtype": str(hh_ds.dtype), "fullShape": list(hh_ds.shape),
        "coordinatesAre": layout.coordinates_are,
        "speckleWindow": speckle_window,
        "validFractionOfWindow": float(both.mean()),
        "maskNote": mask_note,
        "dbRange": [float(np.nanmin(hh_db)), float(np.nanmax(hh_db))] if np.isfinite(hh_db).any() else None,
    }
    return GcovWindow(hh_db, hv_db, grid, meta)


def _attr_text(value) -> str | float | int | None:
    value = np.asarray(value)
    if value.size == 0:
        return None
    first = value.reshape(-1)[0]
    if isinstance(first, bytes):
        return first.decode("utf-8", "replace")
    return first.item() if hasattr(first, "item") else first


def read_window_from_source(source: str, *, token: str | None = None, allow_download: bool = False,
                            bbox=STUDY_BBOX, layout: GcovLayout = DEFAULT_LAYOUT, speckle_window: int = 3,
                            raw_dir: Path = RAW_DIR, expected_size: int | None = None,
                            expected_md5: str | None = None, log=print) -> tuple[GcovWindow, dict]:
    """Read the study window from a local path or an https URL. Returns (window, access info).

    Local paths are read directly. URLs are read with HTTP range requests (only the window's
    chunks move over the network). If that fails and ``allow_download`` is set, the whole file is
    downloaded into ``raw_dir`` (resumable, size/MD5 checked) and read locally.
    """
    is_url = source.startswith(("http://", "https://"))
    info: dict = {"source": remote._redact(source) if is_url else str(source)}
    if not is_url:
        path = Path(source).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"GCOV file not found: {path}")
        with h5py.File(path, "r") as handle:
            window = read_gcov_window(handle, bbox, layout, speckle_window=speckle_window)
        info.update(mode="local", sizeBytes=path.stat().st_size)
        return window, info
    if not token:
        raise remote.AuthError("EARTHDATA_TOKEN is not set. Create a token at https://urs.earthdata.nasa.gov/profile "
                               "(Generate Token) and export it; see docs/NISAR_RUNBOOK.md.")
    try:
        stream = remote.HttpRangeFile(source, token)
        try:
            with h5py.File(stream, "r") as handle:
                window = read_gcov_window(handle, bbox, layout, speckle_window=speckle_window)
            info.update(mode="remote-range", sizeBytes=stream.size, requests=stream.requests_made,
                        bytesFetched=stream.bytes_fetched)
            return window, info
        finally:
            stream.close()
    except remote.AuthError:
        raise
    except (remote.RemoteError, OSError) as exc:
        if not allow_download:
            raise remote.RemoteError(
                f"Remote windowed read failed ({type(exc).__name__}: {exc}). Re-run with --allow-download to fetch the whole file.") from exc
        log(f"  remote range read failed ({type(exc).__name__}); downloading the full file instead")
    local = remote.download(source, raw_dir, token, expected_md5=expected_md5, expected_size=expected_size,
                            progress=remote.print_progress)
    log("")
    with h5py.File(local, "r") as handle:
        window = read_gcov_window(handle, bbox, layout, speckle_window=speckle_window)
    info.update(mode="downloaded", localPath=str(local), sizeBytes=local.stat().st_size)
    return window, info


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
