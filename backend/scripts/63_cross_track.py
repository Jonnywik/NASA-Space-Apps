"""Script 63: independent replication on NISAR track 32 descending (18:24 Manila passes).

Needs the descending product from script 20 (run with --out-dir data/output/camanava_2026/nisar_t032D, --calibrate,
the WorldCover permanent-water mask) and, for the rain check, data/cache/climate/imerg_passes_t032D.json (script 31
with --manifest/--out). Downloads ten small OPERA DSWx-S1 reference tiles (needs EARTHDATA_TOKEN).

It answers three questions and writes data/cache/validation/cross_track.json:
1. Do two independent viewing geometries (05:30 ascending, 18:24 descending) find the same recurring open water?
2. Does the descending track agree with Sentinel-1C OPERA DSWx-S1 maps taken at the same time of day, one day earlier?
   (Total water, like script 61; agreement with another satellite product is not ground truth.)
3. Does the descending open-water series react to rain the same way (IMERG 48 h)?

The canonical ascending product and its validation (scripts 20 and 61) are not touched.
Usage (from backend/):  python scripts/63_cross_track.py
"""
import hashlib
import importlib.util
import json
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject
from scipy.ndimage import binary_dilation
from scipy.stats import rankdata

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from processing.nisar_flood.extras import LANDCOVER_NAMES  # noqa: E402

ASC = BACKEND / "data/output/camanava_2026/nisar"
DESC = BACKEND / "data/output/camanava_2026/nisar_t032D"
IMERG_D = BACKEND / "data/cache/climate/imerg_passes_t032D.json"
WORLDCOVER = BACKEND / "data/cache/places/esa_worldcover_2021_clip.tif"
RAW = BACKEND / "data/raw/validation_t032D"
OUT = BACKEND / "data/cache/validation/cross_track.json"
TOLERANCE_PX = 3  # 30 m

_spec = importlib.util.spec_from_file_location("s61", BACKEND / "scripts/61_opera_comparison.py")
s61 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s61)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def spearman(x, y):
    return float(np.corrcoef(rankdata(x), rankdata(y))[0, 1])


def perm_p(x, y, n=20000, rng=np.random.default_rng(32)):
    rho = spearman(x, y)
    rx = rankdata(x)
    null = np.array([np.corrcoef(rx, rng.permutation(rankdata(y)))[0, 1] for _ in range(n)])
    return rho, float((np.sum(np.abs(null) >= abs(rho) - 1e-12) + 1) / (n + 1))


def geometry_agreement():
    with rasterio.open(ASC / "rhythm_half.tif") as a_src, rasterio.open(DESC / "rhythm_half.tif") as d_src:
        a = a_src.read(1) == 1
        d = np.zeros(a.shape, dtype="float32")
        reproject(d_src.read(1).astype("float32"), d, src_transform=d_src.transform, src_crs=d_src.crs,
                  dst_transform=a_src.transform, dst_crs=a_src.crs, resampling=Resampling.nearest)
        d = d == 1
        px_km2 = abs(a_src.transform.a * a_src.transform.e) / 1e6
        lc = np.zeros(a.shape, dtype="uint8")
        with rasterio.open(WORLDCOVER) as w:
            reproject(w.read(1), lc, src_transform=w.transform, src_crs=w.crs, dst_transform=a_src.transform,
                      dst_crs=a_src.crs, resampling=Resampling.nearest)
    st = np.ones((2 * TOLERANCE_PX + 1,) * 2, bool)
    a_near_d = float((a & binary_dilation(d, st)).sum() / max(a.sum(), 1))
    d_near_a = float((d & binary_dilation(a, st)).sum() / max(d.sum(), 1))
    rng = np.random.default_rng(7)
    chance = []
    for _ in range(100):
        shifted = np.roll(np.roll(d, int(rng.integers(100, 800)), 0), int(rng.integers(100, 800)), 1)
        chance.append(float((a & binary_dilation(shifted, st)).sum() / max(a.sum(), 1)))
    both = a & d
    return {
        "ascendingKm2": round(float(a.sum() * px_km2), 3), "descendingKm2": round(float(d.sum() * px_km2), 3),
        "exactOverlapKm2": round(float(both.sum() * px_km2), 3),
        "toleranceM": TOLERANCE_PX * 10,
        "shareAscendingNearDescending": round(a_near_d, 3), "shareDescendingNearAscending": round(d_near_a, 3),
        "chanceShareMean": round(float(np.mean(chance)), 4), "chanceShareMax": round(float(np.max(chance)), 4),
        "byLandCoverOverlapKm2": [{"class": int(c), "name": LANDCOVER_NAMES.get(int(c), str(c)),
                                   "km2": round(float((lc[both] == c).sum() * px_km2), 3)} for c in np.unique(lc[both])],
        "builtUpOverlapKm2": round(float((lc[both] == 50).sum() * px_km2), 3),
    }


