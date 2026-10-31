"""Count mapped OSM footprints that overlap a published hazard footprint.

This offline processor reads immutable ``coherence-change``,
``change-frequency`` or ``flood-extent`` manifests and a local, hash-bound OSM
GeoJSON snapshot. It never downloads or refreshes OSM data.

Snapshot JSON schema (version 1.0)::

    {
      "schemaVersion": "1.0",
      "dataKind": "observed" | "derived" | "scenario" | "synthetic",
      "sourceDate": "2026-01-01",
      "source": "provider/export and provenance note",
      "geojsonPath": "./buildings.geojson",
      "sha256": "SHA-256 of the exact GeoJSON bytes",
      "coverage": {
        "geometry": {"type": "Polygon", "coordinates": [...]},
        "crs": "EPSG:4326",
        "completeness": "complete" | "partial" | "unknown"
      }
    }

``coverage.completeness`` is optional and defaults to ``unknown``. A complete
count is published only when it explicitly equals ``complete`` and the
coverage polygon contains all valid hazard support in the selected region(s).
Omitting that assertion yields an explicitly partial count. Coverage geometry
and CRS are required; the processor never infers snapshot completeness from
the mere existence of a polygon.

Building feature IDs are read from ``properties.osmType`` and
``properties.osmId``. The documented aliases are ``osm_type`` or ``type`` for
the type, and ``osm_id`` or ``id`` for the identifier. Type values are
``node``, ``way`` or ``relation``; keys are composite (for example,
``way/123`` and ``relation/123`` remain distinct). Duplicate features with the
same composite key have their geometries unioned before counting.

Optional region GeoJSON must be a FeatureCollection of polygon features with
unique ``properties.regionId`` strings. GeoJSON without a legacy ``crs`` member
uses the RFC 7946 default EPSG:4326. All valid geometries are transformed to a
metric analysis CRS before intersections. Selected regions are unioned before
combined totals are deduplicated.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime
import json
import math
from pathlib import Path
import sys
from typing import Any, Mapping

import numpy as np
import rasterio
from pyproj import CRS, Transformer
from rasterio.features import shapes
from shapely.geometry import GeometryCollection, mapping, shape
from shapely.ops import transform as transform_geometry
from shapely.ops import unary_union
from shapely.validation import make_valid

from .p3 import core


PRODUCT = "building-exposure"
HAZARD_PRODUCTS = {"coherence-change", "change-frequency", "flood-extent"}
DATA_KINDS = {"observed", "derived", "scenario", "synthetic"}
OSM_TYPES = {"node", "way", "relation"}
AREA_TOLERANCE_M2 = 1e-6


class BuildingExposureError(ValueError):
    """Invalid hazard, snapshot or region input for building exposure."""


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise BuildingExposureError(f"{label} must be a JSON object")
    return value


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BuildingExposureError(f"Cannot read {label} JSON {path}: {exc}") from exc
    return _object(value, label)


def _date_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BuildingExposureError(f"{label} must be an ISO date or timestamp")
    text = value.strip()
    try:
        if len(text) == 10:
            parsed_date = date.fromisoformat(text)
            if parsed_date.isoformat() != text:
                raise ValueError
            return text
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BuildingExposureError(f"{label} must be an ISO date or timestamp") from exc
    return parsed.isoformat()


def _source_run_ids(manifest: Mapping[str, Any]) -> list[str]:
    values = manifest.get("sourceRunIds", manifest.get("upstreamRunIds", []))
    if values is None:
        values = []
    if not isinstance(values, list):
        raise BuildingExposureError("Hazard sourceRunIds must be a list")
    result: list[str] = []
    for index, value in enumerate(values):
        try:
            core.safe_name(value)
        except ValueError as exc:
            raise BuildingExposureError(f"Hazard sourceRunIds[{index}] is invalid") from exc
        if value not in result:
            result.append(value)
    return result


def _load_hazard(path_value: str | Path, event: str) -> tuple[dict[str, Any], Path, list[str]]:
    path = Path(path_value).expanduser().resolve()
    if not path.is_file():
        raise BuildingExposureError(f"Hazard manifest does not exist: {path}")
    try:
        manifest = core.load_manifest(path)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
        raise BuildingExposureError(f"Invalid hazard manifest: {exc}") from exc
    if manifest.get("event") != event:
        raise BuildingExposureError("Hazard manifest event does not match requested event")
    product = manifest.get("product")
    if product not in HAZARD_PRODUCTS:
        raise BuildingExposureError("Hazard product must be coherence-change, change-frequency or flood-extent")
    try:
        core.safe_name(manifest.get("runId"))
    except ValueError as exc:
        raise BuildingExposureError("Hazard manifest has an invalid runId") from exc
    if manifest.get("dataKind") not in DATA_KINDS:
        raise BuildingExposureError("Hazard manifest must explicitly declare a supported dataKind")
    source_runs = _source_run_ids(manifest)
    if manifest.get("runId") in source_runs:
        raise BuildingExposureError("Hazard lineage cannot list its own runId as a source")
    assets = manifest.get("assets")
    if not isinstance(assets, dict):
        raise BuildingExposureError("Hazard manifest must declare an assets object")
    return manifest, path, source_runs


def _read_grid_raster(manifest: Mapping[str, Any], key: str) -> tuple[np.ndarray, dict[str, Any]]:
    try:
        array, grid = core.read_raster(manifest, key)
    except (OSError, KeyError, ValueError, rasterio.errors.RasterioError) as exc:
        raise BuildingExposureError(f"Cannot read hash-checked hazard raster {key}: {exc}") from exc
    array = np.asarray(array, dtype="float64")
    if array.ndim != 2:
        raise BuildingExposureError(f"Hazard raster {key} must be single-band")
    return array, grid


def _read_hazard_arrays(
    manifest: Mapping[str, Any], frequency_threshold: float | None,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any], int]:
    """Return (supported, detections, grid, detection_count)."""
    product = manifest["product"]
    if product in {"coherence-change", "flood-extent"}:
        if frequency_threshold is not None:
            raise BuildingExposureError("frequency_threshold applies only to change-frequency products")
        assets = manifest["assets"]
        if "changeMask" not in assets or "changeGeometry" not in assets:
            raise BuildingExposureError(f"{product} must include changeMask and changeGeometry assets")
        mask, grid = _read_grid_raster(manifest, "changeMask")
        valid = np.isfinite(mask)
        if not np.isin(mask[valid], (0, 1)).all():
            raise BuildingExposureError("changeMask must contain only 0/1 values with nodata distinct from dry")
        _validate_change_geometry(core.asset_path(manifest, "changeGeometry"))
        supported = valid
        detected = valid & (mask == 1)
    else:
        if frequency_threshold is None:
            raise BuildingExposureError("change-frequency requires an explicit frequency_threshold in [0, 1]")
        if isinstance(frequency_threshold, bool):
            raise BuildingExposureError("frequency_threshold must be finite and in [0, 1]")
        try:
            threshold = float(frequency_threshold)
        except (TypeError, ValueError) as exc:
            raise BuildingExposureError("frequency_threshold must be finite and in [0, 1]") from exc
        if not math.isfinite(threshold) or not 0 <= threshold <= 1:
            raise BuildingExposureError("frequency_threshold must be finite and in [0, 1]")
        frequency, frequency_grid = _read_grid_raster(manifest, "frequency")
        detection_count, detection_grid = _read_grid_raster(manifest, "detectionCount")
        comparison_count, comparison_grid = _read_grid_raster(manifest, "validComparisonCount")
        try:
            core.same_grid(frequency_grid, detection_grid)
            core.same_grid(frequency_grid, comparison_grid)
        except ValueError as exc:
            raise BuildingExposureError(f"change-frequency asset grids differ: {exc}") from exc
        if np.any(np.isfinite(detection_count) != np.isfinite(comparison_count)):
            raise BuildingExposureError("detectionCount and validComparisonCount must share the same nodata support")
        minimum_observations = manifest.get("minimumObservations")
        if isinstance(minimum_observations, bool) or not isinstance(minimum_observations, (int, np.integer)) or minimum_observations < 1:
            raise BuildingExposureError("change-frequency manifest must declare a positive integer minimumObservations")
        finite_counts = np.isfinite(detection_count) & np.isfinite(comparison_count)
        if np.any(detection_count[finite_counts] < 0) or np.any(comparison_count[finite_counts] < 0):
            raise BuildingExposureError("Frequency count rasters cannot contain negative counts")
        if np.any(np.abs(detection_count[finite_counts] - np.rint(detection_count[finite_counts])) > 1e-6) or np.any(
            np.abs(comparison_count[finite_counts] - np.rint(comparison_count[finite_counts])) > 1e-6
        ):
            raise BuildingExposureError("Frequency count rasters must contain integer comparison counts")
        valid_counts = finite_counts & (comparison_count > 0)
        if np.any(detection_count[valid_counts] > comparison_count[valid_counts]):
            raise BuildingExposureError("detectionCount cannot exceed validComparisonCount")
        expected_frequency_support = valid_counts & (comparison_count >= int(minimum_observations))
        if np.any(np.isfinite(frequency) != expected_frequency_support):
            raise BuildingExposureError("frequency nodata support does not match validComparisonCount and minimumObservations")
        valid = np.isfinite(frequency) & valid_counts
        if np.any(valid & ((frequency < 0) | (frequency > 1))):
            raise BuildingExposureError("frequency raster values must be fractions in [0, 1]")
        expected_frequency = detection_count[valid] / comparison_count[valid]
        if not np.allclose(frequency[valid], expected_frequency, rtol=1e-6, atol=1e-7):
            raise BuildingExposureError("frequency values must equal detectionCount / validComparisonCount")
        # The count rasters are the support definition. A nodata or zero
        # denominator cannot be reinterpreted as a valid dry observation.
        supported = valid
        detected = supported & (frequency >= threshold)
        grid = frequency_grid

    return supported, detected, grid, int(np.count_nonzero(detected))


def _validate_change_geometry(path: Path) -> None:
    try:
        collection = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BuildingExposureError(f"Cannot read changeGeometry GeoJSON: {exc}") from exc
    if not isinstance(collection, dict) or collection.get("type") not in {"FeatureCollection", "Feature", "Polygon", "MultiPolygon"}:
        raise BuildingExposureError("changeGeometry must be a GeoJSON FeatureCollection, Feature or polygon")


def _metric_crs(source_value: Any, grid: Mapping[str, Any] | None = None) -> CRS:
    try:
        source = CRS.from_user_input(source_value)
    except (TypeError, ValueError) as exc:
        raise BuildingExposureError("Hazard raster grid has an invalid CRS") from exc
    if source.is_projected:
        factors = [axis.unit_conversion_factor for axis in source.axis_info[:2]]
        if len(factors) >= 2 and all(factor is not None and math.isclose(float(factor), 1.0, rel_tol=0, abs_tol=1e-9) for factor in factors):
            return source
    try:
        geographic = source.geodetic_crs or CRS.from_epsg(4326)
        if grid is not None:
            from affine import Affine

            transform = Affine(*grid["transform"])
            center_x, center_y = transform * (float(grid["width"]) / 2.0, float(grid["height"]) / 2.0)
        else:
            center_x = center_y = 0.0
        to_geographic = Transformer.from_crs(source, geographic, always_xy=True)
        # Use the raster center for UTM zone selection so geographic grids are
        # not accidentally assigned to the zone containing (0, 0).
        lon, lat = to_geographic.transform(center_x, center_y)
        if not math.isfinite(lon) or not math.isfinite(lat) or not -80 <= lat <= 84:
            raise ValueError("not inside UTM latitude limits")
        zone = max(1, min(60, int((lon + 180) // 6) + 1))
        epsg = (32600 if lat >= 0 else 32700) + zone
        return CRS.from_epsg(epsg)
    except Exception as exc:
        raise BuildingExposureError("Cannot choose a metric analysis CRS for this hazard grid") from exc


def _geojson_crs(collection: Mapping[str, Any], explicit: Any = None) -> CRS:
    value = explicit
    if value is None:
        crs = collection.get("crs")
        if isinstance(crs, Mapping):
            props = crs.get("properties", {})
            if isinstance(props, Mapping):
                value = props.get("name")
        elif isinstance(crs, str):
            value = crs
    if value is None:
        value = "EPSG:4326"
    try:
        return CRS.from_user_input(value)
    except (TypeError, ValueError) as exc:
        raise BuildingExposureError(f"Invalid GeoJSON CRS {value!r}") from exc


def _polygonal_geometry(geometry: Any, label: str):
    if not isinstance(geometry, Mapping):
        raise BuildingExposureError(f"{label} must be a GeoJSON polygon geometry")
    try:
        parsed = shape(geometry)
    except Exception as exc:
        raise BuildingExposureError(f"Invalid {label}: {exc}") from exc
    if parsed.geom_type not in {"Polygon", "MultiPolygon"} or parsed.is_empty:
        raise BuildingExposureError(f"{label} must be a nonempty Polygon or MultiPolygon")
    if not parsed.is_valid:
        parsed = make_valid(parsed)
    if parsed.geom_type == "GeometryCollection":
        parts = [part for part in parsed.geoms if part.geom_type in {"Polygon", "MultiPolygon"} and not part.is_empty]
        parsed = unary_union(parts) if parts else GeometryCollection()
    if parsed.is_empty or parsed.area <= 0 or parsed.geom_type not in {"Polygon", "MultiPolygon"}:
        raise BuildingExposureError(f"{label} has no valid positive-area polygon geometry")
    return parsed


def _transform_shape(geometry: Any, source: CRS, target: CRS):
    if source == target:
        return geometry
    try:
        transformer = Transformer.from_crs(source, target, always_xy=True)
        result = transform_geometry(transformer.transform, geometry)
    except Exception as exc:
        raise BuildingExposureError(f"Cannot transform geometry from {source.to_string()} to {target.to_string()}") from exc
    if result.is_empty or not result.is_valid:
        result = make_valid(result)
    if result.is_empty:
        raise BuildingExposureError("Coordinate transformation produced an empty polygon")
    return result


def _coverage_geometry(config: Mapping[str, Any], target_crs: CRS) -> tuple[Any, CRS, dict[str, Any], str]:
    coverage = config.get("coverage")
    if not isinstance(coverage, Mapping):
        raise BuildingExposureError("Snapshot config coverage must declare geometry and crs")
    raw_geometry = coverage.get("geometry")
    if isinstance(raw_geometry, Mapping) and raw_geometry.get("type") == "Feature":
        raw_geometry = raw_geometry.get("geometry")
    elif isinstance(raw_geometry, Mapping) and raw_geometry.get("type") == "FeatureCollection":
        features = raw_geometry.get("features")
        if not isinstance(features, list):
            raise BuildingExposureError("Snapshot coverage FeatureCollection must contain a features list")
        if not features or any(not isinstance(feature, Mapping) for feature in features):
            raise BuildingExposureError("Snapshot coverage FeatureCollection must contain polygon features")
        geometries = [_polygonal_geometry(feature.get("geometry"), "snapshot coverage feature") for feature in features]
        raw_geometry = mapping(unary_union(geometries)) if geometries else None
    if not isinstance(raw_geometry, Mapping):
        raise BuildingExposureError("Snapshot config must provide an explicit coverage polygon geometry")
    coverage_geometry = _polygonal_geometry(raw_geometry, "snapshot coverage geometry")
    coverage_crs_value = coverage.get("crs")
    if not coverage_crs_value:
        raise BuildingExposureError("Snapshot coverage CRS is required; it is never inferred")
    try:
        coverage_crs = CRS.from_user_input(coverage_crs_value)
    except (TypeError, ValueError) as exc:
        raise BuildingExposureError("Snapshot coverage CRS is invalid") from exc
    completeness = coverage.get("completeness", "unknown")
    if completeness not in {"complete", "partial", "unknown"}:
        raise BuildingExposureError("coverage.completeness must be complete, partial or unknown")
    return _transform_shape(coverage_geometry, coverage_crs, target_crs), coverage_crs, dict(raw_geometry), str(completeness)


def _snapshot_inputs(path_value: str | Path, event: str, target_crs: CRS):
    config_path = Path(path_value).expanduser().resolve()
    if not config_path.is_file():
        raise BuildingExposureError(f"Snapshot config does not exist: {config_path}")
    config = _read_json(config_path, "Snapshot config")
    if str(config.get("schemaVersion", "1.0")) != "1.0":
        raise BuildingExposureError("Unsupported snapshot config schemaVersion")
    if "event" in config and config["event"] != event:
        raise BuildingExposureError("Snapshot event does not match requested event")
    if config.get("dataKind") not in DATA_KINDS:
        raise BuildingExposureError("Snapshot config must explicitly declare a supported dataKind")
    source_date = _date_text(config.get("sourceDate"), "Snapshot sourceDate")
    provenance = config.get("source", config.get("provenance"))
    if not isinstance(provenance, (str, dict)) or not provenance:
        raise BuildingExposureError("Snapshot config must provide a nonempty source or provenance record")
    if isinstance(provenance, str) and not provenance.strip():
        raise BuildingExposureError("Snapshot source must be a nonempty string")
    raw_path = config.get("geojsonPath")
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise BuildingExposureError("Snapshot config geojsonPath must name a local GeoJSON file")
    geojson_path = Path(raw_path).expanduser()
    if not geojson_path.is_absolute():
        geojson_path = (config_path.parent / geojson_path).resolve()
    if not geojson_path.is_file():
        raise BuildingExposureError(f"Snapshot GeoJSON does not exist: {geojson_path}")
    expected_hash = config.get("sha256")
    if not isinstance(expected_hash, str) or len(expected_hash) != 64:
        raise BuildingExposureError("Snapshot config sha256 must contain a SHA-256 digest")
    try:
        int(expected_hash, 16)
    except ValueError as exc:
        raise BuildingExposureError("Snapshot config sha256 must contain a SHA-256 digest") from exc
    actual_hash = core.digest(geojson_path)
    if actual_hash.lower() != expected_hash.lower():
        raise BuildingExposureError("Snapshot GeoJSON hash mismatch")
    try:
        collection = json.loads(geojson_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BuildingExposureError(f"Cannot read OSM snapshot GeoJSON: {exc}") from exc
    if not isinstance(collection, Mapping) or collection.get("type") != "FeatureCollection" or not isinstance(collection.get("features"), list):
        raise BuildingExposureError("OSM snapshot must be a GeoJSON FeatureCollection")
    source_crs = _geojson_crs(collection, config.get("geojsonCrs"))
    coverage, coverage_crs, coverage_json, completeness = _coverage_geometry(config, target_crs)
    footprints = _read_footprints(collection, source_crs, target_crs)
    if "event" in collection and collection.get("event") != event:
        raise BuildingExposureError("OSM snapshot GeoJSON event does not match requested event")
    return {
        "configPath": config_path,
        "config": config,
        "geojsonPath": geojson_path,
        "geojsonHash": actual_hash,
        "sourceDate": source_date,
        "dataKind": config["dataKind"],
        "provenance": provenance,
        "sourceCrs": source_crs,
        "coverage": coverage,
        "coverageCrs": coverage_crs,
        "coverageJson": coverage_json,
        "completeness": completeness,
        "footprints": footprints,
    }


def _feature_osm_id(properties: Mapping[str, Any], index: int) -> str:
    osm_type = next((properties[key] for key in ("osmType", "osm_type", "type") if properties.get(key) is not None), None)
    osm_id = next((properties[key] for key in ("osmId", "osm_id", "id") if properties.get(key) is not None), None)
    if not isinstance(osm_type, str) or osm_type.strip().lower() not in OSM_TYPES:
        raise BuildingExposureError(f"OSM feature {index} must declare properties.osmType/osm_type/type as node, way or relation")
    if isinstance(osm_id, bool) or not isinstance(osm_id, (str, int)) or not str(osm_id).strip():
        raise BuildingExposureError(f"OSM feature {index} must declare properties.osmId/osm_id/id")
    identifier = str(osm_id).strip()
    if not identifier.isdecimal() or int(identifier) <= 0:
        raise BuildingExposureError(f"OSM feature {index} OSM identifier must be a positive integer")
    return f"{osm_type.strip().lower()}/{int(identifier)}"


def _read_footprints(collection: Mapping[str, Any], source_crs: CRS, target_crs: CRS) -> dict[str, Any]:
    geometries: dict[str, list[Any]] = {}
    for index, feature in enumerate(collection["features"]):
        if not isinstance(feature, Mapping) or feature.get("type") != "Feature":
            raise BuildingExposureError(f"OSM snapshot feature {index} is not a GeoJSON Feature")
        properties = feature.get("properties")
        if not isinstance(properties, Mapping):
            raise BuildingExposureError(f"OSM feature {index} must contain properties")
        osm_id = _feature_osm_id(properties, index)
        parsed = _polygonal_geometry(feature.get("geometry"), f"OSM feature {index} geometry")
        metric = _transform_shape(parsed, source_crs, target_crs)
        geometries.setdefault(osm_id, []).append(metric)
    return {osm_id: unary_union(parts) for osm_id, parts in geometries.items()}


def _region_geometries(path_value: str | Path | None, target_crs: CRS, fallback: Any) -> list[dict[str, Any]]:
    if path_value is None:
        return [{"regionId": "whole-event", "geometry": fallback}]
    path = Path(path_value).expanduser().resolve()
    if not path.is_file():
        raise BuildingExposureError(f"Region GeoJSON does not exist: {path}")
    try:
        collection = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BuildingExposureError(f"Cannot read region GeoJSON {path}: {exc}") from exc
    if not isinstance(collection, Mapping) or collection.get("type") != "FeatureCollection" or not isinstance(collection.get("features"), list):
        raise BuildingExposureError("Region GeoJSON must be a FeatureCollection")
    source_crs = _geojson_crs(collection)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, feature in enumerate(collection["features"]):
        if not isinstance(feature, Mapping) or feature.get("type") != "Feature" or not isinstance(feature.get("properties"), Mapping):
            raise BuildingExposureError(f"Region feature {index} needs properties and polygon geometry")
        region_id = feature["properties"].get("regionId")
        if not isinstance(region_id, str) or not region_id.strip() or region_id in seen:
            raise BuildingExposureError("Region features need unique nonempty properties.regionId values")
        seen.add(region_id)
        geometry = _polygonal_geometry(feature.get("geometry"), f"region {region_id!r}")
        rows.append({"regionId": region_id, "geometry": _transform_shape(geometry, source_crs, target_crs)})
    if not rows:
        raise BuildingExposureError("Region GeoJSON must contain at least one polygon")
    return rows


def _raster_geometry(mask: np.ndarray, grid: Mapping[str, Any], target_crs: CRS):
    """Polygonize a boolean cell mask and transform it to the analysis CRS."""
    from affine import Affine

    transform = Affine(*grid["transform"])
    parts = [shape(geometry) for geometry, value in shapes(mask.astype("uint8"), mask=mask, transform=transform) if int(value) == 1]
    if not parts:
        return GeometryCollection()
    source_crs = CRS.from_user_input(grid["crs"])
    return _transform_shape(unary_union(parts), source_crs, target_crs)


def _coverage_summary(region: Any, valid: Any, snapshot: Any, completeness: str) -> tuple[dict[str, Any], dict[str, Any], Any, Any]:
    region_area = float(region.area)
    valid_scope = region.intersection(valid)
    valid_area = float(valid_scope.area)
    snapshot_scope = valid_scope.intersection(snapshot)
    snapshot_area = float(snapshot_scope.area)
    valid_percent = 100.0 * valid_area / region_area if region_area > 0 else None
    snapshot_percent = 100.0 * snapshot_area / valid_area if valid_area > 0 else None
    hazard_coverage = {
        "regionAreaKm2": region_area / 1_000_000.0,
        "validAreaKm2": valid_area / 1_000_000.0,
        "validPercentOfRegion": valid_percent,
    }
    snapshot_coverage = {
        "coveredValidAreaKm2": snapshot_area / 1_000_000.0,
        "percentOfValidHazardArea": snapshot_percent,
        "completeness": completeness,
    }
    return hazard_coverage, snapshot_coverage, valid_scope, snapshot_scope


def _region_result(
    region_id: str,
    region: Any,
    valid: Any,
    detections: Any,
    snapshot_coverage: Any,
    footprints: Mapping[str, Any],
    snapshot_completeness: str,
) -> dict[str, Any]:
    hazard_coverage, snapshot_coverage_stats, valid_scope, _ = _coverage_summary(
        region, valid, snapshot_coverage, snapshot_completeness
    )
    valid_area = float(valid_scope.area)
    if valid_area <= AREA_TOLERANCE_M2:
        return {
            "regionId": region_id,
            "mappedHazardOverlapCount": None,
            "partialMappedHazardOverlapCount": None,
            "countStatus": "unavailable",
            "countReason": "No valid hazard raster support overlaps this region; zero cannot be inferred.",
            "uniqueOsmIds": [],
            "validHazardCoverage": hazard_coverage,
            "snapshotCoverage": snapshot_coverage_stats,
        }
    detection_scope = detections.intersection(valid_scope)
    mapped_scope = detection_scope.intersection(snapshot_coverage)
    identifiers: list[str] = []
    for osm_id, footprint in footprints.items():
        if not footprint.intersects(mapped_scope):
            continue
        overlap_area = float(footprint.intersection(mapped_scope).area)
        if overlap_area > AREA_TOLERANCE_M2:
            identifiers.append(osm_id)
    identifiers.sort()
    uncovered_area = float(valid_scope.difference(snapshot_coverage).area)
    unsupported_hazard_area = float(region.difference(valid).area)
    tolerance = max(AREA_TOLERANCE_M2, valid_area * 1e-10)
    spatially_covered = uncovered_area <= tolerance
    hazard_support_complete = unsupported_hazard_area <= max(AREA_TOLERANCE_M2, region.area * 1e-10)
    complete = snapshot_completeness == "complete" and spatially_covered and hazard_support_complete
    reasons: list[str] = []
    if snapshot_completeness != "complete":
        reasons.append(f"Snapshot completeness is {snapshot_completeness}; count covers mapped overlaps within supplied snapshot only.")
    if not spatially_covered:
        reasons.append("Snapshot coverage does not cover all valid hazard support in this region.")
    if not hazard_support_complete:
        reasons.append("Hazard raster support does not cover all of this selected region.")
    reason = None if complete else " ".join(reasons)
    return {
        "regionId": region_id,
        "mappedHazardOverlapCount": len(identifiers) if complete else None,
        "partialMappedHazardOverlapCount": len(identifiers),
        "countStatus": "complete" if complete else "partial",
        "countReason": reason,
        "uniqueOsmIds": identifiers,
        "validHazardCoverage": hazard_coverage,
        "snapshotCoverage": snapshot_coverage_stats,
    }


def _metrics_from_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {key: row[key] for key in (
        "regionId", "mappedHazardOverlapCount", "partialMappedHazardOverlapCount",
        "countStatus", "countReason", "validHazardCoverage", "snapshotCoverage",
    )}


def _lineage(manifest: Mapping[str, Any], hazard_path: Path, hazard_sources: list[str], snapshot: Mapping[str, Any], regions_path: Path | None):
    source_runs: list[str] = []
    for value in [manifest["runId"], *hazard_sources]:
        if value not in source_runs:
            source_runs.append(value)
    synthetic_sources: list[dict[str, Any]] = []
    if manifest.get("dataKind") == "synthetic" or manifest.get("syntheticLineage"):
        synthetic_sources.append({"product": manifest.get("product"), "runId": manifest.get("runId"), "dataKind": manifest.get("dataKind")})
    if snapshot.get("dataKind") == "synthetic" or snapshot["config"].get("syntheticLineage"):
        synthetic_sources.append({"source": "OSM snapshot", "sourceDate": snapshot["sourceDate"], "dataKind": snapshot.get("dataKind")})
    hashes: dict[str, Any] = {
        "hazardManifest": core.digest(hazard_path),
        "hazardAssets": {key: item["sha256"] for key, item in manifest["assets"].items()},
        "snapshotGeoJSON": snapshot["geojsonHash"],
        "snapshotConfig": core.digest(snapshot["configPath"]),
    }
    if regions_path is not None:
        hashes["regionsGeoJSON"] = core.digest(regions_path)
    return source_runs, synthetic_sources, hashes


def _report_metadata(
    event: str,
    manifest: Mapping[str, Any],
    hazard_path: Path,
    hazard_sources: list[str],
    snapshot: Mapping[str, Any],
    regions_path: Path | None,
    analysis_crs: CRS,
    supported: np.ndarray,
    detected: np.ndarray,
    rows: list[dict[str, Any]],
    combined: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_runs, synthetic_sources, source_hashes = _lineage(manifest, hazard_path, hazard_sources, snapshot, regions_path)
    scope = {
        "kind": "registered-regions" if regions_path else "whole-event-valid-hazard-support",
        "regionIds": [row["regionId"] for row in rows],
    }
    report = {
        "schemaVersion": "1.0",
        "event": event,
        "product": PRODUCT,
        "hazardEvent": event,
        "hazardProduct": manifest["product"],
        "hazardRunId": manifest["runId"],
        "hazardSourceRunIds": hazard_sources,
        "snapshotDate": snapshot["sourceDate"],
        "snapshotDataKind": snapshot["dataKind"],
        "snapshotSource": snapshot["provenance"],
        "snapshotSha256": snapshot["geojsonHash"],
        "snapshotCoverage": {
            "geometry": snapshot["coverageJson"],
            "crs": snapshot["coverageCrs"].to_string(),
            "completeness": snapshot["completeness"],
        },
        "analysisCrs": analysis_crs.to_string(),
        "scope": scope,
        "hazardSupport": {
            "validPixelCount": int(np.count_nonzero(supported)),
            "detectionPixelCount": int(np.count_nonzero(detected)),
            "totalRasterPixelCount": int(supported.size),
        },
        "regions": rows,
        "combined": combined,
        "interpretation": "Mapped building footprint overlap with detected hazard cells indicates exposure context only; it does not establish damage, occupancy or causation.",
        "limitations": [
            "Counts represent unique mapped OSM footprints in the supplied snapshot.",
            "Coverage and completeness are explicit; missing snapshot coverage does not imply zero buildings.",
            "Positive-area polygon intersections are counted; boundary-only contact is excluded.",
        ],
    }
    data_kind = "synthetic" if synthetic_sources else "derived"
    metadata = {
        "dataKind": data_kind,
        "syntheticLineage": synthetic_sources,
        "sourceDataKinds": [manifest["dataKind"], snapshot["dataKind"]],
        "sourceRunIds": source_runs,
        "hazardEvent": event,
        "hazardProduct": manifest["product"],
        "hazardRunId": manifest["runId"],
        "snapshotDate": snapshot["sourceDate"],
        "snapshotDataKind": snapshot["dataKind"],
        "snapshotSource": snapshot["provenance"],
        "snapshotCoverage": report["snapshotCoverage"],
        "scope": scope,
        "sourceHashes": source_hashes,
        "analysisCrs": analysis_crs.to_string(),
        "regionalMetrics": [_metrics_from_row(row) for row in rows],
        "combinedMetrics": _metrics_from_row(combined),
        "interpretation": report["interpretation"],
        "algorithmVersion": "building-footprint-hazard-overlap-1.0",
    }
    return report, metadata


def build_exposure(
    event: str,
    hazard_manifest_path: str | Path,
    snapshot_config_path: str | Path,
    output_root: str | Path | None = None,
    regions_path: str | Path | None = None,
    frequency_threshold: float | None = None,
) -> Path:
    """Publish a hash-bound OSM building/hazard overlap report.

    For ``change-frequency`` inputs, pass ``frequency_threshold`` explicitly
    as a fraction in ``[0, 1]``. Static masks use their exact valid 1 cells;
    finite 0 values remain supported dry cells, and nodata remains unsupported.
    """
    event_id = str(event)
    try:
        core.safe_name(event_id)
    except ValueError as exc:
        raise BuildingExposureError(f"Invalid event identifier: {exc}") from exc
    hazard, hazard_path, hazard_sources = _load_hazard(hazard_manifest_path, event_id)
    supported, detected, grid, detection_pixel_count = _read_hazard_arrays(hazard, frequency_threshold)
    declared_grid = hazard.get("grid")
    if not isinstance(declared_grid, Mapping):
        raise BuildingExposureError("Hazard manifest must declare its raster grid")
    try:
        core.same_grid(grid, declared_grid)
    except (KeyError, TypeError, ValueError) as exc:
        raise BuildingExposureError(f"Hazard raster does not match its declared grid: {exc}") from exc
    analysis_crs = _metric_crs(grid["crs"], grid)
    snapshot = _snapshot_inputs(snapshot_config_path, event_id, analysis_crs)

    valid_geometry = _raster_geometry(supported, grid, analysis_crs)
    detection_geometry = _raster_geometry(detected, grid, analysis_crs)
    if valid_geometry.is_empty:
        raise BuildingExposureError("Hazard has no valid raster support; exposure counts cannot be inferred")

    regions = _region_geometries(regions_path, analysis_crs, valid_geometry)
    region_union = unary_union([row["geometry"] for row in regions])
    results = [
        _region_result(
            row["regionId"], row["geometry"], valid_geometry, detection_geometry,
            snapshot["coverage"], snapshot["footprints"], snapshot["completeness"],
        )
        for row in regions
    ]
    combined = _region_result(
        "combined", region_union, valid_geometry, detection_geometry,
        snapshot["coverage"], snapshot["footprints"], snapshot["completeness"],
    )
    report, metadata = _report_metadata(
        event_id, hazard, hazard_path, hazard_sources, snapshot,
        Path(regions_path).expanduser().resolve() if regions_path is not None else None,
        analysis_crs, supported, detected, results, combined,
    )
    report["threshold"] = {"kind": "frequency", "minimumFrequency": float(frequency_threshold)} if frequency_threshold is not None else None
    metadata["threshold"] = report["threshold"]
    metadata["detectionPixelCount"] = detection_pixel_count
    metadata["validHazardPixelCount"] = int(np.count_nonzero(supported))

    def writer(stage: Path) -> dict[str, str]:
        (stage / "exposure.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        return {"exposure": "exposure.json"}

    try:
        manifest_path = core.publish(event_id, PRODUCT, metadata, writer, output_root=output_root, review=False)
    except (OSError, ValueError, TypeError) as exc:
        raise BuildingExposureError(f"Cannot publish building exposure product: {exc}") from exc
    return Path(manifest_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish mapped OSM building overlap with a hash-checked hazard run.")
    parser.add_argument("event", help="registered event ID")
    parser.add_argument("--hazard-manifest", required=True, help="coherence-change, change-frequency or flood-extent manifest")
    parser.add_argument("--snapshot-config", required=True, help="JSON config for a local hash-bound OSM GeoJSON snapshot")
    parser.add_argument("--regions", help="optional FeatureCollection with unique properties.regionId polygon features")
    parser.add_argument("--frequency-threshold", type=float, help="required for change-frequency; detected where frequency >= this fraction in [0,1]")
    parser.add_argument("--output-root", help="product root (default: backend/data/output)")
    args = parser.parse_args(argv)
    try:
        path = build_exposure(
            args.event, args.hazard_manifest, args.snapshot_config,
            output_root=args.output_root, regions_path=args.regions,
            frequency_threshold=args.frequency_threshold,
        )
    except (BuildingExposureError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"Published building-exposure manifest: {path}")
    return 0


__all__ = ["BuildingExposureError", "build_exposure", "main"]
