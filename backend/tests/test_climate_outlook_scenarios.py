"""Outlook aggregation, scenario labelling, flood-scenario refusal and catalogue honesty."""
import copy
import unittest
from datetime import date

from climate_fixtures import SEASONAL_FIXTURE, constant_daily
from processing.climate import stats
from processing.climate.availability import build_catalogue
from processing.climate.flood import InsufficientData, fit_relationship, flood_for_months
from processing.climate.http import UpstreamError
from processing.climate.outlook import aggregate_outlook, fetch_outlook
from processing.climate.scenarios import build_scenarios, next_months


def raw(monthly=True):
    body = copy.deepcopy(SEASONAL_FIXTURE)
    return {"daily": body, "monthly": body if monthly else None, "modelRequested": "ecmwf_seas5",
            "monthlyError": None if monthly else "HTTP 429"}


class OutlookTests(unittest.TestCase):
    def test_member_monthly_totals(self):
        o = aggregate_outlook(raw())
        dec, jan = o["months"]
        # Dec covers 2 of 31 days: member sums 3, 3, 1
        self.assertEqual((dec["year"], dec["month"], dec["coveredDays"], dec["fullMonth"]), (2026, 12, 2, False))
        self.assertEqual((dec["memberMinMm"], dec["memberMaxMm"]), (1.0, 3.0))
        self.assertAlmostEqual(dec["meanMm"], round(7 / 3, 2))
        # Jan covers 2 days: sums 1, 4, 4
        self.assertEqual(jan["members"], 3)
        self.assertEqual((jan["memberMinMm"], jan["memberMaxMm"]), (1.0, 4.0))
        self.assertEqual(o["memberCount"], 3)

    def test_only_returned_months_are_exposed(self):
        o = aggregate_outlook(raw())
        self.assertEqual([(m["year"], m["month"]) for m in o["months"]], [(2026, 12), (2027, 1)])

    def test_run_date_and_model_not_invented(self):
        o = aggregate_outlook(raw())
        self.assertIsNone(o["runDate"])
        self.assertIn("no run", o["runDateReason"])
        self.assertIsNone(o["model"])
        self.assertEqual(o["modelRequested"], "ecmwf_seas5")
        self.assertEqual(o["firstForecastDate"], "2026-12-30")

    def test_native_anomaly_passed_through_not_derived(self):
        o = aggregate_outlook(raw())
        self.assertTrue(o["anomaly"]["available"])
        self.assertEqual(o["months"][0]["anomalyVsModelClimatologyMm"], -76.7)

    def test_missing_anomaly_is_null_with_reason(self):
        o = aggregate_outlook(raw(monthly=False))
        self.assertFalse(o["anomaly"]["available"])
        self.assertEqual(o["anomaly"]["reason"], "HTTP 429")
        self.assertIsNone(o["months"][0]["anomalyVsModelClimatologyMm"])

    def test_member_with_a_null_day_is_left_out_of_that_month(self):
        r = raw()
        r["daily"]["daily"]["precipitation_sum_member02"][0] = None
        dec = aggregate_outlook(r)["months"][0]
        self.assertEqual(dec["members"], 2)

    def test_fetch_falls_back_when_combined_request_fails(self):
        calls = []

        def getter(url, params, **kw):
            calls.append(params)
            if "daily" in params and "monthly" in params:
                raise UpstreamError("429")
            if "monthly" in params:
                raise UpstreamError("429 again")
            return {k: v for k, v in SEASONAL_FIXTURE.items() if k not in ("monthly", "monthly_units")}, "u"
        out = fetch_outlook(getter=getter)
        self.assertIsNone(out["monthly"])
        self.assertIn("429", out["monthlyError"])
        self.assertEqual(len(calls), 3)


def history():
    """2000-2003 monthly series with distinct yearly levels, then Jan-Mar 2004 observed."""
    d = {}
    for y, v in ((1999, 0.5), (2000, 1.0), (2001, 3.0), (2002, 0.2), (2003, 2.0)):
        d.update(constant_daily(date(y, 1, 1), date(y, 12, 31), v))
    d.update(constant_daily(date(2004, 1, 1), date(2004, 11, 30), 1.0))
    return d


