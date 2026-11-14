"""Optional ERA5 daily rainfall via the Open-Meteo archive API. A comparison series; never merged with POWER."""
from __future__ import annotations

from datetime import date

from .constants import POINT
from .http import get_json

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
NATIVE_RESOLUTION = "about 0.25° (ERA5; Open-Meteo may blend with ERA5-Land / higher-resolution sources)"


def fetch_era5(end: date, start: date = date(2000, 1, 1), point: dict | None = None, *, getter=get_json) -> dict:
    point = point or POINT
    body, url = getter(ARCHIVE_URL, {"latitude": point["lat"], "longitude": point["lon"],
                                     "start_date": start.isoformat(), "end_date": end.isoformat(),
                                     "daily": "precipitation_sum", "timezone": "UTC"},
                       timeout=120.0, retries=1, wait=20.0)
    d = body["daily"]
    return {"units": body.get("daily_units", {}).get("precipitation_sum", "mm"),
            "gridCell": {"lat": body.get("latitude"), "lon": body.get("longitude"), "elevationM": body.get("elevation")},
            "nativeResolution": NATIVE_RESOLUTION, "requestUrl": url, "timezone": "UTC",
            "values": dict(zip(d["time"], d["precipitation_sum"]))}
