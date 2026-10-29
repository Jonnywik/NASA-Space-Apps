"""Prepare compatible elevation, coastal masks and water levels for P3 scenarios.

Inputs are local rasters/scalars described by a JSON file.  The module does not
fetch products or perform a tide/surge model.  Any vertical-datum conversion or
change of terrain baseline must be supplied as a documented, reviewed offset.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from affine import Affine
from pyproj import CRS
from rasterio.enums import Resampling
from rasterio.warp import calculate_default_transform, reproject, transform_bounds

from . import core


CODE_VERSION = "p3-terrain/1.0"
_METRES_PER_UNIT = {"m": 1.0, "metre": 1.0, "metres": 1.0, "meter": 1.0,
                    "meters": 1.0, "ft": 0.3048, "foot": 0.3048, "feet": 0.3048}
_COMPONENTS = {"mean_water_level", "tide", "surge"}


class CompatibilityError(ValueError):
    """An input set cannot support a scenario-input package.

    ``report`` is safe to print or persist.  Failed compatibility checks never
    call the publication layer, so they cannot create a ready/current product.
    """

    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None):
        self.report = {
            "schemaVersion": "1.0",
            "product": "scenario-inputs",
            "status": "incompatible",
            "issues": [{"code": code, "message": message, "details": details or {}}],
        }
        super().__init__(message)


def _compat(code: str, message: str, **details: Any) -> None:
    raise CompatibilityError(code, message, details=details)


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def _epoch(value: Any, label: str) -> str:
    """Accept exact ISO dates or decimal year labels (for datum realizations)."""
    text = _text(value, label)
    try:
        parsed = date.fromisoformat(text)
        if parsed.isoformat() == text:
            return text
    except ValueError:
        pass
    # Decimal year labels such as 2010.0 are common for vertical reference epochs.
    try:
        number = float(text)
        if math.isfinite(number) and 1000 <= number <= 9999:
            return text
    except ValueError:
        pass
    raise ValueError(f"{label} must be an ISO date or a decimal-year epoch")


def _date(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be an ISO date in YYYY-MM-DD form")
    try:
        result = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO date in YYYY-MM-DD form") from exc
    if result.isoformat() != value:
        raise ValueError(f"{label} must use canonical YYYY-MM-DD form")
    return value


def _unit_factor(value: Any, label: str) -> float:
    unit = _text(value, label).lower()
    if unit not in _METRES_PER_UNIT:
        raise ValueError(f"{label} must be metres or international feet")
    return _METRES_PER_UNIT[unit]


def _vertical_sign(source: dict[str, Any], label: str) -> float:
    direction = source.get("positiveDirection")
    if direction not in ("up", "down"):
        _compat("vertical_direction_missing", f"{label}.positiveDirection must explicitly be 'up' or 'down'")
    return 1.0 if direction == "up" else -1.0


def _finite_number(value: Any, label: str, *, nonnegative: bool = False) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a finite number")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a finite number") from exc
    if not math.isfinite(number) or (nonnegative and number < 0):
        condition = "finite and non-negative" if nonnegative else "finite"
        raise ValueError(f"{label} must be {condition}")
    return number


def _source_path(source: dict[str, Any], config_path: Path, label: str) -> Path:
    raw = _text(source.get("path"), f"{label}.path")
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = config_path.parent / path
    path = path.resolve()
    if not path.is_file():
        raise ValueError(f"{label} raster does not exist or is not a file: {path}")
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _raster_info(path: Path, label: str) -> dict[str, Any]:
    try:
        with rasterio.open(path) as ds:
            if ds.count != 1:
                raise ValueError(f"{label} raster must have exactly one band; found {ds.count}")
            if ds.crs is None:
                _compat("missing_crs", f"{label} raster has no horizontal CRS", source=str(path))
            if ds.width <= 0 or ds.height <= 0:
                raise ValueError(f"{label} raster has an empty grid")
            crs = CRS.from_user_input(ds.crs)
            if not all(math.isfinite(float(v)) for v in tuple(ds.transform)[:6]):
                raise ValueError(f"{label} raster has a non-finite affine transform")
            if ds.transform.a == 0 or ds.transform.e == 0:
                raise ValueError(f"{label} raster has a degenerate affine transform")
            return {
                "path": path,
                "crs": crs,
                "nativeCrs": crs.to_string(),
                "width": ds.width,
                "height": ds.height,
                "transform": ds.transform,
                "nodata": ds.nodata,
                "dtype": ds.dtypes[0],
                "tags": ds.tags(),
            }
    except rasterio.errors.RasterioError as exc:
        raise ValueError(f"Cannot read {label} raster {path}: {exc}") from exc


def _native_resolution_metres(info: dict[str, Any], target: CRS) -> tuple[float, float]:
    source_crs: CRS = info["crs"]
    transform = info["transform"]
    if source_crs == target and source_crs.is_projected:
        axes = source_crs.axis_info
        factor_x = axes[0].unit_conversion_factor if axes else 1.0
        factor_y = axes[1].unit_conversion_factor if len(axes) > 1 else factor_x
        x = math.hypot(transform.a, transform.d) * float(factor_x)
        y = math.hypot(transform.b, transform.e) * float(factor_y)
    else:
        try:
            warped, _, _ = calculate_default_transform(
                source_crs, target, info["width"], info["height"], *rasterio.transform.array_bounds(
                    info["height"], info["width"], transform
                )
            )
        except Exception as exc:
            raise ValueError(f"Cannot estimate native resolution for {info['path']}: {exc}") from exc
        axes = target.axis_info
        factor_x = axes[0].unit_conversion_factor if axes else 1.0
        factor_y = axes[1].unit_conversion_factor if len(axes) > 1 else factor_x
        x = math.hypot(warped.a, warped.d) * float(factor_x)
        y = math.hypot(warped.b, warped.e) * float(factor_y)
    if not all(math.isfinite(v) and v > 0 for v in (x, y)):
        raise ValueError(f"Invalid native resolution in {info['path']}")
    return x, y


def _target_grid(terrain_info: dict[str, Any], target: CRS,
                 infos: list[tuple[str, dict[str, Any]]]) -> tuple[dict[str, Any], dict[str, dict[str, float]]]:
    target_axes = target.axis_info
    if len(target_axes) < 2 or not target.is_projected:
        raise ValueError("targetCrs must be a projected horizontal CRS")
    target_factor = float(target_axes[0].unit_conversion_factor or 1.0)
    native: dict[str, dict[str, float]] = {}
    max_resolution_m = 0.0
    for name, info in infos:
        rx, ry = _native_resolution_metres(info, target)
        native[name] = {"xMetres": rx, "yMetres": ry}
        max_resolution_m = max(max_resolution_m, rx, ry)
    resolution = max_resolution_m / target_factor
    bounds = transform_bounds(terrain_info["crs"], target, *rasterio.transform.array_bounds(
        terrain_info["height"], terrain_info["width"], terrain_info["transform"]
    ), densify_pts=21)
    minx, miny, maxx, maxy = bounds
    if not all(math.isfinite(v) for v in bounds) or minx >= maxx or miny >= maxy:
        raise ValueError("Terrain bounds cannot be transformed to targetCrs")
    left = math.floor(minx / resolution) * resolution
    top = math.ceil(maxy / resolution) * resolution
    width = max(1, int(math.ceil((maxx - left) / resolution)))
    height = max(1, int(math.ceil((top - miny) / resolution)))
    transform = Affine(resolution, 0.0, left, 0.0, -resolution, top)
    grid = {
        "crs": target.to_string(), "width": width, "height": height,
        "transform": [float(v) for v in tuple(transform)[:6]],
        "resolutionMetres": max_resolution_m,
        "bounds": [left, top - height * resolution, left + width * resolution, top],
        "nativeResolutionsMetres": native,
        "resolutionRule": "maximum native x/y pixel size across all contributing rasters",
    }
    return grid, native


def _read_continuous(info: dict[str, Any], unit_factor: float, grid: dict[str, Any],
                     *, sign: float = 1.0, add_offset: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    """Warp continuous data bilinearly and its validity independently by nearest."""
    with rasterio.open(info["path"]) as ds:
        src = ds.read(1, masked=True).astype("float64").filled(np.nan)
        src_valid = np.isfinite(src) & ds.read_masks(1).astype(bool)
        # Rasterio's mask includes declared nodata and internal masks.  Preserve
        # valid zero elevations/water levels; zero is never a missing sentinel.
        dst = np.full((grid["height"], grid["width"]), np.nan, dtype=np.float64)
        valid = np.zeros(dst.shape, dtype=np.uint8)
        out_transform = Affine(*grid["transform"])
        reproject(
            source=(src * unit_factor * sign + add_offset).astype(np.float64), destination=dst,
            src_transform=ds.transform, src_crs=ds.crs, src_nodata=np.nan,
            dst_transform=out_transform, dst_crs=grid["crs"], dst_nodata=np.nan,
            resampling=Resampling.bilinear,
        )
        reproject(
            source=src_valid.astype(np.uint8), destination=valid,
            src_transform=ds.transform, src_crs=ds.crs, src_nodata=None,
            dst_transform=out_transform, dst_crs=grid["crs"], dst_nodata=0,
            resampling=Resampling.nearest,
        )
    dst[valid == 0] = np.nan
    dst[~np.isfinite(dst)] = np.nan
    return dst.astype(np.float32), valid.astype(bool)


def _read_mask(info: dict[str, Any], grid: dict[str, Any], true_values: list[Any],
               *, role: str) -> tuple[np.ndarray, np.ndarray]:
    with rasterio.open(info["path"]) as ds:
        source = ds.read(1, masked=True)
        src_valid = ~np.ma.getmaskarray(source)
        values = np.asarray(source.filled(0))
        try:
            is_true = np.isin(values, np.asarray(true_values)) & src_valid
        except Exception as exc:
            raise ValueError(f"{role}.trueValues must be an array of scalar values") from exc
        dst = np.full((grid["height"], grid["width"]), 255, dtype=np.uint8)
        reproject(
            source=is_true.astype(np.uint8), destination=dst,
            src_transform=ds.transform, src_crs=ds.crs, src_nodata=None,
            dst_transform=Affine(*grid["transform"]), dst_crs=grid["crs"],
            dst_nodata=255, resampling=Resampling.nearest,
        )
        # A distinct validity warp keeps source nodata distinct from a valid false.
        dst_valid = np.zeros(dst.shape, dtype=np.uint8)
        reproject(
            source=src_valid.astype(np.uint8), destination=dst_valid,
            src_transform=ds.transform, src_crs=ds.crs, src_nodata=None,
            dst_transform=Affine(*grid["transform"]), dst_crs=grid["crs"],
            dst_nodata=0, resampling=Resampling.nearest,
        )
    dst[dst_valid == 0] = 255
    return dst, dst_valid.astype(bool)


def _adjustment(source: dict[str, Any], *, target_datum: str,
                target_reference_epoch: str, label: str) -> tuple[float, dict[str, Any] | None]:
    if not isinstance(source.get("verticalDatum"), str) or not source["verticalDatum"].strip():
        _compat("vertical_datum_missing", f"{label}.verticalDatum is required")
    if source.get("verticalReferenceEpoch") is None:
        _compat("vertical_reference_epoch_missing", f"{label}.verticalReferenceEpoch is required")
    try:
        source_datum = _text(source.get("verticalDatum"), f"{label}.verticalDatum")
        source_epoch = _epoch(source.get("verticalReferenceEpoch"), f"{label}.verticalReferenceEpoch")
    except ValueError as exc:
        _compat("vertical_reference_invalid", str(exc))
    if source_datum == target_datum and source_epoch == target_reference_epoch:
        if source.get("reviewedVerticalAdjustment") is not None:
            _compat("unused_vertical_adjustment", f"{label} declares a vertical adjustment although datum and reference epoch already match")
        return 0.0, None
    adjustment = source.get("reviewedVerticalAdjustment")
    if not isinstance(adjustment, dict):
        _compat(
            "vertical_reference_mismatch",
            f"{label} vertical reference does not match the target and has no reviewed offset",
            sourceDatum=source_datum, sourceReferenceEpoch=source_epoch,
            targetDatum=target_datum, targetReferenceEpoch=target_reference_epoch,
        )
    expected = {
        "fromVerticalDatum": source_datum,
        "toVerticalDatum": target_datum,
        "fromReferenceEpoch": source_epoch,
        "toReferenceEpoch": target_reference_epoch,
    }
    for key, value in expected.items():
        if adjustment.get(key) != value:
            _compat("vertical_adjustment_scope_mismatch", f"{label} reviewed vertical adjustment does not exactly match its source and target", field=key, expected=value, actual=adjustment.get(key))
    if adjustment.get("reviewed") is not True:
        _compat("vertical_adjustment_not_reviewed", f"{label} vertical offset must be explicitly marked reviewed")
    reviewer = _text(adjustment.get("reviewedBy"), f"{label}.reviewedVerticalAdjustment.reviewedBy")
    evidence = _text(adjustment.get("evidence"), f"{label}.reviewedVerticalAdjustment.evidence")
    offset = _finite_number(adjustment.get("offsetMetres"), f"{label}.reviewedVerticalAdjustment.offsetMetres")
    record = {**expected, "offsetMetres": offset, "reviewed": True, "reviewedBy": reviewer, "evidence": evidence}
    return offset, record


def _baseline_adjustment(terrain: dict[str, Any], target_epoch: str) -> tuple[float, dict[str, Any] | None]:
    if terrain.get("baselineEpoch") is None:
        _compat("terrain_baseline_epoch_missing", "terrain.baselineEpoch is required")
    try:
        source_epoch = _date(terrain.get("baselineEpoch"), "terrain.baselineEpoch")
    except ValueError as exc:
        _compat("terrain_baseline_epoch_invalid", str(exc))
    if source_epoch == target_epoch:
        if terrain.get("reviewedBaselineAdjustment") is not None:
            _compat("unused_baseline_adjustment", "Terrain declares a baseline adjustment although baseline epochs already match")
        return 0.0, None
    adjustment = terrain.get("reviewedBaselineAdjustment")
    if not isinstance(adjustment, dict):
        _compat(
            "baseline_epoch_mismatch",
            "Terrain baseline epoch differs from projection baseline and has no reviewed adjustment",
            sourceBaselineEpoch=source_epoch, targetBaselineEpoch=target_epoch,
        )
    if adjustment.get("fromEpoch") != source_epoch or adjustment.get("toEpoch") != target_epoch:
        _compat(
            "baseline_adjustment_scope_mismatch",
            "Reviewed terrain adjustment must exactly match source and target baseline epochs",
            expected={"fromEpoch": source_epoch, "toEpoch": target_epoch},
            actual={"fromEpoch": adjustment.get("fromEpoch"), "toEpoch": adjustment.get("toEpoch")},
        )
    if adjustment.get("reviewed") is not True:
        _compat("baseline_adjustment_not_reviewed", "Terrain baseline offset must be explicitly marked reviewed")
    reviewer = _text(adjustment.get("reviewedBy"), "terrain.reviewedBaselineAdjustment.reviewedBy")
    evidence = _text(adjustment.get("evidence"), "terrain.reviewedBaselineAdjustment.evidence")
    offset = _finite_number(adjustment.get("offsetMetres"), "terrain.reviewedBaselineAdjustment.offsetMetres")
    return offset, {"fromEpoch": source_epoch, "toEpoch": target_epoch, "offsetMetres": offset,
                    "reviewed": True, "reviewedBy": reviewer, "evidence": evidence}


def _write_float(path: Path, array: np.ndarray, grid: dict[str, Any], tags: dict[str, str]) -> None:
    with rasterio.open(
        path, "w", driver="GTiff", width=grid["width"], height=grid["height"],
        count=1, dtype="float32", crs=grid["crs"], transform=Affine(*grid["transform"]),
        nodata=np.nan, compress="lzw", predictor=3,
    ) as ds:
        ds.write(np.asarray(array, dtype=np.float32), 1)
        ds.update_tags(**tags)


def _write_mask(path: Path, array: np.ndarray, grid: dict[str, Any], tags: dict[str, str]) -> None:
    with rasterio.open(
        path, "w", driver="GTiff", width=grid["width"], height=grid["height"],
        count=1, dtype="uint8", crs=grid["crs"], transform=Affine(*grid["transform"]),
        nodata=255, compress="lzw",
    ) as ds:
        ds.write(np.asarray(array, dtype=np.uint8), 1)
        ds.update_tags(**tags)


def _load_config(config_path: Path) -> dict[str, Any]:
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise OSError(f"Cannot read scenario input config {config_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Scenario input config is invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Scenario input config must be a JSON object")
    return data


def _water_groups(config: dict[str, Any], target_datum: str, target_reference_epoch: str,
                  config_path: Path) -> tuple[list[dict[str, Any]], list[tuple[str, dict[str, Any]]]]:
    groups = config.get("waterLevels")
    if not isinstance(groups, list) or not groups:
        _compat("missing_water_level_model", "At least one dated total-water-level or explicitly grouped component model is required")
    seen_years: set[int] = set()
    descriptions: list[dict[str, Any]] = []
    raster_infos: list[tuple[str, dict[str, Any]]] = []
    for index, group in enumerate(groups):
        label = f"waterLevels[{index}]"
        if not isinstance(group, dict):
            raise ValueError(f"{label} must be an object")
        year = group.get("year")
        if isinstance(year, bool) or not isinstance(year, int) or not 1000 <= year <= 9999:
            raise ValueError(f"{label}.year must be an integer four-digit year")
        if year in seen_years:
            _compat("duplicate_water_level_year", f"Only one declared level group is allowed for year {year}; combine components inside that group")
        seen_years.add(year)
        mode = group.get("mode")
        if mode not in ("total", "components"):
            _compat("water_level_semantics_missing", f"{label}.mode must be 'total' or 'components'")
        scenario = _text(group.get("scenario", "unspecified"), f"{label}.scenario")
        if mode == "total":
            if "components" in group:
                _compat("water_level_double_counting", f"{label} cannot declare both a total level and components")
            source = group.get("source")
            if not isinstance(source, dict):
                raise ValueError(f"{label}.source must describe the total-water-level raster or scalar")
            semantics = source.get("semantics")
            if semantics != "total_water_level":
                _compat("water_level_semantics_missing", f"{label}.source.semantics must explicitly declare total_water_level")
            if source.get("verticalRole", "absolute_level") != "absolute_level":
                _compat("total_level_role_mismatch", f"{label}.source must be an absolute_level")
            sources = [("total_water_level", source)]
            combination = {"method": "declared total water level", "note": "No component addition applied."}
        else:
            if "source" in group:
                _compat("water_level_double_counting", f"{label} component mode cannot also declare a total source")
            components = group.get("components")
            review = group.get("combinationReview")
            if (group.get("combination") != "sum" or not isinstance(components, dict) or not components
                    or not isinstance(review, dict) or review.get("componentsAreDisjoint") is not True):
                _compat("component_combination_undeclared", f"{label} components require combination='sum', a non-empty components object, and a reviewed declaration that components are disjoint")
            review_by = _text(review.get("reviewedBy"), f"{label}.combinationReview.reviewedBy")
            review_evidence = _text(review.get("evidence"), f"{label}.combinationReview.evidence")
            if set(components) - _COMPONENTS:
                _compat("unsupported_water_component", f"{label} contains unsupported component names", components=sorted(set(components) - _COMPONENTS))
            sources = []
            absolute_roles = 0
            for name in ("mean_water_level", "tide", "surge"):
                if name in components:
                    item = components[name]
                    if not isinstance(item, dict):
                        raise ValueError(f"{label}.components.{name} must describe a raster or scalar")
                    if item.get("semantics") != name:
                        _compat("water_level_semantics_mismatch", f"{label}.components.{name}.semantics must be '{name}'")
                    if item.get("verticalRole") not in ("absolute_level", "height_anomaly"):
                        _compat("component_vertical_role_missing", f"{label}.components.{name}.verticalRole must declare absolute_level or height_anomaly")
                    if item["verticalRole"] == "absolute_level":
                        absolute_roles += 1
                    sources.append((name, item))
            if absolute_roles != 1:
                _compat("component_absolute_level_count", f"{label} must contain exactly one absolute_level component; the remaining components are height_anomaly values", absoluteLevelCount=absolute_roles)
            combination = {"method": "explicit sum", "componentsAreDisjoint": True,
                           "reviewedBy": review_by, "evidence": review_evidence,
                           "note": "No total-water-level input is accepted in this component group."}
        component_info = []
        for name, source in sources:
            source_label = f"{label}.{name}"
            factor = _unit_factor(source.get("units"), f"{source_label}.units")
            sign = _vertical_sign(source, source_label)
            if "validYear" in source and source["validYear"] != year:
                _compat("water_level_year_mismatch", f"{source_label}.validYear differs from its group year", groupYear=year, sourceYear=source["validYear"])
            if source.get("sourceDate") is None:
                _compat("water_source_date_missing", f"{source_label}.sourceDate is required")
            try:
                source_date = _date(source.get("sourceDate"), f"{source_label}.sourceDate")
            except ValueError as exc:
                _compat("water_source_date_invalid", str(exc))
            provenance = source.get("provenance")
            if not ((isinstance(provenance, str) and provenance.strip())
                    or (isinstance(provenance, dict) and provenance)):
                _compat("water_provenance_missing", f"{source_label}.provenance must identify the model, source product or fixture basis")
            vertical_role = source.get("verticalRole", "absolute_level")
            if mode == "components" and vertical_role == "height_anomaly":
                # A delta is not an absolute height.  It must already be expressed
                # in the target reference context; applying a datum offset to it
                # would shift the water level a second time.
                if not isinstance(source.get("verticalDatum"), str) or not source["verticalDatum"].strip():
                    _compat("vertical_datum_missing", f"{source_label}.verticalDatum is required")
                if source.get("verticalReferenceEpoch") is None:
                    _compat("vertical_reference_epoch_missing", f"{source_label}.verticalReferenceEpoch is required")
                try:
                    source_datum = _text(source.get("verticalDatum"), f"{source_label}.verticalDatum")
                    source_epoch = _epoch(source.get("verticalReferenceEpoch"), f"{source_label}.verticalReferenceEpoch")
                except ValueError as exc:
                    _compat("vertical_reference_invalid", str(exc))
                if source_datum != target_datum or source_epoch != target_reference_epoch:
                    _compat("anomaly_reference_mismatch", f"{source_label} is a height anomaly and cannot receive an absolute datum/reference-epoch offset", sourceDatum=source_datum, sourceReferenceEpoch=source_epoch, targetDatum=target_datum, targetReferenceEpoch=target_reference_epoch)
                if source.get("reviewedVerticalAdjustment") is not None:
                    _compat("anomaly_vertical_adjustment_not_allowed", f"{source_label} height anomaly cannot carry an absolute vertical offset")
                datum_offset, vertical_record = 0.0, None
            else:
                datum_offset, vertical_record = _adjustment(
                    source, target_datum=target_datum,
                    target_reference_epoch=target_reference_epoch, label=source_label,
                )
            uncertainty = source.get("uncertaintyMetres")
            if uncertainty is not None:
                uncertainty = _finite_number(uncertainty, f"{source_label}.uncertaintyMetres", nonnegative=True)
            item_info: dict[str, Any] = {
                "name": name, "sourceId": source_label,
                "semantics": source.get("semantics"), "sourceDate": source_date,
                "units": source["units"], "metresPerUnit": factor,
                "positiveDirection": source["positiveDirection"],
                "inputToPositiveUpSign": sign,
                "verticalDatum": source["verticalDatum"], "verticalReferenceEpoch": source["verticalReferenceEpoch"],
                "verticalRole": vertical_role,
                "reviewedVerticalAdjustment": vertical_record,
                "appliedVerticalOffsetMetres": datum_offset,
                "uncertaintyMetres": uncertainty,
                "provenance": provenance,
            }
            kind = source.get("kind")
            if kind == "raster":
                path = _source_path(source, config_path, source_label)
                info = _raster_info(path, source_label)
                item_info.update({"kind": "raster", "sourceName": path.name, "sourceSha256": _sha256(path),
                                  "nativeCrs": info["nativeCrs"], "nativeWidth": info["width"], "nativeHeight": info["height"]})
                raster_infos.append((source_label, info))
            elif kind == "scalar":
                value = _finite_number(source.get("value"), f"{source_label}.value") * factor * sign + datum_offset
                item_info.update({"kind": "scalar", "valueMetres": value})
            else:
                raise ValueError(f"{source_label}.kind must be 'raster' or 'scalar'")
            component_info.append(item_info)
        descriptions.append({"year": year, "scenario": scenario, "mode": mode,
                             "semantics": "total_water_level" if mode == "total" else "component_sum",
                             "combination": combination, "components": component_info})
    return descriptions, raster_infos


def prepare_inputs(event: str, config_path: str | Path,
                   output_root: str | Path | None = None) -> Path:
    """Validate, align and publish an immutable ``scenario-inputs`` product.

    The JSON contract requires ``dataKind``; target ``verticalDatum`` and
    ``verticalReferenceEpoch``; ``projectionBaselineEpoch``; a ``terrain``
    raster object; a ``coastalSeeds`` mask; and one or more ``waterLevels``.
