"""Dataset availability catalogue (F1). Dates come from live provider queries, cached by script 30."""
from __future__ import annotations

from .constants import BBOX
from .http import get_json, UpstreamError

CMR_URL = "https://cmr.earthdata.nasa.gov/search/granules.json"
STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
CMR_BBOX = "120.85,14.55,121.10,14.95"
NISAR_COLLECTIONS = {"C2854338529-ASF": "NISAR_L2_GCOV_PROVISIONAL_V1", "C3622241360-ASF": "NISAR_L2_GCOV_V1"}
S1_COLLECTIONS = {"C1214470488-ASF": "SENTINEL-1A_SLC", "C1327985661-ASF": "SENTINEL-1B_SLC",
                  "C3470873558-ASF": "SENTINEL-1C_SLC"}


def _cmr_extent(collection_id: str, getter):
    out = {}
    for key, sort in (("first", "start_date"), ("last", "-start_date")):
        body, url = getter(CMR_URL, {"collection_concept_id": collection_id, "bounding_box": CMR_BBOX,
                                     "sort_key": sort, "page_size": 1}, timeout=60.0, retries=1, wait=10.0)
        entries = body.get("feed", {}).get("entry", [])
        out[key] = entries[0]["time_start"] if entries else None
        out["url"] = url
    return out


def _cmr_group(collections: dict, getter):
    found, errors = [], []
    for cid, name in collections.items():
        try:
            e = _cmr_extent(cid, getter)
            if e["first"]:
                found.append({"collection": cid, "shortName": name, **e})
        except UpstreamError as exc:
            errors.append(f"{cid}: {str(exc)[:160]}")
    if not found:
        return {"verified": False, "errors": errors}
    return {"verified": True, "start": min(f["first"] for f in found)[:10], "end": max(f["last"] for f in found)[:10],
            "collections": found, "errors": errors}


def _stac_edge(direction: str, getter, datetime_range: str | None = None):
    body = {"collections": ["landsat-c2-l2"], "bbox": BBOX, "limit": 1,
            "sortby": [{"field": "datetime", "direction": direction}]}
    if datetime_range:
        body["datetime"] = datetime_range
    res, url = getter(STAC_URL, None, timeout=60.0, retries=1, wait=10.0, method="POST", json_body=body)
    feats = res.get("features", [])
    return (feats[0]["properties"]["datetime"][:10], feats[0]["id"]) if feats else (None, None)


def fetch_availability(getter=get_json) -> dict:
    out = {"queryBboxCmr": CMR_BBOX, "queryBboxStac": BBOX}
    out["nisar"] = _cmr_group(NISAR_COLLECTIONS, getter)
    out["sentinel1"] = _cmr_group(S1_COLLECTIONS, getter)
    try:
        first_all, id_all = _stac_edge("asc", getter)
        first_2000, id_2000 = _stac_edge("asc", getter, "2000-01-01T00:00:00Z/..")
        last, id_last = _stac_edge("desc", getter)
        out["landsat"] = {"verified": True, "earliestInCollection": first_all, "earliestItemId": id_all,
                          "start": first_2000, "startItemId": id_2000, "end": last, "endItemId": id_last,
                          "collection": "landsat-c2-l2"}
    except UpstreamError as exc:
        out["landsat"] = {"verified": False, "errors": [str(exc)[:200]]}
    return out


def build_catalogue(avail: dict | None, power: dict | None, era5: dict | None, nisar_integrated: bool) -> list:
    """Honest list of datasets. `avail` is the cached provider check (may be None)."""
    avail = avail or {}
    cat = []
    if power:
        days = [d for d, v in power["values"].items() if v not in (None, power.get("fillValue", -999.0))]
        cat.append({"id": "nasa_power_rainfall", "label": "NASA POWER daily rainfall (MERRA-2, PRECTOTCORR)",
                    "kind": "climate", "start": "2000-01-01" if min(days) < "2000-01-01" else min(days),
                    "end": max(days), "dataStartInCache": min(days), "cadence": "daily",
                    "access": "NASA POWER API (no login), cached", "status": "integrated", "verified": "fetched live"})
    if era5:
        vals = [d for d, v in era5["values"].items() if v is not None]
        cat.append({"id": "era5_rainfall", "label": "ERA5 daily rainfall via Open-Meteo (comparison only)",
                    "kind": "climate", "start": min(vals), "end": max(vals), "cadence": "daily",
                    "access": "Open-Meteo archive API (no login), cached", "status": "integrated",
                    "verified": "fetched live", "note": "kept separate from NASA POWER; never merged"})
    ls = avail.get("landsat") or {}
    cat.append({"id": "landsat_optical", "label": "Landsat Collection 2 Level-2 optical imagery",
                "kind": "optical", "start": ls.get("start") or "2000-01-01", "end": ls.get("end"),
                "cadence": "about every 8 days with two satellites, cloud permitting",
                "access": "Microsoft Planetary Computer STAC (collection landsat-c2-l2)",
                "status": "catalogue_only", "verified": "STAC search over the study bbox" if ls.get("verified") else "not verified",
                "note": "earliest Landsat 5 scene in this bbox is " + str(ls.get("earliestInCollection")) if ls.get("verified") else None})
    s1 = avail.get("sentinel1") or {}
    cat.append({"id": "sentinel1_c_band", "label": "Sentinel-1 C-band SAR (A, B, C)",
                "kind": "sar_c", "start": s1.get("start") or "2014-04-03", "end": s1.get("end"),
                "cadence": "6 to 12 days (varies by satellite and period)",
                "access": "ASF / NASA CMR (Earthdata login to download)", "status": "catalogue_only",
                "verified": "CMR search over the study bbox" if s1.get("verified") else "mission start only (not verified for this area)"})
    ni = avail.get("nisar") or {}
    cat.append({"id": "nisar_l_band", "label": "NISAR L-band GCOV (all tracks over the study area)",
                "kind": "sar_l", "start": ni.get("start") or "2025-01-01", "end": ni.get("end"),
                "cadence": "12 days per track",
                "access": "ASF / NASA CMR (Earthdata login to download)",
                "status": "integrated" if nisar_integrated else "catalogue_only",
                "verified": "CMR search over the study bbox" if ni.get("verified") else "not verified"})
    return cat
