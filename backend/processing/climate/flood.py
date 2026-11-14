"""Exploratory rain-to-flood scenario. Deliberately simple, wide bands, refuses on small n."""
from __future__ import annotations

import statistics

from .constants import MIN_FLOOD_POINTS
from .stats import month_length

METHOD = ("Monotone robust line: Theil-Sen slope of flooded km2 on prior-7-day rainfall, slope floored at 0, "
          "intercept = median of (y - slope*x). Low/high = base plus the smallest/largest residual seen in the "
          "passes (a full-range envelope, not a probability interval). Monthly rainfall is converted to an average "
          "7-day total (month total x 7 / days in month). Outside the observed rainfall range the result is null.")


class InsufficientData(ValueError):
    """Too few points to fit anything defensible."""


def _theil_sen(xs, ys):
    slopes = [(ys[j] - ys[i]) / (xs[j] - xs[i]) for i in range(len(xs)) for j in range(i + 1, len(xs))
              if xs[j] != xs[i]]
    return statistics.median(slopes) if slopes else 0.0


def fit_relationship(points: list, min_n: int = MIN_FLOOD_POINTS) -> dict:
    """points: [(date, prior7DayMm, floodedKm2)]. Points with a null value are dropped (never zero)."""
    clean = [(d, float(x), float(y)) for d, x, y in points if x is not None and y is not None]
    dropped = len(points) - len(clean)
    if len(clean) < min_n:
        raise InsufficientData(f"only {len(clean)} usable passes (dropped {dropped} with missing values); "
                               f"at least {min_n} are needed for an exploratory relationship")
    xs, ys = [c[1] for c in clean], [c[2] for c in clean]
    raw_slope = _theil_sen(xs, ys)
    slope = max(raw_slope, 0.0)
    icpt = statistics.median([y - slope * x for x, y in zip(xs, ys)])
    resid = [y - (icpt + slope * x) for x, y in zip(xs, ys)]
    return {"n": len(clean), "droppedMissing": dropped, "method": METHOD, "slopeKm2PerMm": slope,
            "rawTheilSenSlope": raw_slope, "interceptKm2": icpt,
            "residualMinKm2": min(resid), "residualMaxKm2": max(resid),
            "xRangeMm": [min(xs), max(xs)],
            "points": [{"date": d, "prior7DayMm": x, "floodedKm2": y} for d, x, y in clean]}


def flood_for_months(fit: dict, months: list) -> list:
    """months: [{year, month, rainfallMm, status}] -> adds expectedFloodedKm2 {low, base, high} or null."""
    lo_x, hi_x = fit["xRangeMm"]
    out = []
    for r in months:
        row = {k: r[k] for k in ("year", "month", "rainfallMm", "status") if k in r}
        mm = r.get("rainfallMm")
        if mm is None:
            row["expectedFloodedKm2"] = None
            row["reason"] = "no rainfall value for this month"
        else:
            x = mm * 7.0 / month_length(r["year"], r["month"])
            row["equivalent7DayMm"] = round(x, 2)
            if x < lo_x or x > hi_x:
                row["expectedFloodedKm2"] = None
                row["reason"] = (f"average 7-day rainfall {x:.1f} mm is {'below' if x < lo_x else 'above'} the range "
                                 f"seen on the passes ({lo_x:.1f}-{hi_x:.1f} mm); not extrapolated")
            else:
                base = max(fit["interceptKm2"] + fit["slopeKm2PerMm"] * x, 0.0)
                row["expectedFloodedKm2"] = {
                    "low": round(max(base + fit["residualMinKm2"], 0.0), 3),
                    "base": round(base, 3),
                    "high": round(base + fit["residualMaxKm2"], 3)}
        out.append(row)
    return out
