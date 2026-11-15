"""Climate API: shapes, error codes, cache-only behaviour (no network)."""
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.climate_api import make_router
from climate_fixtures import SEASONAL_FIXTURE, constant_daily, power_payload
from processing.climate.store import read_cache, write_cache

COMMON = ("dataKind", "source", "retrievedAt", "nativeResolution", "warnings", "limitations")


def history_daily():
    d = constant_daily(date(1991, 1, 1), date(2026, 11, 11), 2.0)
    d.update(constant_daily(date(2020, 6, 1), date(2020, 11, 30), 6.0))   # a clearly wet 2020 season
    for iso in ("2026-11-12", "2026-11-13", "2026-11-14"):
        d[iso] = None
    return d


class ApiBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.cache = self.root / "cache"
        self.out = self.root / "output"
        self.out.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def client(self):
        app = FastAPI()
        app.include_router(make_router(self.out, lambda: [], cache_dir=self.cache))
        return TestClient(app)

    def fill(self, power=True, outlook=True, era5=False, availability=False):
        if power:
            write_cache("power_daily", power_payload(history_daily()), {"q": 1}, cache_dir=self.cache,
                        retrieved_at="2026-11-14T10:00:00Z")
        if outlook:
            raw = {"requestUrls": ["u"], "modelRequested": "ecmwf_seas5", "daily": SEASONAL_FIXTURE,
                   "monthly": SEASONAL_FIXTURE, "monthlyError": None}
            write_cache("outlook_raw", raw, {"q": 2}, cache_dir=self.cache, retrieved_at="2026-11-14T10:01:00Z")
        if era5:
            vals = {d: (v if v is not None else None) for d, v in constant_daily(date(2000, 1, 1), date(2026, 11, 14), 1.0).items()}
            write_cache("era5_daily", {"gridCell": {"lat": 1, "lon": 2}, "nativeResolution": "x", "values": vals},
                        {"q": 3}, cache_dir=self.cache)
        if availability:
            write_cache("availability", {"landsat": {"verified": True, "start": "2000-02-01", "end": "2026-10-30",
                                                     "earliestInCollection": "1987-12-14"}}, {}, cache_dir=self.cache)

    def write_nisar(self, passes, kind="derived"):
        d = self.out / "camanava_2026" / "nisar"
        d.mkdir(parents=True)
        (d / "manifest.json").write_text(json.dumps({"dataKind": kind, "passes": passes}))

    def assert_error(self, resp, status, code):
        self.assertEqual(resp.status_code, status, resp.text)
        self.assertEqual(resp.json()["detail"]["code"], code)
        self.assertTrue(resp.json()["detail"]["message"])


class CommonRulesTests(ApiBase):
    def test_unknown_area_everywhere(self):
        self.fill(era5=True)
        c = self.client()
        for path in ("/climate/rainfall/monthly", "/climate/rainfall/season-rank", "/climate/rainfall/trend",
                     "/climate/outlook", "/climate/scenarios", "/timeline/availability", "/climate/rainfall/era5-compare",
                     "/climate/pass-rainfall?dates=2026-06-23", "/climate/rainfall/daily?start=2026-01-01&end=2026-01-02"):
            sep = "&" if "?" in path else "?"
            self.assert_error(c.get(f"/api/v1{path}{sep}area=nowhere"), 404, "unknown_area")

    def test_missing_cache_is_upstream_unavailable_not_fabricated(self):
        c = self.client()
        for path in ("/climate/rainfall/monthly", "/climate/rainfall/season-rank", "/climate/rainfall/trend",
                     "/climate/outlook", "/climate/scenarios"):
            r = c.get(f"/api/v1{path}")
            self.assert_error(r, 503, "upstream_unavailable")
            self.assertIn("cachedAt", r.json()["detail"])

    def test_tampered_cache_is_refused(self):
        self.fill()
        (self.cache / "power_daily.json").write_text("{}")
        self.assertIsNone(read_cache("power_daily", cache_dir=self.cache)[0])
        self.assert_error(self.client().get("/api/v1/climate/rainfall/trend"), 503, "upstream_unavailable")

    def test_failed_refresh_keeps_cache_and_warns(self):
        from processing.climate.store import record_error
        self.fill()
        record_error("power_daily", "HTTP 503", cache_dir=self.cache)
        body = self.client().get("/api/v1/climate/rainfall/trend").json()
        self.assertTrue(any("last refresh failed" in w for w in body["warnings"]))


