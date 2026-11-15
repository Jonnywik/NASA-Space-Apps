"""Seasonal rainfall outlook adapter (Open-Meteo seasonal API, ECMWF SEAS5 ensemble)."""
from __future__ import annotations

import re

from .constants import POINT
from .http import get_json, UpstreamError
from .stats import month_length

SEASONAL_URL = "https://seasonal-api.open-meteo.com/v1/seasonal"
MODEL_REQUESTED = "ecmwf_seas5"
NATIVE_RESOLUTION = "about 36 km (seasonal model grid; the API snaps the request to one grid cell)"
_MEMBER = re.compile(r"^precipitation_sum_member(\d+)$")


def fetch_outlook(point: dict | None = None, *, getter=get_json) -> dict:
    """Daily ensemble members plus the provider's own monthly series in one request.

    If that fails, the daily request is tried alone and the monthly one separately: the monthly
    block is optional, and without it the anomaly is null with the reason recorded."""
    point = point or POINT
    base = {"latitude": point["lat"], "longitude": point["lon"], "models": MODEL_REQUESTED, "timezone": "UTC"}
    opts = {"timeout": 90.0, "retries": 3, "wait": 30.0}
    monthly_q = "precipitation_mean,precipitation_anomaly"
    try:
        body, url = getter(SEASONAL_URL, {**base, "daily": "precipitation_sum", "monthly": monthly_q}, **opts)
        if "daily" not in body:
            raise UpstreamError(f"seasonal response has no daily block: {str(body)[:200]}")
        monthly_error = None if "monthly" in body else "response had no monthly block"
        return {"requestUrls": [url], "modelRequested": MODEL_REQUESTED, "daily": body,
                "monthly": body if "monthly" in body else None, "monthlyError": monthly_error}
    except UpstreamError:
        pass
    daily, url_d = getter(SEASONAL_URL, {**base, "daily": "precipitation_sum"}, **opts)
    if "daily" not in daily:
        raise UpstreamError(f"seasonal response has no daily block: {str(daily)[:200]}")
    monthly, url_m, monthly_error = None, None, None
    try:
        monthly, url_m = getter(SEASONAL_URL, {**base, "monthly": monthly_q}, **opts)
        if "monthly" not in monthly:
            monthly_error, monthly = f"no monthly block in response: {str(monthly)[:200]}", None
    except UpstreamError as exc:
        monthly_error = str(exc)[:300]
    return {"requestUrls": [u for u in (url_d, url_m) if u], "modelRequested": MODEL_REQUESTED,
            "daily": daily, "monthly": monthly, "monthlyError": monthly_error}


def aggregate_outlook(raw: dict) -> dict:
    """Monthly totals per ensemble member -> mean/min/max, only for months present in the response."""
    daily = raw["daily"]
    d = daily["daily"]
    times = d["time"]
    members = {}
    for key, series in d.items():
        mm = _MEMBER.match(key)
        if mm:
            members[int(mm.group(1))] = series
    by_month = {}
    for i, t in enumerate(times):
        by_month.setdefault((int(t[:4]), int(t[5:7])), []).append(i)

    mon = (raw.get("monthly") or {}).get("monthly") or {}
    anom_by_month = {}
    mean_by_month = {}
    for j, t in enumerate(mon.get("time", [])):
        key = (int(t[:4]), int(t[5:7]))
        if "precipitation_anomaly" in mon:
            anom_by_month[key] = mon["precipitation_anomaly"][j]
        if "precipitation_mean" in mon:
            mean_by_month[key] = mon["precipitation_mean"][j]

    months = []
    for (y, m), idx in sorted(by_month.items()):
        totals = []
        for series in members.values():
            vals = [series[i] for i in idx]
            if all(v is not None for v in vals):
                totals.append(sum(vals))
        row = {"year": y, "month": m, "coveredDays": len(idx), "monthDays": month_length(y, m),
               "fullMonth": len(idx) == month_length(y, m), "members": len(totals)}
        if totals:
            row.update(meanMm=round(sum(totals) / len(totals), 2), memberMinMm=round(min(totals), 2),
                       memberMaxMm=round(max(totals), 2))
        else:
            row.update(meanMm=None, memberMinMm=None, memberMaxMm=None)
        row["anomalyVsModelClimatologyMm"] = anom_by_month.get((y, m))
        row["providerMonthlyMeanMm"] = mean_by_month.get((y, m))
        months.append(row)

    anomaly_ok = bool(anom_by_month)
    return {
        "model": None,
        "modelRequested": raw.get("modelRequested"),
        "modelNote": "the response does not name the model; ecmwf_seas5 is the models= value we requested "
                     "(Open-Meteo documents it as the ECMWF SEAS5 ensemble)",
        "runDate": None,
        "runDateReason": "the API response carries no run or initialisation date; firstForecastDate is the "
                        "first day returned and equals the retrieval day",
        "firstForecastDate": times[0] if times else None,
        "lastForecastDate": times[-1] if times else None,
        "gridCell": {"lat": daily.get("latitude"), "lon": daily.get("longitude"), "elevationM": daily.get("elevation")},
        "nativeResolution": NATIVE_RESOLUTION,
        "memberCount": len(members), "units": "mm",
        "anomaly": {"available": anomaly_ok,
                    "reason": None if anomaly_ok else (raw.get("monthlyError") or "provider returned no anomaly series"),
                    "basis": "provider's precipitation_anomaly (model-native; relative to the model's own "
                             "climatology, which the API does not return)" if anomaly_ok else None},
        "months": months,
    }
