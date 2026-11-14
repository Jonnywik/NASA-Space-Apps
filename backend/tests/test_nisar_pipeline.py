import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio

from processing.nisar_flood import export, pipeline, water
from processing.nisar_flood.constants import STUDY_BBOX
from nisar_fixtures import build_product, passes_from_levels


class PipelineProductTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root, cls.out, cls.analysis = build_product(cls.tmp.name)
        cls.manifest = json.loads((cls.out / "manifest.json").read_text())

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_manifest_is_synthetic_everywhere_and_hashes_match(self):
        m = self.manifest
        self.assertEqual(m["dataKind"], "synthetic")
        self.assertIn("SYNTHETIC", m["warnings"][0])
        self.assertIn("not NISAR", m["sensor"])
        for key, entry in m["assets"].items():
            self.assertEqual(export.sha256_path(self.out / entry["path"]), entry["sha256"], key)
        self.assertEqual(m["passCount"], 4)
        self.assertTrue((self.out / "rhythm.tif").is_file() and (self.out / "rhythm_half.tif").is_file())
        with rasterio.open(self.out / "rhythm.tif") as ds:
            self.assertEqual(ds.nodata, -1)
            self.assertEqual(ds.count, 1)
        for expected in ("rhythm", "rhythm_legend", "rhythm_counts", "permanent_water"):
            self.assertIn(expected, m["assets"])
        for p in m["passes"]:
            for kind in ("overlay", "backscatter", "vegetation", "polarization", "state", "db"):
                self.assertIn(p["assets"][kind], m["assets"])

    def test_rule_is_one_rule_with_recorded_calibration(self):
        rule = self.manifest["rule"]
        self.assertEqual(rule["calibration"]["status"], "calibrated")
        self.assertIn("Manila Bay", rule["calibration"]["knownWater"])
        self.assertIn("urban", rule["description"].lower())
        self.assertTrue(any("Urban double-bounce" in text for text in self.manifest["limitations"]))

    def test_study_area_and_equal_area_total(self):
        area = self.manifest["passes"][0]["studyAreaKm2"]
        west, south, east, north = STUDY_BBOX
        expected = 6371.0088 ** 2 * np.radians(east - west) * (np.sin(np.radians(north)) - np.sin(np.radians(south)))
        self.assertAlmostEqual(area, expected, delta=expected * 0.01)

    def test_nodata_block_lowers_valid_fraction_and_denominator(self):
        fractions = [p["validFraction"] for p in self.manifest["passes"]]
        self.assertLess(fractions[2], 1.0)
        self.assertEqual([f for i, f in enumerate(fractions) if i != 2], [1.0] * 3)
        with rasterio.open(self.out / self.manifest["assets"]["rhythm_counts"]["path"]) as ds:
            flood, valid = ds.read()
        # inside the permanent-water-free nodata block the denominator is 3 passes, elsewhere 4
        self.assertEqual(set(np.unique(valid[valid > 0]).tolist()), {3, 4})
        self.assertTrue(np.all(flood[valid == 0] == -1))

    def test_state_codes_are_disjoint_and_permanent_excluded_from_rhythm(self):
        with rasterio.open(self.out / self.manifest["assets"]["permanent_water"]["path"]) as ds:
            perm = ds.read(1) == 1
        with rasterio.open(self.out / self.manifest["assets"]["rhythm_counts"]["path"]) as ds:
            flood, valid = ds.read()
        self.assertTrue(perm.any())
        self.assertTrue(np.all(flood[perm] == -1))
        for p in self.manifest["passes"]:
            with rasterio.open(self.out / self.manifest["assets"][p["assets"]["state"]]["path"]) as ds:
                state = ds.read(1)
            self.assertTrue(np.all(state[perm & (state != 255)] == 2))   # permanent water is never labelled flooded
            self.assertEqual(set(np.unique(state)).issubset({0, 1, 2, 3, 255}), True)
        # flood count equals the number of passes whose state is "flooded"
        states = []
        for p in self.manifest["passes"]:
            with rasterio.open(self.out / self.manifest["assets"][p["assets"]["state"]]["path"]) as ds:
                states.append(ds.read(1))
        counted = np.sum([s == 1 for s in states], axis=0)
        self.assertTrue(np.array_equal(counted[valid > 0], flood[valid > 0]))

    def test_rhythm_stats_in_manifest_match_recomputation(self):
        a = self.analysis
        stats = water.rhythm_stats(a.rhythm, a.area_km2)
        self.assertEqual(self.manifest["rhythm"]["halfOrMoreKm2"], stats["halfOrMoreKm2"])
        self.assertEqual(len(self.manifest["rhythm"]["legend"]), a.rhythm.pass_count)
        self.assertTrue(self.manifest["rhythm"]["permanentWaterMasked"])

    def test_bay_is_permanent_water_not_flooded(self):
        perm_km2 = self.manifest["permanentWater"]["pixelsTotal"]
        self.assertGreater(perm_km2, 0)
        for p in self.manifest["passes"]:
            self.assertGreater(p["permanentWaterKm2"], 0)
            self.assertLess(p["floodedKm2"], p["permanentWaterKm2"])

    def test_png_bounds_cover_the_study_bbox(self):
        (s, w), (n, e) = self.manifest["bounds"]
        west, south, east, north = STUDY_BBOX
        self.assertLessEqual(w, west + 0.002); self.assertGreaterEqual(e, east - 0.002)
        self.assertLessEqual(s, south + 0.002); self.assertGreaterEqual(n, north - 0.002)

    def test_observed_export_has_no_synthetic_warning_and_bad_kind_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "nisar"
            pipeline.export_product(self.analysis, out, data_kind="observed", source={"name": "x"})
            manifest = json.loads((out / "manifest.json").read_text())
            self.assertEqual(manifest["dataKind"], "observed")
            self.assertFalse(any("SYNTHETIC" in w for w in manifest["warnings"]))
            self.assertEqual(manifest["verification"]["layout"], "unverified")
            with self.assertRaises(ValueError):
                pipeline.export_product(self.analysis, Path(tmp) / "bad", data_kind="real", source={})

    def test_replacing_a_product_is_atomic_and_leaves_no_stage_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "nisar"
            pipeline.export_product(self.analysis, out, data_kind="synthetic", source={"name": "x"})
            first = (out / "manifest.json").read_text()
            pipeline.export_product(self.analysis, out, data_kind="synthetic", source={"name": "y"})
            self.assertNotEqual(first, (out / "manifest.json").read_text())
            self.assertEqual([p.name for p in Path(tmp).iterdir()], ["nisar"])