Terrain metadata includes ``units``, ``positiveDirection`` (``up`` or
``down``), ``representation`` (``ground`` or
    ``surface_model``), source datum/reference epoch, ``baselineEpoch`` and
    ``sourceDate``. Water levels use one group per year, each either
    ``mode: total`` with a ``source`` declared as ``total_water_level``, or
    ``mode: components`` with distinct mean-water-level/tide/surge components,
    ``combination: sum`` and a reviewed ``combinationReview`` declaration.
    Component groups require exactly one ``verticalRole: absolute_level`` and
    mark every other component ``height_anomaly``; only the absolute component
    may receive a reviewed datum/reference-epoch offset.
    Sources may be one-band local rasters or dated scalars and must carry units,
    positive direction,
    vertical datum/reference epoch and provenance date. A datum/reference-epoch
    mismatch requires an exact, reviewed offset record; a terrain baseline
    epoch mismatch requires a separate reviewed baseline offset. Raster paths
    are relative to the config file. Continuous layers are bilinear; masks are
    nearest-neighbour. The output grid uses the largest native pixel dimension
    among all contributing rasters.
    """
    core.safe_name(event)
    path_config = Path(config_path).expanduser().resolve()
    config = _load_config(path_config)
    data_kind = config.get("dataKind")
    if data_kind not in ("observed", "derived", "scenario", "synthetic"):
        raise ValueError("dataKind must explicitly be observed, derived, scenario or synthetic")
    if not config.get("verticalDatum"):
        _compat("target_vertical_datum_missing", "verticalDatum is required")
    if config.get("verticalReferenceEpoch") is None:
        _compat("target_vertical_reference_epoch_missing", "verticalReferenceEpoch is required")
    if config.get("projectionBaselineEpoch") is None:
        _compat("projection_baseline_epoch_missing", "projectionBaselineEpoch is required")
    try:
        target_datum = _text(config.get("verticalDatum"), "verticalDatum")
        target_reference_epoch = _epoch(config.get("verticalReferenceEpoch"), "verticalReferenceEpoch")
        projection_baseline = _date(config.get("projectionBaselineEpoch"), "projectionBaselineEpoch")
    except ValueError as exc:
        _compat("target_vertical_reference_invalid", str(exc))
    terrain = config.get("terrain")
    if not isinstance(terrain, dict):
        _compat("terrain_model_missing", "terrain raster metadata is required")
    if terrain.get("representation") not in ("ground", "surface_model"):
        _compat("terrain_representation_missing", "terrain.representation must identify ground or surface_model")
    terrain_units = _unit_factor(terrain.get("units"), "terrain.units")
    terrain_sign = _vertical_sign(terrain, "terrain")
    if terrain.get("sourceDate") is None:
        _compat("terrain_source_date_missing", "terrain.sourceDate is required")
    try:
        terrain_source_date = _date(terrain.get("sourceDate"), "terrain.sourceDate")
    except ValueError as exc:
        _compat("terrain_source_date_invalid", str(exc))
    terrain_path = _source_path(terrain, path_config, "terrain")
    terrain_info = _raster_info(terrain_path, "terrain")
    if terrain.get("expectedCrs") is not None:
        expected_crs = CRS.from_user_input(terrain["expectedCrs"])
        if expected_crs != terrain_info["crs"]:
            _compat("declared_crs_mismatch", "terrain expectedCrs does not match raster CRS", expected=expected_crs.to_string(), actual=terrain_info["nativeCrs"])
    datum_offset, datum_adjustment = _adjustment(
        terrain, target_datum=target_datum,
        target_reference_epoch=target_reference_epoch, label="terrain",
    )
    baseline_offset, baseline_adjustment = _baseline_adjustment(terrain, projection_baseline)
    terrain_offset = datum_offset + baseline_offset
    terrain_uncertainty = terrain.get("uncertaintyMetres")
    if terrain_uncertainty is not None:
        terrain_uncertainty = _finite_number(terrain_uncertainty, "terrain.uncertaintyMetres", nonnegative=True)

    quality_mask = config.get("qualityMask")
    seed_spec = config.get("coastalSeeds")
    barrier_spec = config.get("barriers")
    if not isinstance(seed_spec, dict):
        _compat("coastal_seeds_missing", "A coastalSeeds mask is required for downstream coastal connectivity screening")
    seed_path = _source_path(seed_spec, path_config, "coastalSeeds")
    seed_info = _raster_info(seed_path, "coastalSeeds")
    seed_true = seed_spec.get("trueValues", [1])
    if not isinstance(seed_true, list) or not seed_true:
        raise ValueError("coastalSeeds.trueValues must be a non-empty array")

    quality_info = None
    if quality_mask is not None:
        if not isinstance(quality_mask, dict):
            raise ValueError("qualityMask must be an object")
        quality_info = _raster_info(_source_path(quality_mask, path_config, "qualityMask"), "qualityMask")
    barrier_info = None
    barrier_true: list[Any] | None = None
    if barrier_spec is not None:
        if not isinstance(barrier_spec, dict):
            raise ValueError("barriers must be an object when supplied")
        barrier_info = _raster_info(_source_path(barrier_spec, path_config, "barriers"), "barriers")
        barrier_true = barrier_spec.get("trueValues", [1])
        if not isinstance(barrier_true, list) or not barrier_true:
            raise ValueError("barriers.trueValues must be a non-empty array")

    water_descriptions, water_infos = _water_groups(config, target_datum, target_reference_epoch, path_config)
    target_crs_value = config.get("targetCrs")
    target_crs = CRS.from_user_input(target_crs_value) if target_crs_value else terrain_info["crs"]
    if not target_crs.is_projected:
        _compat("projected_target_crs_required", "A projected targetCrs is required when terrain uses a geographic or non-projected CRS", terrainCrs=terrain_info["nativeCrs"])

    all_infos: list[tuple[str, dict[str, Any]]] = [("terrain", terrain_info), ("coastalSeeds", seed_info)]
    if quality_info is not None:
        all_infos.append(("qualityMask", quality_info))
    if barrier_info is not None:
        all_infos.append(("barriers", barrier_info))
    all_infos.extend(water_infos)
    grid, _ = _target_grid(terrain_info, target_crs, all_infos)

    elevation, elevation_source_valid = _read_continuous(
        terrain_info, terrain_units, grid, sign=terrain_sign, add_offset=terrain_offset
    )
    elevation_valid = elevation_source_valid & np.isfinite(elevation)
    if quality_info is not None:
        q_spec = quality_mask or {}
        q_values = q_spec.get("validValues", [1])
        if not isinstance(q_values, list) or not q_values:
            raise ValueError("qualityMask.validValues must be a non-empty array")
        qmask, _ = _read_mask(quality_info, grid, q_values, role="qualityMask")
        elevation_valid &= (qmask == 1)
    elevation[~elevation_valid] = np.nan
    if not np.any(elevation_valid):
        _compat("no_valid_elevation", "No valid terrain pixels remain after nodata and quality-mask filtering")

    seeds_raw, seeds_coverage = _read_mask(seed_info, grid, seed_true, role="coastalSeeds")
    if np.any(elevation_valid & ~seeds_coverage):
        _compat("coastal_seed_coverage_incomplete", "coastalSeeds must cover every valid terrain cell so false and unknown are not conflated")
    seeds = np.where(elevation_valid, seeds_raw, 255).astype(np.uint8)
    seed_cells = elevation_valid & (seeds == 1)
    if not np.any(seed_cells):
        _compat("coastal_seed_empty", "coastalSeeds has no true seed cell on valid terrain")

    barriers: np.ndarray | None = None
    if barrier_info is not None:
        barrier_raw, barrier_coverage = _read_mask(barrier_info, grid, barrier_true or [1], role="barriers")
        if np.any(elevation_valid & ~barrier_coverage):
            _compat("barrier_coverage_incomplete", "When supplied, barriers must cover every valid terrain cell")
        barriers = np.where(elevation_valid, barrier_raw, 255).astype(np.uint8)
        if np.any(seed_cells & (barriers == 1)):
            _compat("seed_inside_barrier", "Coastal connectivity seeds cannot be marked as barriers")

    water_arrays: dict[int, np.ndarray] = {}
    water_valid_counts: dict[int, int] = {}
    source_by_label = {label: info for label, info in water_infos}
    for group_index, (group, description) in enumerate(zip(config["waterLevels"], water_descriptions)):
        year = description["year"]
        sources: list[tuple[str, dict[str, Any]]] = []
        if description["mode"] == "total":
            sources = [("total_water_level", group["source"])]
        else:
            sources = [(name, item) for name, item in group["components"].items()]
        components: list[np.ndarray] = []
        description_by_name = {item["name"]: item for item in description["components"]}
        for name, source in sources:
            source_label = f"waterLevels[{group_index}].{name}"
            component_description = description_by_name[name]
            factor = component_description["metresPerUnit"]
            sign = component_description["inputToPositiveUpSign"]
            offset = component_description["appliedVerticalOffsetMetres"]
            if source.get("kind") == "scalar":
                value = _finite_number(source.get("value"), f"{source_label}.value") * factor * sign + offset
                component = np.full(elevation.shape, np.nan, dtype=np.float32)
                component[elevation_valid] = value
            else:
                info = source_by_label[source_label]
                component, _ = _read_continuous(info, factor, grid, sign=sign, add_offset=offset)
                component[~elevation_valid] = np.nan
            components.append(component)
        combined_valid = np.logical_and.reduce([np.isfinite(array) for array in components]) & elevation_valid
        level = np.full(elevation.shape, np.nan, dtype=np.float32)
        if components:
            total = np.zeros(elevation.shape, dtype=np.float64)
            for array in components:
                total += np.nan_to_num(array, nan=0.0).astype(np.float64)
            level[combined_valid] = total[combined_valid].astype(np.float32)
        if not np.any(combined_valid):
            _compat("no_valid_water_level", f"Water-level year {year} has no valid cells on the terrain grid", year=year)
        water_arrays[year] = level
        water_valid_counts[year] = int(combined_valid.sum())

    source_records: list[dict[str, Any]] = []
    file_sources: list[tuple[str, dict[str, Any] | None]] = [("terrain", terrain_info), ("coastalSeeds", seed_info)]
    if quality_info is not None:
        file_sources.append(("qualityMask", quality_info))
    if barrier_info is not None:
        file_sources.append(("barriers", barrier_info))
    file_sources.extend(water_infos)
    for label, info in file_sources:
        source_records.append({
            "id": label,
            "name": info["path"].name,
            "sha256": _sha256(info["path"]),
            "nativeCrs": info["nativeCrs"],
            "nativeGrid": {"width": info["width"], "height": info["height"],
                           "transform": [float(v) for v in tuple(info["transform"])[:6]]},
            "nativeResolutionMetres": grid["nativeResolutionsMetres"][label],
        })
    uncertainties = []
    if terrain_uncertainty is not None:
        uncertainties.append({"sourceId": "terrain", "uncertaintyMetres": terrain_uncertainty})
    for description in water_descriptions:
        for component in description["components"]:
            if component["uncertaintyMetres"] is not None:
                uncertainties.append({"sourceId": f"waterLevel{description['year']}:{component['name']}",
                                      "uncertaintyMetres": component["uncertaintyMetres"]})
    water_source_count = sum(len(description["components"]) for description in water_descriptions)
    scalar_water_source_count = sum(
        1 for description in water_descriptions for component in description["components"]
        if component["kind"] == "scalar"
    )

    metadata: dict[str, Any] = {
        "dataKind": data_kind,
        "syntheticLineage": data_kind == "synthetic",
        "codeVersion": CODE_VERSION,
        "sources": source_records,
        "sourceHashes": {item["id"]: item["sha256"] for item in source_records},
        "sourceCounts": {"inputSources": len(source_records) + scalar_water_source_count,
                         "rasterInputs": len(source_records), "waterLevelSources": water_source_count,
                         "waterLevelYears": len(water_arrays),
                         "uncertaintySources": len(uncertainties)},
        "masks": {
            "coastalSeeds": {"sourceId": "coastalSeeds", "trueValues": seed_true,
                             "encoding": "0=no seed, 1=seed, 255=no data"},
            "qualityMask": ({"sourceId": "qualityMask", "validValues": (quality_mask or {}).get("validValues", [1]),
                             "encoding": "validValues are valid; zero/nodata are excluded"}
                            if quality_info is not None else None),
            "barriers": ({"sourceId": "barriers", "trueValues": barrier_true,
                          "encoding": "0=permitted, 1=barrier, 255=no data"}
                         if barrier_info is not None else None),
        },
        "grid": grid,
        "coverage": {"terrainValidCellCount": int(elevation_valid.sum()),
                     "coastalSeedCellCount": int(seed_cells.sum()),
                     "barrierCellCount": int(np.count_nonzero(barriers == 1)) if barriers is not None else None,
                     "waterLevelValidCellCounts": {str(year): count for year, count in water_valid_counts.items()}},
        "verticalDatum": target_datum,
        "verticalReferenceEpoch": target_reference_epoch,
        "baselineEpoch": projection_baseline,
        "terrain": {"representation": terrain["representation"], "sourceDate": terrain_source_date,
                    "sourceBaselineEpoch": terrain["baselineEpoch"], "units": terrain["units"],
                    "sourcePositiveDirection": terrain["positiveDirection"], "outputPositiveDirection": "up",
                    "uncertaintyMetres": terrain_uncertainty,
                    "datumAdjustment": datum_adjustment, "baselineAdjustment": baseline_adjustment,
                    "interpretation": ("ground elevations" if terrain["representation"] == "ground"
                                       else "surface-model elevations; not precise road or building ground elevations")},
        "supportedYears": sorted(water_arrays),
        "waterLevels": water_descriptions,
        "uncertainty": {"sources": uncertainties, "sourceCount": len(uncertainties),
                        "combinedUncertaintyCalculated": False,
                        "reason": "Input uncertainties are retained by source; no independence or covariance assumption is made."},
        "resampling": {"continuous": "bilinear", "categoricalMasks": "nearest", "zeroIsValid": True},
        "warnings": ["Scenario inputs are prepared source layers; this product is not an inundation forecast."],
    }

    def writer(stage: Path) -> dict[str, str]:
        files: dict[str, str] = {}
        common_tags = {"event": event, "product": "scenario-inputs", "dataKind": data_kind,
                       "verticalDatum": target_datum, "baselineEpoch": projection_baseline}
        _write_float(stage / "elevation_metres.tif", elevation, grid,
                     {**common_tags, "asset": "elevationMetres", "units": "metres", "positive": "up",
                      "representation": terrain["representation"]})
        files["elevationMetres"] = "elevation_metres.tif"
        _write_mask(stage / "coastal_seeds.tif", seeds, grid,
                    {**common_tags, "asset": "coastalSeeds", "values": "0=no seed, 1=seed, 255=no data"})
        files["coastalSeeds"] = "coastal_seeds.tif"
        if barriers is not None:
            _write_mask(stage / "barriers.tif", barriers, grid,
                        {**common_tags, "asset": "barriers", "values": "0=permitted, 1=barrier, 255=no data"})
            files["barriers"] = "barriers.tif"
        for year, array in sorted(water_arrays.items()):
            filename = f"water_level_{year}.tif"
            _write_float(stage / filename, array, grid,
                         {**common_tags, "asset": f"waterLevel{year}", "units": "metres",
                          "positive": "up", "semantics": "prepared_water_level"})
            files[f"waterLevel{year}"] = filename
        return files

    return core.publish(event, "scenario-inputs", metadata, writer, output_root=output_root)
