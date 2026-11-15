"""Script 62: how solid are the headline NISAR findings? (no download, no token needed)

Reads only data already cached by scripts 20, 24, 26 and 31, and writes data/cache/validation/robustness.json.

For each headline correlation (per-pass series, n = number of passes):
  - Spearman rho, an exact-style permutation p-value (20 000 random shuffles of the rain series),
  - a 95 % bootstrap interval (5 000 resamples of passes),
  - the leave-one-pass-out range (does one pass carry the result?).
For the rain-response map: a field-significance test. The rain series is shuffled 2 000 times and the whole map is
recomputed each time; how often does a shuffled map reach the observed median rho / share of cells above 0.5?
For the storm coherence loss: a control for the 24-day interval. With Markov (exponential) decorrelation the coherence
of a 24-day pair is about the product of two 12-day coherences, so the expected 24-day coherence per cell is the
squared median of the calm 12-day pairs. Only the loss beyond that is counted.

Usage (from backend/):  python scripts/62_robustness.py
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
from scipy.stats import rankdata

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from processing.nisar_flood import extras as ex  # noqa: E402
from processing.nisar_flood.geo import Grid  # noqa: E402
from app.product_binding import product_fingerprint  # noqa: E402

BACKEND = Path(__file__).resolve().parent.parent
PRODUCT = BACKEND / "data" / "output" / "camanava_2026" / "nisar" / "manifest.json"
WINDOWS = BACKEND / "data" / "raw" / "nisar_windows"
GUNW_DIR = BACKEND / "data" / "raw" / "nisar" / "gunw"
IMERG = BACKEND / "data" / "cache" / "climate" / "imerg_passes.json"
POWER = BACKEND / "data" / "cache" / "climate" / "power_daily.json"
WORLDCOVER = BACKEND / "data" / "cache" / "places" / "esa_worldcover_2021_clip.tif"
OUT = BACKEND / "data" / "cache" / "validation" / "robustness.json"
GUNW_BASE = "science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram"
STORM = ("2026-07-17", "2026-08-10")
RNG = np.random.default_rng(20261115)


def spearman(x, y):
    rx, ry = rankdata(x), rankdata(y)
    return float(np.corrcoef(rx, ry)[0, 1])


def correlation_report(x, y, label, n_perm=20000, n_boot=5000):
    x, y = np.asarray(x, float), np.asarray(y, float)
    rho = spearman(x, y)
    rx, ry = rankdata(x), rankdata(y)
    rx = (rx - rx.mean()) / rx.std()
    perms = np.array([RNG.permutation(ry) for _ in range(n_perm)])
    perms = (perms - perms.mean(axis=1, keepdims=True)) / perms.std(axis=1, keepdims=True)
    null = perms @ rx / len(rx)
    p_perm = float((np.sum(np.abs(null) >= abs(rho) - 1e-12) + 1) / (n_perm + 1))
    boots = []
    for _ in range(n_boot):
        i = RNG.integers(0, len(x), len(x))
        if len(np.unique(x[i])) > 2 and len(np.unique(y[i])) > 2:
            boots.append(spearman(x[i], y[i]))
    lo, hi = np.percentile(boots, [2.5, 97.5])
    loo = [spearman(np.delete(x, k), np.delete(y, k)) for k in range(len(x))]
    return {"label": label, "n": int(len(x)), "rho": round(rho, 3), "pPermutation": round(p_perm, 4),
            "bootstrap95": [round(float(lo), 3), round(float(hi), 3)],
            "leaveOneOut": [round(float(min(loo)), 3), round(float(max(loo)), 3)],
            "signHoldsWithoutAnyOnePass": bool(all(np.sign(v) == np.sign(rho) for v in loo))}


def landcover_on(grid: Grid) -> np.ndarray:
    out = np.zeros((grid.height, grid.width), dtype="uint8")
    with rasterio.open(WORLDCOVER) as src:
        reproject(src.read(1), out, src_transform=src.transform, src_crs=src.crs, dst_transform=grid.affine,
                  dst_crs=grid.crs, resampling=Resampling.mode)
    return out


def load_hh_stack(dates):
    """HH (linear power) for each date from script 20's cached full windows."""
    stack, grid = [], None
    for d in dates:
        best = None
        for f in glob.glob(str(WINDOWS / f"{d.replace('-', '')}_*.npz")):
            z = np.load(f, allow_pickle=True)
            g = json.loads(str(z["grid"]))
            if best is None or g["height"] * g["width"] > best[1]["height"] * best[1]["width"]:
                best = (z, g)
        if best is None:
            raise SystemExit(f"no cached window for {d}; run script 20 first")
        hh_db = best[0]["hh"].astype("float64")
        stack.append(np.where(np.isfinite(hh_db), 10.0 ** (hh_db / 10.0), np.nan))
        grid = best[1]
    return np.stack(stack), grid


