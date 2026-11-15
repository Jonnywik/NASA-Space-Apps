"""Script 26: two exploratory NISAR layers from cached real data (no download, no token needed).

1. Rain response  - per-cell Spearman rho between NISAR HH backscatter (from the cached GCOV windows written by script 20,
   which store dB; averaged in linear power to 50 m) and the 48-hour NASA GPM IMERG rain before each pass (data/cache/climate/imerg_passes.json).
2. Coherence loss - coherence of the GUNW pair spanning the 8 Aug 2026 storm (17 Jul -> 10 Aug) minus... i.e. the median
   coherence of the other pairs minus the storm pair, at 80 m (subsets written by script 24).

Writes small files to data/cache/nisar/extra/ (PNG overlays + JSON summaries), which the API serves.
Usage (from backend/):  python scripts/26_nisar_extras.py
"""
import glob
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from processing.nisar_flood import extras as ex  # noqa: E402
from processing.nisar_flood.export import write_png_overlay  # noqa: E402
from processing.nisar_flood.geo import Grid  # noqa: E402

BACKEND = Path(__file__).resolve().parent.parent
GCOV_MANIFEST = BACKEND / "data" / "cache" / "nisar" / "nisar_manifest_t140_A_f009_m4005.json"
WINDOWS = BACKEND / "data" / "raw" / "nisar_windows"
GUNW_DIR = BACKEND / "data" / "raw" / "nisar" / "gunw"
IMERG = BACKEND / "data" / "cache" / "climate" / "imerg_passes.json"
WORLDCOVER = BACKEND / "data" / "cache" / "places" / "esa_worldcover_2021_clip.tif"
OUT = BACKEND / "data" / "cache" / "nisar" / "extra"
STORM = ("2026-07-17", "2026-08-10")
GUNW_BASE = "science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram"


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def landcover_on(grid: Grid) -> np.ndarray:
    out = np.zeros((grid.height, grid.width), dtype="uint8")
    with rasterio.open(WORLDCOVER) as src:
        reproject(src.read(1), out, src_transform=src.transform, src_crs=src.crs, dst_transform=grid.affine,
                  dst_crs=grid.crs, resampling=Resampling.mode)
    return out


