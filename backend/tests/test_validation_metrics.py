import unittest
import tempfile
from pathlib import Path
import numpy as np
import rasterio
from rasterio.transform import from_origin
from processing.validation.metrics import agreement, sensitivity, compare_rasters
from processing.nisar_flood.water import WaterRule


class ValidationTests(unittest.TestCase):
    def test_agreement_excludes_nodata(self):
        result = agreement([1, 0, 1, 0, 255, 1], [1, 0, 0, 1, 1, 255])
        self.assertEqual(result["confusionMatrix"], {"tp": 1, "tn": 1, "fp": 1, "fn": 1})
        self.assertEqual(result["overallAgreement"], 0.5)
        self.assertEqual(result["f1"], 0.5)
        self.assertAlmostEqual(result["iou"], 1 / 3)

    def test_undefined_and_invalid(self):
        self.assertIsNone(agreement([0], [0])["f1"])
        with self.assertRaises(ValueError):
            agreement([2], [0])
        with self.assertRaises(ValueError):
            agreement([-1], [0])

    def test_sensitivity_uses_fixed_external_permanent_mask(self):
        hh = [np.array([[-10., -8.]]) for _ in range(2)]
        hv = [np.array([[-10., -8.]]), np.array([[-8., -8.]])]
        result = sensitivity(hh, hv, WaterRule(-9, -9), np.ones((1, 2), bool),
                             np.ones((1, 2)), 1, 1.1)
        self.assertEqual(result["halfOrMoreKm2"], {"-1": 0.0, "0": 1.0, "1": 1.0})

    def test_rasters_use_coarser_grid_and_exclude_nodata(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory) / "fine.tif", Path(directory) / "coarse.tif"]
            for path, data, resolution in [(paths[0], [[1, 1, 0, 0], [1, 1, 0, 0],
                                                      [0, 0, 255, 255], [0, 0, 255, 255]], 1),
                                           (paths[1], [[1, 1], [0, 1]], 2)]:
                array = np.array(data, dtype="uint8")
                with rasterio.open(path, "w", driver="GTiff", width=array.shape[1], height=array.shape[0],
                                   count=1, dtype="uint8", crs="EPSG:32651", nodata=255,
                                   transform=from_origin(0, 4, resolution, resolution)) as dataset:
                    dataset.write(array, 1)
            result = compare_rasters(*paths)
            self.assertEqual(result["confusionMatrix"], {"tp": 1, "tn": 1, "fp": 0, "fn": 1})

    def test_different_crs_and_unknown_values_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory) / "a.tif", Path(directory) / "b.tif"]
            for path, crs, value in [(paths[0], "EPSG:4326", 0), (paths[1], "EPSG:32651", 0)]:
                with rasterio.open(path, "w", driver="GTiff", width=1, height=1, count=1, dtype="int16",
                                   crs=crs, transform=from_origin(1, 1, 1, 1)) as dataset:
                    dataset.write(np.array([[value]], dtype="int16"), 1)
            with self.assertRaisesRegex(ValueError, "same CRS"):
                compare_rasters(*paths)
            with rasterio.open(paths[1], "w", driver="GTiff", width=1, height=1, count=1, dtype="int16",
                               crs="EPSG:4326", transform=from_origin(1, 1, 1, 1)) as dataset:
                dataset.write(np.array([[-1]], dtype="int16"), 1)
            with self.assertRaisesRegex(ValueError, "Normalize"):
                compare_rasters(*paths)


if __name__ == "__main__":
    unittest.main()
