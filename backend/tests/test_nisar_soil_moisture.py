import unittest

import numpy as np

from processing.nisar_flood import soil_moisture as sm

BBOX = (120.88, 14.60, 121.04, 14.82)


class WindowTests(unittest.TestCase):
    def test_window_covers_bbox_with_pad(self):
        lat = np.linspace(15.0, 14.4, 61)  # north-up, 0.01 deg steps
        lon = np.linspace(120.7, 121.2, 51)
        rows, cols = sm.lat_lon_window(lat, lon, BBOX, pad=1)
        self.assertLessEqual(lat[rows].min(), 14.60 + 1e-9)
        self.assertGreaterEqual(lat[rows].max(), 14.82 - 1e-9)
        self.assertLessEqual(lon[cols].min(), 120.88 + 1e-9)
        self.assertGreaterEqual(lon[cols].max(), 121.04 - 1e-9)

    def test_window_outside_raises(self):
        with self.assertRaises(ValueError):
            sm.lat_lon_window(np.array([10.0, 9.9]), np.array([100.0, 100.1]), BBOX)


class MaskTests(unittest.TestCase):
    def test_only_recommended_land_retrievals(self):
        soil = np.array([[0.3, 0.3, -9999.0, 0.3, np.nan]])
        flag = np.array([[0, 1, 0, 0, 0]], dtype=np.int16)  # bit 0 set = not recommended
        water = np.array([[0.0, 0.0, 0.0, 0.9, 0.0]])
        ok = sm.recommended_mask(soil, flag, water)
        self.assertEqual(ok.tolist(), [[True, False, False, False, False]])

    def test_fill_flag_is_not_recommended(self):
        ok = sm.recommended_mask(np.array([0.2]), np.array([-9999], dtype=np.int16), None)
        self.assertFalse(ok[0])


class SummaryTests(unittest.TestCase):
    def window(self, soil, flag):
        return {"lat": np.array([14.7, 14.69]), "lon": np.array([120.9, 120.91]), "soil": np.array(soil, dtype=float),
                "uncertainty": np.full((2, 2), 0.05), "flag": np.array(flag, dtype=np.int16), "waterFraction": np.zeros((2, 2))}

    def test_statistics_use_recommended_cells_only(self):
        s = sm.summarise(self.window([[0.2, 0.4], [0.9, -9999.0]], [[0, 0], [1, 0]]), BBOX)
        self.assertEqual(s["recommendedPixels"], 2)
        self.assertAlmostEqual(s["medianM3M3"], 0.3)
        self.assertAlmostEqual(s["recommendedFraction"], 0.5)

    def test_no_recommended_cells_is_null_with_reason_not_zero(self):
        s = sm.summarise(self.window([[0.2, 0.4], [0.9, 0.1]], [[1, 1], [1, 1]]), BBOX)
        self.assertIsNone(s["medianM3M3"])
        self.assertIn("missingReason", s)

    def test_colourise_transparent_where_not_ok(self):
        rgba = sm.colourise(np.array([[0.1, 0.5]]), np.array([[True, False]]))
        self.assertEqual(rgba.shape, (1, 2, 4))
        self.assertGreater(rgba[0, 0, 3], 0)
        self.assertEqual(rgba[0, 1, 3], 0)


if __name__ == "__main__":
    unittest.main()
