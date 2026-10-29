"""Publish reviewed, conditional year-by-year motion and water-exposure scenarios.

Configuration schema (JSON, version 1.0)
-----------------------------------------
Required envelope::

    {
      "schemaVersion": "1.0", "dataKind": "scenario" | "synthetic",
      "scenarioId": "reviewed_scenario", "baselineEpoch": "2026-01-01",
      "horizon": {"startYear": 2026, "endYear": 2035},
      "supportedYears": [2026, 2027],
      "review": {"reviewedBy": "name", "evidence": "review record"},
      "losProjection": {"enabled": true},
      "waterExposure": {"enabled": false}
    }

Years must be explicitly listed, between 2026 and 2035, and inside the
declared horizon.  Annual products represent January 1 of each listed year.
The reviewed baseline is an exact date and must match the scenario-inputs
manifest when water exposure is enabled.  LOS-only products may omit terrain.

When enabled, water exposure requires exactly one of:

* ``verticalMotion`` with ``mode: independent-rate`` and a local single-band
  raster ``path`` in ``mm/year`` or ``m/year`` (positive up), ``sourceId``,
  ``sourceRunId``, ``sourceDate``, ``verticalDatum``,
  ``verticalReferenceEpoch``, ``baselineEpoch``, and ``review``; or
* ``verticalMotion`` with ``mode: verticalOnlyLosInference``,
  ``allowVerticalOnlyLosInference: true``,
  ``horizontalMotionNegligible: true``, ``review``, and an ``incidenceAngle``.
  An incidence angle is either ``{"kind":"scalar", "valueDegrees": 35,
  "angleConvention":"from_vertical", "sourceId":"...", "review":{...}}``
  or a raster descriptor with ``path``, ``units":"degrees",
  ``angleConvention":"from_vertical"``, ``sourceId``, and ``review``.
  The inference is ``vUp = -vAway / cos(incidence)``; it is opt-in and is
  recorded as an assumption, never presented as an independent measurement.

Optional ``exposureSnapshots`` may contain ``assetCount`` and/or
``populationCount`` descriptors.  Each has ``path``, respectively
``units:"assets_per_cell"`` or ``units:"persons_per_cell"``, ``sourceId``,
``sourceDate``, and ``provenance``. These are counts per source cell and are
conservatively summed onto an equal or coarser analysis grid. A coarser
snapshot is unavailable rather than upsampled, and snapshots do not reduce the
physical exposure extent. Missing snapshots are reported as null metrics
with a reason. No water levels, forecasts, probabilities,
confidence intervals, or vertical rates are invented by this module.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from affine import Affine
from pyproj import CRS, Geod, Transformer
from rasterio.enums import Resampling
from rasterio.features import shapes
from rasterio.warp import calculate_default_transform, reproject, transform_bounds
from scipy import ndimage
from shapely.geometry import mapping, shape
from shapely import transform as transform_geometry

from . import core


CODE_VERSION = "p3-projection/1.0"
ALLOWED_YEARS = set(range(2026, 2036))
YEAR_DAYS = 365.2425
_SAFE_UNITS = {"mm/year": 1.0, "m/year": 1000.0}
_SNAPSHOT_UNITS = {"assetCount": "assets_per_cell", "populationCount": "persons_per_cell"}


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def _iso_date(value: Any, label: str) -> date:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be an ISO date in YYYY-MM-DD form")
    try:
        result = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO date in YYYY-MM-DD form") from exc
    if result.isoformat() != value:
        raise ValueError(f"{label} must use canonical YYYY-MM-DD form")
    return result


def _epoch(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be an ISO date or timestamp")
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            return datetime.combine(_iso_date(text, label), datetime.min.time(), tzinfo=timezone.utc)
        except ValueError as exc:
            raise ValueError(f"{label} must be an ISO date or timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _safe_source_id(value: Any, label: str) -> str:
    text = _text(value, label)
    core.safe_name(text)
    return text


def _review(record: Any, label: str) -> dict[str, str]:
    if not isinstance(record, dict):
        raise ValueError(f"{label} must include a reviewer and evidence")
    return {
        "reviewedBy": _text(record.get("reviewedBy"), f"{label}.reviewedBy"),
        "evidence": _text(record.get("evidence"), f"{label}.evidence"),
    }


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read {label} JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _input_manifest(path_value: str | Path, *, event: str, product: str) -> tuple[dict[str, Any], Path]:
    path = Path(path_value).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"{product} manifest does not exist: {path}")
    manifest = core.load_manifest(path)
    if manifest.get("event") != event:
        raise ValueError(f"{product} manifest event does not match requested event")
    if manifest.get("product") != product:
        raise ValueError(f"Expected {product} input manifest")
    run_id = _safe_source_id(manifest.get("runId"), f"{product}.runId")
    if path.parent.name != run_id:
        raise ValueError(f"{product} manifest runId does not match its run directory")
    source_runs = manifest.get("sourceRunIds", manifest.get("upstreamRunIds", []))
    if source_runs is None:
        source_runs = []
    if not isinstance(source_runs, list):
        raise ValueError(f"{product}.sourceRunIds must be a list")
    for index, source_run in enumerate(source_runs):
        _safe_source_id(source_run, f"{product}.sourceRunIds[{index}]")
    return manifest, path


def _read_manifest_raster(manifest: dict[str, Any], key: str, *, required: bool = True) -> dict[str, Any] | None:
    if key not in manifest.get("assets", {}):
        if required:
            raise ValueError(f"Input manifest has no {key} asset")
        return None
    path = core.asset_path(manifest, key)
    return _read_raster(path, key)


def _read_raster(path: Path, label: str) -> dict[str, Any]:
    try:
        with rasterio.open(path) as ds:
            if ds.count != 1:
                raise ValueError(f"{label} raster must have exactly one band")
            if ds.crs is None:
                raise ValueError(f"{label} raster has no CRS")
            crs = CRS.from_user_input(ds.crs)
            if not all(math.isfinite(float(v)) for v in tuple(ds.transform)[:6]):
                raise ValueError(f"{label} raster has a non-finite transform")
            if ds.transform.a == 0 or ds.transform.e == 0:
                raise ValueError(f"{label} raster has a degenerate transform")
            values = ds.read(1, masked=True).astype("float64").filled(np.nan)
            valid = np.isfinite(values) & ds.read_masks(1).astype(bool)
            values[~valid] = np.nan
            return {
                "path": path, "label": label, "array": values,
                "valid": valid, "crs": crs, "transform": ds.transform,
                "width": ds.width, "height": ds.height, "nodata": ds.nodata,
                "tags": ds.tags(), "dtype": ds.dtypes[0],
            }
    except rasterio.errors.RasterioError as exc:
        raise ValueError(f"Cannot read {label} raster: {exc}") from exc


def _resolution_metres(info: dict[str, Any], target: CRS) -> tuple[float, float]:
    source_crs: CRS = info["crs"]
    transform: Affine = info["transform"]
    if source_crs == target and source_crs.is_projected:
        axes = source_crs.axis_info
        fx = float(axes[0].unit_conversion_factor or 1.0)
        fy = float(axes[1].unit_conversion_factor or fx) if len(axes) > 1 else fx
        x = math.hypot(transform.a, transform.d) * fx
        y = math.hypot(transform.b, transform.e) * fy
    else:
        bounds = rasterio.transform.array_bounds(info["height"], info["width"], transform)
        warped, _, _ = calculate_default_transform(
            source_crs, target, info["width"], info["height"], *bounds
        )
        axes = target.axis_info
        fx = float(axes[0].unit_conversion_factor or 1.0)
        fy = float(axes[1].unit_conversion_factor or fx) if len(axes) > 1 else fx
        x = math.hypot(warped.a, warped.d) * fx
        y = math.hypot(warped.b, warped.e) * fy
    if not all(math.isfinite(v) and v > 0 for v in (x, y)):
        raise ValueError(f"Unable to derive {info['label']} native resolution in metres")
    return x, y


def _analysis_grid(infos: list[dict[str, Any]], target: CRS) -> dict[str, Any]:
    if not target.is_projected or len(target.axis_info) < 2:
        raise ValueError("Projection analysis requires a projected horizontal CRS")
    axes = target.axis_info
    factor_x = float(axes[0].unit_conversion_factor or 1.0)
    factor_y = float(axes[1].unit_conversion_factor or factor_x)
    if not math.isclose(factor_x, factor_y, rel_tol=0, abs_tol=1e-12):
        raise ValueError("Projection target CRS axes must use the same linear unit")
    native: dict[str, dict[str, float]] = {}
    resolution_m = 0.0
    extent = None
    for info in infos:
        rx, ry = _resolution_metres(info, target)
        native[info["label"]] = {"x": rx, "y": ry}
        resolution_m = max(resolution_m, rx, ry)
        bounds = rasterio.transform.array_bounds(info["height"], info["width"], info["transform"])
        if info["crs"] != target:
            bounds = transform_bounds(info["crs"], target, *bounds, densify_pts=21)
        if not all(math.isfinite(float(v)) for v in bounds):
            raise ValueError(f"Cannot transform {info['label']} coverage to projection CRS")
        left, bottom, right, top = map(float, bounds)
        if extent is None:
            extent = [left, bottom, right, top]
        else:
            extent = [max(extent[0], left), max(extent[1], bottom),
                      min(extent[2], right), min(extent[3], top)]
    if extent is None or extent[0] >= extent[2] or extent[1] >= extent[3]:
        raise ValueError("Projection inputs do not overlap in map space")
    resolution = resolution_m / factor_x
    left = math.floor(extent[0] / resolution) * resolution
    top = math.ceil(extent[3] / resolution) * resolution
    width = max(1, int(math.ceil((extent[2] - left) / resolution)))
    height = max(1, int(math.ceil((top - extent[1]) / resolution)))
    transform = Affine(resolution, 0.0, left, 0.0, -resolution, top)
    return {
        "crs": target.to_string(), "width": width, "height": height,
        "transform": [float(v) for v in tuple(transform)[:6]],
        "resolutionMetres": resolution_m,
        "bounds": [left, top - height * resolution, left + width * resolution, top],
        "nativeResolutionsMetres": native,
        "resolutionRule": "maximum native x/y pixel dimension across projection inputs",
    }


def _warp_continuous(info: dict[str, Any], grid: dict[str, Any], *,
                     scale: float = 1.0, resampling: Resampling = Resampling.bilinear,
                     sum_counts: bool = False) -> tuple[np.ndarray, np.ndarray]:
    shape_ = (grid["height"], grid["width"])
    source = (np.asarray(info["array"], dtype=np.float64) * scale).copy()
    source[~info["valid"]] = np.nan
    output = np.full(shape_, np.nan, dtype=np.float64)
    valid_output = np.zeros(shape_, dtype=np.uint8)
    method = Resampling.sum if sum_counts else resampling
    reproject(
        source=source, destination=output, src_transform=info["transform"],
        src_crs=info["crs"], src_nodata=np.nan,
        dst_transform=Affine(*grid["transform"]), dst_crs=grid["crs"],
        dst_nodata=np.nan, resampling=method,
    )
    reproject(
        source=info["valid"].astype(np.uint8), destination=valid_output,
        src_transform=info["transform"], src_crs=info["crs"], src_nodata=None,
        dst_transform=Affine(*grid["transform"]), dst_crs=grid["crs"],
        dst_nodata=0, resampling=Resampling.nearest,
    )
    valid = (valid_output == 1) & np.isfinite(output)
    output[~valid] = np.nan
    return output.astype(np.float32), valid


def _warp_mask(info: dict[str, Any], grid: dict[str, Any], label: str) -> tuple[np.ndarray, np.ndarray]:
    src = np.asarray(info["array"])
    finite = info["valid"]
    valid_values = np.unique(src[finite])
    if not set(valid_values.tolist()).issubset({0, 1}):
        raise ValueError(f"{label} mask values must be 0 or 1; nodata must use the raster mask")
    destination = np.full((grid["height"], grid["width"]), 255, dtype=np.uint8)
    source = np.where(finite, src, 255).astype(np.uint8)
    reproject(
        source=source, destination=destination, src_transform=info["transform"],
        src_crs=info["crs"], src_nodata=255,
        dst_transform=Affine(*grid["transform"]), dst_crs=grid["crs"],
        dst_nodata=255, resampling=Resampling.nearest,
    )
    return destination, destination != 255


def _local_source(spec: Any, config_path: Path, label: str) -> dict[str, Any]:
    if not isinstance(spec, dict):
        raise ValueError(f"{label} must be a source object")
    path_value = _text(spec.get("path"), f"{label}.path")
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = config_path.parent / path
    path = path.resolve()
    if not path.is_file():
        raise ValueError(f"{label} raster does not exist: {path}")
    info = _read_raster(path, label)
    info["sourceSpec"] = spec
    info["sha256"] = core.digest(path)
    return info


def _validate_scenario(config: dict[str, Any]) -> tuple[str, date, list[int], dict[str, Any], dict[str, Any]]:
    if config.get("schemaVersion") != "1.0":
        raise ValueError("schemaVersion must be '1.0'")
    if config.get("dataKind") not in ("scenario", "synthetic"):
        raise ValueError("dataKind must be 'scenario' or 'synthetic'")
    scenario_id = _safe_source_id(config.get("scenarioId"), "scenarioId")
    baseline = _iso_date(config.get("baselineEpoch"), "baselineEpoch")
    review = _review(config.get("review"), "review")
    horizon = config.get("horizon")
    if not isinstance(horizon, dict):
        raise ValueError("horizon must declare startYear and endYear")
    start = horizon.get("startYear")
    end = horizon.get("endYear")
    if any(isinstance(v, bool) or not isinstance(v, int) for v in (start, end)):
        raise ValueError("horizon startYear and endYear must be integer years")
    if start not in ALLOWED_YEARS or end not in ALLOWED_YEARS or start > end:
        raise ValueError("horizon must be an ordered range inside 2026–2035")
    years = config.get("supportedYears")
    if not isinstance(years, list) or not years:
        raise ValueError("supportedYears must explicitly list at least one year")
    if any(isinstance(year, bool) or not isinstance(year, int) for year in years):
        raise ValueError("supportedYears entries must be integer years")
    if len(set(years)) != len(years):
        raise ValueError("supportedYears cannot contain duplicates")
    if years != sorted(years):
        raise ValueError("supportedYears must be in ascending order")
    if any(year not in ALLOWED_YEARS or year < start or year > end for year in years):
        raise ValueError("Every supported year must be in 2026–2035 and within the declared horizon")
    los = config.get("losProjection")
    exposure = config.get("waterExposure")
    if not isinstance(los, dict) or not isinstance(los.get("enabled"), bool):
        raise ValueError("losProjection.enabled must be explicitly true or false")
    if not isinstance(exposure, dict) or not isinstance(exposure.get("enabled"), bool):
        raise ValueError("waterExposure.enabled must be explicitly true or false")
    if not los["enabled"] and not exposure["enabled"]:
        raise ValueError("At least one of losProjection and waterExposure must be enabled")
    return scenario_id, baseline, years, review, {"losProjection": los, "waterExposure": exposure}


def _source_lineage(label: str, manifest: dict[str, Any]) -> tuple[bool, list[str]]:
    synthetic = manifest.get("dataKind") == "synthetic" or bool(manifest.get("syntheticLineage"))
    lineage: list[str] = []
    raw = manifest.get("syntheticLineage")
    if isinstance(raw, list):
        lineage.extend(str(item) for item in raw)
    elif synthetic:
        lineage.append(f"{label}:{manifest.get('runId')}")
    return synthetic, lineage


def _grid_check(manifest: dict[str, Any], asset: dict[str, Any], key: str) -> None:
    declared = manifest.get("grid")
    if not isinstance(declared, dict):
        return
    actual = {
        "crs": asset["crs"].to_string(), "width": asset["width"],
        "height": asset["height"], "transform": list(asset["transform"])[:6],
    }
    for field in ("crs", "width", "height"):
        if declared.get(field) is not None and declared[field] != actual[field]:
            raise ValueError(f"{key} asset grid differs from its manifest grid ({field})")
    if declared.get("transform") is not None and not np.allclose(
        declared["transform"], actual["transform"], rtol=0, atol=1e-8
    ):
        raise ValueError(f"{key} asset transform differs from its manifest grid")


def _connected_exposure(elevation: np.ndarray, vertical_rate_mm: np.ndarray,
                        water_level: np.ndarray, seeds: np.ndarray,
                        seed_valid: np.ndarray, barriers: np.ndarray | None,
                        barrier_valid: np.ndarray | None, years_elapsed: float
                        ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    terrain_valid = np.isfinite(elevation)
    support = terrain_valid & np.isfinite(vertical_rate_mm) & np.isfinite(water_level) & seed_valid
    if barriers is not None:
        support &= barrier_valid
    projected_elevation = np.full(elevation.shape, np.nan, dtype=np.float64)
    projected_elevation[support] = (
        elevation[support].astype(np.float64)
        + vertical_rate_mm[support].astype(np.float64) / 1000.0 * years_elapsed
    )
    candidates = support & (projected_elevation <= water_level)
    permitted = candidates.copy()
    if barriers is not None:
        permitted &= barriers == 0
    seed_cells = (seeds == 1) & permitted
    connected = ndimage.binary_propagation(
        seed_cells, structure=ndimage.generate_binary_structure(2, 1), mask=permitted
    ) if np.any(seed_cells) else np.zeros(permitted.shape, dtype=bool)
    # Barriers and nodata are excluded from support. A terrain cell blocked by a
    # wall remains a valid dry cell, so support is reported separately from flood.
    return connected, support, projected_elevation, candidates


def _pixel_area_km2(grid: dict[str, Any]) -> float:
    crs = CRS.from_user_input(grid["crs"])
    if not crs.is_projected or len(crs.axis_info) < 2:
        raise ValueError("Metric exposure areas require a projected CRS")
    fx = float(crs.axis_info[0].unit_conversion_factor or 1.0)
    fy = float(crs.axis_info[1].unit_conversion_factor or fx)
    transform = Affine(*grid["transform"])
    area_m2 = abs(transform.a * transform.e - transform.b * transform.d) * fx * fy
    if not math.isfinite(area_m2) or area_m2 <= 0:
        raise ValueError("Projection grid has an invalid metric pixel area")
    return area_m2 / 1_000_000.0


def _geometry_collection(exposure: np.ndarray, grid: dict[str, Any], year: int,
                         scenario_id: str, pixel_area_km2: float) -> dict[str, Any]:
    labels, _ = ndimage.label(exposure, structure=ndimage.generate_binary_structure(2, 1))
    if not np.any(labels):
        return {"type": "FeatureCollection", "features": []}
    source_crs = CRS.from_user_input(grid["crs"])
    transformer = Transformer.from_crs(source_crs, CRS.from_epsg(4326), always_xy=True)
    features = []
    for geom_mapping, raw_label in shapes(labels.astype(np.int32), mask=labels > 0,
                                          transform=Affine(*grid["transform"]), connectivity=4):
        component_id = int(raw_label)
        polygon = shape(geom_mapping)
        wgs84 = transform_geometry(polygon, transformer.transform, interleaved=False)
        cells = int(np.count_nonzero(labels == component_id))
        features.append({
            "type": "Feature", "geometry": mapping(wgs84),
            "properties": {
                "scenarioId": scenario_id, "year": year,
                "componentId": component_id, "exposedCellCount": cells,
                "areaKm2": cells * pixel_area_km2,
            },
        })
    return {"type": "FeatureCollection", "features": features}


def _write_projection_raster(path: Path, array: np.ndarray, grid: dict[str, Any], tags: dict[str, Any]) -> None:
    core.write_raster(path, array, grid)
    with rasterio.open(path, "r+") as dataset:
        dataset.update_tags(**{key: str(value) for key, value in tags.items()})


def _finite_stats(values: np.ndarray) -> dict[str, Any]:
    finite = np.asarray(values)[np.isfinite(values)]
    if not finite.size:
        return {"validCellCount": 0, "median": None, "minimum": None, "maximum": None}
    return {
        "validCellCount": int(finite.size),
        "median": float(np.median(finite)), "minimum": float(np.min(finite)),
        "maximum": float(np.max(finite)),
    }


def project(event: str, motion_manifest_path: str | Path,
            terrain_manifest_path: str | Path | None, config_path: str | Path,
            output_root: str | Path | None = None) -> Path:
    """Calculate and publish annual LOS and conditional coastal-water scenarios.

    ``terrain_manifest_path`` may be ``None`` only for LOS-only projections.
    Input manifests and every asset are hash-checked by :func:`core.load_manifest`.
    The returned path is the immutable ``projection`` manifest.
    """
    core.safe_name(event)
    config_file = Path(config_path).expanduser().resolve()
    config = _load_json(config_file, "projection config")
    scenario_id, baseline, years, scenario_review, switches = _validate_scenario(config)
    los_enabled = switches["losProjection"]["enabled"]
    exposure_enabled = switches["waterExposure"]["enabled"]

    motion, motion_path = _input_manifest(motion_manifest_path, event=event, product="ground-motion")
    motion_run = motion["runId"]
    if motion.get("units", {}).get("rateMmPerYear") != "mm/year":
        raise ValueError("Ground-motion rate asset must be declared in mm/year")
    convention = motion.get("displacementConvention")
    if convention != "positive_away_from_satellite":
        raise ValueError("Ground-motion displacementConvention must be positive_away_from_satellite")
    reference_epoch = _epoch(motion.get("referenceEpoch"), "ground-motion.referenceEpoch")
    latest_epoch = _epoch(motion.get("latestEpoch"), "ground-motion.latestEpoch")
    epochs = motion.get("epochs")
    if not isinstance(epochs, list) or len(epochs) < 2:
        raise ValueError("Ground-motion manifest must declare its measured epochs")
    parsed_epochs = [_epoch(value, f"ground-motion.epochs[{index}]") for index, value in enumerate(epochs)]
    if parsed_epochs != sorted(parsed_epochs) or parsed_epochs[0] != reference_epoch or parsed_epochs[-1] != latest_epoch:
        raise ValueError("Ground-motion epochs do not match referenceEpoch/latestEpoch")
    annual_dates = {year: datetime(year, 1, 1, tzinfo=timezone.utc) for year in years}
    if any(annual_dates[year] < reference_epoch for year in years):
        raise ValueError("Supported annual dates cannot precede the motion reference epoch")
    if any(annual_dates[year].date() < baseline for year in years):
        raise ValueError("Supported annual dates cannot precede the reviewed scenario baselineEpoch")

    rate_info = _read_manifest_raster(motion, "rateMmPerYear", required=True)
    _grid_check(motion, rate_info, "rateMmPerYear")
    motion_rate_raw = rate_info["array"].astype(np.float64)
    motion_rate_valid_raw = rate_info["valid"]
    rate_se_info = _read_manifest_raster(motion, "rateStandardErrorMmPerYear", required=False)
    if rate_se_info is not None:
        _grid_check(motion, rate_se_info, "rateStandardErrorMmPerYear")
        core.same_grid(
            {"crs": rate_info["crs"].to_string(), "width": rate_info["width"],
             "height": rate_info["height"], "transform": list(rate_info["transform"])[:6]},
            {"crs": rate_se_info["crs"].to_string(), "width": rate_se_info["width"],
             "height": rate_se_info["height"], "transform": list(rate_se_info["transform"])[:6]},
        )

    terrain: dict[str, Any] | None = None
    terrain_path: Path | None = None
    terrain_assets: dict[str, dict[str, Any]] = {}
    water_years: set[int] = set()
    water_scenarios: dict[int, str] = {}
    if terrain_manifest_path is not None:
        terrain, terrain_path = _input_manifest(terrain_manifest_path, event=event, product="scenario-inputs")
        if terrain.get("baselineEpoch") != baseline.isoformat():
            raise ValueError("Scenario baselineEpoch must match scenario-inputs baselineEpoch")
        _text(terrain.get("verticalDatum"), "scenario-inputs.verticalDatum")
        _text(terrain.get("verticalReferenceEpoch"), "scenario-inputs.verticalReferenceEpoch")
        for key in ("elevationMetres", "coastalSeeds"):
            terrain_assets[key] = _read_manifest_raster(terrain, key, required=True)
            _grid_check(terrain, terrain_assets[key], key)
        elevation_tags = {str(k).lower(): str(v).lower() for k, v in terrain_assets["elevationMetres"]["tags"].items()}
        if elevation_tags.get("units") not in {"metres", "meters", "m"} or elevation_tags.get("positive") != "up":
            raise ValueError("elevationMetres must be tagged in metres with positive-up elevation")
        terrain_assets["barriers"] = _read_manifest_raster(terrain, "barriers", required=False)
        if terrain_assets["barriers"] is not None:
            _grid_check(terrain, terrain_assets["barriers"], "barriers")
        raw_water_years = terrain.get("supportedYears")
        if not isinstance(raw_water_years, list) or any(isinstance(y, bool) or not isinstance(y, int) for y in raw_water_years):
            raise ValueError("Scenario-inputs manifest supportedYears must be integer years")
        if len(set(raw_water_years)) != len(raw_water_years):
            raise ValueError("Scenario-inputs manifest supportedYears contains duplicates")
        water_years = set(raw_water_years)
        raw_scenarios = terrain.get("waterLevels", [])
        if not isinstance(raw_scenarios, list):
            raise ValueError("Scenario-inputs waterLevels metadata must be a list")
        for entry in raw_scenarios:
            if not isinstance(entry, dict) or isinstance(entry.get("year"), bool) or not isinstance(entry.get("year"), int):
                raise ValueError("Scenario-inputs waterLevels entries must identify an integer year")
            year = entry["year"]
            if year in water_scenarios:
                raise ValueError(f"Scenario-inputs has duplicate water-level metadata for {year}")
            water_scenarios[year] = _text(entry.get("scenario"), f"waterLevels[{year}].scenario")
        if exposure_enabled:
            missing = sorted(set(years) - water_years)
            if missing:
                raise ValueError(f"Scenario-inputs has no explicit water-level assets for supported years {missing}")
            for year in years:
                if water_scenarios.get(year) != scenario_id:
                    raise ValueError(f"Water-level year {year} scenario does not match requested scenarioId {scenario_id!r}")
                key = f"waterLevel{year}"
                level = _read_manifest_raster(terrain, key, required=True)
                _grid_check(terrain, level, key)
                tags = {str(k).lower(): str(v).lower() for k, v in level["tags"].items()}
                if tags.get("units") not in {"metres", "meters", "m"} or tags.get("positive") != "up":
                    raise ValueError(f"{key} must be tagged in metres with positive-up water level")
                terrain_assets[key] = level
            if baseline.month == 1 and baseline.day == 1 and baseline.year in water_years and baseline.year not in terrain_assets:
                if water_scenarios.get(baseline.year) != scenario_id:
                    raise ValueError(f"Baseline water-level scenario does not match {scenario_id!r}")
                key = f"waterLevel{baseline.year}"
                level = _read_manifest_raster(terrain, key, required=True)
                tags = {str(k).lower(): str(v).lower() for k, v in level["tags"].items()}
                if tags.get("units") not in {"metres", "meters", "m"} or tags.get("positive") != "up":
                    raise ValueError(f"{key} must be tagged in metres with positive-up water level")
                terrain_assets[key] = level
                _grid_check(terrain, terrain_assets[key], key)
    elif exposure_enabled:
        raise ValueError("waterExposure requires a scenario-inputs terrain manifest")

    vertical_cfg = config.get("verticalMotion") if exposure_enabled else None
    vertical_info: dict[str, Any] | None = None
    incidence_info: dict[str, Any] | None = None
    vertical_mode: str | None = None
    vertical_scale = 1.0
    incidence_scalar: float | None = None
    vertical_summary: dict[str, Any] = {}
    if exposure_enabled:
        if not isinstance(vertical_cfg, dict):
            raise ValueError("waterExposure requires verticalMotion evidence")
        vertical_mode = vertical_cfg.get("mode")
        vertical_summary["mode"] = vertical_mode
        if vertical_mode == "independent-rate":
            spec = vertical_cfg
            if spec.get("units") not in _SAFE_UNITS:
                raise ValueError("Independent vertical rate units must be mm/year or m/year")
            if spec.get("positive") != "up":
                raise ValueError("Independent vertical rate must explicitly use positive-up convention")
            vertical_summary.update({
                "sourceId": _safe_source_id(spec.get("sourceId"), "verticalMotion.sourceId"),
                "sourceRunId": _safe_source_id(spec.get("sourceRunId"), "verticalMotion.sourceRunId"),
                "sourceDate": _iso_date(spec.get("sourceDate"), "verticalMotion.sourceDate").isoformat(),
                "verticalDatum": _text(spec.get("verticalDatum"), "verticalMotion.verticalDatum"),
                "verticalReferenceEpoch": _text(spec.get("verticalReferenceEpoch"), "verticalMotion.verticalReferenceEpoch"),
                "baselineEpoch": _iso_date(spec.get("baselineEpoch"), "verticalMotion.baselineEpoch").isoformat(),
                "review": _review(spec.get("review"), "verticalMotion.review"),
            })
            if terrain is None:
                raise ValueError("Independent vertical rate requires terrain reference metadata")
            if vertical_summary["verticalDatum"] != terrain.get("verticalDatum"):
                raise ValueError("Independent vertical rate datum must match terrain verticalDatum")
            if vertical_summary["verticalReferenceEpoch"] != terrain.get("verticalReferenceEpoch"):
                raise ValueError("Independent vertical rate reference epoch must match terrain")
            if vertical_summary["baselineEpoch"] != baseline.isoformat():
                raise ValueError("Independent vertical rate baselineEpoch must match scenario baseline")
            vertical_info = _local_source(spec, config_file, "verticalRate")
            vertical_scale = _SAFE_UNITS[spec["units"]]
        elif vertical_mode == "verticalOnlyLosInference":
            if config.get("allowVerticalOnlyLosInference") is not True:
                raise ValueError("Vertical-only LOS inference is opt-in; set allowVerticalOnlyLosInference: true")
            if vertical_cfg.get("horizontalMotionNegligible") is not True:
                raise ValueError("Vertical-only LOS inference requires the reviewed negligible-horizontal-motion assumption")
            if datetime.combine(baseline, datetime.min.time(), tzinfo=timezone.utc) < reference_epoch:
                raise ValueError("Vertical-only LOS inference cannot adjust terrain before the motion reference epoch")
            review = _review(vertical_cfg.get("review"), "verticalMotion.review")
            incidence = vertical_cfg.get("incidenceAngle")
            if not isinstance(incidence, dict):
                raise ValueError("Vertical-only LOS inference requires incidenceAngle evidence")
            if incidence.get("angleConvention") != "from_vertical":
                raise ValueError("incidenceAngle.angleConvention must be from_vertical")
            incidence_review = _review(incidence.get("review"), "incidenceAngle.review")
            incidence_source_id = _safe_source_id(incidence.get("sourceId"), "incidenceAngle.sourceId")
            if incidence.get("kind") == "scalar":
                raw = incidence.get("valueDegrees")
                if isinstance(raw, bool):
                    raise ValueError("incidenceAngle.valueDegrees must be finite and between 0 and 90")
                try:
                    incidence_scalar = float(raw)
                except (TypeError, ValueError) as exc:
                    raise ValueError("incidenceAngle.valueDegrees must be finite and between 0 and 90") from exc
                if not math.isfinite(incidence_scalar) or not 0 <= incidence_scalar < 90:
                    raise ValueError("incidenceAngle.valueDegrees must be finite and between 0 and 90")
                incidence_info = {"label": "incidenceAngle", "kind": "scalar", "valueDegrees": incidence_scalar,
                                  "sourceId": incidence_source_id, "review": incidence_review}
            elif incidence.get("kind") == "raster":
                if incidence.get("units") != "degrees":
                    raise ValueError("Incidence angle raster units must be degrees")
                incidence_info = _local_source(incidence, config_file, "incidenceAngle")
                values = incidence_info["array"][incidence_info["valid"]]
                if values.size and (np.any(values < 0) or np.any(values >= 90)):
                    raise ValueError("Incidence angles must be in [0, 90) degrees from vertical")
                incidence_info["sourceId"] = incidence_source_id
                incidence_info["review"] = incidence_review
                incidence_info["kind"] = "raster"
            else:
                raise ValueError("incidenceAngle.kind must be scalar or raster")
            vertical_summary.update({
                "conversion": "vVerticalUp = -vAway / cos(incidenceAngleFromVertical)",
                "horizontalMotionNegligible": True, "review": review,
                "allowVerticalOnlyLosInference": True,
                "incidenceAngle": {"sourceId": incidence_source_id,
                                   "kind": incidence_info["kind"],
                                   "review": incidence_review,
                                   "valueDegrees": incidence_scalar},
            })
        else:
            raise ValueError("verticalMotion.mode must be independent-rate or verticalOnlyLosInference")

    snapshot_cfg = config.get("exposureSnapshots", {})
    if snapshot_cfg is None:
        snapshot_cfg = {}
    if not isinstance(snapshot_cfg, dict):
        raise ValueError("exposureSnapshots must be an object")
    if snapshot_cfg and not exposure_enabled:
        raise ValueError("exposureSnapshots require waterExposure.enabled=true")
    snapshot_infos: dict[str, dict[str, Any]] = {}
    snapshot_metadata: dict[str, Any] = {}
    for name, expected_units in _SNAPSHOT_UNITS.items():
        if name not in snapshot_cfg:
            continue
        spec = snapshot_cfg[name]
        if not isinstance(spec, dict) or spec.get("units") != expected_units:
            raise ValueError(f"exposureSnapshots.{name}.units must be {expected_units}")
        info = _local_source(spec, config_file, name)
        valid_values = info["array"][info["valid"]]
        if valid_values.size and (np.any(valid_values < 0) or not np.all(np.isfinite(valid_values))):
            raise ValueError(f"exposureSnapshots.{name} values must be finite and non-negative")
        info["sourceId"] = _safe_source_id(spec.get("sourceId"), f"exposureSnapshots.{name}.sourceId")
        info["sourceDate"] = _iso_date(spec.get("sourceDate"), f"exposureSnapshots.{name}.sourceDate").isoformat()
        info["provenance"] = _text(spec.get("provenance"), f"exposureSnapshots.{name}.provenance")
        snapshot_infos[name] = info
        snapshot_metadata[name] = {
            "sourceId": info["sourceId"], "sourceDate": info["sourceDate"],
            "provenance": info["provenance"], "units": expected_units,
            "sha256": info["sha256"],
        }

    # The target uses terrain's projected CRS when present. Physical motion,
    # terrain, water, masks and vertical/LOS inputs constrain resolution and
    # support. External count snapshots are statistics only; they must never
    # shrink the physical exposure footprint.
    raster_infos: list[dict[str, Any]] = [rate_info]
    if exposure_enabled and terrain is not None:
        raster_infos.extend(info for info in terrain_assets.values() if info is not None)
    if vertical_info is not None:
        raster_infos.append(vertical_info)
    if incidence_info is not None and incidence_info.get("kind") == "raster":
        raster_infos.append(incidence_info)
    target_crs = terrain_assets["elevationMetres"]["crs"] if exposure_enabled and terrain is not None else rate_info["crs"]
    if not target_crs.is_projected:
        raise ValueError("Ground-motion/terrain projection grid must use a projected CRS")
    grid = _analysis_grid(raster_infos, target_crs)

    rate, rate_valid = _warp_continuous(rate_info, grid)
    rate[~rate_valid] = np.nan
    rate_standard_error = None
    if rate_se_info is not None:
        rate_standard_error, se_valid = _warp_continuous(rate_se_info, grid)
        rate_standard_error[~se_valid] = np.nan
    elevation = seeds = seed_valid = barriers = barrier_valid = None
    water_levels: dict[int, np.ndarray] = {}
    terrain_valid = None
    if terrain is not None:
        elevation, elevation_valid = _warp_continuous(terrain_assets["elevationMetres"], grid)
        seeds, seed_valid = _warp_mask(terrain_assets["coastalSeeds"], grid, "coastalSeeds")
        terrain_valid = elevation_valid & seed_valid
        elevation[~terrain_valid] = np.nan
        if terrain_assets.get("barriers") is not None:
            barriers, barrier_valid = _warp_mask(terrain_assets["barriers"], grid, "barriers")
        for year in years if exposure_enabled else []:
            level, level_valid = _warp_continuous(terrain_assets[f"waterLevel{year}"], grid)
            level[~level_valid] = np.nan
            water_levels[year] = level
        if (exposure_enabled and baseline.month == 1 and baseline.day == 1
                and baseline.year in terrain_assets and baseline.year not in water_levels):
            level, level_valid = _warp_continuous(terrain_assets[f"waterLevel{baseline.year}"], grid)
            level[~level_valid] = np.nan
            water_levels[baseline.year] = level

    vertical_rate = None
    vertical_valid = None
    incidence = None
    if exposure_enabled and vertical_mode == "independent-rate":
        assert vertical_info is not None
        vertical_rate, vertical_valid = _warp_continuous(vertical_info, grid, scale=vertical_scale)
        vertical_rate[~vertical_valid] = np.nan
    elif exposure_enabled:
        if incidence_info and incidence_info.get("kind") == "raster":
            incidence, incidence_valid = _warp_continuous(incidence_info, grid)
            invalid_angle = ~incidence_valid | (incidence < 0) | (incidence >= 90)
            incidence[invalid_angle] = np.nan
        else:
            incidence = np.full((grid["height"], grid["width"]), incidence_scalar, dtype=np.float32)
        cos_incidence = np.cos(np.deg2rad(incidence.astype(np.float64)))
        inferred_valid = rate_valid & np.isfinite(cos_incidence) & (cos_incidence > 0)
        vertical_rate = np.full(rate.shape, np.nan, dtype=np.float32)
        vertical_rate[inferred_valid] = -rate[inferred_valid] / cos_incidence[inferred_valid]
        vertical_valid = inferred_valid

    snapshots: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    snapshot_warnings: dict[str, str] = {}
    for name, info in snapshot_infos.items():
        sx, sy = _resolution_metres(info, target_crs)
        if max(sx, sy) > grid["resolutionMetres"] * (1.0 + 1e-9):
            snapshots[name] = (
                np.full((grid["height"], grid["width"]), np.nan, dtype=np.float32),
                np.zeros((grid["height"], grid["width"]), dtype=bool),
            )
            snapshot_warnings[name] = "Snapshot is coarser than the physical analysis grid; counts are unavailable without upsampling."
            continue
        values, valid = _warp_continuous(info, grid, sum_counts=True)
        values[(values < 0) & valid] = np.nan
        valid &= np.isfinite(values) & (values >= 0)
        values[~valid] = np.nan
        snapshots[name] = values, valid

    pixel_area_km2 = _pixel_area_km2(grid) if exposure_enabled else None
    annual_metrics: dict[str, Any] = {}
    output_arrays: dict[str, np.ndarray] = {}
    output_geometries: dict[str, dict[str, Any]] = {}
    exposure_support_by_year: dict[int, np.ndarray] = {}
    exposure_by_year: dict[int, np.ndarray] = {}
    baseline_exposure: np.ndarray | None = None
    baseline_support: np.ndarray | None = None
    comparisons: dict[str, Any] = {"baselineToYear": {}, "yearToYear": {}}
    warnings: list[str] = []
    if not np.any(rate_valid):
        warnings.append("No valid annual LOS rates are available; projected LOS rasters contain nodata rather than a zero baseline.")
    if latest_epoch < annual_dates[years[-1]]:
        warnings.append("Projection years extend beyond the latest ground-motion measurement; constant-rate extrapolation is conditional.")
    measurement_span_days = (latest_epoch - reference_epoch).total_seconds() / 86400.0
    exposure_snapshot_reasons = {
        "assetCount": "No reviewed asset-count snapshot was supplied." if "assetCount" not in snapshots else None,
        "populationCount": "No reviewed population-count snapshot was supplied." if "populationCount" not in snapshots else None,
    }
    exposure_snapshot_reasons.update(snapshot_warnings)
    if (exposure_enabled and baseline.month == 1 and baseline.day == 1
            and baseline.year in water_levels):
        assert elevation is not None and vertical_rate is not None and seeds is not None and seed_valid is not None
        baseline_exposure, baseline_support, _, _ = _connected_exposure(
            elevation, vertical_rate, water_levels[baseline.year], seeds, seed_valid,
            barriers, barrier_valid, 0.0,
        )
    for year in years:
        annual_date = annual_dates[year]
        elapsed_motion_years = (annual_date - reference_epoch).total_seconds() / 86400.0 / YEAR_DAYS
        elapsed_baseline_years = (annual_date - datetime.combine(baseline, datetime.min.time(), tzinfo=timezone.utc)).total_seconds() / 86400.0 / YEAR_DAYS
        item: dict[str, Any] = {"year": year, "annualDate": annual_date.date().isoformat(),
                                "elapsedYearsFromBaseline": elapsed_baseline_years,
                                "measurementSpan": {"referenceEpoch": reference_epoch.isoformat().replace("+00:00", "Z"),
                                                    "latestEpoch": latest_epoch.isoformat().replace("+00:00", "Z"),
                                                    "spanDays": measurement_span_days}}
        if los_enabled:
            los = np.full(rate.shape, np.nan, dtype=np.float32)
            los[rate_valid] = (rate[rate_valid].astype(np.float64) * elapsed_motion_years).astype(np.float32)
            output_arrays[f"losMm{year}"] = los
            los_stats = _finite_stats(los)
            item.update({"losValidCellCount": los_stats["validCellCount"],
                         "medianLosMm": los_stats["median"],
                         "minimumLosMm": los_stats["minimum"],
                         "maximumLosMm": los_stats["maximum"],
                         "elapsedYearsFromMotionReference": elapsed_motion_years,
                         "losProjectionMethod": "constant annual LOS rate from motion reference epoch"})
            if rate_standard_error is not None:
                stderr = rate_standard_error[np.isfinite(rate_standard_error)]
                item["medianRateStandardErrorMmPerYear"] = float(np.median(stderr)) if stderr.size else None
                item["standardErrorTermMm"] = item["medianRateStandardErrorMmPerYear"] * abs(elapsed_motion_years) if stderr.size else None
        if exposure_enabled:
            assert elevation is not None and vertical_rate is not None and seeds is not None and seed_valid is not None
            exposure, support, projected_elevation, candidates = _connected_exposure(
                elevation, vertical_rate, water_levels[year], seeds, seed_valid,
                barriers, barrier_valid, elapsed_baseline_years,
            )
            exposure_by_year[year] = exposure
            exposure_support_by_year[year] = support
            exposed = np.where(support, exposure.astype(np.float32), np.nan).astype(np.float32)
            output_arrays[f"exposure{year}"] = exposed
            if switches["waterExposure"].get("publishDepth", False):
                depth = np.full(elevation.shape, np.nan, dtype=np.float32)
                level = water_levels[year]
                depth[exposure] = np.maximum(level[exposure] - projected_elevation[exposure], 0.0)
                output_arrays[f"depth{year}"] = depth
            output_geometries[f"geometry{year}"] = _geometry_collection(
                exposure, grid, year, scenario_id, pixel_area_km2 or 0.0
            )
            exposed_count = int(np.count_nonzero(exposure))
            valid_count = int(np.count_nonzero(support))
            item.update({
                "validTerrainCellCount": int(np.count_nonzero(np.isfinite(elevation))),
                "validExposureCellCount": valid_count,
                "candidateWaterCellCount": int(np.count_nonzero(candidates)) if valid_count else None,
                "exposedCellCount": exposed_count if valid_count else None,
                "exposedAreaKm2": exposed_count * (pixel_area_km2 or 0.0) if valid_count else None,
                "exposureMethod": "water-level threshold and coastal-seed connectivity with 4-neighbour cells",
                "verticalRateValidCellCount": int(np.count_nonzero(vertical_valid)) if vertical_valid is not None else 0,
            })
            if valid_count == 0:
                item["exposureUnavailableReason"] = "No valid common terrain, vertical-rate, water-level, seed, and barrier support for this year."
            snapshot_status = {}
            for metric_name in ("assetCount", "populationCount"):
                if metric_name not in snapshots:
                    item["exposedAssetCount" if metric_name == "assetCount" else "exposedPopulationCount"] = None
                    snapshot_status[metric_name] = {"value": None, "reason": exposure_snapshot_reasons[metric_name]}
                    continue
                snapshot, snapshot_valid = snapshots[metric_name]
                if valid_count == 0:
                    value = None
                    reason = item["exposureUnavailableReason"]
                elif np.any(support & ~snapshot_valid):
                    value = None
                    reason = "Snapshot does not cover all valid exposure support for this year."
                else:
                    value = float(np.sum(snapshot[exposure], dtype=np.float64))
                    if value.is_integer():
                        value = int(value)
                    reason = None
                metric_key = "exposedAssetCount" if metric_name == "assetCount" else "exposedPopulationCount"
                item[metric_key] = value
                snapshot_status[metric_name] = {"value": value, "reason": reason}
            item["snapshotMetricsAvailability"] = snapshot_status
        annual_metrics[str(year)] = item

    def compare_exposure(first: np.ndarray, second: np.ndarray, common_support: np.ndarray) -> dict[str, Any]:
        common_count = int(np.count_nonzero(common_support))
        if common_count == 0:
            return {
                "validCommonCellCount": 0,
                "firstExposedCellCount": None,
                "secondExposedCellCount": None,
                "newlyExposedCellCount": None,
                "noLongerExposedCellCount": None,
                "netExposedAreaChangeKm2": None,
                "unavailableReason": "No common valid support for this comparison.",
            }
        first_common = first & common_support
        second_common = second & common_support
        first_count = int(np.count_nonzero(first_common))
        second_count = int(np.count_nonzero(second_common))
        return {
            "validCommonCellCount": common_count,
            "firstExposedCellCount": first_count,
            "secondExposedCellCount": second_count,
            "newlyExposedCellCount": int(np.count_nonzero(second_common & ~first_common)),
            "noLongerExposedCellCount": int(np.count_nonzero(first_common & ~second_common)),
            "netExposedAreaChangeKm2": (second_count - first_count) * (pixel_area_km2 or 0.0),
            "comparisonSupport": "intersection of both years' valid terrain, vertical-rate, water-level, coastal-seed, and barrier support",
        }

    if exposure_enabled:
        if baseline_exposure is None or baseline_support is None:
            if baseline.month != 1 or baseline.day != 1:
                comparisons["baselineUnavailableReason"] = (
                    "Baseline comparison requires a January 1 baseline or an explicitly dated same-day baseline water asset; no annual level is relabeled."
                )
            else:
                comparisons["baselineUnavailableReason"] = (
                    f"No same-scenario prepared waterLevel{baseline.year} asset was supplied; no baseline water level is invented."
                )
            for year in years:
                annual_metrics[str(year)]["comparisonToBaseline"] = None
                annual_metrics[str(year)]["comparisonToBaselineUnavailableReason"] = comparisons["baselineUnavailableReason"]
        else:
            comparisons["baselineYear"] = baseline.year
            for year in years:
                common = baseline_support & exposure_support_by_year[year]
                comparison = compare_exposure(baseline_exposure, exposure_by_year[year], common)
                comparisons["baselineToYear"][str(year)] = comparison
                annual_metrics[str(year)]["comparisonToBaseline"] = comparison
        for index, first_year in enumerate(years):
            for second_year in years[index + 1:]:
                common = exposure_support_by_year[first_year] & exposure_support_by_year[second_year]
                comparisons["yearToYear"][f"{first_year}->{second_year}"] = compare_exposure(
                    exposure_by_year[first_year], exposure_by_year[second_year], common
                )

    terrain_synthetic = False
    terrain_lineage: list[str] = []
    if terrain is not None:
        terrain_synthetic, terrain_lineage = _source_lineage("scenario-inputs", terrain)
    motion_synthetic, motion_lineage = _source_lineage("ground-motion", motion)
    synthetic = config.get("dataKind") == "synthetic" or terrain_synthetic or motion_synthetic
    synthetic_lineage: list[str] = []
    synthetic_lineage.extend(terrain_lineage)
    synthetic_lineage.extend(motion_lineage)
    if config.get("dataKind") == "synthetic":
        synthetic_lineage.append(f"scenario-config:{core.digest(config_file)}")
    if vertical_info is not None and (config.get("dataKind") == "synthetic" or vertical_info["sourceSpec"].get("dataKind") == "synthetic"):
        synthetic = True
        synthetic_lineage.append(f"verticalRate:{vertical_info['sha256']}")
    if incidence_info is not None and incidence_info.get("kind") == "raster" and (
        config.get("dataKind") == "synthetic" or incidence_info["sourceSpec"].get("dataKind") == "synthetic"
    ):
        synthetic = True
        synthetic_lineage.append(f"incidenceAngle:{incidence_info['sha256']}")
    for name, info in snapshot_infos.items():
        if config.get("dataKind") == "synthetic" or info["sourceSpec"].get("dataKind") == "synthetic":
            synthetic = True
            synthetic_lineage.append(f"{name}:{info['sha256']}")
    source_run_ids: list[str] = []
    for manifest in (motion, terrain):
        if manifest is None:
            continue
        for source_id in [manifest["runId"], *manifest.get("sourceRunIds", manifest.get("upstreamRunIds", []))]:
            if source_id not in source_run_ids:
                source_run_ids.append(source_id)
    if vertical_mode == "independent-rate":
        source_run_id = vertical_summary["sourceRunId"]
        if source_run_id not in source_run_ids:
            source_run_ids.append(source_run_id)
    source_hashes: dict[str, str] = {
        "projectionConfig": core.digest(config_file),
        f"ground-motion-manifest:{motion_run}": core.digest(motion_path),
    }
    if terrain is not None and terrain_path is not None:
        source_hashes[f"scenario-inputs-manifest:{terrain['runId']}"] = core.digest(terrain_path)
    for manifest_label, manifest in (("ground-motion", motion), ("scenario-inputs", terrain)):
        if manifest is None:
            continue
        for key, asset in manifest.get("assets", {}).items():
            if asset.get("sha256"):
                source_hashes[f"{manifest_label}:{manifest['runId']}:{key}"] = asset["sha256"]
    if vertical_info is not None:
        source_hashes[f"verticalRate:{vertical_summary['sourceId']}"] = vertical_info["sha256"]
    if incidence_info is not None and incidence_info.get("kind") == "raster":
        source_hashes[f"incidenceAngle:{incidence_info['sourceId']}"] = incidence_info["sha256"]
    for name, info in snapshot_infos.items():
        source_hashes[f"{name}:{info['sourceId']}"] = info["sha256"]

    assumptions = {
        "scenarioReview": scenario_review,
        "annualDateConvention": "January 1 of each supported year",
        "los": {
            "enabled": los_enabled,
            "method": "constant rateMmPerYear extrapolated from the motion reference epoch; positive away from the satellite",
            "convention": convention,
            "measurementSpan": {"referenceEpoch": reference_epoch.isoformat().replace("+00:00", "Z"),
                                "latestEpoch": latest_epoch.isoformat().replace("+00:00", "Z"),
                                "spanDays": measurement_span_days},
        },
        "waterExposure": {
            "enabled": exposure_enabled,
            "method": "conditional static water-level threshold after vertical surface adjustment, filtered by coastal connectivity",
            "verticalMotion": vertical_summary if exposure_enabled else None,
            "connectivity": "4-neighbour flood candidates reachable from coastal seed cells; barriers and nodata block passage",
            "waterLevels": "only explicit same-year prepared waterLevelYYYY assets are used; no interpolation or forecast",
            "baselineComparison": ("uses same-scenario prepared waterLevel at baselineEpoch on intersected valid support"
                                   if exposure_enabled and baseline.month == 1 and baseline.day == 1 and baseline.year in water_levels else
                                   "unavailable unless a same-scenario prepared waterLevel asset exists at baselineEpoch"),
            "depthAssetPublished": bool(exposure_enabled and switches["waterExposure"].get("publishDepth", False)),
        },
        "gridAlignment": {
            "analysisResolutionMetres": grid["resolutionMetres"],
            "rule": grid["resolutionRule"],
            "continuous": "bilinear with a separately propagated nearest-neighbour validity mask",
            "categoricalMasks": "nearest-neighbour",
            "countSnapshots": "sum resampling to the no-finer-than-native analysis grid",
        },
        "notForecast": "This is a conditional screening scenario, not a flood forecast or probability estimate.",
    }
    uncertainty = {
        "motionRateStandardErrorAvailable": rate_standard_error is not None,
        "motionRateStandardErrorMeaning": "The series fit standard error is retained as one diagnostic term; it is not a complete geophysical uncertainty or confidence interval.",
        "terrainInput": terrain.get("uncertainty") if terrain is not None else None,
        "waterLevelInput": terrain.get("uncertainty") if terrain is not None else None,
        "independentTermsCombined": False,
        "confidenceIntervalsCalculated": False,
        "reason": "Available source uncertainty terms are reported without fabricated confidence percentages or independence assumptions.",
    }
    metadata = {
        "dataKind": "synthetic" if synthetic else "scenario",
        "syntheticLineage": synthetic_lineage if synthetic_lineage else False,
        "codeVersion": CODE_VERSION,
        "scenarioId": scenario_id,
        "supportedYears": years,
        "baselineEpoch": baseline.isoformat(),
        "horizon": config["horizon"],
        "grid": grid,
        "units": {"losMmYYYY": "mm", "exposureYYYY": "0/1 categorical", "depthYYYY": "m"},
        "assumptions": assumptions,
        "uncertainty": uncertainty,
        "sourceRunIds": source_run_ids,
        "upstreamRunIds": source_run_ids,
        "sourceHashes": source_hashes,
        "sourceManifestHashes": {
            "groundMotion": core.digest(motion_path),
            **({"scenarioInputs": core.digest(terrain_path)} if terrain_path is not None else {}),
        },
        "annualMetrics": annual_metrics,
        "comparisons": comparisons if exposure_enabled else None,
        "exposureSnapshots": snapshot_metadata,
        "coverage": {
            "analysisCellCount": int(grid["width"] * grid["height"]),
            "motionRateValidCellCount": int(np.count_nonzero(rate_valid)),
            "terrainValidCellCount": int(np.count_nonzero(np.isfinite(elevation))) if elevation is not None else None,
        },
        "warnings": warnings,
    }

    def writer(stage: Path) -> dict[str, str]:
        files: dict[str, str] = {}
        for key, array in output_arrays.items():
            filename = f"{key}.tif"
            units = "mm" if key.startswith("losMm") else ("m" if key.startswith("depth") else "0/1")
            positive = "away_from_satellite" if key.startswith("losMm") else ("depth_below_water_surface" if key.startswith("depth") else "")
            _write_projection_raster(stage / filename, array, grid, {
                "event": event, "product": "projection", "scenarioId": scenario_id,
                "asset": key, "year": key[-4:], "units": units, "positive": positive,
                "dataKind": metadata["dataKind"], "baselineEpoch": baseline.isoformat(),
            })
            files[key] = filename
        for key, collection in output_geometries.items():
            filename = f"{key}.geojson"
            (stage / filename).write_text(json.dumps(collection, allow_nan=False) + "\n", encoding="utf-8")
            files[key] = filename
        return files

    return core.publish(event, "projection", metadata, writer, output_root=output_root)
