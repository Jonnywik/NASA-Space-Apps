"""
Script 4: make the before/after pictures for the website's slider.

Run it AFTER scripts 02 and 03:
    python scripts/04_export_overlays.py test_event

Why: the website map can only draw ordinary pictures (PNG) on top of the map.
Script 2 made water maps as GeoTIFF files, which a browser cannot show.
This script turns each one into a see-through PNG (blue = water, empty = nothing)
and records where on Earth the picture goes.

Writes (in data/output/<event>/):
    water_before.png   see-through PNG for the LEFT side of the slider
    water_after.png    see-through PNG for the RIGHT side of the slider
    overlays.json      the corner coordinates the map needs to place the PNGs
"""
import argparse
import json

import numpy as np
import rasterio
from PIL import Image
from rasterio.transform import array_bounds
from rasterio.warp import Resampling, calculate_default_transform, reproject, transform_bounds

from helpers import load_event, out_dir

MAX_SIDE = 2000                    # keep PNGs small enough for a web page
WATER_RGBA = (40, 110, 230, 190)   # blue, a little see-through

parser = argparse.ArgumentParser()
parser.add_argument("event_id")
args = parser.parse_args()

load_event(args.event_id)          # stops with a clear message if the id is wrong
folder = out_dir(args.event_id)


def mask_to_png(tif_path, png_path):
    """Turn a water map (1 = water) into a see-through PNG.

    The picture is re-drawn in "Web Mercator" (EPSG:3857), the projection that
    web maps use, so it lines up with the map tiles. Returns the picture's
    corners as (west, south, east, north) in longitude / latitude.
    """
    dst_crs = "EPSG:3857"
    with rasterio.open(tif_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, dst_crs, src.width, src.height, *src.bounds)

        # shrink very big pictures
        scale = max(width, height) / MAX_SIDE
        if scale > 1:
            transform, width, height = calculate_default_transform(
                src.crs, dst_crs, src.width, src.height, *src.bounds,
                dst_width=int(width / scale), dst_height=int(height / scale))

        out = np.full((height, width), 255, dtype="uint8")       # 255 = no data
        reproject(
            source=rasterio.band(src, 1), destination=out,
            src_transform=src.transform, src_crs=src.crs,
            dst_transform=transform, dst_crs=dst_crs,
            resampling=Resampling.nearest, src_nodata=255, dst_nodata=255,
        )

    rgba = np.zeros((height, width, 4), dtype="uint8")           # all see-through
    rgba[out == 1] = WATER_RGBA                                  # water pixels = blue
    Image.fromarray(rgba).save(png_path, optimize=True)

    west, south, east, north = array_bounds(height, width, transform)
    return transform_bounds(dst_crs, "EPSG:4326", west, south, east, north)


bounds = None
for which in ("before", "after"):
    tif = folder / f"water_{which}.tif"
    if not tif.exists():
        raise SystemExit(f"Cannot find {tif}. Run script 02 first.")
    png = folder / f"water_{which}.png"
    b = mask_to_png(tif, png)
    print(f"Saved {png.name}  ({png.stat().st_size / 1e6:.2f} MB)")
    bounds = bounds or b

west, south, east, north = bounds
# Leaflet wants [[south, west], [north, east]]
info = {"bounds": [[round(south, 6), round(west, 6)], [round(north, 6), round(east, 6)]]}
(folder / "overlays.json").write_text(json.dumps(info, indent=2))
print("Saved overlays.json:", info["bounds"])
