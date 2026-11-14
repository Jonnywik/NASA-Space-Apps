"""Shared constants for the climate package (see docs/API_CONTRACT.md)."""
from pathlib import Path

AREA_ID = "camanava_2026"
POINT = {"lon": 120.96, "lat": 14.70}
BBOX = [120.88, 14.60, 121.04, 14.82]          # W, S, E, N
BASELINE = (1991, 2020)
HISTORY_START_YEAR = 2000
POWER_START = "1991-01-01"
WET_SEASON_MONTHS = (6, 7, 8, 9, 10, 11)
# A month enters baseline / trend / season totals only if no more than this many days are missing.
MISSING_TOLERANCE_DAYS = 0
POWER_FILL_VALUE = -999.0
MIN_FLOOD_POINTS = 8

BACKEND_DIR = Path(__file__).resolve().parents[2]
CACHE_DIR = BACKEND_DIR / "data" / "cache" / "climate"
NISAR_DIR = BACKEND_DIR / "data" / "output" / AREA_ID / "nisar"
