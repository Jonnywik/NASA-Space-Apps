import unittest

import numpy as np

from processing.nisar_flood import polarization, vegetation, water
from processing.nisar_flood.water import WaterRule

NAN = np.nan


class RuleTests(unittest.TestCase):
    def test_thresholds_need_both_channels_and_are_strict(self):
        rule = WaterRule(-18.0, -26.0)
        hh = np.array([-20.0, -20.0, -17.0, -18.0, -30.0])
        hv = np.array([-28.0, -25.0, -28.0, -28.0, -26.0])
        wat, valid = water.classify(hh, hv, rule)
        self.assertEqual(wat.tolist(), [True, False, False, False, False])  # equal to the threshold is not water
        self.assertTrue(valid.all())

    def test_rule_is_the_same_for_every_call(self):
        rule = WaterRule(-18.0, -26.0)
        a = water.classify(np.array([[-22.0]]), np.array([[-30.0]]), rule)[0]
        b = water.classify(np.array([[-22.0]]), np.array([[-30.0]]), rule)[0]
        self.assertTrue(a.all() and b.all())

    def test_nodata_is_neither_water_nor_dry(self):
        rule = WaterRule(-18.0, -26.0)
        hh = np.array([NAN, -22.0, -10.0, -22.0])
        hv = np.array([-30.0, NAN, -15.0, -30.0])
        wat, valid = water.classify(hh, hv, rule)
        self.assertEqual(valid.tolist(), [False, False, True, True])
        self.assertEqual(wat.tolist(), [False, False, False, True])
        # dry = valid & ~water; nodata is excluded from it
        dry = valid & ~wat
        self.assertEqual(dry.tolist(), [False, False, True, False])

    def test_calibration_is_recorded_and_reproducible(self):
        rng = np.random.default_rng(1)
        hh = [rng.normal(-24, 0.8, (60, 60)) for _ in range(3)]
        hv = [rng.normal(-32, 0.8, (60, 60)) for _ in range(3)]
        known = np.zeros((60, 60), bool); known[:, :30] = True
        land_hh = [np.where(known, h, h + 14) for h in hh]  # right half is 14 dB brighter
        land_hv = [np.where(known, h, h + 12) for h in hv]
        rule, record = water.calibrate_rule(land_hh, land_hv, known, known_land=~known, pass_ids=["a", "b", "c"], description="test bay")
        self.assertEqual(record["status"], "calibrated")
        self.assertEqual(record["waterPixels"], 3 * 60 * 30)
        self.assertEqual(rule.calibration, record)
        self.assertGreater(rule.hh_db, record["waterHhDb"]["p95"])  # margin above the 95th percentile
        self.assertLess(rule.hh_db, record["landHhP05Db"])
        self.assertEqual(record["warnings"], [])
        again, _ = water.calibrate_rule(land_hh, land_hv, known)
        self.assertEqual((rule.hh_db, rule.hv_db), (again.hh_db, again.hv_db))
        # most known water is classified as water, nearly no known land is
        wat = water.classify(land_hh[0], land_hv[0], rule)[0]
        self.assertGreater(wat[known].mean(), 0.95)
        self.assertLess(wat[~known].mean(), 0.01)

    def test_calibration_refuses_too_few_pixels(self):
        with self.assertRaises(ValueError):
            water.calibrate_rule([np.full((5, 5), -20.0)], [np.full((5, 5), -28.0)], np.ones((5, 5), bool))

    def test_default_rule_declares_it_is_uncalibrated(self):
        self.assertEqual(WaterRule().calibration["status"], "uncalibrated-default")
        self.assertIn("Urban", "Urban " + water.RULE_DESCRIPTION)
        self.assertIn("urban", water.RULE_DESCRIPTION.lower())


