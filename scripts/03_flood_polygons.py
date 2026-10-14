"""
Script 3: FLOOD = water AFTER and NOT water BEFORE.
Then turn the flood pixels into map shapes (polygons) and measure the area.

Run it:
    python scripts/03_flood_polygons.py test_event

Writes (in data/output/<event>/):
    flood.geojson         the flood shapes, ready for the map
    flood_extent.json     the numbers (km2 flooded, dates, ...) for the sidebar
    03_flood_check.png    a picture to check the result by eye
"""
import argparse
import json

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.features import shapes
from scipy.ndimage import label
from shapely.geometry import shape

from helpers import load_event, out_dir

parser = argparse.ArgumentParser()
parser.add_argument("event_id")
parser.add_argument("--min-pixels", type=int, default=10,
                    help="throw away flood blobs smaller than this many pixels (default 10)")
parser.add_argument("--simplify", type=float, default=15.0,
                    help="make shapes simpler, in meters (default 15)")
args = parser.parse_args()

event = load_event(args.event_id)
folder = out_dir(args.event_id)

# ---- 1. read the two water maps made by script 2 ----
with rasterio.open(folder / "water_before.tif") as src:
    water_before = src.read(1)
    transform = src.transform
    crs = src.crs
with rasterio.open(folder / "water_after.tif") as src:
    water_after = src.read(1)

if not crs.is_projected:
    raise SystemExit("The map must be in meters (UTM) to measure area. Ask Adz.")

# ---- 2. the flood: water now, but NOT water before ----
valid = (water_before != 255) & (water_after != 255)
flood = (water_after == 1) & (water_before == 0) & valid
print("Flood pixels before cleaning:", int(flood.sum()))

# ---- 3. remove tiny specks (they are noise, not floods) ----
labels, count = label(flood, structure=np.ones((3, 3)))  # give every blob a number
sizes = np.bincount(labels.ravel())                      # how many pixels in each blob
keep = sizes >= args.min_pixels
keep[0] = False                                          # blob 0 = the background
flood = keep[labels]
print("Flood pixels after cleaning :", int(flood.sum()), f"({int(keep.sum())} blobs kept)")

# ---- 4. area in km2. UTM is in meters, so pixel area = width x height ----
pixel_area_m2 = abs(transform.a * transform.e)
km2_flooded = float(flood.sum() * pixel_area_m2 / 1e6)
water_before_km2 = float((water_before == 1).sum() * pixel_area_m2 / 1e6)
water_after_km2 = float((water_after == 1).sum() * pixel_area_m2 / 1e6)
print(f"Flooded area: {km2_flooded:.2f} km2")

# ---- 5. pixels -> polygons ----
geoms = [shape(geom) for geom, value in
         shapes(flood.astype("uint8"), mask=flood, transform=transform, connectivity=8)]
gdf = gpd.GeoDataFrame({"geometry": geoms}, crs=crs)

if len(gdf) > 0:
    gdf["geometry"] = gdf.geometry.simplify(args.simplify, preserve_topology=True)
    gdf = gdf[~gdf.geometry.is_empty].copy()
    gdf["area_km2"] = (gdf.geometry.area / 1e6).round(4)  # measured while still in meters
    gdf = gdf.to_crs("EPSG:4326")                         # the web map uses lon/lat

geojson_path = folder / "flood.geojson"
if len(gdf) > 0:
    gdf.to_file(geojson_path, driver="GeoJSON", COORDINATE_PRECISION=5)
else:
    geojson_path.write_text('{"type": "FeatureCollection", "features": []}')

size_mb = geojson_path.stat().st_size / 1e6
print(f"Polygons: {len(gdf)}   GeoJSON size: {size_mb:.2f} MB")
if size_mb > 15:
    print("  That file is big for a web map. Try: --simplify 30 --min-pixels 25")

# ---- 6. the numbers file (the API sends this to the frontend) ----
info_path = folder / "02_info.json"
threshold = json.loads(info_path.read_text())["threshold_db"] if info_path.exists() else None

result = {
    "event": event["id"],
    "aoi": event["aoi"],
    "beforeDate": event["before_date"],
    "afterDate": event["after_date"],
    "stats": {
        "km2Flooded": round(km2_flooded, 2),
        "peopleExposed": None,        # needs population data - later
        "householdsExposed": None,    # needs population data - later
        "waterBeforeKm2": round(water_before_km2, 2),
        "waterAfterKm2": round(water_after_km2, 2),
    },
    "polygonCount": int(len(gdf)),
    "thresholdDb": threshold,
    "bbox": [round(v, 5) for v in gdf.total_bounds] if len(gdf) > 0 else event["bbox"],
}
(folder / "flood_extent.json").write_text(json.dumps(result, indent=2))

# ---- 7. a picture to check by eye: blue = water that was always there, red = new flood ----
picture = np.full(flood.shape + (3,), 225, dtype="uint8")  # grey land
picture[water_before == 1] = (50, 100, 220)                # blue
picture[flood] = (220, 40, 40)                             # red
picture[~valid] = (255, 255, 255)                          # white = no data

step = max(1, max(flood.shape) // 1500)
fig, ax = plt.subplots(figsize=(10, 8))
ax.imshow(picture[::step, ::step])
ax.set_title(f"{event['name']}\nblue = permanent water, red = FLOOD ({km2_flooded:.1f} km2)")
ax.axis("off")
fig.tight_layout()
fig.savefig(folder / "03_flood_check.png", dpi=80)
print("Saved:", folder / "03_flood_check.png")
print("Saved:", folder / "flood_extent.json")