"""
make_test_data.py - makes FAKE before/after radar images for practice.

Run it:
    python scripts/make_test_data.py

It writes:
    data/raw/test_event/before_VV.tif
    data/raw/test_event/after_VV.tif
and prints the TRUE flooded area, so you can compare it with your result.
"""
import numpy as np
import rasterio
from rasterio.transform import from_origin
from scipy.ndimage import gaussian_filter

from helpers import raw_dir

rng = np.random.default_rng(42)

PIXEL = 30.0                  # meters per pixel (same as the real 30 m RTC)
H, W = 900, 1200              # 27 km x 36 km
PAD = 20                      # extra border so the two scenes can be shifted a bit
X0, Y0 = 240000.0, 1665000.0  # top-left corner, UTM zone 51N (Pampanga area)
CRS = "EPSG:32651"

rows, cols = np.mgrid[0:H + PAD, 0:W + PAD]

# ---- 1. the "world" in dB: land is about -9 dB, water is about -23 dB ----
land = -9.0 + gaussian_filter(rng.normal(0, 1, rows.shape), 6) * 8.0
river = np.abs(rows - (300 + 120 * np.sin(cols / 160.0))) < 8  # a winding river
ponds = ((rows > 600) & (rows < 640) & (cols > 200) & (cols < 330)) | \
        ((rows > 650) & (rows < 700) & (cols > 700) & (cols < 800))  # fish ponds

# the flood: big blobs next to the river that appear only AFTER the typhoon
flood = np.zeros(rows.shape, dtype=bool)
for (cy, cx, r) in [(330, 400, 110), (260, 750, 140), (420, 1000, 90), (200, 250, 70)]:
    flood |= (rows - cy) ** 2 + (cols - cx) ** 2 < r ** 2
flood &= ~river
flood &= ~ponds

world_before = np.where(river | ponds, -23.0, land)
world_after = np.where(river | ponds | flood, -23.0, land)


def radar_power(db_world, row0, col0, height, width):
    """Cut a scene out of the world, add radar speckle noise, convert dB -> power."""
    db = db_world[row0:row0 + height, col0:col0 + width]
    looks = 5
    speckle = rng.gamma(shape=looks, scale=1.0 / looks, size=db.shape)  # multiplicative noise
    power = (10.0 ** (db / 10.0)) * speckle
    power[:, :5] = 0.0   # black border = "no data" (like real scenes)
    power[-5:, :] = 0.0
    return power.astype("float32")


def write_scene(path, power, x_left, y_top):
    with rasterio.open(
        path, "w", driver="GTiff", height=power.shape[0], width=power.shape[1],
        count=1, dtype="float32", crs=CRS,
        transform=from_origin(x_left, y_top, PIXEL, PIXEL), nodata=0.0,
        compress="lzw",
    ) as dst:
        dst.write(power, 1)


folder = raw_dir("test_event")
folder.mkdir(parents=True, exist_ok=True)

# BEFORE scene: starts at world pixel (10, 10)
before = radar_power(world_before, 10, 10, H, W)
write_scene(folder / "before_VV.tif", before, X0 + 10 * PIXEL, Y0 - 10 * PIXEL)

# AFTER scene: slightly shifted and narrower, like a real second pass would be
a_row, a_col, a_h, a_w = 14, 17, H - 8, W - 30
after = radar_power(world_after, a_row, a_col, a_h, a_w)
write_scene(folder / "after_VV.tif", after, X0 + a_col * PIXEL, Y0 - a_row * PIXEL)

# ---- the TRUE answer (only possible because the data is fake) ----
true_flood_km2 = flood[20:H, 30:W - 20].sum() * PIXEL * PIXEL / 1e6
print("Fake data written to", folder)
print(f"TRUE flooded area (roughly): {true_flood_km2:.1f} km2")
print("Your pipeline result should be close to this (within about 10%).")