class ScenarioTests(unittest.TestCase):
    def build(self, outlook=None):
        daily = history()
        months = stats.monthly_totals(daily)
        base, _ = stats.baseline_monthly_mean(months, period=(2000, 2003))
        seasons = stats.season_totals(daily, since=2000)["seasons"]
        return build_scenarios(months, base, seasons, (2004, 11), outlook), base

    def test_start_month_and_length(self):
        res, _ = self.build()
        self.assertEqual(res["startMonth"], "2004-12")
        for sc in res["scenarios"]:
            self.assertEqual(len(sc["months"]), 12)
            self.assertEqual((sc["months"][0]["year"], sc["months"][0]["month"]), (2004, 12))
            self.assertEqual((sc["months"][-1]["year"], sc["months"][-1]["month"]), (2005, 11))

    def test_next_months_rolls_over_year(self):
        self.assertEqual(next_months(2026, 11, 3), [(2026, 12), (2027, 1), (2027, 2)])

    def test_ids_and_analog_years(self):
        res, _ = self.build()
        ids = [s["id"] for s in res["scenarios"]]
        self.assertEqual(ids, ["normal", "wet_like_2001", "wettest_since_2000", "dry_like_2002"])

    def test_wet_analog_replays_actual_months(self):
        res, _ = self.build()
        wet = {s["id"]: s for s in res["scenarios"]}["wet_like_2001"]
        by = {(m["year"], m["month"]): m["rainfallMm"] for m in wet["months"]}
        # window = Dec 2000 (1.0 mm/day) then Jan-Nov 2001 (3.0 mm/day)
        self.assertAlmostEqual(by[(2004, 12)], 31.0)
        self.assertAlmostEqual(by[(2005, 1)], 93.0)
        self.assertAlmostEqual(by[(2005, 6)], 90.0)
        self.assertEqual(wet["analogYear"], 2001)

    def test_dry_analog_and_normal(self):
        res, base = self.build()
        sc = {s["id"]: s for s in res["scenarios"]}
        dry = {(m["year"], m["month"]): m["rainfallMm"] for m in sc["dry_like_2002"]["months"]}
        self.assertAlmostEqual(dry[(2005, 1)], 0.2 * 31)
        normal = {m["month"]: m["rainfallMm"] for m in sc["normal"]["months"]}
        self.assertAlmostEqual(normal[1], base[0], places=1)

    def test_envelope_is_per_month_maximum_and_marked(self):
        res, _ = self.build()
        env = {s["id"]: s for s in res["scenarios"]}["wettest_since_2000"]
        self.assertTrue(env["isEnvelope"])
        self.assertIn("not a year that happened", env["basis"])
        by = {m["month"]: m["rainfallMm"] for m in env["months"]}
        self.assertAlmostEqual(by[1], 3.0 * 31)                    # 2001 is the maximum for every month 2000-2003
        self.assertAlmostEqual(by[2], 3.0 * 28)

    def test_without_outlook_every_month_is_scenario(self):
        res, _ = self.build()
        for sc in res["scenarios"]:
            self.assertTrue(all(m["status"] == "scenario" for m in sc["months"]))

    def test_outlook_label_only_for_full_months_and_value_attached(self):
        ol = [{"year": 2004, "month": 12, "fullMonth": True, "meanMm": 30.0, "memberMinMm": 5.0, "memberMaxMm": 90.0,
               "members": 50, "anomalyVsModelClimatologyMm": -10.0},
              {"year": 2005, "month": 1, "fullMonth": False, "meanMm": 9.0, "memberMinMm": 1.0, "memberMaxMm": 20.0,
               "members": 50}]
        res, _ = self.build(ol)
        for sc in res["scenarios"]:
            first, second, third = sc["months"][:3]
            self.assertEqual(first["status"], "outlook")
            self.assertEqual(first["outlook"]["meanMm"], 30.0)
            self.assertEqual(first["rainfallSource"], "scenario_value")
            self.assertEqual(second["status"], "scenario")         # partial month: not labelled outlook
            self.assertNotIn("outlook", second)
            self.assertEqual(third["status"], "scenario")

    def test_no_complete_season_means_no_analogs(self):
        daily = constant_daily(date(2000, 1, 1), date(2000, 9, 1), 1.0)
        months = stats.monthly_totals(daily)
        base, _ = stats.baseline_monthly_mean(months, period=(2000, 2000))
        seasons = stats.season_totals(daily, since=2000)["seasons"]
        ids = [s["id"] for s in build_scenarios(months, base, seasons, (2000, 9))["scenarios"]]
        self.assertEqual(ids, ["normal", "wettest_since_2000"])


POINTS = [(f"2026-07-{i:02d}", x, y) for i, (x, y) in enumerate(
    [(10, 2.0), (30, 3.0), (50, 5.0), (70, 6.0), (90, 9.0), (110, 10.0), (130, 13.0), (150, 14.0), (170, 18.0)], start=1)]


