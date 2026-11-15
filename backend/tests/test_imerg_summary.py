import importlib.util
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

_spec = importlib.util.spec_from_file_location("s31", Path(__file__).resolve().parents[1] / "scripts" / "31_fetch_imerg_passes.py")
s31 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s31)

PASS = datetime(2026, 8, 10, 21, 30, tzinfo=timezone.utc)


def series(skip=()):
    return [{"start": (PASS - timedelta(minutes=30 * (i + 1))).isoformat(), "end": (PASS - timedelta(minutes=30 * i)).isoformat(),
             "meanMmHr": 2.0} for i in range(96) if i not in skip]


class ImergSummaryTest(unittest.TestCase):
    def test_complete_window_totals(self):
        out = s31.summarise(series(), PASS)
        self.assertEqual(out["last3hMm"], 6.0)    # 6 half-hours x 2 mm/hr x 0.5 h
        self.assertEqual(out["last48hMm"], 96.0)

    def test_missing_half_hour_makes_total_unknown_not_smaller(self):
        out = s31.summarise(series(skip={70}), PASS)  # a granule 35-35.5 h before the pass is missing
        self.assertIsNone(out["last48hMm"])
        self.assertEqual(out["last24hMm"], 48.0)      # windows that don't include the gap are unaffected


if __name__ == "__main__":
    unittest.main()
