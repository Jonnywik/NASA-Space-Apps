import tempfile
import unittest
from pathlib import Path

import numpy as np
from pyproj import Geod
from rasterio.transform import from_origin

from processing.places.exposure import exposure_for_mask, pixel_area_km2, rhythm_mask
from test_places_support import make_places_root, mask_array, write_raster, GRID_TF, W, N, STEP

PIX_KM2 = abs(Geod(ellps='WGS84').polygon_area_perimeter([W, W + STEP, W + STEP, W], [N, N, N - STEP, N - STEP])[0]) / 1e6


def by_id(res):
    return {z['placeId']: z for z in res['zones']}


class ExposureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = make_places_root(Path(cls.tmp.name) / 'full')
        cls.root_nopop = make_places_root(Path(cls.tmp.name) / 'nopop', population=False, buildings=False)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_pixel_area_matches_geodesic(self):
        a = pixel_area_km2((4, 4), GRID_TF, __import__('pyproj').CRS.from_epsg(4326))
        self.assertAlmostEqual(a[0, 0] / PIX_KM2, 1.0, delta=0.005)  # sphere vs ellipsoid, under 0.5 percent

    def test_hand_checked_barangay_exposure(self):
        res = exposure_for_mask((mask_array(), GRID_TF), 'barangay', nodata=255, root=self.root)
        z = by_id(res)
        # exposed cells: (0,0) pop 10 -> T1-1, (0,1) pop 20 -> T1-1, (1,2) pop 70 -> T2-1, (3,3) pop 160 -> T2-2
        self.assertEqual(set(z), {'T1-1', 'T2-1', 'T2-2'})
        self.assertEqual((z['T1-1']['population'], z['T2-1']['population'], z['T2-2']['population']), (30, 70, 160))
        self.assertEqual((z['T1-1']['buildings'], z['T2-1']['buildings'], z['T2-2']['buildings']), (3, 1, 0))
        self.assertAlmostEqual(z['T1-1']['areaKm2'] / (2 * PIX_KM2), 1.0, delta=0.005)
        self.assertAlmostEqual(z['T2-2']['areaKm2'] / PIX_KM2, 1.0, delta=0.005)
        t = res['totals']
        self.assertEqual((t['population'], t['buildings']), (260, 4))
        self.assertAlmostEqual(t['areaKm2'] / (4 * PIX_KM2), 1.0, delta=0.005)
        self.assertEqual(z['T1-1']['city'], 'Test City Alpha')
        self.assertEqual(res['zones'][0]['placeId'], 'T2-2')  # sorted by population

    def test_city_level(self):
        res = exposure_for_mask((mask_array(), GRID_TF), 'city', nodata=255, root=self.root)
        z = by_id(res)
        self.assertEqual((z['T1']['population'], z['T2']['population']), (30, 230))
        self.assertEqual((z['T1']['buildings'], z['T2']['buildings']), (3, 1))

    def test_nodata_is_not_exposure(self):
        # without declaring 255 as nodata it would count as exposed (non-zero); with nodata it must not
        res_nd = exposure_for_mask((mask_array(), GRID_TF), 'barangay', nodata=255, root=self.root)
        res_bad = exposure_for_mask((mask_array(), GRID_TF), 'barangay', root=self.root)
        self.assertEqual(res_nd['totals']['buildings'], 4)       # the 2 buildings on the nodata cell are excluded
        self.assertEqual(res_bad['totals']['buildings'], 6)
        f = np.where(mask_array() == 1, 1.0, 0.0).astype('float32')
        f[2, 2] = np.nan
        self.assertEqual(exposure_for_mask((f, GRID_TF), 'barangay', root=self.root)['totals']['population'], 260)

    def test_file_mask_uses_raster_nodata(self):
        p = Path(self.tmp.name) / 'mask.tif'
        write_raster(p, mask_array(), nodata=255)
        res = exposure_for_mask(str(p), 'barangay', root=self.root)
        self.assertEqual(res['totals']['population'], 260)

    def test_partial_cells_finer_mask(self):
        # 8 x 8 mask on a half-step grid: all pixels exposed -> every cell counted once, totals preserved
        tf = from_origin(W, N, STEP / 2, STEP / 2)
        full = exposure_for_mask((np.ones((8, 8), 'uint8'), tf), 'city', root=self.root)
        self.assertEqual(full['totals']['population'], sum(range(10, 170, 10)))
        self.assertAlmostEqual(full['totals']['areaKm2'] / (16 * PIX_KM2), 1.0, delta=0.005)
        # only one of the four sub-pixels of cell (0,0) exposed: a quarter of its 10 people (2.5 -> 2 after rounding)
        m = np.zeros((8, 8), 'uint8')
        m[0, 0] = 1
        part = exposure_for_mask((m, tf), 'city', root=self.root)
        self.assertAlmostEqual(part['totals']['population'], 2.5, delta=0.6)
        self.assertEqual(part['totals']['buildings'], 0)  # the centroids sit at the cell centre, sub-pixel (1,1), not (0,0)
        # all four sub-pixels of cell (0,0): the full 10 people and the 3 buildings centred in that cell
        m = np.zeros((8, 8), 'uint8')
        m[0:2, 0:2] = 1
        both = exposure_for_mask((m, tf), 'city', root=self.root)['totals']
        self.assertEqual((both['population'], both['buildings']), (10, 3))

    def test_coarser_mask_averages_population(self):
        tf = from_origin(W, N, STEP * 2, STEP * 2)  # 2 x 2 mask, each pixel covers 4 population cells
        res = exposure_for_mask((np.ones((2, 2), 'uint8'), tf), 'city', root=self.root)
        self.assertAlmostEqual(res['totals']['population'], 1360, delta=14)  # 10+...+160 = 1360, within 1 percent

    def test_unassigned_area_reported(self):
        tf = from_origin(W - STEP * 2, N, STEP, STEP)  # grid shifted so its left half is outside every polygon
        res = exposure_for_mask((np.ones((4, 4), 'uint8'), tf), 'city', root=self.root)
        self.assertAlmostEqual(res['totals']['unassignedAreaKm2'] / (8 * PIX_KM2), 1.0, delta=0.01)

    def test_missing_population_is_null_with_reason(self):
        res = exposure_for_mask((mask_array(), GRID_TF), 'barangay', nodata=255, root=self.root_nopop)
        self.assertIsNone(res['totals']['population'])
        self.assertIsNone(res['totals']['buildings'])
        self.assertIn('population clip not found', res['populationUnavailableReason'])
        self.assertTrue(all(z['population'] is None for z in res['zones']))
        self.assertGreater(res['totals']['areaKm2'], 0)

    def test_empty_mask_and_bad_input(self):
        res = exposure_for_mask((np.zeros((4, 4), 'uint8'), GRID_TF), 'barangay', root=self.root)
        self.assertEqual(res['zones'], [])
        self.assertEqual(res['totals']['population'], 0)
        with self.assertRaises(ValueError):
            exposure_for_mask(np.ones((4, 4)), 'barangay', root=self.root)  # no transform
        with self.assertRaises(ValueError):
            exposure_for_mask((np.ones((4, 4)), GRID_TF), 'street', root=self.root)

    def test_rhythm_mask_half(self):
        counts = np.array([[0, 1, 2, 3], [4, 4, 255, 2], [0, 0, 0, 0], [0, 0, 0, 0]], 'uint8')
        p = Path(self.tmp.name) / 'rhythm.tif'
        write_raster(p, counts, nodata=255)
        m, tf, crs = rhythm_mask(p, pass_count=4, min_fraction=0.5)  # need >= 2
        self.assertEqual(int(m.sum()), 5)
        self.assertFalse(m[1, 2])  # nodata
        self.assertEqual(int(rhythm_mask(p, 4, 0.75)[0].sum()), 3)  # need >= 3


if __name__ == '__main__':
    unittest.main()