class RainfallEndpointTests(ApiBase):
    def setUp(self):
        super().setUp()
        self.fill()
        self.c = self.client()

    def test_monthly_shape_and_nulls(self):
        r = self.c.get("/api/v1/climate/rainfall/monthly")
        self.assertEqual(r.status_code, 200)
        b = r.json()
        for k in COMMON + ("point", "units", "baseline", "series"):
            self.assertIn(k, b)
        self.assertEqual(b["dataKind"], "derived")
        self.assertEqual(len(b["baseline"]["monthlyMeanMm"]), 12)
        self.assertEqual(b["series"][0]["year"], 2000)
        jan2000 = b["series"][0]
        self.assertAlmostEqual(jan2000["totalMm"], 62.0)            # 31 days x 2 mm
        self.assertEqual(jan2000["missingDays"], 0)
        nov26 = [s for s in b["series"] if (s["year"], s["month"]) == (2026, 11)][0]
        self.assertIsNone(nov26["totalMm"])
        self.assertIsNone(nov26["anomalyMm"])
        self.assertEqual(nov26["missingDays"], 19)                  # 12-30 Nov: fill-value or not yet available
        self.assertEqual(nov26["partialMm"], 22.0)                  # 11 observed days x 2 mm; the gaps are not zeros

    def test_monthly_since_validation(self):
        self.assertEqual(self.c.get("/api/v1/climate/rainfall/monthly?since=2025").json()["series"][0]["year"], 2025)
        self.assert_error(self.c.get("/api/v1/climate/rainfall/monthly?since=abc"), 422, "invalid_request")
        self.assert_error(self.c.get("/api/v1/climate/rainfall/monthly?since=1800"), 422, "invalid_request")

    def test_daily(self):
        r = self.c.get("/api/v1/climate/rainfall/daily?start=2026-11-10&end=2026-11-14")
        self.assertEqual(r.status_code, 200)
        days = {d["date"]: d for d in r.json()["days"]}
        self.assertEqual(days["2026-11-11"]["mm"], 2.0)
        self.assertIsNone(days["2026-11-12"]["mm"])
        self.assertIn("reason", days["2026-11-12"])
        self.assertEqual(r.json()["units"], "mm/day")

    def test_daily_errors(self):
        g = lambda q: self.c.get("/api/v1/climate/rainfall/daily?" + q)
        self.assert_error(g("start=2026-13-01&end=2026-12-01"), 422, "invalid_request")
        self.assert_error(g("start=2026/01/01&end=2026-01-02"), 422, "invalid_request")
        self.assert_error(g("start=2026-02-02&end=2026-02-01"), 422, "invalid_request")
        self.assert_error(g("start=1991-01-01&end=2026-01-02"), 422, "invalid_request")
        self.assert_error(g("end=2026-01-02"), 422, "invalid_request")
        self.assert_error(g("start=1980-01-01&end=1980-01-31"), 404, "outside_coverage")

    def test_season_rank_incomplete_and_complete(self):
        b = self.c.get("/api/v1/climate/rainfall/season-rank?year=2026").json()
        self.assertFalse(b["complete"])
        self.assertIsNone(b["totalMm"])
        self.assertEqual(b["rankBasis"], "to_date_same_window")
        self.assertEqual(b["observedThrough"], "2026-11-11")
        self.assertGreaterEqual(b["rank"], 1)
        self.assertLessEqual(b["rank"], b["of"])
        b2 = self.c.get("/api/v1/climate/rainfall/season-rank?year=2020").json()
        self.assertEqual((b2["rank"], b2["complete"]), (1, True))   # 6 mm/day all season beats 2 mm/day
        self.assertAlmostEqual(b2["totalMm"], 6.0 * 183)
        self.assertEqual(b2["season"], "Jun-Nov")

    def test_season_rank_errors(self):
        self.assert_error(self.c.get("/api/v1/climate/rainfall/season-rank?year=1999"), 404, "outside_coverage")
        self.assert_error(self.c.get("/api/v1/climate/rainfall/season-rank?year=x"), 422, "invalid_request")

    def test_trend_shape(self):
        b = self.c.get("/api/v1/climate/rainfall/trend").json()
        for k in COMMON + ("method", "period", "slopeMmPerDecade", "ci95", "n", "significant"):
            self.assertIn(k, b)
        self.assertEqual(len(b["ci95"]), 2)
        self.assertTrue(any("no cause" in x for x in b["limitations"]))

    def test_pass_rainfall(self):
        r = self.c.get("/api/v1/climate/pass-rainfall?dates=2026-06-23,2026-11-13")
        self.assertEqual(r.status_code, 200)
        p = {x["date"]: x for x in r.json()["passes"]}
        self.assertEqual(p["2026-06-23"]["prior7DayMm"], 14.0)
        self.assertEqual(p["2026-06-23"]["prior3DayMm"], 6.0)
        self.assertIsNone(p["2026-11-13"]["sameDayMm"])             # not yet available: null
        self.assertIsNone(p["2026-11-13"]["prior3DayMm"])            # 12 Nov is missing, so the window is null
        self.assertIn("2026-11-12", p["2026-11-13"]["reasons"]["prior3DayMm"])

    def test_pass_rainfall_errors_and_nisar_default(self):
        self.assert_error(self.c.get("/api/v1/climate/pass-rainfall?dates=2026-06-31"), 422, "invalid_request")
        self.assert_error(self.c.get("/api/v1/climate/pass-rainfall"), 404, "data_unavailable")
        self.write_nisar([{"date": "2026-07-05", "floodedKm2": 1.0}, {"date": "2026-06-23", "floodedKm2": 2.0}], "synthetic")
        b = self.client().get("/api/v1/climate/pass-rainfall").json()
        self.assertEqual([p["date"] for p in b["passes"]], ["2026-06-23", "2026-07-05"])
        self.assertEqual(b["dataKind"], "synthetic")