def rain_response():
    m = json.loads(GCOV_MANIFEST.read_text())
    rain = {p["date"]: p.get("last48hMm") for p in json.loads(IMERG.read_text())["passes"]}
    stack, rains, dates, grid = [], [], [], None
    for row in m["gcov"]:
        d = row["date"]
        files = [f for f in glob.glob(str(WINDOWS / f"{d.replace('-', '')}_*.npz"))]
        best = None
        for f in files:
            z = np.load(f, allow_pickle=True)
            g = json.loads(str(z["grid"]))
            if g["height"] == 2457 or best is None:
                best = (z, g)
        if best is None or rain.get(d) is None:
            print(f"  skip {d}: {'no cached window' if best is None else 'no IMERG total'}")
            continue
        z, g = best
        hh_db = z["hh"].astype("float64")  # script 20 caches HH in dB (speckle-filtered)
        hh = np.where(np.isfinite(hh_db), 10.0 ** (hh_db / 10.0), np.nan)  # back to linear power for averaging
        stack.append(hh)
        rains.append(rain[d])
        dates.append(d)
        grid = g
    if len(stack) < 8:
        sys.exit(f"only {len(stack)} passes with cached windows and IMERG; run scripts 20 and 31 first")
    k = 5  # 10 m -> 50 m
    lin = ex.block_mean(np.stack(stack), k)
    lin[~(lin > 0)] = np.nan  # a 50 m mean that is still <= 0 has no valid dB value
    with np.errstate(invalid="ignore", divide="ignore"):
        db = 10 * np.log10(lin)
    rho = ex.spearman_per_cell(db, np.array(rains))
    a, b, c, d_, e, f = grid["transform"][:6]
    g50 = Grid(crs=grid["crs"], transform=(a * k, b, c, d_, e * k, f), width=db.shape[2], height=db.shape[1])
    lc = landcover_on(g50)
    rho = ex.mask_non_land(rho, lc)  # water responds to wind, not wetness; no-data (class 0) is not land
    bounds = write_png_overlay(ex.ramp_rgba(rho, ex.RESPONSE_STOPS), g50, OUT / "rain_response.png")
    land = np.isfinite(rho)
    doc = {
        "schemaVersion": "1.0", "area": "camanava_2026", "dataKind": "derived", "generatedAt": now(),
        "title": "How strongly NISAR radar brightness follows rain",
        "method": ("Per 50 m cell, Spearman rank correlation between NISAR L2 GCOV HH backscatter (dB, 5x5 mean of 10 m samples) "
                   "and the 48-hour NASA GPM IMERG rain before each pass. WorldCover water and no-data cells are excluded."),
        "nPasses": len(dates), "passDates": dates, "rain48hMm": rains,
        "overlayUrl": "/api/v1/nisar/extra/rain_response.png", "bounds": bounds,
        "legend": [{"value": v, "color": c} for v, c in ex.RESPONSE_STOPS],
        "stats": {"cells": int(land.sum()), "medianRho": round(float(np.nanmedian(rho)), 3),
                  "shareAbove05": round(float(np.mean(rho[land] > 0.5)), 3),
                  "shareBelowMinus05": round(float(np.mean(rho[land] < -0.5)), 3)},
        "byLandCover": ex.by_landcover(rho, lc),
        "nativeResolution": {"x": 50, "y": 50, "units": "m"},
        "source": {"name": "NASA-ISRO NISAR L2 GCOV (ASF) and NASA GPM IMERG Late Run V07 (GES DISC)",
                   "url": "https://nisar-docs.asf.alaska.edu/"},
        "warnings": [],
        "limitations": [
            "Exploratory: 11 passes; with n = 11 a cell needs |rho| above about 0.6 to stand out from chance.",
            "Brighter after rain usually means wetter soil or vegetation. It is not a flood map; flooded streets also look bright.",
            "IMERG rain is one value for about 11 km cells, not street-level rain.",
            "Provisional NISAR products; the 2021 WorldCover classes may not match 2026 land cover.",
        ],
    }
    (OUT / "rain_response.json").write_text(json.dumps(doc, indent=1))
    print(f"rain response: {len(dates)} passes, median rho {doc['stats']['medianRho']}, share > 0.5 {doc['stats']['shareAbove05']}")
    for r in doc["byLandCover"]:
        print(f"  {r['name']}: median rho {r['median']} ({r['cells']} cells)")