class PermanentWaterTests(unittest.TestCase):
    def stacks(self):
        # 1x6 pixels over 10 passes
        water_stack = np.zeros((10, 1, 6), bool)
        valid_stack = np.ones((10, 1, 6), bool)
        water_stack[:, 0, 0] = True            # always water -> permanent
        water_stack[:9, 0, 1] = True           # 9 of 10 -> permanent at 90 %
        water_stack[:8, 0, 2] = True           # 8 of 10 -> flood-like, not permanent
        water_stack[:2, 0, 3] = True           # rare flood
        valid_stack[2:, 0, 4] = False          # only 2 valid passes: too few to call permanent
        water_stack[:2, 0, 4] = True
        valid_stack[:, 0, 5] = False           # never valid
        return list(water_stack), list(valid_stack)

    def test_fraction_of_valid_passes_and_minimum(self):
        w, v = self.stacks()
        perm, info = water.permanent_water(w, v, fraction=0.9, min_valid_passes=3)
        self.assertEqual(perm[0].tolist(), [True, True, False, False, False, False])
        self.assertEqual(info["pixelsFromPasses"], 2)

    def test_denominator_is_valid_passes_not_all_passes(self):
        # water on 4 of 4 valid passes (6 passes invalid) is permanent, not 4/10
        w = [np.array([[True]])] * 4 + [np.array([[False]])] * 6
        v = [np.array([[True]])] * 4 + [np.array([[False]])] * 6
        perm, _ = water.permanent_water(w, v, fraction=0.9, min_valid_passes=3)
        self.assertTrue(perm[0, 0])

    def test_external_mask_is_added(self):
        w, v = self.stacks()
        ext = np.zeros((1, 6), bool); ext[0, 3] = True
        perm, info = water.permanent_water(w, v, external=ext)
        self.assertTrue(perm[0, 3])
        self.assertTrue(info["externalMaskUsed"])
        with self.assertRaises(ValueError):
            water.permanent_water(w, v, external=np.zeros((2, 2), bool))

    def test_flooded_excludes_permanent_water(self):
        wat = np.array([[True, True, False]])
        valid = np.array([[True, True, True]])
        perm = np.array([[True, False, False]])
        self.assertEqual(water.flooded_from(wat, valid, perm).tolist(), [[False, True, False]])


class RhythmTests(unittest.TestCase):
    def build(self):
        # 5 passes, 1x5 pixels
        #  px0: flooded on 3 of 5 valid           -> count 3 of 5
        #  px1: flooded on 2, invalid on 3        -> count 2 of 2 (invalid is NOT dry)
        #  px2: never flooded, valid 5            -> count 0 of 5
        #  px3: permanent water                   -> excluded
        #  px4: valid on only 1 pass              -> excluded by min_valid_passes
        w = np.zeros((5, 1, 5), bool); v = np.ones((5, 1, 5), bool)
        w[:3, 0, 0] = True
        w[:2, 0, 1] = True; v[2:, 0, 1] = False
        w[:, 0, 3] = True
        v[1:, 0, 4] = False; w[0, 0, 4] = True
        perm = np.zeros((1, 5), bool); perm[0, 3] = True
        flooded = [water.flooded_from(wi, vi, perm) for wi, vi in zip(w, v)]
        in_area = np.ones((1, 5), bool)
        return flooded, list(v), perm, in_area

    def test_counts_and_denominators(self):
        flooded, valid, perm, in_area = self.build()
        r = water.compute_rhythm(flooded, valid, perm, in_area, min_valid_passes=2)
        self.assertEqual(r.flood_count[0].tolist(), [3, 2, 0, -1, -1])
        self.assertEqual(r.valid_count[0].tolist(), [5, 2, 5, 0, 0])
        self.assertEqual(r.countable[0].tolist(), [True, True, True, False, False])

    def test_invalid_passes_are_not_counted_as_dry(self):
        flooded, valid, perm, in_area = self.build()
        r = water.compute_rhythm(flooded, valid, perm, in_area, min_valid_passes=2)
        # pixel 1 was flooded on every pass it was observed (2 of 2); treating the 3 invalid passes as dry would give 2 of 5
        self.assertEqual((int(r.flood_count[0, 1]), int(r.valid_count[0, 1])), (2, 2))
        area = np.ones((1, 5))
        stats = water.rhythm_stats(r, area)
        # half-or-more is judged against the pixel's own valid passes: px0 3/5 yes, px1 2/2 yes, px2 no
        self.assertEqual(stats["halfOrMoreKm2"], 2.0)
        self.assertEqual({d["validPasses"]: d["km2"] for d in stats["byValidPasses"]}, {2: 1.0, 5: 2.0})

    def test_exactly_half_counts_and_just_under_does_not(self):
        flooded = [np.array([[True, True]]), np.array([[False, False]]), np.array([[True, False]]), np.array([[False, False]])]
        valid = [np.ones((1, 2), bool)] * 4
        r = water.compute_rhythm(flooded, valid, np.zeros((1, 2), bool), np.ones((1, 2), bool), min_valid_passes=1)
        stats = water.rhythm_stats(r, np.ones((1, 2)))
        # px0: 2 of 4 = exactly half -> counts; px1: 1 of 4 -> does not
        self.assertEqual(stats["halfOrMoreKm2"], 1.0)

    def test_km2_by_count_uses_pixel_area(self):
        flooded, valid, perm, in_area = self.build()
        r = water.compute_rhythm(flooded, valid, perm, in_area, min_valid_passes=2)
        area = np.array([[0.5, 1.5, 2.0, 9.0, 9.0]])
        stats = water.rhythm_stats(r, area)
        by = {d["count"]: d["km2"] for d in stats["km2ByCount"]}
        self.assertEqual(by[3], 0.5)
        self.assertEqual(by[2], 1.5)
        self.assertEqual(by[1], 0.0)
        self.assertEqual(stats["countableKm2"], 4.0)  # permanent and under-sampled pixels do not enter
        self.assertEqual(stats["floodedAtLeastOnceKm2"], 2.0)

    def test_outside_study_area_is_not_counted(self):
        flooded, valid, perm, _ = self.build()
        in_area = np.array([[True, False, True, True, True]])
        r = water.compute_rhythm(flooded, valid, perm, in_area, min_valid_passes=2)
        self.assertEqual(r.flood_count[0, 1], -1)

    def test_pass_stats(self):
        wat = np.array([[True, True, False, False]])
        valid = np.array([[True, True, True, False]])
        perm = np.array([[True, False, False, False]])
        area = np.array([[1.0, 2.0, 4.0, 8.0]])
        s = water.pass_stats(wat, valid, perm, np.ones((1, 4), bool), area, vegetation=np.array([[False, False, True, True]]))
        self.assertEqual(s["floodedKm2"], 2.0)          # water, valid, not permanent
        self.assertEqual(s["permanentWaterKm2"], 1.0)
        self.assertEqual(s["validKm2"], 7.0)            # the nodata pixel (8 km2) is not valid
        self.assertEqual(s["studyAreaKm2"], 15.0)
        self.assertAlmostEqual(s["validFraction"], 7.0 / 15.0, places=4)
        self.assertEqual(s["floodedVegetationKm2"], 4.0)  # the invalid vegetation pixel is dropped


