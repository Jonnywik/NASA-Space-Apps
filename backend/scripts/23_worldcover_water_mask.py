"""Script 23: known permanent-water mask for the NISAR flood rhythm (script 20 --permanent-mask).

Reads the cached ESA WorldCover 2021 clip (scripts/40_fetch_places.py) and writes a GeoTIFF where
WorldCover class 80 (permanent water bodies: Manila Bay, rivers, fishponds) is 1 and everything else 0.
Used so that the bay's nearshore strip, which crosses the SAR water threshold on some passes because
backscatter rises toward the coast, is never counted as flooding.
Usage: python scripts/23_worldcover_water_mask.py [--dilate-px N]
"""
import argparse
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

CACHE = Path(__file__).resolve().parent.parent / "data" / "cache" / "places"

ap = argparse.ArgumentParser()
ap.add_argument("--dilate-px", type=int, default=0, help="grow the water mask by N WorldCover pixels (10 m each)")
args = ap.parse_args()

src = CACHE / "esa_worldcover_2021_clip.tif"
with rasterio.open(src) as r:
    cls = r.read(1)
    prof = r.profile
water = cls == 80
if args.dilate_px:
    water = ndimage.binary_dilation(water, iterations=args.dilate_px)
prof.update(dtype="uint8", count=1, nodata=None, compress="lzw")
out = CACHE / "worldcover_water_mask.tif"
with rasterio.open(out, "w", **prof) as w:
    w.write(water.astype("uint8"), 1)
print(f"wrote {out} ({out.stat().st_size/1e3:.0f} kB); water share {water.mean()*100:.1f}% (dilate {args.dilate_px} px)")
