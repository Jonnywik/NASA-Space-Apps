import sys, zipfile
from pathlib import Path
import numpy as np
import rasterio
from helpers import raw_dir, out_dir

event_id, zip_path = sys.argv[1], Path(sys.argv[2])

dest = raw_dir(event_id) / "insar"
dest.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(zip_path) as z:
    z.extractall(dest)

corr_path = next(dest.rglob("*_corr.tif"))

with rasterio.open(corr_path) as src:
    corr = src.read(1).astype("float32")
    profile = src.profile
    if src.nodata is not None:
        corr[corr == src.nodata] = np.nan

corr[(corr < 0) | (corr > 1)] = np.nan
print(f"{corr_path.name}: {corr.shape}") 

profile.update(dtype="float32", nodata=np.nan, compress="lzw")
with rasterio.open(out_dir(event_id) / "coherence.tif", "w", **profile) as dst:
    dst.write(corr, 1)

# --- simple coherence check: share of pixels in each band ---
valid = corr[np.isfinite(corr)]
total = valid.size

high = (valid > 0.6).sum()
mid = ((valid >= 0.3) & (valid <= 0.6)).sum()
low = (valid < 0.3).sum()

print()
print(f"Mean coherence: {np.nanmean(corr):.2f}")
print(f"Coherence check ({total:,} valid pixels):")
print(f"  Above 0.6  (very stable: buildings, roads, bare ground)      : {high / total:.1%}")
print(f"  0.3 to 0.6 (moderately stable: farmland, mixed land)         : {mid / total:.1%}")
print(f"  Below 0.3  (heavy change or unstable: water, vegetation)     : {low / total:.1%}")

# example on how to run on terminal
# py scripts\05_extract_coherence.py karding_2022 data\output\karding_2022\tanaw-karding-before-and-after.zip