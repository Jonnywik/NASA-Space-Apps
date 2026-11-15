"""Month-length, unit, fill-value, baseline, anomaly, season, trend and pass-window tests."""
import unittest
from datetime import date

from climate_fixtures import POWER_FIXTURE, constant_daily
from processing.climate import stats
from processing.climate.power import clean_value, daily_series, date_chunks, fetch_power, parse_power_response
from processing.climate.http import UpstreamError


class MonthAndUnitTests(unittest.TestCase):
    def test_month_lengths(self):
        self.assertEqual(stats.month_length(2024, 2), 29)
        self.assertEqual(stats.month_length(2025, 2), 28)
        self.assertEqual(stats.month_length(2026, 11), 30)
        self.assertEqual(stats.month_length(2026, 12), 31)

    def test_monthly_total_is_sum_of_daily_mm(self):
        d = constant_daily(date(2000, 1, 1), date(2000, 2, 29), 1.5)
        m = stats.monthly_totals(d)
        self.assertAlmostEqual(m[(2000, 1)]["totalMm"], 46.5)      # 31 days x 1.5 mm/day
        self.assertAlmostEqual(m[(2000, 2)]["totalMm"], 43.5)      # leap February: 29 x 1.5
        self.assertEqual(m[(2000, 2)]["days"], 29)

    def test_fill_value_is_missing_never_zero(self):
        self.assertIsNone(clean_value(-999.0))
        self.assertIsNone(clean_value(None))
        self.assertEqual(clean_value(0.0), 0.0)
        values, header = parse_power_response(POWER_FIXTURE)
        daily = daily_series({"values": values})
        self.assertIsNone(daily["2026-01-03"])
        self.assertEqual(daily["2026-01-04"], 0.0)                 # a real dry day stays 0
        self.assertEqual(header["fill_value"], -999.0)

    def test_incomplete_month_has_no_total_and_no_anomaly(self):
        d = constant_daily(date(2001, 1, 1), date(2001, 1, 31), 1.0, {"2001-01-10": None})
        m = stats.monthly_totals(d)[(2001, 1)]
        self.assertEqual(m["missingDays"], 1)
        self.assertFalse(m["complete"])
        self.assertIsNone(m["totalMm"])
        self.assertEqual(m["partialMm"], 30.0)                      # the 30 observed days, not 31
        rows = stats.anomalies({(2001, 1): m}, [31.0] + [None] * 11, since=2000)
        self.assertIsNone(rows[0]["anomalyMm"])
        self.assertIsNone(rows[0]["anomalyPct"])

    def test_tolerance_parameter(self):
        d = constant_daily(date(2001, 1, 1), date(2001, 1, 31), 1.0, {"2001-01-10": None})
        self.assertTrue(stats.monthly_totals(d, tolerance=1)[(2001, 1)]["complete"])


class BaselineAnomalyTests(unittest.TestCase):
    def setUp(self):
        d = {}
        d.update(constant_daily(date(2001, 1, 1), date(2001, 1, 31), 1.0))   # 31 mm
        d.update(constant_daily(date(2002, 1, 1), date(2002, 1, 31), 2.0))   # 62 mm
        d.update(constant_daily(date(2003, 1, 1), date(2003, 1, 31), 3.0))   # 93 mm
        self.months = stats.monthly_totals(d)

    def test_baseline_hand_check(self):
        base, counts = stats.baseline_monthly_mean(self.months, period=(2001, 2002))
        self.assertAlmostEqual(base[0], 46.5)                       # (31 + 62) / 2
        self.assertEqual(counts[0], 2)
        self.assertIsNone(base[1])                                  # no February data: null, not 0

    def test_anomaly_mm_and_percent(self):
        base, _ = stats.baseline_monthly_mean(self.months, period=(2001, 2002))
        rows = {r["year"]: r for r in stats.anomalies(self.months, base, since=2001) if r["month"] == 1}
        self.assertAlmostEqual(rows[2003]["anomalyMm"], 46.5)       # 93 - 46.5
        self.assertAlmostEqual(rows[2003]["anomalyPct"], 100.0)
        self.assertAlmostEqual(rows[2001]["anomalyMm"], -15.5)

    def test_incomplete_months_excluded_from_baseline(self):
        d = constant_daily(date(2001, 1, 1), date(2001, 1, 31), 1.0)
        d.update(constant_daily(date(2002, 1, 1), date(2002, 1, 31), 2.0, {"2002-01-05": None}))
        base, counts = stats.baseline_monthly_mean(stats.monthly_totals(d), period=(2001, 2002))
        self.assertEqual(counts[0], 1)
        self.assertAlmostEqual(base[0], 31.0)

    def test_zero_baseline_gives_null_percent(self):
        d = constant_daily(date(2001, 1, 1), date(2001, 1, 31), 0.0)
        d.update(constant_daily(date(2002, 1, 1), date(2002, 1, 31), 1.0))
        m = stats.monthly_totals(d)
        base, _ = stats.baseline_monthly_mean(m, period=(2001, 2001))
        rows = {r["year"]: r for r in stats.anomalies(m, base, since=2001) if r["month"] == 1}
        self.assertEqual(rows[2002]["anomalyMm"], 31.0)
        self.assertIsNone(rows[2002]["anomalyPct"])


