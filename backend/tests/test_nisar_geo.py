import unittest

import numpy as np
from pyproj import Transformer

from processing.nisar_flood.geo import Grid, OutsideGrid, pixel_area_km2, study_mask, window_for_bbox
from processing.nisar_flood.constants import STUDY_BBOX

UTM = "EPSG:32651"


def axes(x0=250000.0, x1=310000.0, y_top=1660000.0, y_bot=1600000.0, step=20.0):
    x = np.arange(x0, x1, step) + step / 2
    y = np.arange(y_top, y_bot, -step) - step / 2
    return x, y


class WindowTests(unittest.TestCase):
    def test_window_covers_study_bbox_and_is_small(self):
        x, y = axes()
        rows, cols, grid, info = window_for_bbox(x, y, UTM, STUDY_BBOX, pad=0)
        self.assertLess(grid.width, x.size)
        self.assertLess(grid.height, y.size)
        self.assertEqual(info["requestedRectangleCoveredByGrid"], 1.0)
        # every bbox corner falls inside the window grid
        west, south, east, north = STUDY_BBOX
        for lon, lat in ((west, south), (east, south), (west, north), (east, north)):
            r, c = grid.lonlat_to_rowcol(lon, lat)
            self.assertTrue(0 <= float(r) < grid.height and 0 <= float(c) < grid.width, (lon, lat, r, c))

    def test_pixel_centre_georeferencing_round_trip(self):
        x, y = axes()
        _, _, grid, _ = window_for_bbox(x, y, UTM, STUDY_BBOX)
        lon, lat = grid.rowcol_to_lonlat(np.array([10, 200]), np.array([5, 300]))
        row, col = grid.lonlat_to_rowcol(lon, lat)
        np.testing.assert_allclose(np.floor(row), [10, 200])
        np.testing.assert_allclose(np.floor(col), [5, 300])

    def test_transform_matches_source_coordinates(self):
        """The window grid origin must equal the source pixel edge of the first selected row/col."""
        x, y = axes()
        rows, cols, grid, _ = window_for_bbox(x, y, UTM, STUDY_BBOX, pad=3)
        self.assertAlmostEqual(grid.transform[2], x[cols.start] - 10.0)  # centre minus half a pixel
        self.assertAlmostEqual(grid.transform[5], y[rows.start] + 10.0)
        self.assertEqual(grid.width, cols.stop - cols.start)

    def test_outside_grid_is_an_error_not_an_empty_window(self):
        x, y = axes(x0=400000, x1=420000)
        with self.assertRaises(OutsideGrid):
            window_for_bbox(x, y, UTM, STUDY_BBOX)

    def test_partial_overlap_is_clipped_and_reported(self):
        x, y = axes(x0=250000, x1=280000)  # covers only the west part of the bbox
        _, _, grid, info = window_for_bbox(x, y, UTM, STUDY_BBOX)
        self.assertLess(info["requestedRectangleCoveredByGrid"], 0.95)
        self.assertGreater(info["requestedRectangleCoveredByGrid"], 0.1)
        self.assertLessEqual(grid.width * 20.0, 30000 + 1)

    def test_irregular_or_unsupported_axes_rejected(self):
        x, y = axes()
        bad = x.copy(); bad[100] += 7
        with self.assertRaises(ValueError):
            window_for_bbox(bad, y, UTM, STUDY_BBOX)
        with self.assertRaises(ValueError):  # south-up product needs an explicit adapter
            window_for_bbox(x, y[::-1], UTM, STUDY_BBOX)


class AreaTests(unittest.TestCase):
    def test_utm_pixel_area_uses_true_ground_area(self):
        x, y = axes(step=100.0)
        _, _, grid, _ = window_for_bbox(x, y, UTM, STUDY_BBOX)
        area = pixel_area_km2(grid)
        # UTM scale factor at lon 120.96 (2.04 deg from the central meridian) is ~1.00019, so a 100 m cell is slightly under 0.01 km2
        self.assertAlmostEqual(float(area.mean()), 0.01 / 1.00019 ** 2, delta=2e-6)
        self.assertLess(float(area.max() - area.min()), 1e-5)

    def test_study_area_total_matches_spherical_rectangle(self):
        x, y = axes(step=50.0)
        _, _, grid, _ = window_for_bbox(x, y, UTM, STUDY_BBOX)
        inside = study_mask(grid, STUDY_BBOX)
        total = float(pixel_area_km2(grid)[inside].sum())
        west, south, east, north = STUDY_BBOX
        r = 6371.0088
        expected = r * r * np.radians(east - west) * (np.sin(np.radians(north)) - np.sin(np.radians(south)))
        self.assertAlmostEqual(total, expected, delta=expected * 0.004)

    def test_geographic_grid_area_shrinks_with_latitude(self):
        grid = Grid("EPSG:4326", (0.01, 0.0, 120.0, 0.0, -0.01, 60.0), 10, 400)  # lat 60 .. 56
        area = pixel_area_km2(grid)
        self.assertLess(area[0, 0], area[-1, 0])  # higher-latitude cells are smaller
        self.assertAlmostEqual(float(area[200, 0]), 1.1119 ** 2 * np.cos(np.radians(57.995)), delta=0.01)

    def test_tiny_grids(self):
        grid = Grid(UTM, (30.0, 0.0, 280000.0, 0.0, -30.0, 1630000.0), 1, 1)
        self.assertAlmostEqual(float(pixel_area_km2(grid)[0, 0]) * 1e6, 900.0, delta=1.0)


if __name__ == "__main__":
    unittest.main()