class OutlookEndpointTests(ApiBase):
    def test_outlook_shape(self):
        self.fill(power=False)
        b = self.client().get("/api/v1/climate/outlook").json()
        for k in COMMON + ("model", "runDate", "months", "horizonMonths", "firstForecastDate", "ensembleMembers", "anomaly"):
            self.assertIn(k, b)
        self.assertEqual(b["dataKind"], "outlook")
        self.assertIsNone(b["runDate"])
        self.assertEqual(b["ensembleMembers"], 3)
        self.assertEqual([(m["year"], m["month"]) for m in b["months"]], [(2026, 12), (2027, 1)])
        self.assertEqual(b["months"][0]["anomalyVsModelClimatologyMm"], -76.7)
        self.assertTrue(any("not comparable" in x for x in b["limitations"]))


class ScenarioEndpointTests(ApiBase):
    def test_scenarios_shape_and_labels(self):
        self.fill()
        b = self.client().get("/api/v1/climate/scenarios").json()
        self.assertEqual(b["dataKind"], "scenario")
        self.assertEqual(b["startMonth"], "2026-12")
        ids = [s["id"] for s in b["scenarios"]]
        self.assertEqual(ids[0], "normal")
        self.assertIn("wettest_since_2000", ids)
        self.assertTrue(any(i.startswith("wet_like_") for i in ids))
        self.assertTrue(any("not a prediction" in x for x in b["limitations"]))
        for sc in b["scenarios"]:
            self.assertEqual(len(sc["months"]), 12)
            self.assertIn(sc["months"][0]["status"], ("outlook", "scenario"))
            self.assertEqual(sc["months"][-1]["status"], "scenario")

    def test_scenarios_without_outlook_cache_still_work_and_say_so(self):
        self.fill(outlook=False)
        b = self.client().get("/api/v1/climate/scenarios").json()
        self.assertTrue(all(m["status"] == "scenario" for s in b["scenarios"] for m in s["months"]))
        self.assertTrue(any("not cached" in w for w in b["warnings"]))


