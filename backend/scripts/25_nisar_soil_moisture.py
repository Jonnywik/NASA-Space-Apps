"""Script 25: NISAR L3 soil moisture (SME2) for the CAMANAVA study area.

Finds SME2 granules for one track/frame in NASA CMR, reads the study window of each by HTTP range requests
(needs EARTHDATA_TOKEN), keeps recommended retrievals only, and writes:
  data/cache/nisar/soil_moisture/manifest.json      per-pass statistics, provenance, rain comparison
  data/cache/nisar/soil_moisture/sm_<YYYYMMDD>.png   per-pass map (brown = dry, teal = wet)
These files are small and committed, so the API can serve them without a token.

Usage (from backend/):
    python scripts/25_nisar_soil_moisture.py                     # track 140 A, frame 9
    python scripts/25_nisar_soil_moisture.py --track 32 --direction D --frame 81
"""
import argparse
import json
import sys
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

import h5py
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from processing.nisar_flood import remote  # noqa: E402
from processing.nisar_flood import soil_moisture as sm  # noqa: E402
from processing.nisar_flood.constants import STUDY_BBOX  # noqa: E402

BACKEND = Path(__file__).resolve().parent.parent
OUT = BACKEND / "data" / "cache" / "nisar" / "soil_moisture"
COLLECTION = "NISAR_L3_SME2_PROVISIONAL_V1"
CMR = "https://cmr.earthdata.nasa.gov/search/granules.json"


def find_granules(track: int, direction: str, frame: int) -> list[dict]:
    q = urllib.parse.urlencode({"short_name": COLLECTION, "bounding_box": ",".join(map(str, STUDY_BBOX)),
                                "page_size": 500, "sort_key": "start_date"})
    entries = json.load(urllib.request.urlopen(f"{CMR}?{q}", timeout=60))["feed"]["entry"]
    tag = f"_{track:03d}_{direction}_{frame:03d}_"
    rows = []
    for e in entries:
        if tag not in e["title"]:
            continue
        url = next((l["href"] for l in e.get("links", []) if l["href"].startswith("https") and l["href"].endswith(".h5")), None)
        if url:
            rows.append({"title": e["title"], "date": e["time_start"][:10], "acquisitionTime": e["time_start"],
                         "url": url, "cmrConceptId": e["id"]})
    return rows


def rain_for(dates: list[str]) -> dict:
    """Prior 3- and 7-day NASA POWER rain for each pass date, from the cached climate API data."""
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    out = {}
    for d in dates:
        r = client.get("/api/v1/climate/pass-rainfall", params={"area": "camanava_2026", "dates": d})
        if r.status_code == 200:
            p = r.json()["passes"][0]
            out[d] = {"prior3DayMm": p.get("prior3DayMm"), "prior7DayMm": p.get("prior7DayMm")}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--track", type=int, default=140)
    ap.add_argument("--direction", default="A")
    ap.add_argument("--frame", type=int, default=9)
    a = ap.parse_args(argv)
    remote.get_token()
    rows = find_granules(a.track, a.direction, a.frame)
    if not rows:
        sys.exit(f"no {COLLECTION} granules for track {a.track} {a.direction} frame {a.frame} over the study area")
    OUT.mkdir(parents=True, exist_ok=True)
    passes = []
    bounds = None
    for i, row in enumerate(rows, 1):
        print(f"[{i}/{len(rows)}] {row['date']} {row['title']}")
        with h5py.File(remote.HttpRangeFile(row["url"]), "r") as h:
            w = sm.read_window(h, STUDY_BBOX)
        stats = sm.summarise(w, STUDY_BBOX)
        ok = sm.recommended_mask(w["soil"], w["flag"], w["waterFraction"])
        name = f"sm_{row['date'].replace('-', '')}.png"
        (OUT / name).write_bytes(sm.png_bytes(sm.colourise(w["soil"], ok)))
        bounds = sm.bounds_of(w)
        passes.append({"date": row["date"], "acquisitionTime": row["acquisitionTime"], "productId": row["title"],
                       "maturity": "provisional", "overlay": name, **stats})
        print(f"  median {stats['medianM3M3']} m3/m3, recommended {stats['recommendedFraction']:.0%} of study cells")
    rain = rain_for([p["date"] for p in passes])
    for p in passes:
        p.update(rain.get(p["date"], {"prior3DayMm": None, "prior7DayMm": None}))
    comparison = None
    pairs = [(p["prior7DayMm"], p["medianM3M3"]) for p in passes if p.get("prior7DayMm") is not None and p.get("medianM3M3") is not None]
    if len(pairs) >= 5:
        from scipy.stats import spearmanr
        rho, pval = spearmanr([x for x, _ in pairs], [y for _, y in pairs])
        comparison = {"method": "Spearman rank correlation between 7-day prior NASA POWER rain and the study-area median soil moisture",
                      "n": len(pairs), "rho": round(float(rho), 3), "pValue": round(float(pval), 4),
                      "note": "Exploratory, small sample; rain is one ~50 km NASA POWER grid cell; correlation is not causation."}
    manifest = {
        "schemaVersion": "1.0", "area": "camanava_2026", "dataKind": "observed", "generatedAt": sm.utc_now(),
        "sensor": "NISAR L-band SAR", "product": "L3 SME2 soil moisture (provisional)", "collection": COLLECTION,
        "track": {"track": a.track, "direction": a.direction, "frame": a.frame},
        "layer": "science/LSAR/SME2/grids/soilMoisture (average of recommended retrievals)",
        "units": "m3/m3", "nativeResolution": {"x": 200, "y": 200, "units": "m", "grid": "EASE-Grid 2.0"},
        "selection": "recommended retrievals only (retrievalQualityFlag bit 0 == 0); cells with waterbodyFraction > 0.5 excluded",
        "bounds": bounds, "legend": [{"value": s, "color": "#%02X%02X%02X" % c} for s, c in sm.RAMP],
        "passes": passes, "rainComparison": comparison,
        "source": {"name": "NASA/ISRO NISAR L3 SME2 via ASF", "url": "https://nisar-docs.asf.alaska.edu/",
                   "algorithmReferences": "Lal et al. 2023 (RSE 295, 113667); Kim & Liao 2021; Mattia et al. 2009"},
        "limitations": [
            "Provisional product: values and quality flags may change in later NISAR releases.",
            "200 m cells: one value per cell, not per street or plot.",
            "Retrievals over dense urban areas are usually not recommended by the product; those cells are left blank, not set to zero.",
            "Soil moisture is not flooding: it describes the top few centimetres of soil where the product can retrieve it.",
        ],
        "warnings": [],
    }
    sm.write_json(OUT / "manifest.json", manifest)
    print(f"\nWrote {OUT / 'manifest.json'}  ({len(passes)} passes)")
    if comparison:
        print(f"  rain vs soil moisture: Spearman rho {comparison['rho']} (p {comparison['pValue']}, n {comparison['n']})")


if __name__ == "__main__":
    main()