class VegetationTests(unittest.TestCase):
    def test_brightening_above_dry_reference_and_separate_from_water(self):
        # one pixel row, 5 passes. px0: stable. px1: +6 dB on pass 4. px2: water on pass 4. px3: bright on pass 4 but nodata ref.
        hh = [np.array([[-10.0, -10.0, -10.0, NAN]]) for _ in range(5)]
        hh[4] = np.array([[-10.0, -4.0, -23.0, -4.0]])
        wat = [np.zeros((1, 4), bool) for _ in range(5)]
        wat[4][0, 2] = True
        ref = vegetation.dry_reference_db(hh, wat, min_reference_passes=3)
        np.testing.assert_allclose(ref[0, :3], [-10.0, -10.0, -10.0])
        self.assertTrue(np.isnan(ref[0, 3]))
        perm = np.zeros((1, 4), bool)
        veg = vegetation.flooded_vegetation(hh[4], ref, wat[4], perm, np.ones((1, 4), bool), margin_db=3.0)
        self.assertEqual(veg[0].tolist(), [False, True, False, False])
        self.assertFalse((veg & wat[4]).any())  # never overlaps open water

    def test_landcover_mask_restricts_and_permanent_water_excluded(self):
        hh = np.array([[-4.0, -4.0, -4.0]])
        ref = np.array([[-10.0, -10.0, -10.0]])
        wat = np.zeros((1, 3), bool)
        perm = np.array([[False, False, True]])
        lc = np.array([[40, 50, 40]])  # cropland, built-up, cropland
        cand = vegetation.landcover_candidate_mask(lc)
        veg = vegetation.flooded_vegetation(hh, ref, wat, perm, np.ones((1, 3), bool), margin_db=3.0, candidate=cand)
        self.assertEqual(veg[0].tolist(), [True, False, False])

    def test_reference_needs_enough_passes(self):
        hh = [np.array([[-10.0]]), np.array([[-10.0]])]
        wat = [np.zeros((1, 1), bool)] * 2
        self.assertTrue(np.isnan(vegetation.dry_reference_db(hh, wat, min_reference_passes=3)[0, 0]))


class PolarizationTests(unittest.TestCase):
    def test_channels_and_nodata_alpha(self):
        hh = np.array([[-25.0, 0.0, NAN]]); hv = np.array([[-35.0, -10.0, -20.0]])
        rgba = polarization.polarization_rgba(hh, hv)
        self.assertEqual(rgba[0, 0, :3].tolist(), [0, 0, 127])          # HH and HV at the low end; ratio 10 dB is mid-stretch (0..20)
        self.assertEqual(int(rgba[0, 1, 0]), 255)                       # HH at the top of its stretch
        self.assertEqual(int(rgba[0, 1, 1]), 255)
        self.assertEqual(rgba[0, :, 3].tolist(), [255, 255, 0])
        self.assertEqual(polarization.CHANNELS, {"r": "HH", "g": "HV", "b": "HH/HV"})
        self.assertEqual(len(polarization.EXPLANATION), 3)


if __name__ == "__main__":
    unittest.main()
