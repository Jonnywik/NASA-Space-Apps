"""NASA CMR (Common Metadata Repository) search for NISAR GCOV and GUNW granules.

CMR needs no login. Nothing here downloads science data. The result is a small
manifest (titles, dates, URLs, sizes, checksums) that the later stages read.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable

from shapely.geometry import Polygon, box

from .constants import CMR_GRANULES_URL, GCOV_COLLECTIONS, GUNW_COLLECTIONS

USER_AGENT = "tanaw-nisar-search/1.0"

_GCOV_RE = re.compile(
    r"^NISAR_L2_(?P<stage>[A-Z]{2})_GCOV_(?P<cycle>\d{3})_(?P<track>\d{3})_(?P<dir>[AD])_(?P<frame>\d{3})_"
    r"(?P<mode>\d{4})_(?P<pols>[A-Z]{4})_(?P<bw>[A-Z])_(?P<start>\d{8}T\d{6})_(?P<end>\d{8}T\d{6})_"
    r"(?P<crid>[A-Z]\d{5})_(?P<orbit>[A-Z])_(?P<full>[A-Z])_(?P<proc>[A-Z])_(?P<counter>\d{3})$")
_GUNW_RE = re.compile(
    r"^NISAR_L2_(?P<stage>[A-Z]{2})_GUNW_(?P<refcycle>\d{3})_(?P<track>\d{3})_(?P<dir>[AD])_(?P<frame>\d{3})_"
    r"(?P<seccycle>\d{3})_(?P<mode>\d{4})_(?P<pols>[A-Z]{2})_(?P<rs>\d{8}T\d{6})_(?P<re>\d{8}T\d{6})_"
    r"(?P<ss>\d{8}T\d{6})_(?P<se>\d{8}T\d{6})_(?P<crid>[A-Z]\d{5})_(?P<orbit>[A-Z])_(?P<full>[A-Z])_"
    r"(?P<proc>[A-Z])_(?P<counter>\d{3})$")


def _stamp(text: str) -> str:
    """20260623T103220 -> 2026-06-23T10:32:20Z"""
    return datetime.strptime(text, "%Y%m%dT%H%M%S").strftime("%Y-%m-%dT%H:%M:%SZ")


def _attrs(umm: dict) -> dict[str, list[str]]:
    return {a["Name"]: a.get("Values", []) for a in umm.get("AdditionalAttributes", [])}


def _first(attrs: dict, name: str, default: str | None = None) -> str | None:
    values = attrs.get(name) or []
    return values[0] if values else default


def _footprint(umm: dict) -> Polygon | None:
    try:
        geometry = umm["SpatialExtent"]["HorizontalSpatialDomain"]["Geometry"]
        points = geometry["GPolygons"][0]["Boundary"]["Points"]
        polygon = Polygon([(p["Longitude"], p["Latitude"]) for p in points])
        return polygon if polygon.is_valid and not polygon.is_empty else polygon.buffer(0)
    except (KeyError, IndexError, TypeError):
        return None


def bbox_coverage_fraction(umm: dict, bbox: Iterable[float]) -> float | None:
    """Fraction of the study bbox that lies inside the granule's catalogue footprint.

    This is the footprint CMR advertises, not a measurement of valid pixels.
    ``None`` means the footprint was not published.
    """
    footprint = _footprint(umm)
    if footprint is None:
        return None
    study = box(*bbox)
    return round(float(footprint.intersection(study).area / study.area), 4)


def _h5_entry(umm: dict) -> dict:
    entries = umm.get("DataGranule", {}).get("ArchiveAndDistributionInformation", [])
    for entry in entries:
        if str(entry.get("Name", "")).endswith(".h5") and not str(entry["Name"]).endswith("_QA_STATS.h5"):
            return entry
    return {}


def _data_url(umm: dict) -> str | None:
    for related in umm.get("RelatedUrls", []):
        if related.get("Type") == "GET DATA" and str(related.get("URL", "")).startswith("https://"):
            return related["URL"]
    return None


def _acquisition_fields(start_iso: str) -> dict[str, str]:
    start = datetime.fromisoformat(start_iso.replace("Z", "+00:00")).astimezone(timezone.utc)
    local = start.astimezone(timezone(timedelta(hours=8)))
    return {
        "date": start.strftime("%Y-%m-%d"),  # UTC calendar date; ascending passes fall on the next Manila day
        "acquisitionTime": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "acquisitionTimeManila": local.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
    }


def parse_granule(item: dict, collection_id: str, product: str, bbox: Iterable[float]) -> dict | None:
    """Turn one CMR UMM item into a manifest row; ``None`` when the title is not a NISAR pattern."""
    umm = item["umm"]
    title = umm["GranuleUR"]
    attrs = _attrs(umm)
    collections = GCOV_COLLECTIONS if product == "GCOV" else GUNW_COLLECTIONS
    short_name, maturity = collections[collection_id]
    pattern = _GCOV_RE if product == "GCOV" else _GUNW_RE
    match = pattern.match(title)
    if not match:
        return None
    start = umm["TemporalExtent"]["RangeDateTime"]["BeginningDateTime"]
    entry = _h5_entry(umm)
    row: dict[str, Any] = {
        "title": title,
        **_acquisition_fields(start),
        "url": _data_url(umm),
        "sizeBytes": entry.get("SizeInBytes"),
        "md5": (entry.get("Checksum") or {}).get("Value") if (entry.get("Checksum") or {}).get("Algorithm") == "MD5" else None,
        "collection": collection_id,
        "collectionShortName": short_name,
        "maturity": maturity,
        "productVersion": _first(attrs, "PRODUCT_VERSION"),
        "track": int(match["track"]),
        "direction": match["dir"],
        "frame": int(match["frame"]),
        "mode": match["mode"],
        "polarizations": match["pols"],
        "frequencyAPolarizations": attrs.get("FREQUENCY_A_POLARIZATION") or [],
        "rangeBandwidthMHz": _first(attrs, "RANGE_BANDWIDTH_CONCAT"),
        "fullFrame": _first(attrs, "FULL_FRAME") == "TRUE",
        "bboxCoverageFraction": bbox_coverage_fraction(umm, bbox),
        "cmrConceptId": item.get("meta", {}).get("concept-id"),
    }
    if product == "GUNW":
        row["referenceTime"] = _stamp(match["rs"])
        row["secondaryTime"] = _stamp(match["ss"])
        row["referenceDate"] = row["referenceTime"][:10]
        row["secondaryDate"] = row["secondaryTime"][:10]
        row["referenceCycle"] = int(match["refcycle"])
        row["secondaryCycle"] = int(match["seccycle"])
        row["pairDays"] = (datetime.strptime(row["secondaryDate"], "%Y-%m-%d")
                           - datetime.strptime(row["referenceDate"], "%Y-%m-%d")).days
    return row


def fetch_granules(collection_id: str, bbox: Iterable[float], *, page_size: int = 200,
                   fetch_json: Callable[[str], dict] | None = None) -> tuple[list[dict], str]:
    """Return (UMM items, first request URL) for a collection and bbox, following paging."""
    fetch_json = fetch_json or _fetch_json
    west, south, east, north = bbox
    items: list[dict] = []
    first_url = ""
    page = 1
    while True:
        query = urllib.parse.urlencode({
            "collection_concept_id": collection_id,
            "bounding_box": f"{west},{south},{east},{north}",
            "page_size": page_size, "page_num": page, "sort_key": "start_date"})
        url = f"{CMR_GRANULES_URL}?{query}"
        first_url = first_url or url
        body = fetch_json(url)
        batch = body.get("items", [])
        items.extend(batch)
        if len(items) >= body.get("hits", 0) or not batch:
            return items, first_url
        page += 1


def _fetch_json(url: str, *, timeout: int = 90, attempts: int = 3) -> dict:
    last: Exception | None = None
    for _ in range(attempts):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except (OSError, ValueError) as exc:  # URLError, timeouts, bad JSON
            last = exc
    raise RuntimeError(f"CMR request failed after {attempts} attempts: {last}")


def search(bbox: Iterable[float], *, fetch_json: Callable[[str], dict] | None = None) -> dict[str, Any]:
    """Query all four NISAR collections over ``bbox``; returns rows and the request URLs."""
    bbox = tuple(bbox)
    rows: dict[str, list[dict]] = {"GCOV": [], "GUNW": []}
    requests_made: dict[str, str] = {}
    for product, collections in (("GCOV", GCOV_COLLECTIONS), ("GUNW", GUNW_COLLECTIONS)):
        for collection_id in collections:
            items, url = fetch_granules(collection_id, bbox, fetch_json=fetch_json)
            requests_made[collection_id] = url
            for item in items:
                row = parse_granule(item, collection_id, product, bbox)
                if row is not None:
                    rows[product].append(row)
    for product in rows:
        rows[product].sort(key=lambda r: (r["acquisitionTime"], r["collection"]))
    return {"rows": rows, "requests": requests_made}


def _same_stack(row: dict, track: int, direction: str, frame: int, mode: str | None) -> bool:
    return (row["track"] == track and row["direction"] == direction and row["frame"] == frame
            and (mode is None or row["mode"] == mode))


def select_gcov(rows: list[dict], track: int, direction: str, frame: int, mode: str | None) -> tuple[list[dict], list[str]]:
    """One GCOV granule per UTC date. V1 replaces a Provisional granule of the same date."""
    chosen: dict[str, dict] = {}
    notes: list[str] = []
    for row in rows:
        if not _same_stack(row, track, direction, frame, mode):
            continue
        date = row["date"]
        if date in chosen:
            keep = row if row["maturity"] == "v1" else chosen[date]
            notes.append(f"{date}: two granules in the catalogue; kept {keep['collectionShortName']}")
            chosen[date] = keep
        else:
            chosen[date] = row
    return [chosen[d] for d in sorted(chosen)], notes


def gunw_mode_for(gcov_mode: str | None) -> str | None:
    """GCOV mode 4005 (40 MHz + 5 MHz) pairs with GUNW mode 4000; 2005 with 2000."""
    return f"{gcov_mode[0]}000" if gcov_mode else None


def select_gunw(rows: list[dict], track: int, direction: str, frame: int, mode: str | None = None) -> list[dict]:
    """GUNW pairs on the stack, one per (reference date, secondary date). ``mode`` is the GUNW mode (4000)."""
    chosen: dict[tuple[str, str], dict] = {}
    for row in rows:
        if not _same_stack(row, track, direction, frame, mode):
            continue
        key = (row["referenceDate"], row["secondaryDate"])
        if key not in chosen or row["maturity"] == "v1":
            chosen[key] = row
    return [chosen[k] for k in sorted(chosen)]


def pair_chain_gaps(pairs: list[dict]) -> list[dict]:
    """Report where consecutive pairs fail to chain (secondary of one != reference of next)."""
    gaps = []
    for previous, current in zip(pairs, pairs[1:]):
        if previous["secondaryDate"] != current["referenceDate"]:
            gaps.append({"after": previous["secondaryDate"], "next": current["referenceDate"]})
    return gaps


def track_summary(rows: dict[str, list[dict]]) -> list[dict]:
    """Per stack (track, direction, frame, mode): how many dates/pairs and how much of the bbox it covers."""
    groups: dict[tuple, dict] = defaultdict(lambda: {"gcovDates": set(), "gunwPairs": set(), "coverage": [], "full": set(),
                                                    "first": None, "last": None, "sizes": []})
    for product, key in (("GCOV", "gcovDates"), ("GUNW", "gunwPairs")):
        for row in rows[product]:
            group = groups[(row["track"], row["direction"], row["frame"], row["mode"], product)]
            group[key].add(row["date"] if product == "GCOV" else (row["referenceDate"], row["secondaryDate"]))
            if row["bboxCoverageFraction"] is not None:
                group["coverage"].append(row["bboxCoverageFraction"])
            group["full"].add(row["fullFrame"])
            group["first"] = min(filter(None, [group["first"], row["date"]]))
            group["last"] = max(filter(None, [group["last"], row["date"]]))
            if row["sizeBytes"]:
                group["sizes"].append(row["sizeBytes"])
    summary = []
    for (track, direction, frame, mode, product), g in sorted(groups.items()):
        summary.append({
            "product": product, "track": track, "direction": direction, "frame": frame, "mode": mode,
            "dates": len(g["gcovDates"]) if product == "GCOV" else None,
            "pairs": len(g["gunwPairs"]) if product == "GUNW" else None,
            "firstDate": g["first"], "lastDate": g["last"],
            "bboxCoverageFraction": {"min": min(g["coverage"]), "max": max(g["coverage"])} if g["coverage"] else None,
            "fullFrame": sorted(g["full"]),
            "typicalSizeGB": round(sorted(g["sizes"])[len(g["sizes"]) // 2] / 1e9, 2) if g["sizes"] else None,
        })
    return summary


def build_manifest(bbox: Iterable[float], found: dict[str, Any], *, track: int, direction: str, frame: int,
                   mode: str | None, retrieved_at: datetime | None = None) -> dict[str, Any]:
    rows = found["rows"]
    gcov, notes = select_gcov(rows["GCOV"], track, direction, frame, mode)
    gunw = select_gunw(rows["GUNW"], track, direction, frame, gunw_mode_for(mode))
    warnings = list(notes)
    coverage = [r["bboxCoverageFraction"] for r in gcov if r["bboxCoverageFraction"] is not None]
    if not gcov:
        warnings.append("No GCOV granules matched the track/frame/mode filter over this bbox.")
    elif coverage and min(coverage) < 0.9:
        warnings.append(
            f"Catalogue footprints of this stack cover only {min(coverage):.0%}-{max(coverage):.0%} of the study bbox. "
            "Pixels outside the swath will be nodata. Compare the other stacks in trackSummary.")
    if any(not r["fullFrame"] for r in gcov):
        warnings.append("Some selected GCOV granules are partial frames (FULL_FRAME=FALSE).")
    if len({r["maturity"] for r in gcov}) > 1:
        warnings.append("Selection mixes Provisional and V1 processing; record both in the method notes.")
    gaps = pair_chain_gaps(gunw)
    for pair in gunw:
        if pair["pairDays"] != 12:
            warnings.append(f"GUNW pair {pair['referenceDate']} -> {pair['secondaryDate']} spans {pair['pairDays']} days, not 12.")
    if gaps:
        warnings.append(f"GUNW pairs do not chain at {len(gaps)} place(s): {gaps}")
    when = (retrieved_at or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "schemaVersion": "1.0",
        "kind": "nisar-cmr-manifest",
        "dataKind": "observed",
        "retrievedAt": when,
        "source": {"name": "NASA CMR (ASF DAAC NISAR collections)", "url": "https://cmr.earthdata.nasa.gov/search",
                   "version": "granules.umm_json"},
        "query": {"bbox": list(bbox), "requests": found["requests"]},
        "selection": {"track": track, "direction": direction, "frame": frame, "mode": mode, "gunwMode": gunw_mode_for(mode),
                      "gcovDates": [r["date"] for r in gcov], "gunwPairs": len(gunw)},
        "warnings": warnings,
        "trackSummary": track_summary(rows),
        "gcov": gcov,
        "gunw": gunw,
        "gunwChainGaps": gaps,
    }
