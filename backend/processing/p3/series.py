"""Acquisition-network reconstruction and regional/point motion summaries.

Pair rasters are signed differences ``d(secondary) - d(reference)``.  The
solver fits acquisition values to those edges instead of accumulating each
interferogram as if it were an independent cumulative measurement.
"""
from __future__ import annotations

from collections import deque
from datetime import date, datetime, timezone
import json
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine
from pyproj import Geod
from rasterio.warp import transform as transform_coordinates

from . import core


YEAR_DAYS = 365.2425
MINIMUM_RATE_EPOCHS = 6
MINIMUM_RATE_SPAN_DAYS = 90.0


def _parse_epoch(value):
    """Parse an acquisition timestamp and normalize it to UTC."""
    if isinstance(value, np.datetime64):
        if np.isnat(value):
            raise ValueError('Acquisition dates cannot be NaT')
        value = np.datetime_as_string(value, unit='us')
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime(value.year, value.month, value.day)
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError('Acquisition dates cannot be empty')
        if text.endswith('Z') or text.endswith('z'):
            text = text[:-1] + '+00:00'
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValueError(f'Invalid acquisition date: {value!r}') from exc
    else:
        raise TypeError(f'Unsupported acquisition date: {value!r}')
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso_epoch(value):
    return value.isoformat().replace('+00:00', 'Z')


def _date_pairs(pair_dates, pair_count):
    if len(pair_dates) != pair_count:
        raise ValueError('pair_dates must contain one reference/secondary pair per displacement raster')
    parsed = []
    for index, dates in enumerate(pair_dates):
        if isinstance(dates, dict):
            reference = dates.get('reference') or dates.get('ref')
            secondary = dates.get('secondary') or dates.get('sec')
        else:
            try:
                reference, secondary = dates
            except (TypeError, ValueError) as exc:
                raise ValueError(f'Pair {index} must contain reference and secondary dates') from exc
        reference = _parse_epoch(reference)
        secondary = _parse_epoch(secondary)
        if reference == secondary:
            raise ValueError(f'Pair {index} has identical acquisition dates')
        parsed.append((reference, secondary))
    return parsed


