"""Script 31: NASA GPM IMERG half-hourly rain in the hours before each NISAR pass over CAMANAVA.

For every pass in the NISAR GCOV manifest (script 19), finds the IMERG Late Run half-hourly granules
(GPM_3IMERGHHL, V07, 0.1 deg) covering the HOURS before the pass in NASA CMR, reads only the 0.1-degree cells
that overlap the study bbox (HTTP range reads; needs EARTHDATA_TOKEN and the GES DISC data-use approval),
and writes data/cache/climate/imerg_passes.json:
  per pass: the half-hourly area-mean rain rate (mm/hr) series, totals for the last 3/6/12/24/48 h,
  peak rate and its time, and hours since the last half-hour with >= 1 mm/hr.
Missing granules or fill values are recorded as null, never as zero.

Usage (from backend/):
    python scripts/31_fetch_imerg_passes.py [--hours 48] [--workers 12]
"""
import argparse
import json
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

import h5py
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from processing.nisar_flood import remote  # noqa: E402
from processing.nisar_flood.constants import STUDY_BBOX  # noqa: E402

BACKEND = Path(__file__).resolve().parent.parent
MANIFEST = BACKEND / "data" / "cache" / "nisar" / "nisar_manifest_t140_A_f009_m4005.json"
OUT = BACKEND / "data" / "cache" / "climate" / "imerg_passes.json"
SHORT_NAME = "GPM_3IMERGHHL"
CMR = "https://cmr.earthdata.nasa.gov/search/granules.json"
FILL = -9999.9
RAIN_MMHR = 1.0  # a half-hour counts as "raining" at or above this area-mean rate