def opera_matches(manifest):
    RAW.mkdir(parents=True, exist_ok=True)
    params = urlencode({"collection_concept_id": s61.COLLECTION, "bounding_box": ",".join(map(str, s61.BBOX)),
                        "temporal": "2026-06-20T00:00:00Z,2026-11-15T00:00:00Z", "page_size": 200})
    entries = json.load(urlopen("https://cmr.earthdata.nasa.gov/search/granules.json?" + params, timeout=30))["feed"]["entry"]
    rule = manifest["rule"]
    reports = []
    for p in manifest["passes"]:
        t = datetime.fromisoformat(p["acquisitionTime"].replace("Z", "+00:00"))
        near = [e for e in entries
                if abs(datetime.fromisoformat(e["time_start"].replace("Z", "+00:00")) - t) <= timedelta(hours=36)]
        if not near:
            print(f"  {p['date']}: no DSWx-S1 within 36 h")
            continue
        near.sort(key=lambda e: abs(datetime.fromisoformat(e["time_start"].replace("Z", "+00:00")) - t))
        try:
            ref, _, reference, md5, count = s61.prepare_reference(near[0]["id"], RAW, allow_empty=True)
        except Exception as exc:  # noqa: BLE001 - report and continue with the other dates
            print(f"  {p['date']}: reference failed: {exc}")
            continue
        if count == 0:
            print(f"  {p['date']}: reference has no valid pixels in the study window")
            continue
        asset = manifest["assets"][p["assets"]["db"]]
        db = DESC / asset["path"]
        with rasterio.open(db) as src:
            hh = src.read(1, masked=True).filled(np.nan)
            hv = src.read(2, masked=True).filled(np.nan)
            valid = np.isfinite(hh) & np.isfinite(hv)
            values = np.full(hh.shape, 255, dtype="uint8")
            values[valid] = ((hh[valid] < rule["hhThresholdDb"]) & (hv[valid] < rule["hvThresholdDb"])).astype("uint8")
            profile = src.profile.copy()
            profile.update(count=1, dtype="uint8", nodata=255, compress="deflate")
            binary = RAW / f"nisar_t032D_{p['id']}_total_open_water.tif"
            with rasterio.open(binary, "w", **profile) as dst:
                dst.write(values, 1)
        provenance = {
            "nisar": {"dataKind": "derived", "date": p["date"], "acquisitionTime": p["acquisitionTime"],
                      "source": "NISAR L2 GCOV track 32 D threshold-derived total open water", "url": p["source"]["url"],
                      "productId": p["productId"], "dbSha256": sha(db), "binarySha256": sha(binary), "rule": rule,
                      "productManifestSha256": sha(DESC / "manifest.json")},
            "reference": {"dataKind": "derived", "date": ref["time_start"][:10], "acquisitionTime": ref["time_start"],
                          "source": "OPERA DSWx-S1 BWTR total water",
                          "url": f"https://cmr.earthdata.nasa.gov/search/concepts/{ref['id']}.html",
                          "granuleId": ref["id"], "productId": ref["title"], "sourceMd5": md5, "binarySha256": sha(reference)},
        }
        prov_path = RAW / f"comparison_{p['id']}_provenance.json"
        prov_path.write_text(json.dumps(provenance, indent=2))
        report_path = RAW / f"comparison_{p['id']}.json"
        subprocess.run([sys.executable, str(BACKEND / "scripts/60_validation.py"), "--nisar", str(binary), "--reference",
                        str(reference), "--provenance", str(prov_path), "--out", str(report_path)], check=True,
                       capture_output=True)
        r = json.loads(report_path.read_text())
        hours = abs(datetime.fromisoformat(ref["time_start"].replace("Z", "+00:00")) - t).total_seconds() / 3600
        cm = r["agreement"]["confusionMatrix"]
        reports.append({"nisarDate": p["date"], "referenceTime": ref["time_start"], "referenceGranule": ref["id"],
                        "hoursApart": round(hours, 1), "validPixels": r["agreement"]["validPixels"],
                        "overallAgreement": round(r["agreement"]["overallAgreement"], 3),
                        "f1": round(r["agreement"]["f1"], 3), "iou": round(r["agreement"]["iou"], 3),
                        "nisarRecall": round(cm["tp"] / max(cm["tp"] + cm["fn"], 1), 3),
                        "nisarPrecision": round(cm["tp"] / max(cm["tp"] + cm["fp"], 1), 3)})
        print(f"  {p['date']} vs {ref['time_start'][:16]} ({hours:.1f} h): F1 {reports[-1]['f1']}, IoU {reports[-1]['iou']}, "
              f"agreement {reports[-1]['overallAgreement']}")
    return reports


