"""
Script 1: LOOK at the data before doing anything with it.

Run it:
    python scripts/01_inspect.py test_event
    python scripts/01_inspect.py karding_2022

What it does:
  1. opens the BEFORE and AFTER GeoTIFFs
  2. prints facts about each one (size, map projection, value range)
  3. saves a picture: data/output/<event>/01_inspect.png

Open the picture and check that it looks like a real map, not a black square.
"""
import sys

import matplotlib
matplotlib.use("Agg")  # draw pictures into files (no pop-up window)
import matplotlib.pyplot as plt
import numpy as np
import rasterio

from helpers import load_event, load_pair, out_dir, raw_dir, to_db

if len(sys.argv) != 2:
    raise SystemExit("Usage: python scripts/01_inspect.py <event_id>")

event_id = sys.argv[1]
event = load_event(event_id)

# ---- facts about the ORIGINAL files (the whole scene) ----
for label in ("before", "after"):
    path = raw_dir(event_id) / f"{label}_VV.tif"
    if not path.exists():
        raise SystemExit(f"Cannot find {path}")
    with rasterio.open(path) as src:
        print(f"\n=== {label.upper()} ({path.name}) ===")
        print("  size (pixels)  :", src.width, "x", src.height)
        print("  map projection :", src.crs)
        print("  pixel size (m) :", src.res)
        print("  bounds         :", src.bounds)

# ---- the pair after cutting to the bbox and lining them up ----
before, after, transform, crs = load_pair(event)
print("\nAfter cutting to the bbox in events.json:")
print("  size (pixels)  :", before.shape[1], "x", before.shape[0])

before_db = to_db(before)
after_db = to_db(after)

for label, power, db in (("before", before, before_db), ("after", after, after_db)):
    valid = np.isfinite(db)
    print(f"\n{label.upper()}:")
    print(f"  pixels with no data : {100 * (1 - valid.mean()):.1f} %")
    print(f"  power min / max     : {np.nanmin(power):.5f} / {np.nanmax(power):.3f}")
    p5, p50, p95 = np.nanpercentile(db, [5, 50, 95])
    print(f"  dB 5% / median / 95%: {p5:.1f} / {p50:.1f} / {p95:.1f}")

print("\nWhat to expect for Sentinel-1 VV in dB: land about -5 to -14, water about -20 to -28.")
print("If every dB value is positive or all the same, something is wrong - tell Adz.")

# ---- the picture ----
step = max(1, max(before_db.shape) // 1500)  # shrink big images so plotting is quick
fig, axes = plt.subplots(1, 3, figsize=(18, 6))
for ax, db, title in ((axes[0], before_db, f"BEFORE {event['before_date']}"),
                      (axes[1], after_db, f"AFTER {event['after_date']}")):
    ax.imshow(db[::step, ::step], cmap="gray", vmin=-25, vmax=0)
    ax.set_title(title)
    ax.axis("off")

axes[2].hist(before_db[np.isfinite(before_db)].ravel()[::50], bins=120, range=(-35, 5),
             alpha=0.6, label="before")
axes[2].hist(after_db[np.isfinite(after_db)].ravel()[::50], bins=120, range=(-35, 5),
             alpha=0.6, label="after")
axes[2].set_title("How many pixels have each dB value\n(two bumps = water + land)")
axes[2].set_xlabel("dB")
axes[2].legend()

fig.tight_layout()
picture = out_dir(event_id) / "01_inspect.png"
fig.savefig(picture, dpi=80)
print("\nPicture saved:", picture)