"""Reference unwrapped phase and publish positive-away LOS displacement.

The JSON configuration is deliberately explicit. ``reference`` must contain
exactly one of ``polygonWgs84`` (a GeoJSON Polygon/MultiPolygon), ``geojson``
(a local GeoJSON file in WGS84), or ``maskRaster`` (a local raster on the exact
input grid). Optional ``minCoherence`` and ``minimumReferencePixels`` values
default to 0.3 and 5. ``correctionsToSubtract`` is a list of correction names;
each must be advertised by the input manifest as a compatible phase screen in
radians and must not already appear in ``correctionsApplied``.

``phase_to_los`` returns metres. The published ``displacementMm`` asset is the
single conversion to millimetres, after reference subtraction.
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
from pyproj import CRS, Transformer
from rasterio.features import geometry_mask
from shapely.geometry import mapping, shape
from shapely.ops import transform as transform_geometry, unary_union

from processing.p3 import core


ALGORITHM_VERSION = "phase-to-los/1.0"
_RADIAN_UNITS = {"rad", "radian", "radians"}
_METRE_UNITS = {"m", "metre", "metres", "meter", "meters"}


def phase_to_los(phase: Any, wavelength: float, sign: int | float) -> np.ndarray:
    """Convert radians of unwrapped phase to LOS displacement in metres.

    ``sign`` is the verified source convention: +1 when positive phase means
    away from the satellite, or -1 when positive phase means toward it. NaN
    values pass through and remain invalid; zero phase is a valid zero value.
    """
    if isinstance(wavelength, bool) or not isinstance(wavelength, (int, float, np.number)):
        raise ValueError("wavelength must be a finite positive number of metres")
    wavelength_value = float(wavelength)
    if not math.isfinite(wavelength_value) or wavelength_value <= 0:
        raise ValueError("wavelength must be a finite positive number of metres")
    if isinstance(sign, bool) or not isinstance(sign, (int, float, np.number)) or float(sign) not in (-1.0, 1.0):
        raise ValueError("phase-to-away sign must be exactly +1 or -1")
    phase_values = np.asarray(phase, dtype=np.float64)
    return float(sign) * wavelength_value * phase_values / (4.0 * math.pi)


def _sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise OSError(f"Cannot read {label} {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} {path} is not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return value


def _metadata(manifest: dict[str, Any]) -> dict[str, Any]:
    result = dict(manifest)
    nested = manifest.get("metadata")
    if nested is not None:
        if not isinstance(nested, dict):
            raise ValueError("Input manifest metadata must be an object")
        result.update(nested)
    return result


def _normal_unit(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.strip().lower().replace("_", " ").split())


def _phase_units(metadata: dict[str, Any]) -> None:
    units = metadata.get("units")
    if not isinstance(units, dict):
        units = {}
    phase_units = metadata.get("phaseUnits", units.get("phase"))
    normalized = _normal_unit(phase_units)
    if normalized in {"degree", "degrees", "deg"}:
        raise ValueError("Input phase is in degrees; convert and label it as radians before phase-to-LOS processing")
    if normalized not in _RADIAN_UNITS:
        raise ValueError("Input manifest must explicitly identify phase units as radians")

    wavelength_units = metadata.get("wavelengthUnits", units.get("wavelength"))
    if wavelength_units is not None and _normal_unit(wavelength_units) not in _METRE_UNITS:
        raise ValueError("Input wavelength units must be metres")


def _pair_dates(metadata: dict[str, Any]) -> list[str]:
    dates = metadata.get("acquisitionDates")
    if not isinstance(dates, list) or len(dates) != 2:
        raise ValueError("Input acquisitionDates must contain [reference, secondary]")
    normalized: list[str] = []
    for index, value in enumerate(dates):
        if not isinstance(value, str):
            raise ValueError(f"acquisitionDates[{index}] must be an ISO date string")
        try:
            parsed = date.fromisoformat(value[:10])
        except ValueError as exc:
            raise ValueError(f"acquisitionDates[{index}] must start with an ISO date") from exc
        if parsed.isoformat() != value[:10]:
            raise ValueError(f"acquisitionDates[{index}] must start with a canonical ISO date")
        normalized.append(value)
    return normalized


def _grid_from_dataset(dataset: rasterio.io.DatasetReader) -> dict[str, Any]:
    if dataset.crs is None:
        raise ValueError("Input raster has no CRS")
    return {
        "crs": dataset.crs.to_string(),
        "transform": list(dataset.transform)[:6],
        "width": dataset.width,
        "height": dataset.height,
    }


def _resolve_local_path(value: Any, base: Path, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a local file path")
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base / path
    try:
        path = path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise OSError(f"{label} does not exist: {path}") from exc
    if not path.is_file():
        raise ValueError(f"{label} must be a file: {path}")
    return path


def _extract_geometry(value: Any, label: str) -> tuple[Any, dict[str, Any]]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a GeoJSON geometry or Feature")
    if value.get("type") == "Feature":
        geometry_json = value.get("geometry")
    else:
        geometry_json = value
    if not isinstance(geometry_json, dict):
        raise ValueError(f"{label} does not contain a GeoJSON geometry")
    geometry_type = geometry_json.get("type")
    if geometry_type not in {"Polygon", "MultiPolygon"}:
        raise ValueError(f"{label} must be a Polygon or MultiPolygon")
    try:
        geometry = shape(geometry_json)
    except Exception as exc:
        raise ValueError(f"{label} is not valid GeoJSON geometry: {exc}") from exc
    if geometry.is_empty or not geometry.is_valid:
        raise ValueError(f"{label} must be a non-empty valid polygon")
    west, south, east, north = geometry.bounds
    if not (-180 <= west <= east <= 180 and -90 <= south <= north <= 90):
        raise ValueError(f"{label} coordinates must be WGS84 longitude/latitude")
    _check_wgs84_crs(value.get("crs"), label)
    return geometry, geometry_json


def _check_wgs84_crs(crs_info: Any, label: str) -> None:
    if not crs_info:
        return
    try:
        declared_value = crs_info.get("properties", {}).get("name", crs_info) if isinstance(crs_info, dict) else crs_info
        declared = CRS.from_user_input(declared_value)
    except Exception as exc:
        raise ValueError(f"{label} has an invalid CRS declaration") from exc
    if not declared.equals(CRS.from_epsg(4326)):
        raise ValueError(f"{label} must use WGS84 coordinates (EPSG:4326)")


def _reference_mask(
    config: dict[str, Any], config_path: Path, grid: dict[str, Any]
) -> tuple[np.ndarray, dict[str, Any]]:
    reference = config.get("reference")
    if not isinstance(reference, dict):
        raise ValueError("Config reference must define polygonWgs84, geojson, or maskRaster")
    selectors = [name for name in ("polygonWgs84", "geojson", "maskRaster") if name in reference]
    if len(selectors) != 1:
        raise ValueError("Config reference must define exactly one of polygonWgs84, geojson, or maskRaster")
    selector = selectors[0]
    if selector == "maskRaster":
        path = _resolve_local_path(reference[selector], config_path.parent, "Reference mask raster")
        with rasterio.open(path) as source:
            mask_grid = _grid_from_dataset(source)
            core.same_grid(grid, mask_grid)
            values = source.read(1, masked=True).astype("float64").filled(np.nan)
        mask = np.isfinite(values) & (values > 0)
        if not mask.any():
            raise ValueError("Reference mask contains no selected pixels")
        digest = _canonical_hash({"maskSha256": _sha256(path), "grid": mask_grid})
        return mask, {
            "type": "maskRaster",
            "hash": digest,
            "maskSourceSha256": _sha256(path),
            "maskGrid": mask_grid,
        }

    if selector == "polygonWgs84":
        geometry_value = reference[selector]
        geometry, geometry_json = _extract_geometry(geometry_value, "reference.polygonWgs84")
    else:
        path = _resolve_local_path(reference[selector], config_path.parent, "Reference GeoJSON")
        geojson = _read_json(path, "Reference GeoJSON")
        _check_wgs84_crs(geojson.get("crs"), "reference.geojson")
        if geojson.get("type") == "FeatureCollection":
            features = geojson.get("features")
            if not isinstance(features, list) or not features:
                raise ValueError("Reference FeatureCollection must contain at least one feature")
            geoms = []
            for index, feature in enumerate(features):
                geom, _ = _extract_geometry(feature, f"reference.geojson.features[{index}]")
                geoms.append(geom)
            geometry = unary_union(geoms)
            if geometry.geom_type not in {"Polygon", "MultiPolygon"}:
                raise ValueError("Reference FeatureCollection must resolve to polygon geometry")
            if not geometry.is_valid:
                raise ValueError("Reference GeoJSON polygons overlap or form invalid geometry")
            geometry_json = mapping(geometry)
        else:
            geometry, geometry_json = _extract_geometry(geojson, "reference.geojson")

    try:
        target_crs = CRS.from_user_input(grid["crs"])
        project = Transformer.from_crs(CRS.from_epsg(4326), target_crs, always_xy=True).transform
        projected = transform_geometry(project, geometry)
    except Exception as exc:
        raise ValueError(f"Cannot transform WGS84 reference polygon to input CRS: {exc}") from exc
    if projected.is_empty or not projected.is_valid:
        raise ValueError("Reference polygon is invalid after transformation to input CRS")
    mask = geometry_mask(
        [projected.__geo_interface__],
        out_shape=(grid["height"], grid["width"]),
        transform=rasterio.Affine(*grid["transform"]),
        all_touched=False,
        invert=True,
    )
    if not mask.any():
        raise ValueError("Reference polygon does not cover any input pixel centers")
    return mask, {"type": "polygonWgs84", "hash": _canonical_hash(geometry_json), "geometry": geometry_json}


def _correction_catalog(metadata: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = metadata.get("correctionsAvailable", [])
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        raise ValueError("Input correctionsAvailable must be a list")
    catalog: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"correctionsAvailable[{index}] must be an object")
        name = item.get("name")
        asset_key = item.get("assetKey")
        if not isinstance(name, str) or not name or not isinstance(asset_key, str) or not asset_key:
            raise ValueError(f"correctionsAvailable[{index}] must include name and assetKey")
        if name in catalog:
            raise ValueError(f"Duplicate correction name in input manifest: {name}")
        catalog[name] = item
    return catalog


def _validate_corrections(
    config: dict[str, Any], metadata: dict[str, Any], manifest: dict[str, Any]
) -> tuple[dict[str, dict[str, Any]], list[str], list[str], list[str]]:
    source_applied = metadata.get("correctionsApplied", [])
    if not isinstance(source_applied, list) or any(not isinstance(item, str) for item in source_applied):
        raise ValueError("Input correctionsApplied must be a list of correction names")
    if len(set(source_applied)) != len(source_applied):
        raise ValueError("Input correctionsApplied contains duplicate correction names")
    catalog = _correction_catalog(metadata)
    requested = config.get("correctionsToSubtract", [])
    if not isinstance(requested, list) or any(not isinstance(item, str) or not item for item in requested):
        raise ValueError("Config correctionsToSubtract must be a list of correction names")
    if len(set(requested)) != len(requested):
        raise ValueError("Config correctionsToSubtract contains duplicate names")
    selected: dict[str, dict[str, Any]] = {}
    for name in requested:
        if name in source_applied:
            raise ValueError(f"Correction {name!r} is already applied in the source; refusing double application")
        if name not in catalog:
            raise ValueError(f"Configured correction {name!r} is not advertised by the input manifest")
        item = catalog[name]
        if _normal_unit(item.get("units")) not in _RADIAN_UNITS:
            raise ValueError(f"Correction {name!r} must be a verified phase screen in radians")
        applies_to = str(item.get("appliesTo", "")).strip().lower()
        if applies_to != "phase":
            raise ValueError(f"Correction {name!r} is not declared as a phase correction")
        convention = str(item.get("signConvention", "")).strip().lower().replace("-", "_")
        if convention not in {
            "same_as_phase", "phase_contribution", "positive_phase_contribution", "opposite_phase"
        }:
            raise ValueError(f"Correction {name!r} has no compatible phase-screen sign convention")
        asset_key = item["assetKey"]
        if asset_key not in manifest.get("assets", {}):
            raise ValueError(f"Correction {name!r} references missing asset {asset_key!r}")
        selected[name] = item

    subtracted = list(selected)
    final_applied = list(source_applied)
    final_applied.extend(name for name in subtracted if name not in final_applied)
    unapplied = [name for name in catalog if name not in final_applied]
    return selected, source_applied, final_applied, unapplied


def convert(
    event: str,
    manifest_path: str | Path,
    config_path: str | Path,
    output_root: str | Path | None = None,
) -> Path:
    """Convert one normalized GUNW phase pair into a referenced LOS product.

    The input manifest must contain hashed ``phase`` and ``coherence`` assets,
    and explicit wavelength, sign, radians, pair dates, grid and correction
    state. A connected-component asset is used when supplied; a tied dominant
    component in the reference area is rejected. If component labels are not
    supplied, the conversion is published with a warning that ambiguity could
    not be assessed. The configured reference is hashed into a spatial
    reference ID so downstream pairs can check that their reference matches.
    """
    input_path = Path(manifest_path).expanduser().resolve(strict=True)
    config_file = Path(config_path).expanduser().resolve(strict=True)
    manifest = core.load_manifest(input_path)
    if manifest.get("event") != event:
        raise ValueError(f"Input event must be {event!r}; received {manifest.get('event')!r}")
    if manifest.get("product") not in {"gunw", "GUNW", "nisar-gunw", None}:
        raise ValueError(f"Input product must be a normalized GUNW manifest; received {manifest.get('product')!r}")
    if not {"phase", "coherence"}.issubset(manifest.get("assets", {})):
        raise ValueError("Input manifest must contain phase and coherence assets")
    metadata = _metadata(manifest)
    _phase_units(metadata)
    dates = _pair_dates(metadata)
    wavelength = metadata.get("wavelengthMetres")
    sign = metadata.get("phaseToAwaySign")
    if isinstance(wavelength, bool) or not isinstance(wavelength, (int, float, np.number)) or not math.isfinite(float(wavelength)) or float(wavelength) <= 0:
        raise ValueError("Input wavelengthMetres must be a finite positive value")
    if isinstance(sign, bool) or not isinstance(sign, (int, float, np.number)) or float(sign) not in (-1.0, 1.0):
        raise ValueError("Input phaseToAwaySign must be exactly +1 or -1")

    config = _read_json(config_file, "Phase conversion config")
    min_coherence = config.get("minCoherence", 0.3)
    minimum_reference_pixels = config.get("minimumReferencePixels", 5)
    if isinstance(min_coherence, bool) or not isinstance(min_coherence, (int, float)) or not math.isfinite(float(min_coherence)) or not 0 <= float(min_coherence) <= 1:
        raise ValueError("Config minCoherence must be between 0 and 1")
    if isinstance(minimum_reference_pixels, bool) or not isinstance(minimum_reference_pixels, int) or minimum_reference_pixels < 1:
        raise ValueError("Config minimumReferencePixels must be a positive integer")

    phase, phase_grid = core.read_raster(manifest, "phase")
    coherence, coherence_grid = core.read_raster(manifest, "coherence")
    core.same_grid(phase_grid, coherence_grid)
    declared_grid = metadata.get("grid")
    if isinstance(declared_grid, dict):
        core.same_grid(phase_grid, declared_grid)
    reference_area, reference_description = _reference_mask(config, config_file, phase_grid)

    components = None
    component_valid = None
    if "components" in manifest.get("assets", {}):
        components, component_grid = core.read_raster(manifest, "components")
        core.same_grid(phase_grid, component_grid)
        finite_labels = components[np.isfinite(components)]
        if finite_labels.size and not np.all(np.isclose(finite_labels, np.rint(finite_labels), rtol=0, atol=1e-6)):
            raise ValueError("Connected-component labels must be integer-valued")
        # GUNW component zero and negative labels are commonly background or
        # unconnected pixels. They cannot support a phase reference. Profiles
        # may additionally declare product-specific background labels.
        component_valid = np.isfinite(components) & (components > 0)
        background_values = metadata.get("componentBackgroundValues", [])
        if isinstance(background_values, (int, float)) and not isinstance(background_values, bool):
            background_values = [background_values]
        if not isinstance(background_values, list):
            raise ValueError("componentBackgroundValues must be a number or list of numbers")
        for background in background_values:
            if isinstance(background, bool) or not isinstance(background, (int, float, np.number)) or not math.isfinite(float(background)):
                raise ValueError("componentBackgroundValues must contain only finite numbers")
            component_valid &= components != float(background)
    elif manifest.get("dataKind") != "synthetic":
        raise ValueError("Real phase conversion requires connected-component labels to reject unconnected pixels")

    correction_layers, source_corrections_applied, corrections_applied, unapplied = _validate_corrections(
        config, metadata, manifest
    )
    applied_phase = phase.copy()
    source_hashes = {
        "inputManifestSha256": _sha256(input_path),
        "inputAssets": {name: details["sha256"] for name, details in manifest.get("assets", {}).items()},
        "configSha256": _sha256(config_file),
    }
    for name, item in correction_layers.items():
        correction, correction_grid = core.read_raster(manifest, item["assetKey"])
        core.same_grid(phase_grid, correction_grid)
        convention = str(item["signConvention"]).strip().lower().replace("-", "_")
        screen_sign = -1.0 if convention == "opposite_phase" else 1.0
        applied_phase = applied_phase - screen_sign * correction
        source_hashes.setdefault("correctionAssets", {})[name] = manifest["assets"][item["assetKey"]]["sha256"]

    base_valid = (
        np.isfinite(applied_phase)
        & np.isfinite(coherence)
        & (coherence >= 0)
        & (coherence <= 1)
        & (coherence >= float(min_coherence))
    )
    if components is not None:
        base_valid &= component_valid

    reference_candidates = reference_area & base_valid
    if components is None:
        reference_valid = reference_candidates
        component_value = None
        component_counts: dict[str, int] = {}
    else:
        labels, counts = np.unique(components[reference_candidates], return_counts=True)
        if labels.size == 0:
            raise ValueError("Reference area has no coherent valid pixels")
        max_count = int(counts.max())
        dominant = labels[counts == max_count]
        if dominant.size != 1:
            detail = {str(label): int(count) for label, count in zip(labels, counts)}
            raise ValueError(f"Reference is ambiguous across tied connected components: {detail}")
        component_value = float(dominant[0])
        reference_valid = reference_candidates & (components == component_value)
        component_counts = {str(label): int(count) for label, count in zip(labels, counts)}
    reference_count = int(reference_valid.sum())
    if reference_count < minimum_reference_pixels:
        raise ValueError(
            f"Reference has {reference_count} coherent pixels in its selected component; "
            f"at least {minimum_reference_pixels} are required"
        )

    reference_phase_median = float(np.median(applied_phase[reference_valid]))
    # Convert the raw pair to metres, then remove its component-local reference
    # median before the one and only metres-to-millimetres export conversion.
    displacement_metres = phase_to_los(applied_phase, float(wavelength), float(sign))
    reference_offset_metres = float(phase_to_los(reference_phase_median, float(wavelength), float(sign)))
    retained = base_valid
    if component_value is not None:
        retained &= components == component_value
    referenced_mm = (displacement_metres - reference_offset_metres) * 1000.0
    displacement_mm = np.where(retained, referenced_mm, np.nan)
    quality = np.where(retained, coherence, np.nan)
    source_coverage = np.isfinite(phase) | np.isfinite(coherence)
    valid_mask = np.where(source_coverage, retained.astype(np.float64), np.nan)

    warnings = [
        f"Correction {name!r} is available but unapplied"
        for name in unapplied
    ]
    if components is None:
        warnings.append("Connected-component labels are absent; component ambiguity could not be assessed")
    if manifest.get("dataKind") not in {"observed", "derived", "scenario", "synthetic"}:
        raise ValueError("Input manifest must state dataKind as observed, derived, scenario, or synthetic")
    synthetic_lineage = manifest.get("syntheticLineage")
    data_kind = manifest.get("dataKind")
    if synthetic_lineage:
        data_kind = "synthetic"

    geometry_hash = reference_description["hash"]
    reference_id = config.get("referenceId")
    # A supplied ID helps operators refer to a named stable region; the hash
    # remains authoritative and makes accidental ID reuse detectable.
    if reference_id is not None:
        if not isinstance(reference_id, str) or not reference_id.strip():
            raise ValueError("Config referenceId must be a non-empty string")
        spatial_reference_id = reference_id.strip()
    else:
        spatial_reference_id = f"ref-{geometry_hash[:16]}"

    component_reference = None if component_value is None else {
        "label": component_value,
        "countsInReference": component_counts,
        "dominantFraction": max(component_counts.values()) / sum(component_counts.values()),
    }
    source_upstream_ids = manifest.get("upstreamRunIds", [])
    if not isinstance(source_upstream_ids, list):
        source_upstream_ids = []
    upstream_run_ids = list(dict.fromkeys([*source_upstream_ids, *([manifest["runId"]] if manifest.get("runId") else [])]))
    provenance_keys = (
        "sensor", "frequency", "polarization", "sourceProfile", "processingVersion",
        "relativeOrbit", "flightDirection", "frame", "maturity", "orbit", "track",
        "geometryId", "sourceGeometryId", "nativeResolution", "sourceHashes",
    )
    source_provenance = {key: metadata[key] for key in provenance_keys if key in metadata}
    native_resolution_metres = metadata.get("nativeResolutionMetres")
    if native_resolution_metres is None and isinstance(metadata.get("nativeResolution"), dict):
        native_resolution = metadata["nativeResolution"]
        native_units = _normal_unit(native_resolution.get("units"))
        if native_units in _METRE_UNITS:
            if "value" in native_resolution:
                native_resolution_metres = native_resolution["value"]
            elif "x" in native_resolution and "y" in native_resolution:
                native_resolution_metres = {"x": native_resolution["x"], "y": native_resolution["y"]}
    if native_resolution_metres is not None:
        if isinstance(native_resolution_metres, dict):
            if set(native_resolution_metres) - {"x", "y"} or not {"x", "y"}.issubset(native_resolution_metres):
                raise ValueError("nativeResolutionMetres must contain both x and y values")
            for axis in ("x", "y"):
                value = native_resolution_metres[axis]
                if isinstance(value, bool) or not isinstance(value, (int, float, np.number)) or not math.isfinite(float(value)) or float(value) <= 0:
                    raise ValueError("nativeResolutionMetres x/y values must be finite and positive")
            native_resolution_metres = {axis: float(native_resolution_metres[axis]) for axis in ("x", "y")}
        else:
            if isinstance(native_resolution_metres, bool) or not isinstance(native_resolution_metres, (int, float, np.number)) or not math.isfinite(float(native_resolution_metres)) or float(native_resolution_metres) <= 0:
                raise ValueError("nativeResolutionMetres must be a finite positive value")
            native_resolution_metres = float(native_resolution_metres)
    geometry_compatibility = {
        key: metadata[key]
        for key in (
            "relativeOrbit", "flightDirection", "frame", "orbit", "track",
            "geometryId", "sourceGeometryId",
        )
        if key in metadata
    }
    if isinstance(metadata.get("geometry"), dict):
        # Keep only source-declared stable geometry identifiers, never a
        # pair-specific polygon or arbitrary provider payload.
        for key in ("id", "frame", "relativeOrbit", "flightDirection", "track"):
            if key in metadata["geometry"] and key not in geometry_compatibility:
                geometry_compatibility[key] = metadata["geometry"][key]
    source_profile_basis = metadata.get("sourceProfile")
    if isinstance(source_profile_basis, dict):
        source_profile_basis = {
            key: source_profile_basis[key]
            for key in ("id", "version", "adapter")
            if key in source_profile_basis
        }
    source_basis = {
        key: metadata[key]
        for key in (
            "sensor", "frequency", "polarization", "processingVersion",
            "relativeOrbit", "flightDirection", "frame", "maturity", "orbit", "track",
            "geometryId", "sourceGeometryId",
        )
        if key in metadata
    }
    if source_profile_basis:
        source_basis["sourceProfile"] = source_profile_basis
    source_basis.update({
        "wavelengthMetres": float(wavelength),
        "phaseToAwaySign": int(sign),
    })
    if geometry_compatibility:
        source_basis["geometry"] = geometry_compatibility
    inherited_source_hashes = source_provenance.get("sourceHashes")
    if not isinstance(inherited_source_hashes, dict):
        inherited_source_hashes = {}
    metadata_out: dict[str, Any] = {
        "dataKind": data_kind,
        "syntheticLineage": synthetic_lineage,
        "upstreamRunIds": upstream_run_ids,
        "sourceRunIds": upstream_run_ids,
        "sourceHashes": {**inherited_source_hashes, **source_hashes},
        "algorithmVersion": ALGORITHM_VERSION,
        "configSha256": source_hashes["configSha256"],
        "event": event,
        "grid": phase_grid,
        "nativeResolution": metadata.get("nativeResolution"),
        "units": {"phase": "radian", "wavelength": "metre", "displacement": "mm"},
        "displacementUnits": "mm",
        "displacementConvention": "positive_away_from_satellite",
        "wavelengthMetres": float(wavelength),
        "phaseToAwaySign": int(sign),
        "acquisitionDates": dates,
        "temporalDirection": "reference_to_secondary",
        "spatialReferenceId": spatial_reference_id,
        "spatialReferenceHash": geometry_hash,
        "sourceBasis": source_basis,
        "geometry": geometry_compatibility,
        "referenceRegion": {
            "type": reference_description["type"],
            "hash": geometry_hash,
            "geometry": reference_description.get("geometry"),
            "maskSourceSha256": reference_description.get("maskSourceSha256"),
        },
        "reference": {
            "minimumCoherence": float(min_coherence),
            "minimumPixels": minimum_reference_pixels,
            "validPixels": reference_count,
            "phaseMedianRadians": reference_phase_median,
            "displacementOffsetMetres": reference_offset_metres,
            "component": component_reference,
        },
        "correctionsApplied": corrections_applied,
        "correctionState": {
            "sourceApplied": source_corrections_applied,
            "subtractedByThisRun": list(correction_layers),
            "operations": [
                {
                    "name": name,
                    "operation": "subtract",
                    "screenSignConvention": item["signConvention"],
                }
                for name, item in correction_layers.items()
            ],
            "availableUnapplied": unapplied,
        },
        "quality": {
            "minimumCoherence": float(min_coherence),
            "validPixelCount": int(retained.sum()),
            "sourceCoveragePixelCount": int(source_coverage.sum()),
            "referenceCandidatePixelCount": int(reference_candidates.sum()),
            "referenceValidPixelCount": reference_count,
            "componentLabelsAvailable": components is not None,
            "retainedComponent": component_reference,
            "warnings": warnings,
        },
        "validCoverage": {
            "validPixelCount": int(retained.sum()),
            "sourceCoveragePixelCount": int(source_coverage.sum()),
            "fractionOfSourceCoverage": float(retained.sum() / source_coverage.sum()) if source_coverage.any() else 0.0,
        },
        "warnings": warnings,
        **{key: source_provenance[key] for key in provenance_keys if key in source_provenance and key != "sourceHashes"},
    }
    if native_resolution_metres is not None:
        metadata_out["nativeResolutionMetres"] = native_resolution_metres

    def writer(stage: Path) -> dict[str, str]:
        core.write_raster(stage / "displacement_mm.tif", displacement_mm, phase_grid)
        core.write_raster(stage / "quality.tif", quality, phase_grid)
        core.write_raster(stage / "valid_mask.tif", valid_mask, phase_grid)
        return {
            "displacementMm": "displacement_mm.tif",
            "quality": "quality.tif",
            "validMask": "valid_mask.tif",
        }

    return core.publish(
        event,
        "los-pair",
        metadata_out,
        writer,
        output_root=output_root,
        review=(data_kind == "synthetic"),
    )
