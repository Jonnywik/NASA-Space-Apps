"""Small recorded-style fixtures for the climate tests. No network anywhere."""
from datetime import date, timedelta

POWER_FIXTURE = {   # shape of a real NASA POWER daily/point response (trimmed)
    "properties": {"parameter": {"PRECTOTCORR": {
        "20260101": 15.57, "20260102": 19.17, "20260103": -999.0, "20260104": 0.0, "20260105": 4.98}}},
    "header": {"api": {"version": "v2.10.3", "name": "POWER Daily API"}, "sources": ["MERRA2"],
               "fill_value": -999.0, "time_standard": "LST", "start": "20260101", "end": "20260105"},
}

# Shape of a real Open-Meteo seasonal response (3 members, 4 days over a month boundary).
SEASONAL_FIXTURE = {
    "latitude": 14.754099, "longitude": 121.102936, "elevation": 3.0,
    "daily_units": {"time": "iso8601", "precipitation_sum": "mm"},
    "daily": {
        "time": ["2026-12-30", "2026-12-31", "2027-01-01", "2027-01-02"],
        "precipitation_sum": [0.4, 0.0, 0.0, 0.1],
        "precipitation_sum_member01": [1.0, 2.0, 0.0, 1.0],
        "precipitation_sum_member02": [3.0, 0.0, 4.0, 0.0],
        "precipitation_sum_member03": [0.0, 1.0, 2.0, 2.0],
    },
    "monthly_units": {"precipitation_mean": "mm", "precipitation_anomaly": "mm"},
    "monthly": {"time": ["2026-12-01", "2027-01-01"], "precipitation_mean": [31.5, 23.1],
                "precipitation_anomaly": [-76.7, -36.0]},
}


def constant_daily(start: date, end: date, value: float = 1.0, overrides: dict | None = None) -> dict:
    """{iso: value} for every day start..end, with overrides {iso: value or None}."""
    out, d = {}, start
    while d <= end:
        out[d.isoformat()] = value
        d += timedelta(days=1)
    out.update(overrides or {})
    return out


def power_payload(daily: dict) -> dict:
    """Wrap a {iso: mm|None} dict the way scripts/30 caches POWER (None stored as the -999 fill value)."""
    return {"parameter": "PRECTOTCORR", "units": "mm/day", "point": {"lon": 120.96, "lat": 14.70},
            "fillValue": -999.0, "apiVersion": "v2.10.3", "sources": ["MERRA2"],
            "chunks": [{"start": min(daily), "end": max(daily), "sources": ["MERRA2"]}],
            "timeStandard": "LST", "nativeResolution": "0.5° x 0.625° (MERRA-2 grid cell)",
            "values": {d: (-999.0 if v is None else v) for d, v in sorted(daily.items())}}
