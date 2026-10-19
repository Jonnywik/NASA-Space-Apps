"""
helpers.py - shared tools used by all the other scripts.

Think of this file like a C header + library: the other scripts "import" it,
the same way a C program does #include "something.h".
You do not run this file directly.
"""
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling, transform_bounds
from rasterio.windows import Window, from_bounds

# The tanaw-backend folder (one level above the scripts folder)
ROOT = Path(__file__).resolve().parent.parent
EVENTS_FILE = ROOT / "events.json"


# ----------------------------------------------------------------------
# Finding events and folders
# ----------------------------------------------------------------------
def load_event(event_id):
    """Look up one event (a dictionary) in events.json by its id."""
    with open(EVENTS_FILE, encoding="utf-8") as f:
        events = json.load(f)
    for event in events:
        if event["id"] == event_id:
            return event
    known = ", ".join(e["id"] for e in events)
    raise SystemExit(f"Event '{event_id}' is not in events.json. Known events: {known}")


def raw_dir(event_id):
    """Folder where the downloaded radar files for this event live."""
    return ROOT / "data" / "raw" / event_id


def out_dir(event_id):
    """Folder where our results go (created if it does not exist)."""
    folder = ROOT / "data" / "output" / event_id
    folder.mkdir(parents=True, exist_ok=True)
    return folder


# ----------------------------------------------------------------------
# Radar maths
# ----------------------------------------------------------------------
def to_db(power):
    """Convert radar power values to decibels (dB): dB = 10 * log10(power).

    Radar power values are tiny numbers like 0.0063. Decibels turn them into
    friendlier numbers like -22 dB, and make water (very dark) easy to separate.
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        db = 10.0 * np.log10(power)
    db[~np.isfinite(db)] = np.nan
    return db.astype("float32")


# ----------------------------------------------------------------------
# Reading the two images so that they line up pixel-for-pixel
# ----------------------------------------------------------------------
def _read_aligned(path, shape, transform, crs):
    """Read a GeoTIFF and re-draw it onto the exact pixel grid we give it."""
    out = np.full(shape, np.nan, dtype="float32")
    with rasterio.open(path) as src:
        reproject(
            source=rasterio.band(src, 1),
            destination=out,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=transform,
            dst_crs=crs,
            resampling=Resampling.bilinear,
            src_nodata=0,
            dst_nodata=np.nan,
        )
    out[out <= 0] = np.nan
    return out


def load_pair(event):
    """Load the BEFORE and AFTER images, cut to the event's bbox.

    Returns: before, after, transform, crs
      before / after : 2-D arrays of radar POWER (np.nan where there is no data)
      transform      : maps pixel (row, col) to map coordinates (meters)
      crs            : the map projection (UTM zone, in meters)
    """
    folder = raw_dir(event["id"])
    before_path = folder / "before_VV.tif"
    after_path = folder / "after_VV.tif"
    for p in (before_path, after_path):
        if not p.exists():
            raise SystemExit(f"Cannot find {p}\nPut the file there (see the guide, Day 4).")

    west, south, east, north = event["bbox"]

    with rasterio.open(before_path) as src:
        crs = src.crs
        # turn the lon/lat box into the raster's own coordinates (UTM meters)
        left, bottom, right, top = transform_bounds("EPSG:4326", crs, west, south, east, north)
        win = from_bounds(left, bottom, right, top, transform=src.transform)

        col_off = max(int(np.floor(win.col_off)), 0)
        row_off = max(int(np.floor(win.row_off)), 0)
        col_end = min(int(np.ceil(win.col_off + win.width)), src.width)
        row_end = min(int(np.ceil(win.row_off + win.height)), src.height)

        if col_end <= col_off or row_end <= row_off:
            raise SystemExit(
                "The bbox in events.json is not inside this radar scene.\n"
                "Check the bbox numbers (west, south, east, north in lon/lat)."
            )

        window = Window(col_off, row_off, col_end - col_off, row_end - row_off)
        before = src.read(1, window=window).astype("float32")
        transform = src.window_transform(window)

    before[before <= 0] = np.nan
    after = _read_aligned(after_path, before.shape, transform, crs)
    return before, after, transform, crs


# ----------------------------------------------------------------------
# Saving a yes/no map as a GeoTIFF
# ----------------------------------------------------------------------
def save_mask(path, mask, transform, crs):
    """Save a uint8 map (0 = no, 1 = yes, 255 = no data) as a GeoTIFF."""
    with rasterio.open(
        path, "w", driver="GTiff",
        height=mask.shape[0], width=mask.shape[1], count=1, dtype="uint8",
        crs=crs, transform=transform, nodata=255, compress="lzw",
    ) as dst:
        dst.write(mask, 1)