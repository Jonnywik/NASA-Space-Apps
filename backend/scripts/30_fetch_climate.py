"""Fetch and cache climate data for Tanaw (NASA POWER, Open-Meteo seasonal, ERA5, availability).

Usage (from backend/):  ../.venv/bin/python scripts/30_fetch_climate.py [--force] [--skip-era5]

Idempotent: a source cached less than --max-age-hours ago is kept unless --force. A provider that fails
keeps its previous cache and records the error in manifest.json; the API then reports that honestly.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from processing.climate import stats                                      # noqa: E402
from processing.climate.availability import fetch_availability           # noqa: E402
from processing.climate.constants import BASELINE, CACHE_DIR, POINT, POWER_START  # noqa: E402
from processing.climate.era5 import fetch_era5                            # noqa: E402
from processing.climate.http import UpstreamError                         # noqa: E402
from processing.climate.outlook import aggregate_outlook, fetch_outlook   # noqa: E402
from processing.climate.power import POWER_URL, daily_series, fetch_power  # noqa: E402
from processing.climate.store import read_manifest, record_error, write_cache  # noqa: E402


def fresh(name: str, hours: float) -> bool:
    entry = read_manifest(CACHE_DIR).get(name)
    if not entry or "retrievedAt" not in entry:
        return False
    at = datetime.strptime(entry["retrievedAt"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - at < timedelta(hours=hours)


def step(name, hours, force, fn, query):
    if not force and fresh(name, hours):
        print(f"[skip] {name}: cached within {hours} h")
        return None
    try:
        payload = fn()
    except (UpstreamError, ValueError, KeyError) as exc:
        record_error(name, str(exc), cache_dir=CACHE_DIR)
        print(f"[FAIL] {name}: {exc}")
        return None
    entry = write_cache(name, payload, query, cache_dir=CACHE_DIR)
    print(f"[ok]   {name}: {entry['bytes']} bytes sha256={entry['sha256'][:12]} at {entry['retrievedAt']}")
    return payload


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--skip-era5", action="store_true")
    ap.add_argument("--max-age-hours", type=float, default=6.0)
    a = ap.parse_args()
    today = datetime.now(timezone.utc).date()

    step("power_daily", a.max_age_hours, a.force, lambda: fetch_power(today),
         {"url": POWER_URL, "parameter": "PRECTOTCORR", "community": "AG", **POINT,
          "start": POWER_START, "end": today.isoformat()})
    step("outlook_raw", a.max_age_hours, a.force, fetch_outlook,
         {"url": "https://seasonal-api.open-meteo.com/v1/seasonal", "models": "ecmwf_seas5", **POINT})
    step("availability", 24.0, a.force, fetch_availability, {"cmr": "NISAR GCOV, Sentinel-1", "stac": "landsat-c2-l2"})
    if not a.skip_era5:
        step("era5_daily", 24.0, a.force, lambda: fetch_era5(today),
             {"url": "https://archive-api.open-meteo.com/v1/archive", **POINT, "start": "2000-01-01", "end": today.isoformat()})

    # summary from whatever is cached now
    from processing.climate.store import read_cache
    power, pe = read_cache("power_daily", cache_dir=CACHE_DIR)
    if power:
        daily = daily_series(power)
        have = [d for d, v in daily.items() if v is not None]
        months = stats.monthly_totals(daily)
        base, counts = stats.baseline_monthly_mean(months)
        print(f"\nPOWER {power['apiVersion']}: {min(daily)}..{max(daily)}, observed through {max(have)}, "
              f"{len(daily) - len(have)} fill-value days; retrieved {pe['retrievedAt']}")
        print(f"baseline {BASELINE[0]}-{BASELINE[1]} monthly mean mm:", [round(b, 1) for b in base], "n:", counts)
        seasons = stats.season_totals(daily)
        for s in seasons["seasons"][-3:]:
            print("season", s)
        print("2026 rank:", stats.rank_season(seasons["seasons"], int(max(have)[:4])))
    ol, oe = read_cache("outlook_raw", cache_dir=CACHE_DIR)
    if ol:
        agg = aggregate_outlook(ol)
        print(f"\noutlook: {agg['firstForecastDate']}..{agg['lastForecastDate']} members={agg['memberCount']} "
              f"anomaly available={agg['anomaly']['available']}")
        for m in agg["months"]:
            print("  ", m)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
