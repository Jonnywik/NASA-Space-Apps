from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from processing.p3 import series


def _timestamp(day_offset):
    return (datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(days=day_offset)).isoformat().replace('+00:00', 'Z')


def _pair_observations(epoch_days, epoch_values, pairs):
    dates = []
    differences = []
    for first, second in pairs:
        dates.append((_timestamp(epoch_days[first]), _timestamp(epoch_days[second])))
        differences.append(epoch_values[second] - epoch_values[first])
    return dates, np.asarray(differences, dtype=np.float64)


def _write_raster(path, array, transform):
    array = np.asarray(array, dtype=np.float32)
    with rasterio.open(
        path, 'w', driver='GTiff', width=array.shape[1], height=array.shape[0], count=1,
        dtype='float32', crs='EPSG:4326', transform=transform, nodata=np.nan,
    ) as dataset:
        dataset.write(array, 1)


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class NetworkSolverTests(unittest.TestCase):
    def test_redundant_reversed_irregular_network_recovers_displacement_and_rate(self):
        epoch_days = [0, 11, 29, 59, 109, 209]
        rate = 4.25
        truth = np.asarray([rate * day / series.YEAR_DAYS for day in epoch_days])
        pairs = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (1, 0), (0, 2), (2, 4), (5, 3)]
        dates, displacements = _pair_observations(epoch_days, truth, pairs)

        result = series.solve_network(dates, displacements[:, None, None], tile_shape=(1, 1))

        self.assertEqual(result['referenceEpoch'], _timestamp(0))
        np.testing.assert_allclose(result['displacementMm'][:, 0, 0], truth, atol=1e-6)
        self.assertAlmostEqual(float(result['rateMmPerYear'][0, 0]), rate, places=5)
        self.assertEqual(int(result['validEpochCount'][0, 0]), 6)
        self.assertEqual(float(result['spanDays'][0, 0]), 209.0)
        self.assertLess(float(result['fitResidualMm'][0, 0]), 1e-5)

    def test_pixel_disconnected_from_earliest_epoch_is_unavailable(self):
        epoch_days = [0, 17, 51, 95, 142, 201]
        truth = np.asarray([2.0 * day / series.YEAR_DAYS for day in epoch_days])
        pairs = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (1, 0), (0, 2)]
        dates, displacements = _pair_observations(epoch_days, truth, pairs)
        stack = np.repeat(displacements[:, None, None], 2, axis=2)
        # The right-hand cell has an early component and a later isolated one.
        # It must not be re-zeroed at epoch 3 or blindly summed into a history.
        stack[:, 0, 1] = np.nan
        for edge_index in (0, 1, 3, 4):
            stack[edge_index, 0, 1] = displacements[edge_index]

        result = series.solve_network(dates, stack)

        np.testing.assert_allclose(result['displacementMm'][:3, 0, 1], truth[:3], atol=1e-6)
        self.assertTrue(np.all(np.isnan(result['displacementMm'][3:, 0, 1])))
        self.assertEqual(int(result['validEpochCount'][0, 1]), 3)
        self.assertTrue(np.isnan(result['rateMmPerYear'][0, 1]))
        self.assertTrue(np.isfinite(result['rateMmPerYear'][0, 0]))

    def test_rate_requires_six_epochs_and_at_least_ninety_elapsed_days(self):
        six_short_days = [0, 17, 35, 53, 71, 89]
        six_long_days = [0, 18, 36, 54, 72, 90]
        five_days = [0, 20, 40, 60, 90]

        def solve(days):
            values = np.asarray([3.5 * day / series.YEAR_DAYS for day in days])
            pairs = [(index, index + 1) for index in range(len(days) - 1)]
            dates, differences = _pair_observations(days, values, pairs)
            return series.solve_network(dates, differences[:, None, None])

        self.assertTrue(np.isnan(solve(six_short_days)['rateMmPerYear'][0, 0]))
        self.assertAlmostEqual(float(solve(six_long_days)['rateMmPerYear'][0, 0]), 3.5, places=5)
        five = solve(five_days)
        self.assertEqual(int(five['validEpochCount'][0, 0]), 5)
        self.assertTrue(np.isnan(five['rateMmPerYear'][0, 0]))

    def test_compatible_pair_variances_use_inverse_variance_weights(self):
        pair = (_timestamp(0), _timestamp(30))
        result = series.solve_network(
            [pair, pair], np.asarray([10.0, 20.0])[:, None, None],
            pair_variances=np.asarray([1.0, 9.0]),
        )

        self.assertAlmostEqual(float(result['displacementMm'][1, 0, 0]), 11.0, places=6)
        self.assertAlmostEqual(float(result['displacementStandardErrorMm'][1, 0, 0]), np.sqrt(0.9), places=6)


class PublishedSeriesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='p3-series-')
        self.root = Path(self.temp.name)
        self.transform = from_origin(-123.0, 45.0, 0.01, 0.01)

    def tearDown(self):
        self.temp.cleanup()

    def _write_pair_manifest(self, index, first_day, second_day, difference):
        directory = self.root / f'pair-{index}'
        directory.mkdir()
        displacement_path = directory / 'displacementMm.tif'
        mask_path = directory / 'validMask.tif'
        _write_raster(displacement_path, difference, self.transform)
        valid = np.ones_like(difference, dtype=np.float32)
        valid[1, 1] = 0
        _write_raster(mask_path, valid, self.transform)
        assets = {
            'displacementMm': {'path': displacement_path.name, 'sha256': _hash(displacement_path)},
            'validMask': {'path': mask_path.name, 'sha256': _hash(mask_path)},
        }
        manifest = {
            'schemaVersion': '1.0', 'event': 'series_event', 'product': 'los-pair',
            'runId': f'pair-run-{index}', 'dataKind': 'synthetic', 'syntheticLineage': True,
            'displacementUnits': 'mm', 'units': {'displacement': 'mm'},
            'acquisitionDates': [_timestamp(first_day), _timestamp(second_day)],
            'spatialReferenceId': 'stable-ref-v1', 'spatialReferenceHash': 'sha256:stable-ref',
            'correctionState': 'provider-as-delivered', 'correctionsApplied': [],
            'geometry': {'lookDirection': 'right', 'headingDegrees': 190.0},
            'sourceBasis': {
                'sensor': 'NISAR', 'frequency': 'L', 'phaseToAwaySign': 1,
                'orbitDirection': 'ascending', 'frameId': 'pilot-frame-1', 'maturity': 'science',
            },
            'assets': assets,
        }
        path = directory / 'manifest.json'
        path.write_text(json.dumps(manifest), encoding='utf-8')
        return path

    def _published_manifest(self):
        epoch_days = [0, 20, 40, 60, 80, 100]
        truth = np.asarray([2.5 * day / series.YEAR_DAYS for day in epoch_days])
        pairs = [(index, index + 1) for index in range(5)]
        paths = [
            self._write_pair_manifest(index, epoch_days[first], epoch_days[second],
                                      np.full((2, 2), truth[second] - truth[first], dtype=np.float32))
            for index, (first, second) in enumerate(pairs)
        ]
        return series.build_series('series_event', paths, output_root=self.root / 'published')

    def test_build_publishes_synthetic_series_and_point_and_region_helpers(self):
        manifest_path = self._published_manifest()
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        self.assertEqual(manifest['product'], 'ground-motion')
        self.assertEqual(manifest['dataKind'], 'synthetic')
        self.assertTrue(manifest['syntheticLineage'])
        self.assertEqual(manifest['sourceRunIds'], [f'pair-run-{index}' for index in range(5)])
        self.assertIn('series', manifest['assets'])
        self.assertIn('rateMmPerYear', manifest['assets'])
        self.assertAlmostEqual(manifest['regionalSummary']['medianRateMmPerYear'], 2.5, places=5)
        self.assertEqual(manifest['regionalSummary']['validRateCellCount'], 3)
        self.assertGreater(manifest['nativeResolutionMetres']['x'], 100.0)
        self.assertGreater(manifest['nativeResolutionMetres']['y'], 100.0)

        inside = series.sample_point(manifest_path, -122.995, 44.995)
        self.assertEqual(inside['status'], 'ok')
        self.assertEqual(inside['validEpochCount'], 6)
        self.assertAlmostEqual(inside['rateMmPerYear'], 2.5, places=5)
        self.assertIsNotNone(inside['cellCenter'])
        outside = series.sample_point(manifest_path, -120.0, 44.0)
        self.assertEqual(outside['reason'], 'outside_coverage')
        nodata = series.sample_point(manifest_path, -122.985, 44.985)
        self.assertEqual(nodata['reason'], 'nodata')

        region = np.zeros((2, 2), dtype=bool)
        region[0, 0] = True
        summary = series.summarize_region(manifest_path, region)
        self.assertEqual(summary['status'], 'ok')
        self.assertEqual(summary['validRateCellCount'], 1)
        self.assertAlmostEqual(summary['rateMmPerYear'], 2.5, places=5)
        empty = series.summarize_region(manifest_path, np.zeros((2, 2), dtype=bool))
        self.assertEqual(empty['reason'], 'empty_region')

    def test_incompatible_reference_hash_is_rejected(self):
        pair_a = self._write_pair_manifest(0, 0, 20, np.zeros((2, 2)))
        pair_b = self._write_pair_manifest(1, 20, 40, np.zeros((2, 2)))
        second = json.loads(pair_b.read_text(encoding='utf-8'))
        second['spatialReferenceHash'] = 'sha256:different-ref'
        pair_b.write_text(json.dumps(second), encoding='utf-8')

        with self.assertRaisesRegex(ValueError, 'spatialReferenceHash'):
            series.build_series('series_event', [pair_a, pair_b], output_root=self.root / 'published')

    def test_positive_toward_pairs_cannot_be_published_as_positive_away(self):
        pair = self._write_pair_manifest(0, 0, 20, np.zeros((2, 2)))
        manifest = json.loads(pair.read_text())
        manifest['displacementConvention'] = 'positive_toward_satellite'
        pair.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'positive-away'):
            series.build_series('series_event', [pair], output_root=self.root / 'published')


if __name__ == '__main__':
    unittest.main()
