"""Read-only climate, history, outlook and scenario API. Serves from the cache written by
scripts/30_fetch_climate.py; it never calls a provider while handling a request."""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException

from processing.climate import stats
from processing.climate.availability import build_catalogue
from processing.climate.constants import (AREA_ID, BASELINE, CACHE_DIR, HISTORY_START_YEAR, MIN_FLOOD_POINTS,
                                          MISSING_TOLERANCE_DAYS, POINT)
from processing.climate.flood import InsufficientData, fit_relationship, flood_for_months
from processing.climate.outlook import aggregate_outlook
from processing.climate.power import NATIVE_RESOLUTION as POWER_RES, POWER_URL, daily_series
from processing.climate.scenarios import build_scenarios
from processing.climate.store import read_cache

POWER_SOURCE = {"name": "NASA POWER Daily API, PRECTOTCORR (MERRA-2 based)", "url": POWER_URL}
OUTLOOK_SOURCE = {"name": "Open-Meteo Seasonal API (ECMWF SEAS5 ensemble)", "url": "https://seasonal-api.open-meteo.com/v1/seasonal"}
ERA5_SOURCE = {"name": "ERA5 via Open-Meteo Historical Weather API", "url": "https://archive-api.open-meteo.com/v1/archive"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

POWER_LIMITS = [
    "one MERRA-2 grid cell (about 0.5 x 0.625 degrees), not a city average",
    "satellite-and-model reanalysis rainfall, not a rain-gauge record; in the dry months it reads much wetter than ERA5 "
    "over the same years (see /climate/rainfall/era5-compare), so use it for relative comparison with its own baseline",
    "the latest 1 to 3 days are usually not yet available and stay null; they are never treated as dry",
]


def err(status: int, code: str, message: str, **extra):
    return HTTPException(status, detail={"code": code, "message": message, **extra})


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_router(output_root, read_public_events, cache_dir: Path | None = None):
    cache = Path(cache_dir) if cache_dir else CACHE_DIR
    nisar_dir = Path(output_root) / AREA_ID / "nisar"
    router = APIRouter(prefix="/api/v1")
    memo: dict = {}

    # ---------------------------------------------------------------- helpers
    def check_area(area: str):
        if area != AREA_ID:
            raise err(404, "unknown_area", f"unknown area '{area}'; this API serves '{AREA_ID}'")

    def load(name: str):
        payload, entry = read_cache(name, cache_dir=cache)
        return payload, entry

    def need(name: str, what: str):
        payload, entry = load(name)
        if payload is None:
            raise err(503, "upstream_unavailable",
                      f"{what} has not been fetched (or its cache failed the hash check). "
                      "Run backend/scripts/30_fetch_climate.py; requests never call the provider.", cachedAt=None)
        return payload, entry

    def stale_warning(entry) -> list:
        e = (entry or {}).get("lastRefreshError")
        if not e:
            return []
        return [f"the last refresh failed at {e['at']} ({e['message'][:120]}); serving the cache from {entry['retrievedAt']}"]

    def power():
        payload, entry = need("power_daily", "NASA POWER rainfall")
        key = ("power", entry["sha256"])
        if key not in memo:
            daily = daily_series(payload)
            months = stats.monthly_totals(daily)
            base, counts = stats.baseline_monthly_mean(months)
            series = stats.anomalies(months, base)
            seasons = stats.season_totals(daily)
            observed = [d for d, v in daily.items() if v is not None]
            memo[key] = {"payload": payload, "daily": daily, "months": months, "baseline": base, "counts": counts,
                         "series": series, "seasons": seasons, "lastObserved": max(observed) if observed else None}
        return memo[key], entry

    def common(kind, source, entry, **extra):
        return {"area": AREA_ID, "dataKind": kind, "source": source, "retrievedAt": entry["retrievedAt"], **extra}

    def source_warnings(payload) -> list:
        other = [c for c in payload.get("chunks", []) if c.get("sources") and set(c["sources"]) != {"MERRA2"}]
        if not other:
            return []
        return [f"from {other[0]['start']} the provider serves {'/'.join(other[0]['sources'])} (near-real-time) instead of "
                f"MERRA-2 for the latest months; those values can differ from the final MERRA-2 record and may be revised"]

    def power_common(entry, payload, kind="derived"):
        return common(kind, {**POWER_SOURCE, "version": payload.get("apiVersion"), "dataSources": payload.get("sources"),
                             "parameter": "PRECTOTCORR", "timeStandard": payload.get("timeStandard")}, entry,
                      nativeResolution=POWER_RES, point=payload["point"], sha256=entry["sha256"],
                      warnings=source_warnings(payload) + stale_warning(entry))

    def nisar_passes():
        """Pass list from Agent B's manifest, or None. Looks for manifest.json then passes.json with a
        top-level 'passes' list of {date, floodedKm2} and an optional dataKind."""
        for name in ("manifest.json", "passes.json"):
            f = nisar_dir / name
            if f.exists():
                try:
                    body = json.loads(f.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                if isinstance(body, dict) and isinstance(body.get("passes"), list):
                    return body
        return None

    def to_int(value, name: str, default: int, lo: int, hi: int) -> int:
        if value is None or value == "":
            return default
        try:
            n = int(value)
        except (TypeError, ValueError):
            raise err(422, "invalid_request", f"{name} must be an integer")
        if not lo <= n <= hi:
            raise err(422, "invalid_request", f"{name} must be between {lo} and {hi}")
        return n

    def parse_date(s: str, field: str) -> date:
        if not DATE_RE.match(s or ""):
            raise err(422, "invalid_request", f"{field} must be YYYY-MM-DD")
        try:
            return date.fromisoformat(s)
        except ValueError:
            raise err(422, "invalid_request", f"{field} is not a real calendar date")

    # -------------------------------------------------------------- endpoints
    @router.get("/climate/rainfall/monthly")
    def rainfall_monthly(area: str = AREA_ID, since: str | None = None):
        check_area(area)
        since = to_int(since, "since", HISTORY_START_YEAR, 1991, 2100)
        p, entry = power()
        rows = [r for r in p["series"] if r["year"] >= since]
        return {**power_common(entry, p["payload"]), "units": "mm",
                "baseline": {"period": f"{BASELINE[0]}-{BASELINE[1]}", "monthlyMeanMm": p["baseline"],
                             "yearsUsedPerMonth": p["counts"],
                             "rule": f"complete months only (at most {MISSING_TOLERANCE_DAYS} missing days)"},
                "series": [{"year": r["year"], "month": r["month"], "totalMm": r["totalMm"], "anomalyMm": r["anomalyMm"],
                            "anomalyPct": r["anomalyPct"], "missingDays": r["missingDays"], "complete": r["complete"],
                            "partialMm": r["partialMm"]} for r in rows],
                "lastObservedDay": p["lastObserved"],
                "method": "monthly total = sum of daily mm/day values (each day = 1 day of rain); a month with missing "
                          "days has totalMm null, a partialMm and no anomaly",
                "limitations": POWER_LIMITS + ["anomalies are against the 1991-2020 mean of the same calendar month"]}

    @router.get("/climate/rainfall/daily")
    def rainfall_daily(start: str | None = None, end: str | None = None, area: str = AREA_ID):
        check_area(area)
        a, b = parse_date(start, "start"), parse_date(end, "end")
        if a > b:
            raise err(422, "invalid_request", "start must not be after end")
        if (b - a).days > 3700:
            raise err(422, "invalid_request", "range too long (maximum 3700 days)")
        p, entry = power()
        first, last = min(p["daily"]), max(p["daily"])
        if b.isoformat() < first or a.isoformat() > last:
            raise err(404, "outside_coverage", f"cached series covers {first} to {last}")
        days = []
        for iso in sorted(d for d in p["daily"] if a.isoformat() <= d <= b.isoformat()):
            v = p["daily"][iso]
            days.append({"date": iso, "mm": v, **({} if v is not None else {"reason": "missing (fill value -999 or not yet available)"})})
        return {**power_common(entry, p["payload"], "observed"), "units": "mm/day", "days": days,
                "coveredFrom": first, "coveredThrough": last, "lastObservedDay": p["lastObserved"],
                "limitations": POWER_LIMITS}

    @router.get("/climate/rainfall/season-rank")
    def season_rank(area: str = AREA_ID, year: str | None = None):
        check_area(area)
        year = to_int(year, "year", 2026, 1991, 2100)
        p, entry = power()
        seasons = p["seasons"]["seasons"]
        row = next((s for s in seasons if s["year"] == year), None)
        if row is None:
            raise err(404, "outside_coverage", f"no wet-season data for {year}; available "
                                              f"{seasons[0]['year']}-{seasons[-1]['year']}")
        rk = stats.rank_season(seasons, year)
        warn = []
        if not row["complete"]:
            warn.append(f"the {year} season is not complete: rank compares the total to {p['seasons']['asOf']} with the "
                        f"same window (1 Jun to that day) in every other year, not full-season totals")
        return {**power_common(entry, p["payload"]), "units": "mm", "season": "Jun-Nov", "year": year,
                "totalMm": row["totalMm"], "toDateMm": row["toDateMm"], "partialMm": row["partialMm"],
                "observedThrough": p["seasons"]["asOf"], "rank": rk["rank"], "of": rk["of"], "rankBasis": rk["basis"],
                "rankMeaning": "1 = wettest", "complete": row["complete"],
                "seasons": [{"year": s["year"], "totalMm": s["totalMm"], "toDateMm": s["toDateMm"],
                             "complete": s["complete"]} for s in seasons],
                "warnings": warn + source_warnings(p["payload"]) + stale_warning(entry),
                "limitations": POWER_LIMITS + [f"seasons {HISTORY_START_YEAR} onward only; a season is complete only if every "
                                               "Jun-Nov day was observed"]}

    @router.get("/climate/rainfall/trend")
    def rainfall_trend(area: str = AREA_ID):
        check_area(area)
        p, entry = power()
        try:
            t = stats.trend_from_anomalies(p["series"])
        except ValueError as exc:
            raise err(404, "data_unavailable", str(exc))
        return {**power_common(entry, p["payload"]), "units": "mm per decade (monthly anomaly)",
                "method": "linear fit on monthly anomalies (1991-2020 calendar-month means removed), 2000 onward, "
                          "complete months only; 95% interval widened for lag-1 autocorrelation",
                "period": t["period"], "slopeMmPerDecade": round(t["slopeMmPerDecade"], 3),
                "ci95": [round(c, 3) for c in t["ci95"]], "n": t["n"], "effectiveN": round(t["effectiveN"], 1),
                "lag1Autocorrelation": round(t["lag1Autocorrelation"], 3), "significant": t["significant"],
                "limitations": POWER_LIMITS + [
                    "a 25-year linear fit mixes natural variability (ENSO, monsoon) with any trend; no cause is claimed",
                    "monthly anomalies are autocorrelated and not Gaussian; the interval is approximate",
                    "slope is mm of monthly rainfall per decade, not a change in extreme rainfall or flooding"]}

    @router.get("/climate/pass-rainfall")
    def pass_rainfall(area: str = AREA_ID, dates: str | None = None):
        check_area(area)
        p, entry = power()
        warnings = []
        kind = "derived"
        if dates:
            lst = [x.strip() for x in dates.split(",") if x.strip()]
            if not lst or len(lst) > 60:
                raise err(422, "invalid_request", "dates must list 1 to 60 comma-separated YYYY-MM-DD values")
            for x in lst:
                parse_date(x, "dates")
        else:
            body = nisar_passes()
            if body is None:
                raise err(404, "data_unavailable", "no dates given and the NISAR pass list does not exist yet")
            lst = sorted({q["date"] for q in body["passes"] if q.get("date")})
            if body.get("dataKind") == "synthetic":
                kind = "synthetic"
                warnings.append("pass dates come from a synthetic NISAR product")
            if not lst:
                raise err(404, "data_unavailable", "NISAR pass list is empty")
        rows = stats.pass_rainfall(p["daily"], lst)
        first, last = min(p["daily"]), max(p["daily"])
        for r in rows:
            if r["date"] > last or r["date"] < first:
                r["reasons"]["all"] = f"outside the cached series ({first} to {last})"
        return {**power_common(entry, p["payload"], kind), "units": "mm", "passes": rows,
                "windowDefinition": "sameDayMm = the calendar day of the pass; prior3DayMm = the 3 days before it; "
                                    "prior7DayMm = the 7 days before it (the pass day is excluded). Null if any day is missing.",
                "warnings": warnings + source_warnings(p["payload"]) + stale_warning(entry),
                "limitations": POWER_LIMITS + [
                    "POWER days follow local standard time; a pass in the evening local time may precede rain later that day"]}

    def outlook_data():
        raw, entry = need("outlook_raw", "the seasonal outlook")
        key = ("outlook", entry["sha256"])
        if key not in memo:
            memo[key] = aggregate_outlook(raw)
        return memo[key], entry

    @router.get("/climate/outlook")
    def outlook(area: str = AREA_ID):
        check_area(area)
        o, entry = outlook_data()
        full = [m for m in o["months"] if m["fullMonth"]]
        warn = stale_warning(entry)
        if not o["anomaly"]["available"]:
            warn.append("model-native anomalies were not returned: " + str(o["anomaly"]["reason"]))
        return {**common("outlook", {**OUTLOOK_SOURCE, "version": None}, entry),
                "model": o["model"], "modelRequested": o["modelRequested"], "modelNote": o["modelNote"],
                "runDate": o["runDate"], "runDateReason": o["runDateReason"],
                "firstForecastDate": o["firstForecastDate"], "lastForecastDate": o["lastForecastDate"],
                "nativeResolution": o["nativeResolution"], "gridCell": o["gridCell"], "units": "mm",
                "ensembleMembers": o["memberCount"], "anomaly": o["anomaly"],
                "months": o["months"], "horizonMonths": len(o["months"]), "fullMonths": len(full),
                "warnings": warn,
                "limitations": [
                    "rainfall outlook for one model grid cell (about 36 km), not a street-level forecast",
                    "totals are ensemble-member sums of daily rainfall; min and max are the spread across members",
                    "first and last months are partial (see coveredDays); compare only full months",
                    "anomalyVsModelClimatologyMm is the provider's own anomaly against the model's climatology, "
                    "which is not the NASA POWER 1991-2020 baseline and is not comparable with it",
                    "seasonal skill for rainfall at this range is modest; use for guidance only"]}

    @router.get("/climate/scenarios")
    def scenarios(area: str = AREA_ID):
        check_area(area)
        p, entry = power()
        warn = source_warnings(p["payload"]) + stale_warning(entry)
        ol_months, ol_entry = None, None
        try:
            o, ol_entry = outlook_data()
            ol_months = o["months"]
        except HTTPException:
            warn.append("the seasonal outlook is not cached; every month is labelled scenario")
        if not p["lastObserved"]:
            raise err(404, "data_unavailable", "no observed rainfall in the cache")
        ly, lm = int(p["lastObserved"][:4]), int(p["lastObserved"][5:7])
        res = build_scenarios(p["months"], p["baseline"], p["seasons"]["seasons"], (ly, lm), ol_months)
        return {**power_common(entry, p["payload"], "scenario"), "units": "mm", "startMonth": res["startMonth"],
                "lastObservedMonth": f"{ly}-{lm:02d}", "scenarios": res["scenarios"],
                "outlookRetrievedAt": ol_entry["retrievedAt"] if ol_entry else None, "warnings": warn,
                "limitations": ["conditional scenario, not a prediction",
                                "a month labelled outlook is covered by the seasonal run; the scenario value is still the "
                                "scenario's own rainfall and the outlook figures are attached for comparison",
                                "analog years replay observed monthly totals of NASA POWER; they carry its biases"] + POWER_LIMITS[:2]}

    @router.get("/climate/flood-scenario")
    def flood_scenario(scenarioId: str | None = None, area: str = AREA_ID):
        check_area(area)
        if not scenarioId:
            raise err(422, "invalid_request", "scenarioId is required")
        sc = scenarios(area)
        chosen = next((s for s in sc["scenarios"] if s["id"] == scenarioId), None)
        if chosen is None:  # a bad scenarioId is the client's error, whatever data exists
            raise err(422, "invalid_request", f"unknown scenarioId '{scenarioId}'",
                      validIds=[s["id"] for s in sc["scenarios"]])
        body = nisar_passes()
        if body is None:
            raise err(404, "data_unavailable", "the NISAR pass list does not exist yet")
        p, entry = power()
        passes = [q for q in body["passes"] if q.get("date")]
        rain = {r["date"]: r for r in stats.pass_rainfall(p["daily"], [q["date"] for q in passes])}
        pts = [(q["date"], rain[q["date"]]["prior7DayMm"], q.get("floodedKm2")) for q in passes]
        try:
            fit = fit_relationship(pts)
        except InsufficientData as exc:
            raise err(404, "data_unavailable", str(exc), minimumPasses=MIN_FLOOD_POINTS)
        kind = "synthetic" if body.get("dataKind") == "synthetic" else "scenario"
        warn = list(sc["warnings"])
        if kind == "synthetic":
            warn.append("the NISAR pass list is synthetic; this relationship is not real")
        return {**power_common(entry, p["payload"], kind), "scenarioId": scenarioId, "scenarioLabel": chosen["label"],
                "scenarioBasis": chosen["basis"],
                "relationship": {"n": fit["n"], "method": fit["method"], "points": fit["points"],
                                 "slopeKm2PerMm": round(fit["slopeKm2PerMm"], 5),
                                 "rawTheilSenSlope": round(fit["rawTheilSenSlope"], 5),
                                 "residualRangeKm2": [round(fit["residualMinKm2"], 3), round(fit["residualMaxKm2"], 3)],
                                 "observedPrior7DayRangeMm": fit["xRangeMm"], "droppedMissing": fit["droppedMissing"]},
                "months": flood_for_months(fit, chosen["months"]), "exploratory": True,
                "nisarDataKind": body.get("dataKind"), "warnings": warn,
                "limitations": ["exploratory: about a dozen passes in one wet season, no validation, no probabilities",
                                "low/base/high span the residuals seen in the passes; reality can fall outside them",
                                "monthly rainfall is converted to an average 7-day total, which understates storm peaks",
                                "months outside the rainfall range seen on the passes are null, not extrapolated",
                                "does not model tides, drainage works or subsidence"]}

    @router.get("/climate/rainfall/era5-compare")
    def era5_compare(area: str = AREA_ID):
        check_area(area)
        p, entry = power()
        era, ee = need("era5_daily", "the ERA5 comparison series")
        key = ("era5", ee["sha256"])
        if key not in memo:
            memo[key] = stats.monthly_totals({d: (v if v is not None and v >= 0 else None) for d, v in era["values"].items()})
        em = memo[key]
        rows = []
        for (y, m), r in sorted(em.items()):
            pw = p["months"].get((y, m))
            rows.append({"year": y, "month": m, "era5Mm": r["totalMm"], "powerMm": pw["totalMm"] if pw else None})
        both = [r for r in rows if r["era5Mm"] is not None and r["powerMm"] is not None and 2000 <= r["year"] <= 2020]
        by_month = []
        for m in range(1, 13):
            xs = [r for r in both if r["month"] == m]
            by_month.append({"month": m, "era5MeanMm": round(sum(r["era5Mm"] for r in xs) / len(xs), 1) if xs else None,
                             "powerMeanMm": round(sum(r["powerMm"] for r in xs) / len(xs), 1) if xs else None})
        return {**common("observed", ERA5_SOURCE, ee, nativeResolution=era["nativeResolution"],
                         warnings=stale_warning(ee)), "units": "mm", "gridCell": era["gridCell"],
                "powerSource": POWER_SOURCE, "series": rows, "meanByCalendarMonth2000to2020": by_month,
                "limitations": ["a comparison series: the two products are never merged or averaged",
                                "different grids and models; differences are expected and not an error bar"]}

    @router.get("/timeline/availability")
    def timeline(area: str = AREA_ID):
        check_area(area)
        avail, ae = load("availability")
        pw, pe = load("power_daily")
        era, _ = load("era5_daily")
        datasets = build_catalogue(avail, pw, era, nisar_integrated=nisar_passes() is not None)
        warn = []
        if avail is None:
            warn.append("provider availability has not been fetched; dates for Landsat, Sentinel-1 and NISAR are "
                        "mission starts, not verified for this area")
        return {"area": AREA_ID, "dataKind": "observed", "datasets": datasets,
                "source": {"name": "provider catalogue searches (NASA CMR, Microsoft Planetary Computer STAC) and the cached rainfall series",
                           "url": "https://cmr.earthdata.nasa.gov/search"},
                "retrievedAt": (ae or pe or {}).get("retrievedAt"), "nativeResolution": "not applicable (catalogue dates)",
                "warnings": warn,
                "limitations": ["optical, C-band and L-band data are never spliced into one numeric series",
                                "'catalogue_only' means the data exists but is not processed into Tanaw",
                                "dates are the first and last scenes over the study bounding box"]}

    @router.get("/climate/imerg/passes")
    def imerg_passes(area: str = AREA_ID, series: str = "true"):
        """NASA GPM IMERG half-hourly rain in the hours before each NISAR pass (written by scripts/31)."""
        check_area(area)
        flag = series.strip().lower()
        if flag not in ("true", "1", "yes", "on", "false", "0", "no", "off"):
            raise err(422, "invalid_request", "series must be true or false")
        path = cache / "imerg_passes.json"
        if not path.is_file():
            raise err(404, "data_unavailable", "IMERG rain before NISAR passes has not been fetched (run scripts/31_fetch_imerg_passes.py)")
        try:
            doc = json.loads(path.read_text())
        except (OSError, ValueError):
            raise err(503, "upstream_unavailable", "the cached IMERG file could not be read")
        if flag in ("false", "0", "no", "off"):
            doc = {**doc, "passes": [{k: v for k, v in p.items() if k != "series"} for p in doc.get("passes", [])]}
        return doc

    return router