class FloodScenarioEndpointTests(ApiBase):
    def passes(self, n):
        return [{"date": f"2026-{6 + i // 3:02d}-{(i % 3) * 10 + 5:02d}", "floodedKm2": 1.0 + i} for i in range(n)]

    def test_404_until_nisar_exists(self):
        self.fill()
        self.assert_error(self.client().get("/api/v1/climate/flood-scenario?scenarioId=normal"), 404, "data_unavailable")

    def test_refuses_below_minimum_n(self):
        self.fill()
        self.write_nisar(self.passes(5))
        r = self.client().get("/api/v1/climate/flood-scenario?scenarioId=normal")
        self.assert_error(r, 404, "data_unavailable")
        self.assertIn("at least 8", r.json()["detail"]["message"])

    def test_scenario_id_validation(self):
        self.fill()
        self.write_nisar(self.passes(10))
        c = self.client()
        self.assert_error(c.get("/api/v1/climate/flood-scenario"), 422, "invalid_request")
        r = c.get("/api/v1/climate/flood-scenario?scenarioId=nope")
        self.assert_error(r, 422, "invalid_request")
        self.assertIn("normal", r.json()["detail"]["validIds"])

    def test_shape_with_ten_passes(self):
        self.fill()
        passes = self.passes(10)
        self.write_nisar(passes)
        b = self.client().get("/api/v1/climate/flood-scenario?scenarioId=normal").json()
        self.assertTrue(b["exploratory"])
        self.assertEqual(b["relationship"]["n"], 10)
        self.assertIn("Theil-Sen", b["relationship"]["method"])
        self.assertEqual(len(b["months"]), 12)
        self.assertEqual(b["dataKind"], "scenario")
        for m in b["months"]:
            self.assertIn("status", m)
            self.assertTrue(m["expectedFloodedKm2"] is None or set(m["expectedFloodedKm2"]) == {"low", "base", "high"})

    def test_synthetic_propagates(self):
        self.fill()
        self.write_nisar(self.passes(10), kind="synthetic")
        b = self.client().get("/api/v1/climate/flood-scenario?scenarioId=normal").json()
        self.assertEqual(b["dataKind"], "synthetic")
        self.assertTrue(any("synthetic" in w for w in b["warnings"]))


class TimelineEndpointTests(ApiBase):
    def test_availability_honest_status(self):
        self.fill(era5=True, availability=True)
        b = self.client().get("/api/v1/timeline/availability").json()
        ds = {d["id"]: d for d in b["datasets"]}
        self.assertEqual(ds["nasa_power_rainfall"]["status"], "integrated")
        self.assertEqual(ds["nasa_power_rainfall"]["end"], "2026-11-11")
        self.assertEqual(ds["landsat_optical"]["status"], "catalogue_only")
        self.assertEqual(ds["nisar_l_band"]["status"], "catalogue_only")   # no NISAR product on disk yet
        for d in b["datasets"]:
            self.assertIn(d["kind"], ("climate", "optical", "sar_c", "sar_l", "insar"))
            self.assertIn(d["status"], ("integrated", "catalogue_only"))

    def test_nisar_integrated_when_pass_list_exists(self):
        self.fill(availability=True)
        self.write_nisar([{"date": "2026-06-23", "floodedKm2": 1.0}])
        ds = {d["id"]: d for d in self.client().get("/api/v1/timeline/availability").json()["datasets"]}
        self.assertEqual(ds["nisar_l_band"]["status"], "integrated")

    def test_works_with_empty_cache_and_says_unverified(self):
        b = self.client().get("/api/v1/timeline/availability").json()
        self.assertTrue(b["warnings"])


class Era5Tests(ApiBase):
    def test_comparison_kept_separate(self):
        self.fill(era5=True)
        b = self.client().get("/api/v1/climate/rainfall/era5-compare").json()
        self.assertEqual(b["dataKind"], "observed")
        self.assertIn("ERA5", b["source"]["name"])
        self.assertIn("powerMm", b["series"][0])
        self.assertEqual(len(b["meanByCalendarMonth2000to2020"]), 12)

    def test_missing_cache_503(self):
        self.fill()
        self.assert_error(self.client().get("/api/v1/climate/rainfall/era5-compare"), 503, "upstream_unavailable")


if __name__ == "__main__":
    unittest.main()