class SeasonTests(unittest.TestCase):
    def daily(self):
        d = {}
        d.update(constant_daily(date(2000, 1, 1), date(2000, 12, 31), 1.0))   # Jun-Nov: 183 mm
        d.update(constant_daily(date(2001, 1, 1), date(2001, 12, 31), 2.0))   # 366 mm
        d.update(constant_daily(date(2002, 1, 1), date(2002, 12, 31), 0.5))   # 91.5 mm
        # 2003: observed through 15 Aug only, 1.5 mm/day; the rest not yet available
        d.update(constant_daily(date(2003, 1, 1), date(2003, 8, 15), 1.5))
        d.update(constant_daily(date(2003, 8, 16), date(2003, 12, 31), None))
        return d

    def test_complete_season_totals_and_rank(self):
        s = stats.season_totals(self.daily(), since=2000)
        by = {r["year"]: r for r in s["seasons"]}
        self.assertAlmostEqual(by[2000]["totalMm"], 183.0)
        self.assertAlmostEqual(by[2001]["totalMm"], 366.0)
        self.assertTrue(by[2001]["complete"])
        self.assertEqual(stats.rank_season(s["seasons"], 2001)["rank"], 1)
        self.assertEqual(stats.rank_season(s["seasons"], 2002)["rank"], 3)

    def test_current_season_flagged_incomplete_and_ranked_like_for_like(self):
        s = stats.season_totals(self.daily(), since=2000)
        cur = {r["year"]: r for r in s["seasons"]}[2003]
        self.assertFalse(cur["complete"])
        self.assertIsNone(cur["totalMm"])
        self.assertEqual(s["asOf"], "2003-08-15")
        # Jun 1 - Aug 15 = 30 + 31 + 15 = 76 days x 1.5 mm
        self.assertAlmostEqual(cur["toDateMm"], 114.0)
        rk = stats.rank_season(s["seasons"], 2003)
        self.assertEqual(rk["basis"], "to_date_same_window")
        # same window: 2000 -> 76, 2001 -> 152, 2002 -> 38; 2003 (114) is 2nd of 4
        self.assertEqual((rk["rank"], rk["of"]), (2, 4))

    def test_season_with_a_missing_day_is_not_complete(self):
        d = constant_daily(date(2000, 1, 1), date(2000, 12, 31), 1.0, {"2000-07-04": None})
        row = stats.season_totals(d, since=2000)["seasons"][0]
        self.assertFalse(row["complete"])
        self.assertEqual(row["missingDays"], 1)
        self.assertIsNone(row["totalMm"])

    def test_unknown_year(self):
        self.assertIsNone(stats.rank_season([], 2026)["rank"])