def iso(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def granules(start: datetime, end: datetime) -> list[dict]:
    q = urllib.parse.urlencode({"short_name": SHORT_NAME, "temporal": f"{iso(start)},{iso(end)}", "page_size": 500,
                                "sort_key": "start_date"})
    entries = json.load(urllib.request.urlopen(f"{CMR}?{q}", timeout=60))["feed"]["entry"]
    out = []
    for e in entries:
        url = next((l["href"] for l in e.get("links", []) if l["href"].startswith("https://data.gesdisc")
                    and l["href"].endswith(".HDF5")), None)
        if url:
            out.append({"start": e["time_start"], "end": e["time_end"], "url": url, "title": e["title"]})
    return out


def cell_slices(lat: np.ndarray, lon: np.ndarray) -> tuple[slice, slice]:
    """0.1-degree cells whose extent overlaps the study bbox (cell centres +/- 0.05)."""
    west, south, east, north = STUDY_BBOX
    i = np.where((lon + 0.05 > west) & (lon - 0.05 < east))[0]
    j = np.where((lat + 0.05 > south) & (lat - 0.05 < north))[0]
    return slice(int(i.min()), int(i.max()) + 1), slice(int(j.min()), int(j.max()) + 1)


_SLICES = {}


def read_one(g: dict) -> dict:
    for attempt in range(3):
        try:
            with h5py.File(remote.HttpRangeFile(g["url"]), "r") as h:
                grid = h["Grid"]
                if "s" not in _SLICES:
                    _SLICES["s"] = cell_slices(grid["lat"][...], grid["lon"][...])
                si, sj = _SLICES["s"]
                v = grid["precipitation"][0, si, sj].astype("float64")
            v = np.where((v <= FILL + 1) | ~np.isfinite(v), np.nan, v)
            return {**g, "meanMmHr": None if np.all(np.isnan(v)) else round(float(np.nanmean(v)), 3),
                    "maxCellMmHr": None if np.all(np.isnan(v)) else round(float(np.nanmax(v)), 3), "cells": int(v.size)}
        except Exception as exc:  # network hiccup: retry, then record as missing
            err = f"{type(exc).__name__}: {str(exc)[:120]}"
    return {**g, "meanMmHr": None, "maxCellMmHr": None, "error": err}


def summarise(series: list[dict], pass_time: datetime) -> dict:
    def total(hours):
        rows = [s for s in series if datetime.fromisoformat(s["end"].replace("Z", "+00:00")) > pass_time - timedelta(hours=hours)]
        vals = [s["meanMmHr"] for s in rows]
        if not rows or any(v is None for v in vals):
            return None  # incomplete window: unknown, not zero
        return round(sum(v * 0.5 for v in vals), 2)  # mm/hr over half an hour -> mm

    known = [s for s in series if s["meanMmHr"] is not None]
    peak = max(known, key=lambda s: s["meanMmHr"]) if known else None
    raining = [s for s in known if s["meanMmHr"] >= RAIN_MMHR]
    last = max(raining, key=lambda s: s["end"]) if raining else None
    hours_since = None
    if last:
        hours_since = round((pass_time - datetime.fromisoformat(last["end"].replace("Z", "+00:00"))).total_seconds() / 3600, 1)
    return {
        "last3hMm": total(3), "last6hMm": total(6), "last12hMm": total(12), "last24hMm": total(24), "last48hMm": total(48),
        "peakMmHr": peak["meanMmHr"] if peak else None, "peakAt": peak["start"] if peak else None,
        "hoursSinceRain": hours_since,
        "hoursSinceRainNote": (f"hours since the last half-hour with an area-mean rate >= {RAIN_MMHR} mm/hr"
                               if last else f"no half-hour reached {RAIN_MMHR} mm/hr in the window"),
        "missingHalfHours": sum(1 for s in series if s["meanMmHr"] is None),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hours", type=int, default=48)
    ap.add_argument("--workers", type=int, default=12)
    a = ap.parse_args(argv)
    remote.get_token()
    m = json.loads(MANIFEST.read_text())
    passes = []
    for row in m["gcov"]:
        t = datetime.fromisoformat(row["acquisitionTime"].replace("Z", "+00:00"))
        gs = granules(t - timedelta(hours=a.hours), t)
        print(f"{row['date']}: {len(gs)} IMERG half-hours")
        passes.append({"date": row["date"], "acquisitionTime": row["acquisitionTime"],
                       "acquisitionTimeManila": row.get("acquisitionTimeManila"), "granules": gs, "t": t})
    jobs = [(p_i, g) for p_i, p in enumerate(passes) for g in p["granules"]]
    results = {}
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(read_one, g): (p_i, g["url"]) for p_i, g in jobs}
        for n, f in enumerate(as_completed(futs), 1):
            results[futs[f]] = f.result()
            if n % 100 == 0 or n == len(futs):
                print(f"  read {n}/{len(futs)}")
    out_passes = []
    for p_i, p in enumerate(passes):
        series = sorted((results[(p_i, g["url"])] for g in p["granules"]), key=lambda s: s["start"])
        out_passes.append({
            "date": p["date"], "acquisitionTime": p["acquisitionTime"], "acquisitionTimeManila": p["acquisitionTimeManila"],
            **summarise(series, p["t"]),
            "series": [{"start": s["start"], "end": s["end"], "meanMmHr": s["meanMmHr"], "maxCellMmHr": s["maxCellMmHr"]}
                       for s in series],
        })
    cells = _SLICES.get("s")
    doc = {
        "schemaVersion": "1.0", "area": "camanava_2026", "dataKind": "observed", "retrievedAt": iso(datetime.now(timezone.utc)),
        "source": {"name": "NASA GPM IMERG Late Run half-hourly V07 (GPM_3IMERGHHL)", "url": "https://disc.gsfc.nasa.gov/datasets/GPM_3IMERGHHL_07/summary",
                   "doi": "10.5067/GPM/IMERG/3B-HH-L/07", "provider": "NASA GES DISC"},
        "units": {"rate": "mm/hr", "totals": "mm"},
        "nativeResolution": "0.1 degree (about 11 km), 30 minutes",
        "spatialAggregation": f"mean of the 0.1-degree cells overlapping the study bbox {list(STUDY_BBOX)}"
                              + (f" ({(cells[0].stop - cells[0].start) * (cells[1].stop - cells[1].start)} cells)" if cells else ""),
        "hoursBeforePass": a.hours, "rainThresholdMmHr": RAIN_MMHR,
        "passes": out_passes,
        "limitations": [
            "IMERG Late Run (about 14 h latency) is a satellite estimate, not a gauge measurement; the research-grade Final Run is not yet available for 2026.",
            "About 11 km cells: one value for a few barangays, not street-level rain.",
            "Totals are null when any half-hour in the window is missing; missing is never treated as dry.",
        ],
        "warnings": [],
    }
    OUT.write_text(json.dumps(doc, indent=1))
    print(f"\nWrote {OUT}")
    for p in out_passes:
        print(f"  {p['date']} (pass 05:30 Manila): last6h {p['last6hMm']} mm, last24h {p['last24hMm']} mm, last48h {p['last48hMm']} mm, "
              f"peak {p['peakMmHr']} mm/hr at {p['peakAt']}, hours since rain {p['hoursSinceRain']}, missing {p['missingHalfHours']}")


if __name__ == "__main__":
    main()
