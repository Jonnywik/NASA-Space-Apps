"""Rainfall statistics from a daily series {iso_date: mm or None}. Pure functions, no I/O.

Rules: missing days are never zero. A month is `complete` (and enters baseline, anomalies,
trend and season totals) only if it has at most `tolerance` missing days, default 0.
"""
from __future__ import annotations

import calendar
import math
from datetime import date, timedelta

from .constants import BASELINE, HISTORY_START_YEAR, MISSING_TOLERANCE_DAYS, WET_SEASON_MONTHS


def month_length(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def monthly_totals(daily: dict, tolerance: int = MISSING_TOLERANCE_DAYS) -> dict:
    """{(year, month): record}. Days absent from `daily` or None count as missing.

    Only months that start on or before the last day present in `daily` are returned."""
    if not daily:
        return {}
    last = max(daily)
    ly, lm = int(last[:4]), int(last[5:7])
    first = min(daily)
    y, m = int(first[:4]), int(first[5:7])
    out = {}
    while (y, m) <= (ly, lm):
        n = month_length(y, m)
        vals = [daily.get(f"{y:04d}-{m:02d}-{d:02d}") for d in range(1, n + 1)]
        have = [v for v in vals if v is not None]
        missing = n - len(have)
        complete = missing <= tolerance
        out[(y, m)] = {
            "year": y, "month": m, "days": n, "missingDays": missing, "complete": complete,
            # an incomplete month has no total: the partial sum is not a monthly total
            "totalMm": round(sum(have), 3) if complete else None,
            "partialMm": None if complete else (round(sum(have), 3) if have else None),
        }
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def baseline_monthly_mean(months: dict, period=BASELINE) -> tuple[list, list]:
    """Mean total per calendar month over `period` using complete months only.
    Returns (means[12] or None, counts[12])."""
    means, counts = [], []
    for m in range(1, 13):
        vals = [r["totalMm"] for (y, mm), r in months.items()
                if mm == m and period[0] <= y <= period[1] and r["complete"]]
        counts.append(len(vals))
        means.append(round(sum(vals) / len(vals), 4) if vals else None)
    return means, counts


def anomalies(months: dict, baseline: list, since: int = HISTORY_START_YEAR) -> list:
    """Series from `since` with anomaly in mm and %. Anomaly is null when the month is incomplete
    or the baseline is missing; % is null when the baseline mean is 0."""
    rows = []
    for (y, m), r in sorted(months.items()):
        if y < since:
            continue
        base = baseline[m - 1]
        row = dict(r)
        row["baselineMm"] = base
        if r["totalMm"] is None or base is None:
            row["anomalyMm"], row["anomalyPct"] = None, None
        else:
            row["anomalyMm"] = round(r["totalMm"] - base, 3)
            row["anomalyPct"] = round(100.0 * (r["totalMm"] - base) / base, 2) if base > 0 else None
        rows.append(row)
    return rows


def season_days(year: int, season=WET_SEASON_MONTHS) -> list[str]:
    return [f"{year:04d}-{m:02d}-{d:02d}" for m in season for d in range(1, month_length(year, m) + 1)]


def season_totals(daily: dict, since: int = HISTORY_START_YEAR, season=WET_SEASON_MONTHS,
                   tolerance: int = MISSING_TOLERANCE_DAYS) -> dict:
    """Wet-season (Jun-Nov) totals per year, plus a like-for-like total over the same calendar
    window as the latest observed season-day, so an unfinished season can be ranked fairly.

    Returns {"seasons": [...], "latestYear", "asOf"}. For each year:
      totalMm (None if incomplete), partialMm, observedDays, missingDays, complete,
      toDateMm (sum over the window Jun 1 .. asOf month-day, None if any day missing there).
    """
    if not daily:
        return {"seasons": [], "asOf": None}
    last_obs = max(d for d, v in daily.items() if v is not None)
    last_year = int(last_obs[:4])
    # month-day cut-off: the latest observed day when it falls inside the season, else the season end
    md = last_obs[5:]
    if int(last_obs[5:7]) not in season:
        md = None  # the latest year is outside the season: no cut-off needed for completed seasons
    rows = []
    for y in range(since, last_year + 1):
        days = season_days(y, season)
        vals = [daily.get(d) for d in days]
        have = [v for v in vals if v is not None]
        missing = len(days) - len(have)
        # days not yet reached by the series count as missing
        complete = missing <= tolerance
        row = {"year": y, "observedDays": len(have), "missingDays": missing, "complete": complete,
               "totalMm": round(sum(have), 3) if complete else None,
               "partialMm": None if complete else (round(sum(have), 3) if have else None)}
        if md is not None and int(last_obs[5:7]) in season:
            win = [d for d in days if d[5:] <= md]
        else:
            win = days
        wv = [daily.get(d) for d in win]
        row["toDateMm"] = round(sum(wv), 3) if all(v is not None for v in wv) else None
        row["toDateDays"] = len(win)
        rows.append(row)
    return {"seasons": rows, "asOf": last_obs}


def rank_season(seasons: list, year: int) -> dict:
    """Rank `year` (1 = wettest). Complete seasons are ranked on their full total; an incomplete
    season is ranked on the like-for-like to-date total against every year's same window."""
    row = next((s for s in seasons if s["year"] == year), None)
    if row is None:
        return {"rank": None, "of": 0, "basis": None, "reason": f"no data for {year}"}
    if row["complete"]:
        pool = [(s["year"], s["totalMm"]) for s in seasons if s["complete"]]
        basis, val = "full_season_total", row["totalMm"]
    else:
        pool = [(s["year"], s["toDateMm"]) for s in seasons if s["toDateMm"] is not None]
        basis, val = "to_date_same_window", row["toDateMm"]
        if val is None:
            return {"rank": None, "of": 0, "basis": basis, "reason": "days missing inside the observed window"}
    rank = 1 + sum(1 for _, v in pool if v > val)
    return {"rank": rank, "of": len(pool), "basis": basis}


def linear_trend(xs: list, ys: list) -> dict:
    """OLS slope with a 95% interval.

    The interval is widened for lag-1 autocorrelation of the residuals using the effective sample
    size n_eff = n (1 - r) / (1 + r) when r > 0. xs are decimal years, ys anomalies in mm/month.
    Returns slope in mm per decade."""
    from scipy import stats as sps
    n = len(xs)
    if n < 24:
        raise ValueError(f"trend needs at least 24 months, got {n}")
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    icpt = my - slope * mx
    res = [y - (icpt + slope * x) for x, y in zip(xs, ys)]
    s2 = sum(r * r for r in res) / (n - 2)
    se = math.sqrt(s2 / sxx)
    den = sum(r * r for r in res)
    r1 = sum(res[i] * res[i + 1] for i in range(n - 1)) / den if den > 0 else 0.0
    n_eff = n * (1 - r1) / (1 + r1) if r1 > 0 else float(n)
    n_eff = max(n_eff, 3.0)
    se_adj = se * math.sqrt(n / n_eff)
    t = sps.t.ppf(0.975, max(n_eff - 2, 1))
    lo, hi = slope - t * se_adj, slope + t * se_adj
    per_decade = 10.0  # x is in years
    return {"n": n, "slopeMmPerMonthPerYear": slope, "slopeMmPerDecade": slope * per_decade,
            "ci95": [lo * per_decade, hi * per_decade], "lag1Autocorrelation": r1,
            "effectiveN": n_eff, "significant": bool(lo > 0 or hi < 0)}


def trend_from_anomalies(rows: list, since: int = HISTORY_START_YEAR) -> dict:
    pts = [(r["year"] + (r["month"] - 0.5) / 12.0, r["anomalyMm"]) for r in rows
           if r["anomalyMm"] is not None and r["year"] >= since]
    res = linear_trend([p[0] for p in pts], [p[1] for p in pts])
    res["period"] = f"{int(pts[0][0])}-{int(pts[-1][0])}"
    res["monthsUsed"] = len(pts)
    return res


def pass_rainfall(daily: dict, dates: list[str]) -> list:
    """Per date: sameDayMm, prior3DayMm (days d-3..d-1) and prior7DayMm (d-7..d-1).

    The windows exclude the pass day itself. Any missing day in a window gives null with a reason."""
    out = []
    for ds in dates:
        d = date.fromisoformat(ds)
        row = {"date": ds}

        def window(n):
            days = [(d - timedelta(days=k)).isoformat() for k in range(1, n + 1)]
            vals = [daily.get(x) for x in days]
            miss = [x for x, v in zip(days, vals) if v is None]
            return (round(sum(vals), 3), []) if not miss else (None, miss)

        same = daily.get(ds)
        row["sameDayMm"] = None if same is None else round(same, 3)
        row["prior3DayMm"], m3 = window(3)
        row["prior7DayMm"], m7 = window(7)
        reasons = {}
        if same is None:
            reasons["sameDayMm"] = "date outside the cached series" if ds not in daily else "missing (fill value)"
        if m3:
            reasons["prior3DayMm"] = f"missing days: {', '.join(m3)}"
        if m7:
            reasons["prior7DayMm"] = f"missing days: {', '.join(m7)}"
        row["reasons"] = reasons
        out.append(row)
    return out
