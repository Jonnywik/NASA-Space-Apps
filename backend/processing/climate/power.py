"""NASA POWER daily PRECTOTCORR adapter (mm/day, MERRA-2 based, ~0.5 x 0.625 degree grid cell)."""
from __future__ import annotations

from datetime import date, timedelta

from .constants import POINT, POWER_FILL_VALUE, POWER_START
from .http import get_json

POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
NATIVE_RESOLUTION = "0.5° x 0.625° (MERRA-2 grid cell)"
CHUNK_YEARS = 5


def date_chunks(start: date, end: date, years: int = CHUNK_YEARS):
    """Bounded request windows [(start, end)] of at most `years` calendar years."""
    out, cur = [], start
    while cur <= end:
        stop = min(date(cur.year + years - 1, 12, 31), end)
        out.append((cur, stop))
        cur = stop + timedelta(days=1)
    return out


def parse_power_response(body: dict) -> tuple[dict, dict]:
    """Return ({iso_date: raw_value}, header). Raw values keep the fill value; use `clean_value`."""
    try:
        raw = body["properties"]["parameter"]["PRECTOTCORR"]
    except (KeyError, TypeError) as exc:
        raise ValueError("POWER response has no PRECTOTCORR series") from exc
    values = {f"{k[:4]}-{k[4:6]}-{k[6:8]}": v for k, v in raw.items()}
    return values, body.get("header", {})


def clean_value(v):
    """Fill value (-999) and non-numbers become None. Never 0."""
    if v is None or isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    if v == POWER_FILL_VALUE or v < 0:
        return None
    return float(v)


def fetch_power(end: date, start: date | None = None, point: dict | None = None, *, getter=get_json):
    """Fetch PRECTOTCORR in bounded chunks. Returns the payload to cache.

    `getter` is injectable for tests. Raises UpstreamError if any chunk fails."""
    point = point or POINT
    start = start or date.fromisoformat(POWER_START)
    values, header, urls = {}, {}, []
    for a, b in date_chunks(start, end):
        params = {"parameters": "PRECTOTCORR", "community": "AG", "longitude": point["lon"],
                  "latitude": point["lat"], "start": a.strftime("%Y%m%d"), "end": b.strftime("%Y%m%d"),
                  "format": "JSON"}
        body, url = getter(POWER_URL, params, timeout=90.0, retries=1, wait=10.0)
        v, header = parse_power_response(body)
        values.update(v)
        urls.append(url)
    return {
        "parameter": "PRECTOTCORR", "units": "mm/day", "point": point,
        "fillValue": POWER_FILL_VALUE,
        "apiVersion": (header.get("api") or {}).get("version"),
        "sources": header.get("sources"), "timeStandard": header.get("time_standard"),
        "nativeResolution": NATIVE_RESOLUTION,
        "requestedStart": start.isoformat(), "requestedEnd": end.isoformat(),
        "requestUrls": urls, "values": dict(sorted(values.items())),
    }


def daily_series(payload: dict) -> dict:
    """{date: mm or None} for every day in the payload."""
    return {d: clean_value(v) for d, v in payload["values"].items()}