def coherence_change():
    files = sorted(glob.glob(str(GUNW_DIR / "*.h5")))
    if len(files) < 5:
        sys.exit("GUNW window subsets missing; run scripts/24_nisar_gunw_subset.py first")
    storm, calm, pairs, grid = None, [], [], None
    for f in files:
        with h5py.File(f, "r") as h:
            coh = h[f"{GUNW_BASE}/HH/coherenceMagnitude"][...].astype("float64")
            x = h[f"{GUNW_BASE}/xCoordinates"][...]
            y = h[f"{GUNW_BASE}/yCoordinates"][...]
            epsg = int(h[f"{GUNW_BASE}/projection"][()])
            title = h.attrs.get("tanawSubsetOf", Path(f).stem)
        coh[~np.isfinite(coh)] = np.nan
        parts = str(title).split("_")
        ref, sec = parts[11][:8], parts[13][:8]
        ref = f"{ref[:4]}-{ref[4:6]}-{ref[6:]}"
        sec = f"{sec[:4]}-{sec[4:6]}-{sec[6:]}"
        dx, dy = float(x[1] - x[0]), float(y[1] - y[0])
        grid = Grid(crs=f"EPSG:{epsg}", transform=(dx, 0.0, float(x[0]) - dx / 2, 0.0, dy, float(y[0]) - dy / 2),
                    width=x.size, height=y.size)
        if (ref, sec) == STORM:
            storm = coh
        else:
            calm.append(coh)
            pairs.append({"reference": ref, "secondary": sec})
    if storm is None:
        sys.exit(f"storm pair {STORM} not found among GUNW subsets")
    drop = ex.coherence_drop(storm, np.stack(calm))
    lc = landcover_on(grid)
    drop_land = ex.mask_non_land(drop, lc)
    bounds = write_png_overlay(ex.ramp_rgba(drop_land, ex.DROP_STOPS, transparent_below=0.05), grid, OUT / "coherence_change.png")
    cell_km2 = abs(grid.transform[0] * grid.transform[4]) / 1e6
    land = np.isfinite(drop_land)
    # Interval control (script 62 has the full test): with Markov decorrelation a 24-day pair is expected to keep about
    # (median 12-day coherence)^2, so only loss beyond that can be credited to the storm.
    with np.errstate(invalid="ignore"):
        excess = np.nanmedian(np.stack(calm), axis=0) ** 2 - storm
    excess[~land] = np.nan
    doc = {
        "schemaVersion": "1.0", "area": "camanava_2026", "dataKind": "derived", "generatedAt": now(),
        "title": "Coherence loss across the 8 Aug 2026 storm",
        "method": ("NISAR L2 GUNW HH coherence at 80 m: median coherence of the other 12-day pairs minus the coherence of the pair "
                   "17 Jul -> 10 Aug 2026, which spans the 8-9 Aug storm. Positive = coherence lost. WorldCover water and no-data cells excluded."),
        "stormPair": {"reference": STORM[0], "secondary": STORM[1], "days": 24}, "calmPairs": pairs,
        "overlayUrl": "/api/v1/nisar/extra/coherence_change.png", "bounds": bounds,
        "legend": [{"value": v, "color": c} for v, c in ex.DROP_STOPS],
        "stats": {"cells": int(land.sum()), "medianDrop": round(float(np.nanmedian(drop_land)), 3),
                  "km2DropOver03": round(float(np.sum(drop_land[land] > 0.3) * cell_km2), 2),
                  "landKm2": round(float(land.sum() * cell_km2), 1),
                  "km2DropOver03IntervalCorrected": round(float(np.sum(excess[land] > 0.3) * cell_km2), 2)},
        "byLandCover": ex.by_landcover(drop_land, lc),
        "nativeResolution": {"x": 80, "y": 80, "units": "m"},
        "source": {"name": "NASA-ISRO NISAR L2 GUNW (ASF), provisional", "url": "https://nisar-docs.asf.alaska.edu/gunw/"},
        "warnings": ["The storm pair spans 24 days (one pass is missing around 29 Jul), the calm pairs 12 days. A longer interval "
                     "also lowers coherence: allowing for that (expected 24-day coherence = median 12-day coherence squared), "
                     f"only {round(float(np.sum(excess[land] > 0.3) * cell_km2), 2)} km2 of loss over 0.3 is left. "
                     "Most of this layer can be explained by the longer interval alone; the storm's effect cannot be separated."],
        "limitations": [
            "Exploratory. Coherence loss can come from standing water, wet or changed vegetation, construction, or noise; it is never a flood map.",
            "80 m cells; dense urban areas usually keep high coherence.",
            "Provisional NISAR products; WorldCover 2021 classes.",
        ],
    }
    (OUT / "coherence_change.json").write_text(json.dumps(doc, indent=1))
    print(f"coherence change: median drop {doc['stats']['medianDrop']}, {doc['stats']['km2DropOver03']} km2 with drop > 0.3 of {doc['stats']['landKm2']} km2 land")
    for r in doc["byLandCover"]:
        print(f"  {r['name']}: median drop {r['median']} ({r['cells']} cells)")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    rain_response()
    coherence_change()