def _coerce_displacements(pair_displacements, pair_count):
    try:
        values = np.asarray(pair_displacements, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError('pair_displacements must be a rectangular [pair, row, column] array') from exc
    if values.ndim == 2 and pair_count == 1:
        values = values[np.newaxis, ...]
    if values.ndim != 3 or values.shape[0] != pair_count or min(values.shape[1:]) <= 0:
        raise ValueError('pair_displacements must have shape [pair, row, column]')
    return values


def _coerce_variances(pair_variances, shape):
    if pair_variances is None:
        return None
    n_pairs, height, width = shape
    try:
        values = np.asarray(pair_variances, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError('pair_variances must be scalar, [pair], or [pair, row, column]') from exc
    if values.ndim == 0:
        values = np.full(shape, float(values), dtype=np.float64)
    elif values.shape == (n_pairs,):
        values = np.broadcast_to(values[:, None, None], shape)
    elif values.shape == (n_pairs, height, width):
        pass
    elif n_pairs == 1 and values.shape == (height, width):
        values = values[np.newaxis, ...]
    else:
        raise ValueError('pair_variances must be scalar, [pair], or [pair, row, column]')
    if np.any(np.isfinite(values) & (values <= 0)):
        raise ValueError('Finite pair variances must be greater than zero')
    return values


def _connected_component(pair_indices, valid_edges, reference_index, epoch_count):
    adjacency = [[] for _ in range(epoch_count)]
    for edge_index in valid_edges:
        first, second = pair_indices[edge_index]
        adjacency[first].append(second)
        adjacency[second].append(first)
    if not adjacency[reference_index]:
        return [], []
    connected = {reference_index}
    queue = deque([reference_index])
    while queue:
        node = queue.popleft()
        for neighbor in adjacency[node]:
            if neighbor not in connected:
                connected.add(neighbor)
                queue.append(neighbor)
    nodes = sorted(connected)
    if len(nodes) < 2:
        return [], []
    node_set = set(nodes)
    edges = [i for i in valid_edges if pair_indices[i][0] in node_set and pair_indices[i][1] in node_set]
    return nodes, edges


def _network_design(pair_indices, edge_indices, nodes, reference_index):
    unknowns = [node for node in nodes if node != reference_index]
    columns = {node: index for index, node in enumerate(unknowns)}
    design = np.zeros((len(edge_indices), len(unknowns)), dtype=np.float64)
    for row, edge_index in enumerate(edge_indices):
        first, second = pair_indices[edge_index]
        if first != reference_index:
            design[row, columns[first]] -= 1.0
        if second != reference_index:
            design[row, columns[second]] += 1.0
    return design, unknowns


def _fit_rate(series, epoch_times_days, minimum_rate_epochs, minimum_rate_span_days):
    epoch_count, height, width = series.shape
    flat = series.reshape(epoch_count, -1)
    valid = np.isfinite(flat)
    counts = valid.sum(axis=0)
    times = np.asarray(epoch_times_days, dtype=np.float64)[:, None]
    # Centered acquisition times avoid loss of precision for long-running data.
    sum_t = np.sum(np.where(valid, times, 0.0), axis=0)
    sum_y = np.nansum(flat, axis=0)
    mean_t = np.divide(sum_t, counts, out=np.zeros_like(sum_t), where=counts > 0)
    mean_y = np.divide(sum_y, counts, out=np.zeros_like(sum_y), where=counts > 0)
    centered_t = np.where(valid, times - mean_t[None, :], 0.0)
    centered_y = np.where(valid, flat - mean_y[None, :], 0.0)
    sxx = np.sum(centered_t * centered_t, axis=0)
    sxy = np.sum(centered_t * centered_y, axis=0)
    slope_per_day = np.divide(sxy, sxx, out=np.full_like(sxy, np.nan), where=sxx > 0)
    intercept = mean_y - slope_per_day * mean_t
    prediction = intercept[None, :] + slope_per_day[None, :] * times
    residuals = np.where(valid, flat - prediction, 0.0)
    sse = np.sum(residuals * residuals, axis=0)
    rms = np.sqrt(np.divide(sse, counts, out=np.full_like(sse, np.nan), where=counts > 0))
    standard_error_per_day = np.sqrt(np.divide(
        sse / np.maximum(counts - 2, 1), sxx,
        out=np.full_like(sse, np.nan), where=(counts > 2) & (sxx > 0)
    ))

    indices = np.arange(epoch_count)[:, None]
    earliest = np.min(np.where(valid, indices, epoch_count), axis=0)
    latest = np.max(np.where(valid, indices, -1), axis=0)
    safe_earliest = np.clip(earliest, 0, epoch_count - 1)
    safe_latest = np.clip(latest, 0, epoch_count - 1)
    span = np.where(counts > 0, np.asarray(epoch_times_days)[safe_latest] -
                    np.asarray(epoch_times_days)[safe_earliest], np.nan)
    rate_allowed = (counts >= minimum_rate_epochs) & (span >= minimum_rate_span_days)
    rate = np.where(rate_allowed, slope_per_day * YEAR_DAYS, np.nan)
    rate_se = np.where(rate_allowed, standard_error_per_day * YEAR_DAYS, np.nan)
    rms = np.where(counts >= 3, rms, np.nan)

    def raster(array, dtype=np.float32):
        return array.reshape(height, width).astype(dtype)

    return {
        'rateMmPerYear': raster(rate),
        'validEpochCount': raster(counts, np.uint16),
        'spanDays': raster(span),
        'fitResidualMm': raster(rms),
        'rateStandardErrorMmPerYear': raster(rate_se),
    }


def solve_network(pair_dates, pair_displacements, *, pair_variances=None,
                  reference_epoch=None, minimum_rate_epochs=MINIMUM_RATE_EPOCHS,
                  minimum_rate_span_days=MINIMUM_RATE_SPAN_DAYS,
                  tile_shape=(64, 64)):
    """Reconstruct per-acquisition displacement and estimate supported rates.

    Parameters
    ----------
    pair_dates:
        One ``(reference, secondary)`` acquisition-date pair per raster. Each
        raster value must equal secondary displacement minus reference
        displacement in millimetres.
    pair_displacements:
        A stack or sequence shaped ``[pair, row, column]``. Non-finite values
        are invalid observations and are excluded per pixel.
    pair_variances:
        Optional compatible measurement variances in mm², as a scalar, one
        variance per pair, or a raster stack. Positive finite values activate
        inverse-variance weighted least squares.

    The returned dictionary holds ISO epochs, a ``[time,row,column]``
    displacement stack, its network-fit standard-error stack, and 2-D rate,
    support, span and trend-fit diagnostic rasters.
    """
    raw_values = np.asarray(pair_displacements)
    if raw_values.ndim == 2:
        pair_count = 1
    elif raw_values.ndim == 3:
        pair_count = raw_values.shape[0]
    else:
        try:
            pair_count = len(pair_displacements)
        except TypeError as exc:
            raise ValueError('pair_displacements must be a stack or sequence of rasters') from exc
    if pair_count < 1:
        raise ValueError('At least one pair displacement raster is required')
    values = _coerce_displacements(pair_displacements, pair_count)
    parsed_pairs = _date_pairs(pair_dates, pair_count)
    variances = _coerce_variances(pair_variances, values.shape)
    if isinstance(minimum_rate_epochs, bool) or int(minimum_rate_epochs) < 2:
        raise ValueError('minimum_rate_epochs must be an integer of at least two')
    minimum_rate_epochs = int(minimum_rate_epochs)
    minimum_rate_span_days = float(minimum_rate_span_days)
    if not np.isfinite(minimum_rate_span_days) or minimum_rate_span_days < 0:
        raise ValueError('minimum_rate_span_days must be finite and non-negative')
    if len(tile_shape) != 2 or any(isinstance(v, bool) or int(v) <= 0 for v in tile_shape):
        raise ValueError('tile_shape must contain positive row and column sizes')
    tile_height, tile_width = map(int, tile_shape)

    epoch_dates = sorted({date for pair in parsed_pairs for date in pair})
    if reference_epoch is None:
        reference_date = epoch_dates[0]
    else:
        reference_date = _parse_epoch(reference_epoch)
        if reference_date not in epoch_dates:
            raise ValueError('reference_epoch must be present in the acquisition network')
    epoch_index = {date: index for index, date in enumerate(epoch_dates)}
    reference_index = epoch_index[reference_date]
    pair_indices = [(epoch_index[first], epoch_index[second]) for first, second in parsed_pairs]
    epoch_strings = [_iso_epoch(value) for value in epoch_dates]
    epoch_times_days = np.asarray([(value - reference_date).total_seconds() / 86400.0 for value in epoch_dates])

    n_pairs, height, width = values.shape
    epoch_count = len(epoch_dates)
    series = np.full((epoch_count, height, width), np.nan, dtype=np.float64)
    standard_errors = np.full_like(series, np.nan)
    series_flat = series.reshape(epoch_count, -1)
    se_flat = standard_errors.reshape(epoch_count, -1)

    for row_start in range(0, height, tile_height):
        row_end = min(row_start + tile_height, height)
        for col_start in range(0, width, tile_width):
            col_end = min(col_start + tile_width, width)
            tile_values = values[:, row_start:row_end, col_start:col_end]
            tile_variances = None if variances is None else variances[:, row_start:row_end, col_start:col_end]
            tile_h, tile_w = tile_values.shape[1:]
            tile_size = tile_h * tile_w
            flat_values = tile_values.reshape(n_pairs, tile_size)
            flat_variances = None if tile_variances is None else tile_variances.reshape(n_pairs, tile_size)
            valid = np.isfinite(flat_values)
            if flat_variances is not None:
                valid &= np.isfinite(flat_variances) & (flat_variances > 0)
            packed = np.packbits(valid.T, axis=1)
            patterns, inverse = np.unique(packed, axis=0, return_inverse=True)
            # Convert tile-local coordinates to whole-image flat indices.
            tile_global_indices = (
                np.arange(row_start, row_end)[:, None] * width +
                np.arange(col_start, col_end)[None, :]
            ).reshape(-1)
            for pattern_index, packed_pattern in enumerate(patterns):
                local_pixels = np.flatnonzero(inverse == pattern_index)
                pattern_valid = np.unpackbits(packed_pattern, count=n_pairs).astype(bool)
                _pattern_solve(flat_values, flat_variances, pattern_valid, local_pixels,
                               pair_indices, reference_index, epoch_count,
                               series_flat, se_flat, tile_global_indices)

    diagnostics = _fit_rate(series, epoch_times_days, minimum_rate_epochs, minimum_rate_span_days)
    return {
        'epochs': epoch_strings,
        'referenceEpoch': epoch_strings[reference_index],
        'displacementMm': series.astype(np.float32),
        'displacementStandardErrorMm': standard_errors.astype(np.float32),
        **diagnostics,
    }


def _pattern_solve(values, variances, valid, local_pixels, pair_indices,
                   reference_index, epoch_count, series_flat, se_flat,
                   global_pixels):
    """Solve one common edge-validity pattern in bounded pixel batches."""
    valid_edges = np.flatnonzero(valid)
    nodes, edges = _connected_component(pair_indices, valid_edges, reference_index, epoch_count)
    if not edges:
        return
    design, unknowns = _network_design(pair_indices, edges, nodes, reference_index)
    edge_indices = np.asarray(edges, dtype=np.int64)
    equation_count, unknown_count = design.shape
    if equation_count == 0 or unknown_count == 0:
        return

    for offset in range(0, len(local_pixels), 128):
        pixels = local_pixels[offset:offset + 128]
        observations = values[edge_indices][:, pixels].T
        if variances is None:
            weights = np.ones_like(observations)
        else:
            pixel_variances = variances[edge_indices][:, pixels].T
            if not np.all(np.isfinite(pixel_variances) & (pixel_variances > 0)):
                continue
            weights = 1.0 / pixel_variances
        scale = np.max(weights, axis=1, keepdims=True)
        normalized_weights = weights / scale
        normal = np.einsum('ek,pe,el->pkl', design, normalized_weights, design, optimize=True)
        rhs = np.einsum('ek,pe,pe->pk', design, normalized_weights, observations, optimize=True)
        try:
            beta = np.linalg.solve(normal, rhs[..., None])[..., 0]
            inverse_normal = np.linalg.inv(normal)
        except np.linalg.LinAlgError:
            beta = np.empty((len(pixels), unknown_count), dtype=np.float64)
            inverse_normal = np.full((len(pixels), unknown_count, unknown_count), np.nan)
            for pixel_index in range(len(pixels)):
                root_w = np.sqrt(normalized_weights[pixel_index])
                beta[pixel_index], *_ = np.linalg.lstsq(
                    design * root_w[:, None], observations[pixel_index] * root_w, rcond=None
                )

        residual = observations - beta @ design.T
        weighted_sse = np.sum(normalized_weights * residual * residual, axis=1)
        dof = equation_count - unknown_count
        if variances is None:
            if dof > 0:
                diagonal = np.diagonal(inverse_normal, axis1=1, axis2=2)
                standard_errors = np.sqrt(np.maximum(diagonal * (weighted_sse / dof)[:, None], 0.0))
            else:
                standard_errors = np.full((len(pixels), unknown_count), np.nan)
        else:
            diagonal = np.diagonal(inverse_normal, axis1=1, axis2=2)
            standard_errors = np.sqrt(np.maximum(diagonal / scale, 0.0))

        selected_global = global_pixels[pixels]
        for node in nodes:
            if node == reference_index:
                series_flat[node, selected_global] = 0.0
                se_flat[node, selected_global] = 0.0
        for column, node in enumerate(unknowns):
            series_flat[node, selected_global] = beta[:, column]
            se_flat[node, selected_global] = standard_errors[:, column]


def _manifest(value):
    return core.load_manifest(value) if isinstance(value, (str, Path)) else value


def _load_series(manifest):
    series_path = core.asset_path(manifest, 'series')
    with np.load(series_path, allow_pickle=False) as arrays:
        epochs = [str(value) for value in arrays['epochs'].tolist()]
        displacement = np.asarray(arrays['displacementMm'], dtype=np.float64)
    return epochs, displacement


def _load_asset(manifest, key):
    if key not in manifest.get('assets', {}):
        return None, None
    return core.read_raster(manifest, key)


def _json_key(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), default=str)


def _is_mm(value):
    return isinstance(value, str) and value.strip().lower().replace(' ', '') in {'mm', 'millimetre', 'millimetres', 'millimeter', 'millimeters'}


def _metadata_compatible(manifests, key):
    values = [manifest.get(key) for manifest in manifests]
    if all(value is None for value in values):
        return None
    if any(value is None for value in values):
        raise ValueError(f'Input pair manifests do not all provide {key}')
    present = values
    if len({_json_key(value) for value in present}) > 1:
        raise ValueError(f'Input pair manifests have incompatible {key}')
    return present[0] if present else None


def _native_resolution_metres(grid, supplied):
    """Use the declared source resolution or measure a pixel in WGS84 metres."""
    if supplied is not None:
        if isinstance(supplied, dict):
            try:
                x_size = float(supplied['x'])
                y_size = float(supplied['y'])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError('nativeResolutionMetres must contain numeric x and y values') from exc
        elif np.isscalar(supplied):
            x_size = y_size = float(supplied)
        else:
            raise ValueError('nativeResolutionMetres must be a scalar or an x/y object')
        if not np.isfinite(x_size) or not np.isfinite(y_size) or x_size <= 0 or y_size <= 0:
            raise ValueError('nativeResolutionMetres must be finite and positive')
        return {'x': x_size, 'y': y_size}

    transform = Affine(*grid['transform'])
    column = grid['width'] / 2.0
    row = grid['height'] / 2.0
    sample_points = [transform @ (column, row), transform @ (column + 1.0, row), transform @ (column, row + 1.0)]
    x_values, y_values = transform_coordinates(
        grid['crs'], 'EPSG:4326', [point[0] for point in sample_points], [point[1] for point in sample_points]
    )
    geod = Geod(ellps='WGS84')
    x_length = geod.inv(x_values[0], y_values[0], x_values[1], y_values[1])[2]
    y_length = geod.inv(x_values[0], y_values[0], x_values[2], y_values[2])[2]
    if not np.isfinite(x_length) or not np.isfinite(y_length) or x_length <= 0 or y_length <= 0:
        raise ValueError('Unable to derive native raster resolution in metres')
    return {'x': float(x_length), 'y': float(y_length)}


def _whole_grid_summary(solved):
    displacement = solved['displacementMm']
    rates = solved['rateMmPerYear']
    counts = solved['validEpochCount']
    spans = solved['spanDays']
    residuals = solved['fitResidualMm']
    standard_errors = solved['rateStandardErrorMmPerYear']
    supported_pixels = np.any(np.isfinite(displacement), axis=0)
    rate_values = rates[np.isfinite(rates)]
    count_values = counts[supported_pixels]
    span_values = spans[supported_pixels & np.isfinite(spans)]
    residual_values = residuals[np.isfinite(residuals)]
    standard_error_values = standard_errors[np.isfinite(standard_errors)]
    per_epoch = []
    for index, epoch in enumerate(solved['epochs']):
        values = displacement[index]
        valid = np.isfinite(values)
        per_epoch.append({
            'epoch': epoch,
            'medianDisplacementMm': float(np.median(values[valid])) if np.any(valid) else None,
            'validCellCount': int(np.count_nonzero(valid)),
        })
    return {
        'regionId': 'whole-event-grid',
        'scope': 'all valid pixels in the published analysis grid',
        'epochs': per_epoch,
        'medianRateMmPerYear': float(np.median(rate_values)) if rate_values.size else None,
        'validRateCellCount': int(rate_values.size),
        'validSeriesCellCount': int(np.count_nonzero(supported_pixels)),
        'medianValidEpochCount': float(np.median(count_values)) if count_values.size else None,
        'medianSpanDays': float(np.median(span_values)) if span_values.size else None,
        'medianFitResidualMm': float(np.median(residual_values)) if residual_values.size else None,
        'medianRateStandardErrorMmPerYear': float(np.median(standard_error_values)) if standard_error_values.size else None,
    }


def build_series(event, input_manifest_paths, output_root=None):
    """Build and publish a ground-motion product from LOS-pair manifests."""
    paths = [Path(path) for path in input_manifest_paths]
    if not paths:
        raise ValueError('At least one LOS-pair manifest is required')
    manifests = [core.load_manifest(path) for path in paths]
    pair_dates = []
    displacement_arrays = []
    variances = []
    have_variance = True
    common_grid = None
    for manifest in manifests:
        if manifest.get('displacementConvention', 'positive_away_from_satellite') != 'positive_away_from_satellite':
            raise ValueError('LOS pairs must use the positive-away displacement convention')
        if manifest.get('event') not in (None, event):
            raise ValueError('Input pair event does not match requested event')
        if manifest.get('dataKind') not in ('observed', 'derived', 'scenario', 'synthetic'):
            raise ValueError('Each LOS-pair manifest must state a supported dataKind')
        product = manifest.get('product')
        if product is not None and product not in ('los-pair', 'los_displacement_pair', 'los-displacement-pair'):
            raise ValueError(f'Expected LOS-pair product, got {product!r}')
        dates = manifest.get('acquisitionDates')
        if not isinstance(dates, (list, tuple)) or len(dates) != 2:
            raise ValueError('Each LOS-pair manifest must provide acquisitionDates [reference, secondary]')
        pair_dates.append(dates)
        units = manifest.get('units') if isinstance(manifest.get('units'), dict) else {}
        displacement_units = manifest.get('displacementUnits', units.get('displacement'))
        if not _is_mm(displacement_units):
            raise ValueError('Each LOS-pair displacement asset must be explicitly labeled in millimetres')
        array, grid = core.read_raster(manifest, 'displacementMm')
        if common_grid is None:
            common_grid = grid
        else:
            core.same_grid(common_grid, grid)
        displacement_arrays.append(array)
        if 'validMask' in manifest.get('assets', {}):
            valid_mask, valid_mask_grid = core.read_raster(manifest, 'validMask')
            core.same_grid(common_grid, valid_mask_grid)
            array[~np.isfinite(valid_mask) | (valid_mask <= 0)] = np.nan
        variance = manifest.get('assets', {}).get('varianceMm2')
        if variance is None:
            variance = manifest.get('assets', {}).get('displacementVarianceMm2')
        if variance is None:
            have_variance = False
            variances.append(None)
        else:
            variance_array, variance_grid = core.read_raster(manifest, 'varianceMm2' if 'varianceMm2' in manifest['assets'] else 'displacementVarianceMm2')
            core.same_grid(common_grid, variance_grid)
            variances.append(variance_array)

    reference_ids = [manifest.get('spatialReferenceId') for manifest in manifests]
    if any(not isinstance(value, str) or not value for value in reference_ids):
        raise ValueError('Each LOS-pair manifest must identify its spatialReferenceId')
    if len(set(reference_ids)) != 1:
        raise ValueError('Input LOS-pair manifests use different spatial reference regions')
    for key in ('spatialReferenceHash', 'correctionState', 'correctionsApplied', 'sourceBasis'):
        if any(manifest.get(key) is None for manifest in manifests):
            raise ValueError(f'Each LOS-pair manifest must provide {key}')
    if any(not manifest['spatialReferenceHash'] for manifest in manifests):
        raise ValueError('Each LOS-pair manifest must provide a non-empty spatialReferenceHash')
    if any(not manifest['correctionState'] for manifest in manifests):
        raise ValueError('Each LOS-pair manifest must provide a non-empty correctionState')
    if any(not isinstance(manifest['sourceBasis'], dict) or not manifest['sourceBasis'] for manifest in manifests):
        raise ValueError('Each LOS-pair manifest must provide a populated sourceBasis object')
    for manifest in manifests:
        basis = manifest['sourceBasis']
        required_basis_groups = {
            'orbit': ('orbit', 'orbitDirection', 'orbitPass', 'relativeOrbit', 'flightDirection'),
            'frame': ('frame', 'frameId', 'frameNumber'),
            'maturity': ('maturity', 'productMaturity'),
        }
        for group, aliases in required_basis_groups.items():
            if not any(basis.get(key) is not None and basis.get(key) != '' for key in aliases):
                raise ValueError(f'Each LOS-pair sourceBasis must record {group}')
    for key in (
        'spatialReferenceHash', 'correctionState', 'correctionsApplied', 'sourceBasis',
        'geometry', 'sensor', 'sourceProfile', 'frequency', 'polarization',
        'orbitDirection', 'track', 'processingVersion', 'instrumentMode',
    ):
        _metadata_compatible(manifests, key)

    pair_variances = np.stack(variances) if have_variance else None
    solved = solve_network(pair_dates, np.stack(displacement_arrays), pair_variances=pair_variances)
    source_resolution = _metadata_compatible(manifests, 'nativeResolutionMetres')
    native_resolution = _native_resolution_metres(common_grid, source_resolution)
    latest = solved['displacementMm'][-1]
    source_run_ids = [manifest.get('runId') for manifest in manifests if manifest.get('runId')]
    source_hashes = {}
    source_manifest_hashes = {}
    for index, (manifest, path) in enumerate(zip(manifests, paths)):
        prefix = manifest.get('runId') or f'pair-{index + 1}'
        source_manifest_hashes[prefix] = core.digest(path)
        upstream_hashes = manifest.get('sourceHashes')
        if isinstance(upstream_hashes, dict):
            for name, value in upstream_hashes.items():
                source_hashes[f'{prefix}:{name}'] = value
        elif isinstance(upstream_hashes, list):
            for hash_index, value in enumerate(upstream_hashes):
                source_hashes[f'{prefix}:source-{hash_index + 1}'] = value
        for name, asset in manifest.get('assets', {}).items():
            if asset.get('sha256'):
                source_hashes[f'{prefix}:asset:{name}'] = asset['sha256']
    lineage_synthetic = any(manifest.get('dataKind') == 'synthetic' or manifest.get('syntheticLineage') for manifest in manifests)
    valid_count = solved['validEpochCount']
    rate = solved['rateMmPerYear']
    total_cells = int(valid_count.size)
    rate_cells = int(np.count_nonzero(np.isfinite(rate)))
    regional_summary = _whole_grid_summary(solved)
    warnings = []
    if rate_cells == 0:
        warnings.append('No pixel met the minimum acquisition-count and temporal-span requirements for an annual rate.')
    if np.any((valid_count > 0) & (valid_count < MINIMUM_RATE_EPOCHS)):
        warnings.append('Some pixels have displacement support but fewer than the minimum epochs required for annual rates.')
    if lineage_synthetic:
        warnings.append('Synthetic input lineage is preserved; this product is not an observation.')

    metadata = {
        'dataKind': 'synthetic' if lineage_synthetic else 'derived',
        'syntheticLineage': bool(lineage_synthetic),
        'sourceRunIds': source_run_ids,
        'upstreamRunIds': source_run_ids,
        'sourceHashes': source_hashes,
        'sourceManifestHashes': source_manifest_hashes,
        'algorithm': 'reference-constrained acquisition-network least squares',
        'algorithmVersion': '1.0',
        'displacementConvention': 'positive_away_from_satellite',
        'quality': {
            'minimumRateEpochs': MINIMUM_RATE_EPOCHS,
            'minimumRateSpanDays': MINIMUM_RATE_SPAN_DAYS,
            'compatibleMeasurementVariancesUsed': pair_variances is not None,
        },
        'units': {
            'displacementMm': 'mm',
            'rateMmPerYear': 'mm/year',
            'spanDays': 'days',
            'fitResidualMm': 'mm',
            'rateStandardErrorMmPerYear': 'mm/year',
            'displacementStandardErrorMm': 'mm',
        },
        'nativeResolutionMetres': native_resolution,
        'grid': common_grid,
        'spatialReferenceId': reference_ids[0],
        'referenceEpoch': solved['referenceEpoch'],
        'latestEpoch': solved['epochs'][-1],
        'epochs': solved['epochs'],
        'sourcePairCount': len(manifests),
        'rateMinimumEpochs': MINIMUM_RATE_EPOCHS,
        'rateMinimumSpanDays': MINIMUM_RATE_SPAN_DAYS,
        'coverage': {
            'pixelCount': total_cells,
            'displacementValidPixelCount': regional_summary['validSeriesCellCount'],
            'displacementValidCoverageFraction': (regional_summary['validSeriesCellCount'] / total_cells) if total_cells else 0.0,
            'rateValidPixelCount': rate_cells,
            'rateValidCoverageFraction': (rate_cells / total_cells) if total_cells else 0.0,
        },
        'correctionState': _metadata_compatible(manifests, 'correctionState'),
        'correctionsApplied': _metadata_compatible(manifests, 'correctionsApplied'),
        'appliedCorrections': _metadata_compatible(manifests, 'correctionsApplied'),
        'geometry': _metadata_compatible(manifests, 'geometry'),
        'sourceBasis': _metadata_compatible(manifests, 'sourceBasis'),
        'spatialReferenceHash': _metadata_compatible(manifests, 'spatialReferenceHash'),
        'sensor': _metadata_compatible(manifests, 'sensor') or _metadata_compatible(manifests, 'sourceBasis').get('sensor'),
        'frequency': _metadata_compatible(manifests, 'frequency') or _metadata_compatible(manifests, 'sourceBasis').get('frequency'),
        'polarization': _metadata_compatible(manifests, 'polarization') or _metadata_compatible(manifests, 'sourceBasis').get('polarization'),
        'sourceProfile': _metadata_compatible(manifests, 'sourceProfile') or _metadata_compatible(manifests, 'sourceBasis').get('sourceProfile'),
        'processingVersion': _metadata_compatible(manifests, 'processingVersion') or _metadata_compatible(manifests, 'sourceBasis').get('processingVersion'),
        'orbit': _metadata_compatible(manifests, 'orbit') or _metadata_compatible(manifests, 'sourceBasis').get('orbit'),
        'relativeOrbit': _metadata_compatible(manifests, 'relativeOrbit') or _metadata_compatible(manifests, 'sourceBasis').get('relativeOrbit'),
        'flightDirection': _metadata_compatible(manifests, 'flightDirection') or _metadata_compatible(manifests, 'sourceBasis').get('flightDirection'),
        'track': _metadata_compatible(manifests, 'track') or _metadata_compatible(manifests, 'sourceBasis').get('track'),
        'frame': _metadata_compatible(manifests, 'frame') or _metadata_compatible(manifests, 'sourceBasis').get('frame'),
        'maturity': _metadata_compatible(manifests, 'maturity') or _metadata_compatible(manifests, 'sourceBasis').get('maturity'),
        'warnings': warnings,
        'regionalSummary': regional_summary,
    }

    def writer(stage):
        np.savez_compressed(
            stage / 'series.npz',
            epochs=np.asarray(solved['epochs'], dtype=f'<U{max(map(len, solved["epochs"]))}'),
            displacementMm=solved['displacementMm'],
            displacementStandardErrorMm=solved['displacementStandardErrorMm'],
        )
        products = {
            'displacementMm': latest,
            'rateMmPerYear': solved['rateMmPerYear'],
            'validEpochCount': solved['validEpochCount'],
            'spanDays': solved['spanDays'],
            'fitResidualMm': solved['fitResidualMm'],
            'rateStandardErrorMmPerYear': solved['rateStandardErrorMmPerYear'],
        }
        files = {'series': 'series.npz'}
        for key, array in products.items():
            filename = f'{key}.tif'
            core.write_raster(stage / filename, array, common_grid)
            files[key] = filename
        return files

    return core.publish(event, 'ground-motion', metadata, writer, output_root=output_root)


def _manifest_and_grid(manifest):
    loaded = _manifest(manifest)
    displacement, grid = _load_asset(loaded, 'displacementMm')
    if displacement is None:
        raise ValueError('Ground-motion manifest has no displacementMm asset')
    return loaded, grid


def _cell_for_point(manifest, longitude, latitude):
    loaded, _ = _manifest_and_grid(manifest)
    raster_path = core.asset_path(loaded, 'displacementMm')
    with rasterio.open(raster_path) as dataset:
        if dataset.crs is None:
            raise ValueError('Ground-motion raster has no CRS')
        try:
            x, y = transform_coordinates('EPSG:4326', dataset.crs, [float(longitude)], [float(latitude)])
        except Exception as exc:
            raise ValueError('Unable to transform longitude/latitude into the product CRS') from exc
        row, column = dataset.index(x[0], y[0])
        if row < 0 or row >= dataset.height or column < 0 or column >= dataset.width:
            return loaded, None
        center_x, center_y = dataset.xy(row, column, offset='center')
        center_lon, center_lat = transform_coordinates(dataset.crs, 'EPSG:4326', [center_x], [center_y])
        return loaded, {
            'row': int(row),
            'column': int(column),
            'x': float(center_x),
            'y': float(center_y),
            'longitude': float(center_lon[0]),
            'latitude': float(center_lat[0]),
        }


def _series_point(arrays, row, column):
    epochs, displacement = _load_series(arrays)
    if displacement.ndim != 3 or displacement.shape[0] != len(epochs):
        raise ValueError('Series asset must contain [time,row,column] displacementMm')
    values = displacement[:, row, column]
    return epochs, values


def sample_point(manifest, lon, lat):
    """Sample the native cell containing a WGS84 point from a motion product."""
    try:
        longitude, latitude = float(lon), float(lat)
    except (TypeError, ValueError) as exc:
        raise ValueError('lon and lat must be finite numeric coordinates') from exc
    if not np.isfinite(longitude) or not np.isfinite(latitude) or not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
        raise ValueError('lon and lat must be finite WGS84 coordinates')
    loaded, cell = _cell_for_point(manifest, longitude, latitude)
    if cell is None:
        return {
            'status': 'no-data', 'reason': 'outside_coverage',
            'longitude': longitude, 'latitude': latitude,
            'epochs': loaded.get('epochs', []), 'displacementMm': [],
            'validEpochCount': 0, 'spanDays': None, 'rateMmPerYear': None,
            'rateStandardErrorMmPerYear': None, 'fitResidualMm': None,
        }
    epochs, displacement = _series_point(loaded, cell['row'], cell['column'])
    valid = np.isfinite(displacement)
    if not np.any(valid):
        return {
            'status': 'no-data', 'reason': 'nodata',
            'longitude': longitude, 'latitude': latitude, 'cellCenter': cell,
            'epochs': epochs, 'displacementMm': [None] * len(epochs),
            'validEpochCount': 0, 'spanDays': None, 'rateMmPerYear': None,
            'rateStandardErrorMmPerYear': None, 'fitResidualMm': None,
        }
    sampled = [float(value) if np.isfinite(value) else None for value in displacement]
    result = {
        'status': 'ok', 'reason': None,
        'longitude': longitude, 'latitude': latitude, 'cellCenter': cell,
        'epochs': epochs, 'displacementMm': sampled,
        'validEpochCount': int(np.count_nonzero(valid)),
        'spanDays': None, 'rateMmPerYear': None,
        'rateStandardErrorMmPerYear': None, 'fitResidualMm': None,
    }
    for key in ('rateMmPerYear', 'spanDays', 'fitResidualMm', 'rateStandardErrorMmPerYear'):
        array, _ = _load_asset(loaded, key)
        if array is not None:
            value = array[cell['row'], cell['column']]
            result[key] = float(value) if np.isfinite(value) else None
    return result


def summarize_region(manifest, mask):
    """Summarize valid native cells selected by a boolean raster-shaped mask."""
    loaded, grid = _manifest_and_grid(manifest)
    region = np.asarray(mask, dtype=bool)
    if region.shape != (grid['height'], grid['width']):
        raise ValueError('Region mask must match the product raster shape')
    if not np.any(region):
        return {
            'status': 'no-data', 'reason': 'empty_region', 'selectedCellCount': 0,
            'epochs': loaded.get('epochs', []), 'displacementMm': [],
            'rateMmPerYear': None, 'validRateCellCount': 0,
            'medianValidEpochCount': None, 'medianSpanDays': None,
            'medianFitResidualMm': None,
        }
    epochs, displacement = _load_series(loaded)
    if displacement.shape[1:] != region.shape:
        raise ValueError('Series array grid does not match the displacement asset')
    series_valid = np.isfinite(displacement) & region[None, :, :]
    epoch_summaries = []
    for epoch_index, epoch in enumerate(epochs):
        values = displacement[epoch_index][series_valid[epoch_index]]
        epoch_summaries.append({
            'epoch': epoch,
            'medianDisplacementMm': float(np.median(values)) if values.size else None,
            'validCellCount': int(values.size),
        })
    rate, _ = _load_asset(loaded, 'rateMmPerYear')
    counts, _ = _load_asset(loaded, 'validEpochCount')
    spans, _ = _load_asset(loaded, 'spanDays')
    residuals, _ = _load_asset(loaded, 'fitResidualMm')
    rate_values = np.array([]) if rate is None else rate[region & np.isfinite(rate)]
    count_values = np.array([]) if counts is None else counts[region & np.isfinite(counts)]
    span_values = np.array([]) if spans is None else spans[region & np.isfinite(spans)]
    residual_values = np.array([]) if residuals is None else residuals[region & np.isfinite(residuals)]
    if not np.any(series_valid):
        return {
            'status': 'no-data', 'reason': 'nodata', 'selectedCellCount': int(region.sum()),
            'epochs': epochs, 'displacementMm': epoch_summaries,
            'rateMmPerYear': None, 'validRateCellCount': 0,
            'medianValidEpochCount': None, 'medianSpanDays': None,
            'medianFitResidualMm': None,
        }
    return {
        'status': 'ok', 'reason': None,
        'selectedCellCount': int(region.sum()),
        'validSeriesCellCount': int(np.count_nonzero(np.any(series_valid, axis=0))),
        'epochs': epochs,
        'displacementMm': epoch_summaries,
        'rateMmPerYear': float(np.median(rate_values)) if rate_values.size else None,
        'validRateCellCount': int(rate_values.size),
        'medianValidEpochCount': float(np.median(count_values)) if count_values.size else None,
        'medianSpanDays': float(np.median(span_values)) if span_values.size else None,
        'medianFitResidualMm': float(np.median(residual_values)) if residual_values.size else None,
    }
