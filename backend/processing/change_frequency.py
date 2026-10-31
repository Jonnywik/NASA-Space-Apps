"""Aggregate compatible coherence-change masks into a detection frequency."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import rasterio
from affine import Affine
from rasterio.crs import CRS
from rasterio.transform import array_bounds, from_origin
from rasterio.warp import Resampling, reproject

from .p3 import core


class ChangeFrequencyError(ValueError):
    """Invalid input comparisons or frequency publication error."""


_SOURCE_BASIS_FIELDS = {
    "sensor", "frequency", "polarization", "polarisation", "track", "relativeOrbit",
    "orbit", "orbitDirection", "orbitPass", "flightDirection", "frame", "frameId",
    "frameNumber", "processingVersion", "maturity", "productMaturity", "instrumentMode",
    "sourceProfile",
}
_ACQUISITION_ID_FIELDS = ("sceneIds", "sourceIds", "acquisitionIds", "sceneId", "sourceId", "acquisitionId")
_PRODUCT_ID_FIELDS = ("granuleIds", "productIds", "granuleId", "productId")
_METHOD_FIELDS = ("method", "algorithm", "algorithmVersion", "methodVersion", "codeVersion")
_GRID_TOLERANCE = 1e-8


@dataclass
class _Comparison:
    path: Path
    manifest: dict[str, Any]
    comparison_id: str
    run_id: str
    source_run_ids: list[str]
    pre_pair: list[str]
    co_pair: list[str]
    all_dates: list[str]
    logical_source_ids: Any
    mask: np.ndarray
    crs: CRS
    transform: Affine
    grid: dict[str, Any]


def _parse_date(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ChangeFrequencyError(f"{label} must contain ISO acquisition dates")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError as exc:
        raise ChangeFrequencyError(f"{label} contains an invalid ISO date: {value!r}") from exc
    return parsed.isoformat()


def _date_pair(value: Any, label: str) -> list[str]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ChangeFrequencyError(f"{label} must contain two acquisition dates")
    dates = [_parse_date(item, label) for item in value]
    if dates[0] >= dates[1]:
        raise ChangeFrequencyError(f"{label} dates must be increasing")
    return dates


def _canonical(value: Any) -> Any:
    """Convert metadata into a stable JSON-compatible form for comparisons."""
    if isinstance(value, Mapping):
        return {str(key): _canonical(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (str, int, float, bool)) or value is None:
        if isinstance(value, float) and not math.isfinite(value):
            raise ChangeFrequencyError("Comparison metadata cannot contain non-finite numbers")
        return value
    raise ChangeFrequencyError(f"Unsupported comparison metadata value: {type(value).__name__}")


def _source_ids(sources: Any, manifest: Mapping[str, Any]) -> Any:
    """Extract source/acquisition identity while ignoring per-run lineage IDs."""
    identities: dict[str, Any] = {}
    if isinstance(sources, Mapping):
        for pair_name in ("pre", "co"):
            pair = sources.get(pair_name)
            if isinstance(pair, Mapping):
                # Scene/acquisition IDs are the logical identity. Product IDs
                # identify a processing instance and may change when the same
                # acquisitions are reprocessed, so use them only as fallback.
                selected = {
                    key: _canonical(pair[key])
                    for key in _ACQUISITION_ID_FIELDS
                    if key in pair and pair[key] not in (None, "", [])
                }
                if not selected:
                    selected = {
                        key: _canonical(pair[key])
                        for key in _PRODUCT_ID_FIELDS
                        if key in pair and pair[key] not in (None, "", [])
                    }
                if selected:
                    identities[pair_name] = selected
        # Some normalized manifests flatten identifiers into sources.sourceIds.
        for key in _ACQUISITION_ID_FIELDS:
            if key in sources and key not in identities and sources[key] not in (None, "", []):
                identities[key] = _canonical(sources[key])
        if not identities:
            for key in _PRODUCT_ID_FIELDS:
                if key in sources and key not in identities and sources[key] not in (None, "", []):
                    identities[key] = _canonical(sources[key])
    top_level = manifest.get("sourceIds")
    if top_level not in (None, "", []):
        identities["manifestSourceIds"] = _canonical(top_level)
    if identities:
        return identities
    # Older producers may expose only a stable source descriptor. Comparing it
    # with dates still rejects a relabeled duplicate, without using run IDs.
    return _canonical(sources)


def _walk_basis(value: Any, path: str = "") -> dict[str, Any]:
    found: dict[str, Any] = {}
    if not isinstance(value, Mapping):
        return found
    for key, item in value.items():
        key_text = str(key)
        location = f"{path}.{key_text}" if path else key_text
        if key_text in _SOURCE_BASIS_FIELDS and item not in (None, "", [], {}):
            found[location] = _canonical(item)
        elif isinstance(item, Mapping):
            found.update(_walk_basis(item, location))
    return found


def _source_basis(manifest: Mapping[str, Any]) -> dict[str, Any]:
    explicit = manifest.get("sourceBasis")
    if isinstance(explicit, Mapping) and explicit:
        basis = _walk_basis(explicit)
        # Preserve fields with nonstandard names in an explicitly supplied basis.
        for key, value in explicit.items():
            if key not in basis and value not in (None, "", [], {}):
                basis[f"sourceBasis.{key}"] = _canonical(value)
    else:
        basis = {}
    for key in _SOURCE_BASIS_FIELDS:
        if key in manifest and manifest[key] not in (None, "", [], {}):
            basis[f"manifest.{key}"] = _canonical(manifest[key])
    sources = manifest.get("sources")
    if isinstance(sources, Mapping):
        basis.update({f"sources.{key}": value for key, value in _walk_basis(sources).items()})

    def has_any(*names: str) -> bool:
        return any(any(path.rsplit(".", 1)[-1] == name for path in basis) for name in names)

    if not has_any("track", "relativeOrbit", "orbit", "orbitDirection", "orbitPass", "flightDirection"):
        raise ChangeFrequencyError("Each comparison sources must identify a track or orbit")
    if not has_any("polarization", "polarisation"):
        raise ChangeFrequencyError("Each comparison sources must identify polarization")
    if not has_any("processingVersion"):
        raise ChangeFrequencyError("Each comparison sources must identify processingVersion")
    return basis


def _method_basis(manifest: Mapping[str, Any]) -> dict[str, Any]:
    method = {key: _canonical(manifest[key]) for key in _METHOD_FIELDS if key in manifest}
    if not method:
        raise ChangeFrequencyError("Each coherence-change manifest must identify its method or algorithmVersion")
    parameters = manifest.get("parameters")
    if not isinstance(parameters, Mapping) or not parameters:
        raise ChangeFrequencyError("Each coherence-change manifest must provide populated parameters")
    return {"method": method, "parameters": _canonical(parameters)}


def _check_grid_metadata(manifest: Mapping[str, Any], crs: CRS, transform: Affine, width: int, height: int) -> None:
    grid = manifest.get("grid")
    if not isinstance(grid, Mapping):
        raise ChangeFrequencyError("Each coherence-change manifest must provide its grid")
    try:
        expected_crs = CRS.from_user_input(grid["crs"])
        expected_transform = tuple(float(value) for value in grid["transform"])
        expected_width = grid["width"]
        expected_height = grid["height"]
    except (KeyError, TypeError, ValueError) as exc:
        raise ChangeFrequencyError("A coherence-change manifest has an invalid grid definition") from exc
    if expected_crs != crs:
        raise ChangeFrequencyError("changeMask CRS does not match its manifest grid")
    if (
        isinstance(expected_width, bool) or isinstance(expected_height, bool)
        or expected_width != width or expected_height != height
    ):
        raise ChangeFrequencyError("changeMask dimensions do not match its manifest grid")
    actual_transform = tuple(transform)[:6]
    if len(expected_transform) != 6 or not np.allclose(
        actual_transform, expected_transform, rtol=0, atol=_GRID_TOLERANCE
    ):
        raise ChangeFrequencyError("changeMask transform does not match its manifest grid")


def _read_geometry(path: Path) -> None:
    try:
        geometry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ChangeFrequencyError(f"Cannot read changeGeometry GeoJSON {path}: {exc}") from exc
    if not isinstance(geometry, Mapping) or geometry.get("type") not in {"FeatureCollection", "Feature"}:
        raise ChangeFrequencyError("changeGeometry must be a GeoJSON FeatureCollection or Feature")
    features = geometry.get("features", []) if geometry.get("type") == "FeatureCollection" else [geometry]
    if not isinstance(features, list):
        raise ChangeFrequencyError("changeGeometry FeatureCollection.features must be a list")
    for index, feature in enumerate(features):
        if not isinstance(feature, Mapping) or feature.get("type") != "Feature":
            raise ChangeFrequencyError(f"changeGeometry feature {index} is invalid")
        if feature.get("geometry") is not None and not isinstance(feature["geometry"], Mapping):
            raise ChangeFrequencyError(f"changeGeometry feature {index} has an invalid geometry")


def _load_comparison(path_value: str | Path, event: str) -> _Comparison:
    path = Path(path_value).expanduser().resolve()
    if not path.is_file():
        raise ChangeFrequencyError(f"Coherence-change manifest does not exist: {path}")
    try:
        manifest = core.load_manifest(path)
    except Exception as exc:
        raise ChangeFrequencyError(f"Cannot load coherence-change manifest {path}: {exc}") from exc
    if manifest.get("event") != event:
        raise ChangeFrequencyError(f"Input manifest event does not match requested event {event!r}")
    if manifest.get("product") != "coherence-change":
        raise ChangeFrequencyError("Expected a coherence-change product manifest")
    data_kind = manifest.get("dataKind")
    if data_kind not in {"observed", "derived", "synthetic"}:
        raise ChangeFrequencyError("Each coherence-change manifest must state dataKind as observed, derived, or synthetic")
    comparison_id = manifest.get("comparisonId")
    if not isinstance(comparison_id, str) or not comparison_id.strip():
        raise ChangeFrequencyError("Each coherence-change manifest must provide a non-empty comparisonId")
    run_id = manifest.get("runId")
    if not isinstance(run_id, str) or not run_id.strip():
        raise ChangeFrequencyError("Each coherence-change manifest must provide a non-empty runId")
    source_run_ids = manifest.get("sourceRunIds")
    if (
        not isinstance(source_run_ids, list) or not source_run_ids
        or any(not isinstance(value, str) or not value.strip() for value in source_run_ids)
    ):
        raise ChangeFrequencyError("Each coherence-change manifest must provide non-empty sourceRunIds")
    pre_pair = _date_pair(manifest.get("prePair"), "prePair")
    co_pair = _date_pair(manifest.get("coPair"), "coPair")
    sources = manifest.get("sources")
    if not isinstance(sources, Mapping) or not sources:
        raise ChangeFrequencyError("Each coherence-change manifest must provide populated sources")
    logical_source_ids = _source_ids(sources, manifest)
    _source_basis(manifest)
    _method_basis(manifest)

    assets = manifest.get("assets")
    if not isinstance(assets, Mapping) or "changeMask" not in assets or "changeGeometry" not in assets:
        raise ChangeFrequencyError("Each coherence-change manifest must include changeMask and changeGeometry assets")
    try:
        mask_path = core.asset_path(manifest, "changeMask")
        geometry_path = core.asset_path(manifest, "changeGeometry")
    except Exception as exc:
        raise ChangeFrequencyError(f"Invalid coherence-change asset path: {exc}") from exc
    _read_geometry(geometry_path)

    try:
        with rasterio.open(mask_path) as dataset:
            if dataset.count != 1:
                raise ChangeFrequencyError("changeMask must be a single-band GeoTIFF")
            if dataset.crs is None:
                raise ChangeFrequencyError("changeMask must declare a CRS")
            crs = CRS.from_user_input(dataset.crs)
            transform = dataset.transform
            if not all(math.isfinite(value) for value in tuple(transform)[:6]):
                raise ChangeFrequencyError("changeMask has a non-finite affine transform")
            if not math.isclose(transform.b, 0.0, abs_tol=_GRID_TOLERANCE) or not math.isclose(
                transform.d, 0.0, abs_tol=_GRID_TOLERANCE
            ):
                raise ChangeFrequencyError("Rotated or sheared changeMask grids are not supported")
            if transform.a == 0 or transform.e == 0:
                raise ChangeFrequencyError("changeMask has a degenerate pixel size")
            values = dataset.read(1, masked=True).astype("float64").filled(np.nan)
            valid = np.isfinite(values) & (dataset.read_masks(1) > 0)
            if np.any(valid & (values != 0) & (values != 1)):
                raise ChangeFrequencyError("changeMask valid cells must contain only 0 or 1")
            values[~valid] = np.nan
            width, height = dataset.width, dataset.height
    except ChangeFrequencyError:
        raise
    except Exception as exc:
        raise ChangeFrequencyError(f"Cannot read changeMask {mask_path}: {exc}") from exc
    _check_grid_metadata(manifest, crs, transform, width, height)
    if values.ndim != 2 or values.size == 0:
        raise ChangeFrequencyError("changeMask must contain a non-empty two-dimensional raster")

    grid = {
        "crs": crs.to_string(),
        "transform": list(tuple(transform)[:6]),
        "width": int(width),
        "height": int(height),
    }
    return _Comparison(
        path=path,
        manifest=manifest,
        comparison_id=comparison_id,
        run_id=run_id,
        source_run_ids=list(source_run_ids),
        pre_pair=pre_pair,
        co_pair=co_pair,
        all_dates=sorted(set(pre_pair + co_pair)),
        logical_source_ids=logical_source_ids,
        mask=values,
        crs=crs,
        transform=transform,
        grid=grid,
    )


def _validate_compatibility(comparisons: Sequence[_Comparison]) -> None:
    comparison_ids = [item.comparison_id for item in comparisons]
    if len(comparison_ids) != len(set(comparison_ids)):
        raise ChangeFrequencyError("comparisonId values must be unique")
    logical_pairs: dict[str, str] = {}
    for item in comparisons:
        signature = json.dumps(
            {"prePair": item.pre_pair, "coPair": item.co_pair, "sourceIds": item.logical_source_ids},
            sort_keys=True,
            separators=(",", ":"),
        )
        previous = logical_pairs.get(signature)
        if previous is not None:
            raise ChangeFrequencyError(
                f"Comparisons {previous!r} and {item.comparison_id!r} repeat the same date and source IDs"
            )
        logical_pairs[signature] = item.comparison_id

    for field, selector in (
        ("dataKind", lambda item: item.manifest["dataKind"]),
        ("sourceBasis", lambda item: _source_basis(item.manifest)),
        ("method and parameters", lambda item: _method_basis(item.manifest)),
    ):
        reference = selector(comparisons[0])
        if any(selector(item) != reference for item in comparisons[1:]):
            raise ChangeFrequencyError(f"Input comparisons have incompatible {field}")
    reference_crs = comparisons[0].crs
    if any(item.crs != reference_crs for item in comparisons[1:]):
        raise ChangeFrequencyError("Input comparison grids use different CRS values")


def _analysis_grid(comparisons: Sequence[_Comparison]) -> tuple[dict[str, Any], Affine]:
    bounds = [array_bounds(item.mask.shape[0], item.mask.shape[1], item.transform) for item in comparisons]
    x_resolution = max(abs(item.transform.a) for item in comparisons)
    y_resolution = max(abs(item.transform.e) for item in comparisons)
    left = min(bound[0] for bound in bounds)
    bottom = min(bound[1] for bound in bounds)
    right = max(bound[2] for bound in bounds)
    top = max(bound[3] for bound in bounds)
    width = max(1, int(math.ceil((right - left) / x_resolution - 1e-10)))
    height = max(1, int(math.ceil((top - bottom) / y_resolution - 1e-10)))
    transform = from_origin(left, top, x_resolution, y_resolution)
    grid_right = left + width * x_resolution
    grid_bottom = top - height * y_resolution
    grid = {
        "crs": comparisons[0].crs.to_string(),
        "transform": list(tuple(transform)[:6]),
        "width": width,
        "height": height,
        "resolution": {"x": x_resolution, "y": y_resolution},
        "bounds": [left, grid_bottom, grid_right, top],
        "inputUnionBounds": [left, bottom, right, top],
        "resampling": "nearest",
        "extent": "union of input changeMask extents",
    }
    return grid, transform


def _align(comparison: _Comparison, grid: Mapping[str, Any], transform: Affine) -> np.ndarray:
    aligned = np.full((grid["height"], grid["width"]), np.nan, dtype=np.float32)
    reproject(
        source=comparison.mask.astype(np.float32, copy=False),
        destination=aligned,
        src_transform=comparison.transform,
        src_crs=comparison.crs,
        src_nodata=np.nan,
        dst_transform=transform,
        dst_crs=comparison.crs,
        dst_nodata=np.nan,
        resampling=Resampling.nearest,
        init_dest_nodata=True,
    )
    valid = np.isfinite(aligned)
    if np.any(valid & (aligned != 0) & (aligned != 1)):
        raise ChangeFrequencyError(f"Nearest-neighbor alignment produced invalid categories for {comparison.comparison_id}")
    return aligned


def _warnings(comparisons: Sequence[_Comparison]) -> list[str]:
    warnings = [
        "Detection frequency is detections divided by mask-supported comparisons; it is descriptive and is not an independent probability.",
        "Comparisons may share acquisitions or time periods, so their counts are not independent measurements.",
        "The change mask does not expose baseline eligibility separately; its zero class includes supported cells without a retained detection.",
    ]
    for left_index, left in enumerate(comparisons):
        left_dates = set(left.all_dates)
        left_start, left_end = left.pre_pair[0], left.co_pair[1]
        for right in comparisons[left_index + 1:]:
            shared = sorted(left_dates.intersection(right.all_dates))
            if shared:
                warnings.append(
                    f"Comparisons {left.comparison_id} and {right.comparison_id} share acquisition dates: {', '.join(shared)}."
                )
            right_start, right_end = right.pre_pair[0], right.co_pair[1]
            if max(left_start, right_start) <= min(left_end, right_end):
                warnings.append(
                    f"Comparison periods overlap for {left.comparison_id} and {right.comparison_id}; detections are not independent observations."
                )
    return warnings


def _input_lineage(comparisons: Sequence[_Comparison]) -> tuple[list[str], dict[str, str], dict[str, Any], list[dict[str, Any]]]:
    source_run_ids: list[str] = []
    manifest_hashes: dict[str, str] = {}
    source_hashes: dict[str, Any] = {}
    synthetic_lineage: list[dict[str, Any]] = []
    for item in comparisons:
        source_run_ids.append(item.run_id)
        manifest_hash = core.digest(item.path)
        manifest_hashes[item.run_id] = manifest_hash
        asset_hashes = {
            name: asset.get("sha256")
            for name, asset in item.manifest.get("assets", {}).items()
            if isinstance(asset, Mapping) and isinstance(asset.get("sha256"), str)
        }
        source_hashes[item.run_id] = {"manifestSha256": manifest_hash, "assetSha256": asset_hashes}
        if item.manifest.get("dataKind") == "synthetic" or item.manifest.get("syntheticLineage"):
            synthetic_lineage.append({
                "event": item.manifest.get("event"),
                "product": item.manifest.get("product"),
                "comparisonId": item.comparison_id,
                "runId": item.run_id,
                "manifestSha256": manifest_hash,
                "assetSha256": asset_hashes,
                "sourceRunIds": item.source_run_ids,
                "upstreamSyntheticLineage": item.manifest.get("syntheticLineage", []),
            })
    return source_run_ids, manifest_hashes, source_hashes, synthetic_lineage


def _valid_range(values: np.ndarray) -> float | None:
    return float(values.min()) if values.size else None


def build_frequency(event, manifest_paths, output_root=None, minimum_observations=2):
    """Publish coherence-change frequency over compatible comparisons.

    Inputs are core product manifests for ``coherence-change``. Categorical
    masks are aligned with nearest-neighbor resampling onto the coarsest grid
    covering their union extent. Counts remain available wherever at least one
    comparison is valid; frequency is masked until ``minimum_observations``
    valid comparisons support a cell.
    """
    if isinstance(minimum_observations, bool) or not isinstance(minimum_observations, (int, np.integer)) or minimum_observations < 1:
        raise ChangeFrequencyError("minimum_observations must be an integer >= 1")
    event_id = str(event)
    try:
        core.safe_name(event_id)
    except Exception as exc:
        raise ChangeFrequencyError(f"Invalid event: {exc}") from exc
    if isinstance(manifest_paths, (str, Path)):
        paths = [manifest_paths]
    else:
        try:
            paths = list(manifest_paths)
        except TypeError as exc:
            raise ChangeFrequencyError("manifest_paths must be a sequence of coherence-change manifest paths") from exc
    if not paths:
        raise ChangeFrequencyError("At least one coherence-change manifest is required")

    comparisons = [_load_comparison(path, event_id) for path in paths]
    _validate_compatibility(comparisons)
    grid, transform = _analysis_grid(comparisons)
    aligned = np.stack([_align(item, grid, transform) for item in comparisons], axis=0)
    valid = np.isfinite(aligned)
    support = valid.sum(axis=0).astype(np.float32)
    detections = ((aligned == 1) & valid).sum(axis=0).astype(np.float32)
    any_support = support > 0
    detection_count = np.full(support.shape, np.nan, dtype=np.float32)
    valid_count = np.full(support.shape, np.nan, dtype=np.float32)
    detection_count[any_support] = detections[any_support]
    valid_count[any_support] = support[any_support]
    frequency_valid = support >= int(minimum_observations)
    frequency = np.full(support.shape, np.nan, dtype=np.float32)
    frequency[frequency_valid] = detections[frequency_valid] / support[frequency_valid]

    supported_frequencies = frequency[frequency_valid]
    observed_support = support[any_support].astype(np.int64)
    support_histogram = {
        str(count): int(np.count_nonzero(observed_support == count))
        for count in range(1, len(comparisons) + 1)
        if np.any(observed_support == count)
    }
    data_kind = "synthetic" if comparisons[0].manifest["dataKind"] == "synthetic" else "derived"
    source_run_ids, source_manifest_hashes, source_hashes, synthetic_lineage = _input_lineage(comparisons)
    all_dates = [date.fromisoformat(value) for item in comparisons for value in item.all_dates]
    date_range = {
        "start": min(all_dates).isoformat(),
        "end": max(all_dates).isoformat(),
    }
    stats = {
        "inputComparisonCount": len(comparisons),
        "supportedPixelCount": int(np.count_nonzero(any_support)),
        "frequencyPixelCount": int(np.count_nonzero(frequency_valid)),
        "detectionsTotal": int(np.nansum(detection_count)),
        "validComparisonCountTotal": int(np.nansum(valid_count)),
        "supportHistogram": support_histogram,
        "minimumFrequency": _valid_range(supported_frequencies),
        "maximumFrequency": float(supported_frequencies.max()) if supported_frequencies.size else None,
        "meanFrequency": float(supported_frequencies.mean()) if supported_frequencies.size else None,
    }
    warnings = _warnings(comparisons)
    for item in comparisons:
        existing = item.manifest.get("warnings")
        if isinstance(existing, list):
            for warning in existing:
                if isinstance(warning, str) and warning and warning not in warnings:
                    warnings.append(f"{item.comparison_id}: {warning}")

    metadata = {
        "dataKind": data_kind,
        "syntheticLineage": synthetic_lineage,
        "sourceRunIds": source_run_ids,
        "sourceManifestHashes": source_manifest_hashes,
        "sourceHashes": source_hashes,
        "method": "fraction of valid coherence-change comparisons with a detection",
        "algorithmVersion": "coherence-change-frequency-1.0",
        "units": {
            "frequency": "fraction",
            "detectionCount": "comparisons",
            "validComparisonCount": "comparisons",
        },
        "minimumObservations": int(minimum_observations),
        "comparisonCount": len(comparisons),
        "comparisonIds": [item.comparison_id for item in comparisons],
        "comparisons": [
            {
                "comparisonId": item.comparison_id,
                "prePair": item.pre_pair,
                "coPair": item.co_pair,
                "acquisitionDates": item.all_dates,
                "sourceRunIds": item.source_run_ids,
                "runId": item.run_id,
            }
            for item in comparisons
        ],
        "dateRange": date_range,
        "sourceBasis": _source_basis(comparisons[0].manifest),
        "thresholds": _canonical(comparisons[0].manifest["parameters"]),
        "inputMethod": _method_basis(comparisons[0].manifest)["method"],
        "grid": grid,
        "support": {
            "definition": "validComparisonCount counts finite 0/1 mask cells after nearest-neighbor alignment; these are the detector's mask-supported cells",
            "frequencyDefinition": "detectionCount / validComparisonCount where validComparisonCount >= minimumObservations",
            "minimumObservations": int(minimum_observations),
            "histogram": support_histogram,
            "eligibility": "The input mask does not preserve baseline eligibility separately; no eligibility mask is inferred.",
        },
        "statistics": stats,
        "warnings": warnings,
    }

    def writer(stage: Path) -> dict[str, str]:
        core.write_raster(stage / "frequency.tif", frequency, grid)
        core.write_raster(stage / "detection_count.tif", detection_count, grid)
        core.write_raster(stage / "valid_comparison_count.tif", valid_count, grid)
        return {
            "frequency": "frequency.tif",
            "detectionCount": "detection_count.tif",
            "validComparisonCount": "valid_comparison_count.tif",
        }

    try:
        return core.publish(event_id, "change-frequency", metadata, writer, output_root=output_root)
    except Exception as exc:
        if isinstance(exc, ChangeFrequencyError):
            raise
        raise ChangeFrequencyError(f"Cannot publish change-frequency product: {exc}") from exc


__all__ = ["ChangeFrequencyError", "build_frequency"]
