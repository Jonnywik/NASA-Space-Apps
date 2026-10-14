"""
Script 2: radar power -> decibels -> "is this pixel water?" maps.

Run it:
    python scripts/02_water_masks.py test_event
Optional:
    python scripts/02_water_masks.py karding_2022 --threshold -18
    python scripts/02_water_masks.py karding_2022 --no-median

Steps inside:
  A. load the pair (cut to bbox, lined up)
  B. convert power -> dB
  C. smooth the grainy "speckle" noise (median filter, 3x3 pixels)
  D. choose a threshold: pixels darker than it are WATER
  E. save two water maps (before / after) and a picture
"""
import argparse
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import median_filter
from skimage.filters import threshold_otsu

from helpers import load_event, load_pair, out_dir, save_mask, to_db

parser = argparse.ArgumentParser()
parser.add_argument("event_id")
parser.add_argument("--threshold", type=float, default=None,
                    help="water threshold in dB (default: found automatically)")
parser.add_argument("--no-median", action="store_true",
                    help="skip smoothing (use if you ticked the speckle filter in Vertex)")
args = parser.parse_args()

event = load_event(args.event_id)

# ---- A. load ----
before, after, transform, crs = load_pair(event)

# ---- B. power -> dB ----
before_db = to_db(before)
after_db = to_db(after)


# ---- C. smooth speckle ----
def smooth(db):
    valid = np.isfinite(db)
    filled = np.where(valid, db, 0.0)             # the filter cannot handle NaN
    smoothed = median_filter(filled, size=3)      # each pixel becomes the median of its 3x3 block
    smoothed[~valid] = np.nan                     # put the "no data" pixels back
    return smoothed.astype("float32")


if not args.no_median:
    before_db = smooth(before_db)
    after_db = smooth(after_db)


# ---- D. threshold ----
def find_threshold(db):
    """Otsu's method: finds the dB value that best splits dark (water) from bright (land)."""
    values = db[np.isfinite(db)]
    if values.size > 2_000_000:                   # use a random sample so it stays fast
        values = np.random.default_rng(0).choice(values, 2_000_000, replace=False)
    values = values[(values > -35) & (values < 5)]
    return float(threshold_otsu(values))


if args.threshold is not None:
    threshold = args.threshold
    print(f"Using the threshold you gave: {threshold:.1f} dB")
else:
    # We use the AFTER image (it has the most water) and apply the SAME threshold
    # to both images, so the comparison is fair.
    threshold = find_threshold(after_db)
    print(f"Automatic (Otsu) threshold: {threshold:.1f} dB")
    if not (-25 <= threshold <= -12):
        print("  WARNING: this is outside the usual range (-25 to -12 dB).")
        print("  Look at 02_water_masks.png. If it looks wrong, try --threshold -18")


# ---- E. water maps: 1 = water, 0 = not water, 255 = no data ----
def make_mask(db):
    mask = (db < threshold).astype("uint8")
    mask[~np.isfinite(db)] = 255
    return mask


water_before = make_mask(before_db)
water_after = make_mask(after_db)

folder = out_dir(args.event_id)
save_mask(folder / "water_before.tif", water_before, transform, crs)
save_mask(folder / "water_after.tif", water_after, transform, crs)

pixel_area_km2 = abs(transform.a * transform.e) / 1e6
print(f"Water BEFORE: {(water_before == 1).sum() * pixel_area_km2:.1f} km2")
print(f"Water AFTER : {(water_after == 1).sum() * pixel_area_km2:.1f} km2")

with open(folder / "02_info.json", "w") as f:
    json.dump({"threshold_db": round(threshold, 2), "median_filter": not args.no_median}, f)

# ---- picture ----
step = max(1, max(water_before.shape) // 1500)
fig, axes = plt.subplots(1, 3, figsize=(18, 6))
axes[0].imshow(water_before[::step, ::step] == 1, cmap="Blues")
axes[0].set_title("Water BEFORE (blue = water)")
axes[1].imshow(water_after[::step, ::step] == 1, cmap="Blues")
axes[1].set_title("Water AFTER")
axes[2].hist(after_db[np.isfinite(after_db)].ravel()[::50], bins=120, range=(-35, 5))
axes[2].axvline(threshold, color="red", linestyle="--")
axes[2].set_title(f"AFTER dB values - red line = threshold ({threshold:.1f} dB)")
for ax in axes[:2]:
    ax.axis("off")
fig.tight_layout()
fig.savefig(folder / "02_water_masks.png", dpi=80)
print("Saved:", folder / "02_water_masks.png")