class TrendTests(unittest.TestCase):
    def test_known_linear_series(self):
        xs = [2000 + i / 12 for i in range(120)]
        ys = [5.0 * (x - 2000) / 10 for x in xs]                    # exactly 5 mm per decade
        t = stats.linear_trend(xs, ys)
        self.assertAlmostEqual(t["slopeMmPerDecade"], 5.0, places=6)
        self.assertTrue(t["significant"])
        self.assertLessEqual(t["ci95"][0], 5.0 + 1e-9)
        self.assertGreaterEqual(t["ci95"][1], 5.0 - 1e-9)

    def test_alternating_series_is_not_significant(self):
        xs = [2000 + i / 12 for i in range(120)]
        ys = [(-1.0) ** i * 10 for i in range(120)]
        t = stats.linear_trend(xs, ys)
        self.assertFalse(t["significant"])
        self.assertLess(t["ci95"][0], 0 < t["ci95"][1])

    def test_too_few_months_refused(self):
        with self.assertRaises(ValueError):
            stats.linear_trend([1.0] * 10, [1.0] * 10)

    def test_trend_skips_null_anomalies(self):
        rows = [{"year": 2000 + i // 12, "month": i % 12 + 1, "anomalyMm": None if i % 5 == 0 else 1.0}
                for i in range(120)]
        t = stats.trend_from_anomalies(rows)
        self.assertEqual(t["n"], sum(1 for r in rows if r["anomalyMm"] is not None))
        self.assertEqual(t["period"], "2000-2009")


class PassRainfallTests(unittest.TestCase):
    def setUp(self):
        # mm on day D of Jan 2026 = D, so windows are hand-checkable
        self.daily = {f"2026-01-{d:02d}": float(d) for d in range(1, 21)}

    def test_windows_exclude_the_pass_day(self):
        r = stats.pass_rainfall(self.daily, ["2026-01-10"])[0]
        self.assertEqual(r["sameDayMm"], 10.0)
        self.assertEqual(r["prior3DayMm"], 7 + 8 + 9)
        self.assertEqual(r["prior7DayMm"], sum(range(3, 10)))
        self.assertEqual(r["reasons"], {})

    def test_missing_day_makes_window_null_not_zero(self):
        d = dict(self.daily)
        d["2026-01-08"] = None
        r = stats.pass_rainfall(d, ["2026-01-10"])[0]
        self.assertIsNone(r["prior3DayMm"])
        self.assertIsNone(r["prior7DayMm"])
        self.assertIn("2026-01-08", r["reasons"]["prior3DayMm"])
        self.assertEqual(r["sameDayMm"], 10.0)

    def test_window_before_series_start_is_null(self):
        r = stats.pass_rainfall(self.daily, ["2026-01-04"])[0]
        self.assertIsNone(r["prior7DayMm"])
        self.assertEqual(r["prior3DayMm"], 6.0)


class PowerAdapterTests(unittest.TestCase):
    def test_chunks_are_bounded_and_contiguous(self):
        ch = date_chunks(date(1991, 1, 1), date(2026, 11, 14))
        self.assertTrue(all((b - a).days < 366 * 5 for a, b in ch))
        self.assertEqual(ch[0][0], date(1991, 1, 1))
        self.assertEqual(ch[-1][1], date(2026, 11, 14))
        for (a, b), (c, d) in zip(ch, ch[1:]):
            self.assertEqual((c - b).days, 1)

    def test_fetch_uses_getter_and_records_metadata(self):
        calls = []

        def getter(url, params, **kw):
            calls.append((params["start"], params["end"], kw["timeout"]))
            return POWER_FIXTURE, url + "?x"
        p = fetch_power(date(2026, 1, 5), start=date(2026, 1, 1), getter=getter)
        self.assertEqual(p["apiVersion"], "v2.10.3")
        self.assertEqual(p["fillValue"], -999.0)
        self.assertEqual(p["values"]["2026-01-03"], -999.0)         # raw cache keeps the fill value
        self.assertEqual(p["units"], "mm/day")
        self.assertIn("0.5", p["nativeResolution"])
        self.assertTrue(calls)

    def test_upstream_failure_propagates(self):
        def getter(url, params, **kw):
            raise UpstreamError("boom")
        with self.assertRaises(UpstreamError):
            fetch_power(date(2026, 1, 5), start=date(2026, 1, 1), getter=getter)


if __name__ == "__main__":
    unittest.main()
