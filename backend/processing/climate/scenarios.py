"""12-month conditional rainfall scenarios built from observed history. Not predictions."""
from __future__ import annotations

from .constants import HISTORY_START_YEAR


def next_months(year: int, month: int, n: int = 12) -> list[tuple[int, int]]:
    out = []
    for _ in range(n):
        month += 1
        if month == 13:
            year, month = year + 1, 1
        out.append((year, month))
    return out


def _analog_months(months: dict, season_year: int):
    """Dec(Y-1) .. Nov(Y): the 12 months that end with wet season Y. None if any month is incomplete."""
    seq = []
    for i in range(12):
        m = (11 + i) % 12 + 1          # Dec, Jan, ..., Nov
        y = season_year - 1 if m == 12 else season_year
        rec = months.get((y, m))
        if rec is None or not rec["complete"]:
            return None
        seq.append(rec["totalMm"])
    return seq


def _pick_analogs(months: dict, seasons: list):
    cands = []
    for s in seasons:
        if s["complete"] and s["year"] >= HISTORY_START_YEAR:
            seq = _analog_months(months, s["year"])
            if seq is not None:
                cands.append((s["totalMm"], s["year"], seq))
    if not cands:
        return None, None
    return max(cands), min(cands)


def _month_rows(targets, values, outlook_by_month, source_label):
    rows = []
    for (y, m), v in zip(targets, values):
        ol = outlook_by_month.get((y, m))
        covered = ol is not None and ol.get("fullMonth") and ol.get("meanMm") is not None
        row = {"year": y, "month": m, "rainfallMm": None if v is None else round(v, 2),
               "rainfallSource": source_label,
               "status": "outlook" if covered else "scenario"}
        if covered:
            row["outlook"] = {"meanMm": ol["meanMm"], "memberMinMm": ol["memberMinMm"],
                              "memberMaxMm": ol["memberMaxMm"], "members": ol["members"],
                              "anomalyVsModelClimatologyMm": ol.get("anomalyVsModelClimatologyMm")}
        rows.append(row)
    return rows


def build_scenarios(months: dict, baseline: list, seasons: list, last_observed_month: tuple,
                    outlook_months: list | None = None) -> dict:
    """`months` from stats.monthly_totals, `seasons` from stats.season_totals()['seasons'].

    Scenario values are placed on the 12 months after `last_observed_month`. A month is labelled
    "outlook" only where the seasonal run covers the whole month; the scenario value is still the
    scenario's own rainfall and the outlook values are attached alongside for comparison."""
    targets = next_months(*last_observed_month)
    outlook_by_month = {(r["year"], r["month"]): r for r in (outlook_months or [])}
    wet, dry = _pick_analogs(months, seasons)
    out = []

    out.append({"id": "normal", "label": "A normal year (1991-2020 mean)",
                "basis": "mean total for each calendar month over 1991-2020, complete months only",
                "months": _month_rows(targets, [baseline[m - 1] for _, m in targets], outlook_by_month, "scenario_value")})

    if wet:
        total, y, seq = wet
        vals = [seq[(m - 12) % 12] for _, m in targets]      # seq index 0 = Dec
        out.append({"id": f"wet_like_{y}", "label": f"A wet year like {y}",
                    "basis": f"Dec {y-1}-Nov {y}: the observed monthly sequence ending with the wettest complete "
                             f"Jun-Nov season since {HISTORY_START_YEAR} ({total:.0f} mm), mapped onto the same calendar months",
                    "analogYear": y, "analogSeasonTotalMm": round(total, 1),
                    "months": _month_rows(targets, vals, outlook_by_month, "scenario_value")})

    env = []
    for cm in range(1, 13):
        vals = [r["totalMm"] for (yy, mm), r in months.items()
                if mm == cm and yy >= HISTORY_START_YEAR and r["complete"]]
        env.append(max(vals) if vals else None)
    out.append({"id": "wettest_since_2000", "label": "The wettest each month has been since 2000",
                "basis": "per-calendar-month maximum of the monthly totals since 2000. This is an upper envelope "
                         "built from different years, not a year that happened.",
                "isEnvelope": True,
                "months": _month_rows(targets, [env[m - 1] for _, m in targets], outlook_by_month, "scenario_value")})

    if dry:
        total, y, seq = dry
        vals = [seq[(m - 12) % 12] for _, m in targets]
        out.append({"id": f"dry_like_{y}", "label": f"A dry year like {y}",
                    "basis": f"Dec {y-1}-Nov {y}: the observed monthly sequence ending with the driest complete "
                             f"Jun-Nov season since {HISTORY_START_YEAR} ({total:.0f} mm)",
                    "analogYear": y, "analogSeasonTotalMm": round(total, 1),
                    "months": _month_rows(targets, vals, outlook_by_month, "scenario_value")})
    return {"startMonth": f"{targets[0][0]}-{targets[0][1]:02d}", "scenarios": out}