class FloodScenarioTests(unittest.TestCase):
    def test_refuses_below_minimum_n_with_reason(self):
        with self.assertRaises(InsufficientData) as cm:
            fit_relationship(POINTS[:5])
        self.assertIn("only 5", str(cm.exception))
        self.assertIn("at least 8", str(cm.exception))

    def test_missing_values_are_dropped_not_zeroed(self):
        pts = list(POINTS) + [("2026-08-01", None, 7.0), ("2026-08-02", 80.0, None)]
        fit = fit_relationship(pts)
        self.assertEqual(fit["n"], 9)
        self.assertEqual(fit["droppedMissing"], 2)
        with self.assertRaises(InsufficientData):
            fit_relationship(POINTS[:8] + [("d", None, 1.0)] * 5, min_n=9)

    def test_fit_is_monotone_and_bands_ordered(self):
        fit = fit_relationship(POINTS)
        self.assertGreaterEqual(fit["slopeKm2PerMm"], 0.0)
        rows = flood_for_months(fit, [{"year": 2027, "month": 6, "rainfallMm": 400.0, "status": "scenario"},
                                      {"year": 2027, "month": 8, "rainfallMm": 600.0, "status": "scenario"}])
        for r in rows:
            e = r["expectedFloodedKm2"]
            self.assertLessEqual(e["low"], e["base"])
            self.assertLessEqual(e["base"], e["high"])
            self.assertGreaterEqual(e["low"], 0.0)
        self.assertLess(rows[0]["expectedFloodedKm2"]["base"], rows[1]["expectedFloodedKm2"]["base"])

    def test_negative_slope_is_floored_at_zero(self):
        pts = [(f"d{i}", 10.0 * (i + 1), 20.0 - i) for i in range(9)]
        fit = fit_relationship(pts)
        self.assertLess(fit["rawTheilSenSlope"], 0)
        self.assertEqual(fit["slopeKm2PerMm"], 0.0)

    def test_outside_observed_range_is_null_not_extrapolated(self):
        fit = fit_relationship(POINTS)
        rows = flood_for_months(fit, [{"year": 2027, "month": 2, "rainfallMm": 10.0, "status": "outlook"},
                                      {"year": 2027, "month": 9, "rainfallMm": 3000.0, "status": "scenario"},
                                      {"year": 2027, "month": 10, "rainfallMm": None, "status": "scenario"}])
        self.assertTrue(all(r["expectedFloodedKm2"] is None for r in rows))
        self.assertIn("below", rows[0]["reason"])
        self.assertIn("above", rows[1]["reason"])
        self.assertIn("no rainfall", rows[2]["reason"])

    def test_monthly_to_weekly_conversion(self):
        fit = fit_relationship(POINTS)
        r = flood_for_months(fit, [{"year": 2027, "month": 7, "rainfallMm": 310.0, "status": "scenario"}])[0]
        self.assertAlmostEqual(r["equivalent7DayMm"], 70.0)         # 310 x 7 / 31


class CatalogueTests(unittest.TestCase):
    POWER = {"fillValue": -999.0, "values": {"1991-01-01": 1.0, "2026-11-10": 2.0, "2026-11-12": -999.0}}

    def test_integrated_vs_catalogue_only(self):
        cat = {d["id"]: d for d in build_catalogue({"landsat": {"verified": True, "start": "2000-02-01", "end": "2026-10-30",
                                                                "earliestInCollection": "1987-12-14"}}, self.POWER, None, False)}
        self.assertEqual(cat["nasa_power_rainfall"]["status"], "integrated")
        self.assertEqual(cat["nasa_power_rainfall"]["end"], "2026-11-10")      # fill value day is not "available"
        self.assertEqual(cat["landsat_optical"]["status"], "catalogue_only")
        self.assertEqual(cat["sentinel1_c_band"]["status"], "catalogue_only")
        self.assertEqual(cat["nisar_l_band"]["status"], "catalogue_only")
        self.assertNotIn("era5_rainfall", cat)

    def test_unverified_provider_says_so(self):
        cat = {d["id"]: d for d in build_catalogue(None, None, None, True)}
        self.assertEqual(cat["nisar_l_band"]["status"], "integrated")
        self.assertIn("not verified", cat["nisar_l_band"]["verified"])
        self.assertIn("not verified", cat["sentinel1_c_band"]["verified"])
        self.assertNotIn("nasa_power_rainfall", cat)


if __name__ == "__main__":
    unittest.main()