def main():
    product = json.loads(PRODUCT.read_text())
    passes = product["passes"]
    dates = [p["date"] for p in passes]
    imerg = {p["date"]: p for p in json.loads(IMERG.read_text())["passes"]}
    rain48 = np.array([imerg[d]["last48hMm"] for d in dates], float)
    open_water = np.array([p["floodedKm2"] for p in passes], float)
    out = {"schemaVersion": "1.0", "area": "camanava_2026", "dataKind": "derived",
           "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "productManifestSha256": __import__("hashlib").sha256(PRODUCT.read_bytes()).hexdigest(),
           "productFingerprint": product_fingerprint(product),
           "passDates": dates, "rain48hMm": rain48.tolist(), "correlations": []}
    out["correlations"].append(correlation_report(open_water, rain48, "Open water outside permanent water vs 48 h IMERG rain"))

    # Per-pass mean HH change against each pixel's median, by land cover (built-up vs other land).
    stack, g = load_hh_stack(dates)
    grid = Grid(crs=g["crs"], transform=tuple(g["transform"][:6]), width=g["width"], height=g["height"])
    lc = landcover_on(grid)
    with np.errstate(invalid="ignore", divide="ignore"):
        db = 10 * np.log10(stack)
    anomaly = db - np.nanmedian(db, axis=0)
    for name, mask in (("built-up land", lc == 50), ("other land", (lc != 50) & (lc != 80) & (lc > 0))):
        series = np.array([np.nanmean(a[mask]) for a in anomaly])
        out["correlations"].append(correlation_report(series, rain48, f"Mean HH change over {name} vs 48 h IMERG rain"))

    # Field significance of the rain-response map (same 50 m aggregation as script 26).
    k = 5
    lin = ex.block_mean(stack, k)
    lin[~(lin > 0)] = np.nan
    with np.errstate(invalid="ignore", divide="ignore"):
        db50 = 10 * np.log10(lin)
    a, b, c, d_, e, f = g["transform"][:6]
    g50 = Grid(crs=g["crs"], transform=(a * k, b, c, d_, e * k, f), width=db50.shape[2], height=db50.shape[1])
    lc50 = landcover_on(g50)
    valid = np.all(np.isfinite(db50), axis=0) & (lc50 != 80) & (lc50 > 0)
    r = rankdata(db50[:, valid], axis=0)
    r = (r - r.mean(axis=0)) / r.std(axis=0)
    r[~np.isfinite(r)] = 0
    ry = rankdata(rain48)
    ry = (ry - ry.mean()) / ry.std()
    obs = ry @ r / len(ry)
    obs_median, obs_share = float(np.median(obs)), float(np.mean(obs > 0.5))
    n_perm = 2000
    null_med, null_share = np.empty(n_perm), np.empty(n_perm)
    for i in range(n_perm):
        rho = RNG.permutation(ry) @ r / len(ry)
        null_med[i], null_share[i] = np.median(rho), np.mean(rho > 0.5)
    out["rainResponseField"] = {
        "cells": int(valid.sum()), "observedMedianRho": round(obs_median, 3), "observedShareAbove05": round(obs_share, 3),
        "nullMedianRho95": round(float(np.percentile(null_med, 95)), 3),
        "nullShareAbove05_95": round(float(np.percentile(null_share, 95)), 3),
        "nullShareAbove05Mean": round(float(null_share.mean()), 3),
        "pFieldMedian": round(float((np.sum(null_med >= obs_median) + 1) / (n_perm + 1)), 4),
        "pFieldShare": round(float((np.sum(null_share >= obs_share) + 1) / (n_perm + 1)), 4),
        "permutations": n_perm,
        "note": "Shuffling the rain series breaks any real link but keeps the spatial pattern of the radar, "
                "so this test accounts for neighbouring cells not being independent.",
    }

    # Coherence loss beyond the 24-day interval effect.
    storm, calm, cgrid = None, [], None
    for fpath in sorted(glob.glob(str(GUNW_DIR / "*.h5"))):
        with h5py.File(fpath, "r") as h:
            coh = h[f"{GUNW_BASE}/HH/coherenceMagnitude"][...].astype("float64")
            x = h[f"{GUNW_BASE}/xCoordinates"][...]
            y = h[f"{GUNW_BASE}/yCoordinates"][...]
            epsg = int(h[f"{GUNW_BASE}/projection"][()])
            title = str(h.attrs.get("tanawSubsetOf", Path(fpath).stem))
        coh[~np.isfinite(coh)] = np.nan
        parts = title.split("_")
        ref = f"{parts[11][:4]}-{parts[11][4:6]}-{parts[11][6:8]}"
        sec = f"{parts[13][:4]}-{parts[13][4:6]}-{parts[13][6:8]}"
        dx, dy = float(x[1] - x[0]), float(y[1] - y[0])
        cgrid = Grid(crs=f"EPSG:{epsg}", transform=(dx, 0.0, float(x[0]) - dx / 2, 0.0, dy, float(y[0]) - dy / 2),
                     width=x.size, height=y.size)
        (calm.append(coh) if (ref, sec) != STORM else None)
        if (ref, sec) == STORM:
            storm = coh
    calm = np.stack(calm)
    with np.errstate(invalid="ignore"):
        med12 = np.nanmedian(calm, axis=0)
    expected24 = med12 ** 2
    lcc = landcover_on(cgrid)
    land = np.isfinite(storm) & np.isfinite(med12) & (lcc != 80) & (lcc > 0)
    naive = med12 - storm
    excess = expected24 - storm
    cell_km2 = abs(cgrid.transform[0] * cgrid.transform[4]) / 1e6
    # how unusual is the storm pair? compare each calm pair's naive drop the same way (leave-one-out median)
    calm_km2 = []
    for i in range(calm.shape[0]):
        with np.errstate(invalid="ignore"):
            others = np.nanmedian(np.delete(calm, i, axis=0), axis=0)
        dd = others - calm[i]
        calm_km2.append(float(np.sum(dd[land] > 0.3) * cell_km2))
    out["coherenceLoss"] = {
        "landKm2": round(float(land.sum() * cell_km2), 1),
        "naiveKm2DropOver03": round(float(np.sum(naive[land] > 0.3) * cell_km2), 2),
        "intervalCorrectedKm2DropOver03": round(float(np.sum(excess[land] > 0.3) * cell_km2), 2),
        "intervalCorrectedMedian": round(float(np.median(excess[land])), 3),
        "calmPairsKm2DropOver03": [round(v, 2) for v in calm_km2],
        "byLandCoverCorrected": ex.by_landcover(np.where(land, excess, np.nan), lcc),
        "note": "Expected 24-day coherence = (median 12-day coherence)^2 (Markov decorrelation). This is an approximation; "
                "real decorrelation often levels off, so the corrected figure is a conservative lower bound.",
    }
    OUT.write_text(json.dumps(out, indent=1))
    for c_ in out["correlations"]:
        print(f"{c_['label']}: rho {c_['rho']}, p {c_['pPermutation']}, 95% CI {c_['bootstrap95']}, LOO {c_['leaveOneOut']}")
    print("rain-response field:", {k_: v for k_, v in out["rainResponseField"].items() if k_ != "note"})
    print("coherence:", {k_: v for k_, v in out["coherenceLoss"].items() if k_ not in ("note", "byLandCoverCorrected")})


if __name__ == "__main__":
    main()