class AnalyseGuardTests(unittest.TestCase):
    def test_duplicate_date_ids_rejected_and_uncalibrated_default_warned(self):
        with tempfile.TemporaryDirectory() as tmp:
            passes = passes_from_levels(tmp, (0.1, 0.3), spacing=400.0)
            analysis = pipeline.analyse(passes, log=lambda *a: None, min_valid_passes=1)
            self.assertTrue(any("not been calibrated" in w for w in analysis.warnings))
            passes[1].id = passes[0].id
            with self.assertRaises(ValueError):
                pipeline.analyse(passes, log=lambda *a: None)

    def test_saved_rule_round_trips(self):
        with tempfile.TemporaryDirectory() as tmp:
            rule = water.WaterRule(-20.5, -28.0, {"status": "calibrated"})
            pipeline.save_rule(Path(tmp) / "r.json", rule)
            again = pipeline.load_rule(Path(tmp) / "r.json")
            self.assertEqual((again.hh_db, again.hv_db, again.calibration["status"]), (-20.5, -28.0, "calibrated"))

    def test_window_cache_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            passes = passes_from_levels(tmp, (0.2,), spacing=400.0)
            path = Path(tmp) / "w.npz"
            pipeline.save_window(path, passes[0].window)
            back = pipeline.load_window(path)
            np.testing.assert_array_equal(np.nan_to_num(back.hh_db, nan=-1), np.nan_to_num(passes[0].window.hh_db, nan=-1))
            self.assertTrue(back.grid.same_as(passes[0].window.grid))
            self.assertEqual(pipeline.window_sha256(back), pipeline.window_sha256(passes[0].window))


if __name__ == "__main__":
    unittest.main()