def main():
    manifest = json.loads((DESC / "manifest.json").read_text())
    if manifest.get("dataKind") != "observed" or manifest["rule"]["calibration"]["status"] != "calibrated":
        sys.exit("expected a calibrated observed descending product in " + str(DESC))
    asc = json.loads((ASC / "manifest.json").read_text())
    doc = {"schemaVersion": "1.0", "area": "camanava_2026", "dataKind": "derived",
           "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "productManifestSha256": sha(ASC / "manifest.json"),
           "descendingManifestSha256": sha(DESC / "manifest.json"),
           "title": "Independent check: NISAR track 32 descending (18:24 Manila)",
           "ascending": {"track": "140 A frame 9", "passes": asc["passCount"], "localTime": "05:30",
                         "rule": {"hhThresholdDb": asc["rule"]["hhThresholdDb"], "hvThresholdDb": asc["rule"]["hvThresholdDb"]},
                         "halfOrMoreKm2": asc["rhythm"]["halfOrMoreKm2"],
                         "openWaterKm2Range": [min(p["floodedKm2"] for p in asc["passes"]), max(p["floodedKm2"] for p in asc["passes"])]},
           "descending": {"track": "32 D frame 81", "passes": manifest["passCount"], "localTime": "18:24",
                          "rule": {"hhThresholdDb": manifest["rule"]["hhThresholdDb"], "hvThresholdDb": manifest["rule"]["hvThresholdDb"]},
                          "halfOrMoreKm2": manifest["rhythm"]["halfOrMoreKm2"],
                          "openWaterKm2Range": [min(p["floodedKm2"] for p in manifest["passes"]), max(p["floodedKm2"] for p in manifest["passes"])],
                          "series": [{"date": p["date"], "acquisitionTimeManila": p["acquisitionTimeManila"], "openWaterKm2": p["floodedKm2"],
                                      "maturity": p.get("maturity")} for p in manifest["passes"]]}}
    print("geometry agreement ...")
    doc["geometryAgreement"] = geometry_agreement()
    print(" ", {k: v for k, v in doc["geometryAgreement"].items() if k != "byLandCoverOverlapKm2"})
    if IMERG_D.is_file():
        rain = {p["date"]: p.get("last48hMm") for p in json.loads(IMERG_D.read_text())["passes"]}
        pairs = [(p["floodedKm2"], rain.get(p["date"])) for p in manifest["passes"] if rain.get(p["date"]) is not None]
        for row in doc["descending"]["series"]:
            row["rain48hMm"] = rain.get(row["date"])
        if len(pairs) >= 6:
            rho, p = perm_p([x for x, _ in pairs], [y for _, y in pairs])
            doc["descending"]["rainCorrelation"] = {"label": "Open water outside permanent water vs 48 h IMERG rain",
                                                    "n": len(pairs), "rho": round(rho, 3), "pPermutation": round(p, 4)}
            print("  descending rain rho", round(rho, 3), "p", round(p, 4))
    print("OPERA DSWx-S1 matches ...")
    doc["operaMatches"] = opera_matches(manifest)
    if doc["operaMatches"]:
        m = doc["operaMatches"]
        doc["operaSummary"] = {"n": len(m), "medianF1": round(float(np.median([x["f1"] for x in m])), 3),
                               "medianIoU": round(float(np.median([x["iou"] for x in m])), 3),
                               "medianAgreement": round(float(np.median([x["overallAgreement"] for x in m])), 3),
                               "medianRecall": round(float(np.median([x["nisarRecall"] for x in m])), 3),
                               "medianPrecision": round(float(np.median([x["nisarPrecision"] for x in m])), 3),
                               "hoursApartRange": [min(x["hoursApart"] for x in m), max(x["hoursApart"] for x in m)]}
        print(" ", doc["operaSummary"])
    doc["limitations"] = [
        "Agreement with Sentinel-1 OPERA DSWx-S1 is agreement between two satellites, not ground truth.",
        "OPERA scenes are about 24 hours before each NISAR pass; water can change in a day.",
        "Total water includes permanent and coastal water, so these scores do not measure flood-only accuracy.",
        "Provisional NISAR products; the descending track uses its own Manila Bay calibration.",
    ]
    OUT.write_text(json.dumps(doc, indent=1))
    print("Wrote", OUT)


if __name__ == "__main__":
    main()
