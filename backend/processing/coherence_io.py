"""Validated paired coherence extraction for the Kobe change pipeline.

This module deliberately does not use the flood helpers: their zero-as-nodata
assumption is incorrect for coherence data.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import tempfile
import uuid
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from affine import Affine
from pyproj import CRS, Transformer
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from rasterio.warp import calculate_default_transform, reproject
from rasterio.windows import Window
from shapely.geometry import Polygon, mapping
from shapely.ops import transform as transform_geometry


ROOT = Path(__file__).resolve().parents[1]
EVENTS_FILE = ROOT / "events.json"
TARGET_CRS = CRS.from_epsg(32651)
TARGET_CRS_NAME = "EPSG:32651"
CODE_VERSION = "kobe-coherence-extract/1.0"
OUTPUT_FILES = ("coh_pre.tif", "coh_co.tif", "coherence_info.json")
_WINDOW_MARGIN_PIXELS = 2


class _RollbackError(OSError):
    """Publication failed and at least one prior output could not be restored."""


def load_event(event_id: str, events_path: str | Path | None = None) -> dict[str, Any]:
    """Return a registered event without creating or modifying any folders."""
    path = Path(events_path) if events_path is not None else Path(EVENTS_FILE)
    try:
        with path.open(encoding="utf-8") as stream:
            events = json.load(stream)
    except OSError as exc:
        raise OSError(f"Cannot read event registry {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Event registry {path} is not valid JSON: {exc}") from exc
    if not isinstance(events, list):
        raise ValueError(f"Event registry {path} must contain a JSON list.")

    for event in events:
        if isinstance(event, dict) and event.get("id") == event_id:
            return dict(event)
    known = ", ".join(str(item.get("id")) for item in events if isinstance(item, dict))
    raise ValueError(f"Event '{event_id}' is not registered in {path}. Known events: {known or '(none)'}")


def _strict_date(value: Any, label: str) -> date:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be an ISO date in YYYY-MM-DD form.")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO date in YYYY-MM-DD form; received {value!r}.") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"{label} must use canonical YYYY-MM-DD form; received {value!r}.")
    return parsed


def _required_text(value: Any, label: str) -> str:
    if not isinstance(value, (str, int)) or isinstance(value, bool) or not str(value).strip():
        raise ValueError(f"{label} is required and must be a non-empty string or integer.")
    return str(value).strip()


def _normal_orbit(value: Any, label: str) -> str:
    text = _required_text(value, label)
    if not text.isdecimal() or int(text) < 1:
        raise ValueError(f"{label} must be a positive integer relative orbit; received {value!r}.")
    return str(int(text))


def _normal_direction(value: Any, label: str) -> str:
    text = _required_text(value, label).replace(" ", "").replace("-", "").replace("_", "").upper()
    aliases = {"ASC": "ASCENDING", "ASCENDING": "ASCENDING", "DESC": "DESCENDING", "DESCENDING": "DESCENDING"}
    if text not in aliases:
        raise ValueError(f"{label} must be ASCENDING or DESCENDING; received {value!r}.")
    return aliases[text]


def _normal_polarization(value: Any, label: str) -> str:
    polarization = re.sub(r"\s+", "", _required_text(value, label)).upper()
    if polarization not in {"VV", "VH", "HH", "HV"}:
        raise ValueError(f"{label} must be one Sentinel-1 polarization (VV, VH, HH, or HV); received {value!r}.")
    return polarization


def _validate_event_bbox(event: dict[str, Any], event_id: str) -> tuple[float, float, float, float]:
    raw_bbox = event.get("bbox")
    if not isinstance(raw_bbox, (list, tuple)) or len(raw_bbox) != 4:
        raise ValueError(f"Registered event '{event_id}' must define bbox as [west,south,east,north].")
    try:
        west, south, east, north = (float(value) for value in raw_bbox)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Registered event '{event_id}' has a non-numeric bbox.") from exc
    if not all(math.isfinite(v) for v in (west, south, east, north)):
        raise ValueError(f"Registered event '{event_id}' bbox values must be finite.")
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError(f"Registered event '{event_id}' bbox is invalid; expected west < east and south < north in degrees.")
    return west, south, east, north


def _validate_pair(pair_name: str, raw: Any, manifest_path: Path) -> tuple[dict[str, Any], Path]:
    if not isinstance(raw, dict):
        raise ValueError(f"Manifest field '{pair_name}' must be an object.")
    required = (
        "source", "productId", "sceneIds", "acquisitionDates", "relativeOrbit",
        "flightDirection", "polarization", "processingVersion",
    )
    missing = [key for key in required if key not in raw]
    if missing:
        raise ValueError(f"Manifest field '{pair_name}' is missing required field(s): {', '.join(missing)}.")

    pair = dict(raw)
    pair["productId"] = _required_text(raw["productId"], f"{pair_name}.productId")
    pair["processingVersion"] = _required_text(raw["processingVersion"], f"{pair_name}.processingVersion")
    pair["relativeOrbit"] = _required_text(raw["relativeOrbit"], f"{pair_name}.relativeOrbit")
    pair["flightDirection"] = _normal_direction(raw["flightDirection"], f"{pair_name}.flightDirection")
    pair["polarization"] = _normal_polarization(raw["polarization"], f"{pair_name}.polarization")

    scenes = raw["sceneIds"]
    dates = raw["acquisitionDates"]
    if not isinstance(scenes, list) or len(scenes) != 2:
        raise ValueError(f"{pair_name}.sceneIds must be an ordered array of exactly two scene IDs.")
    if not isinstance(dates, list) or len(dates) != 2:
        raise ValueError(f"{pair_name}.acquisitionDates must be an ordered array of exactly two ISO dates.")
    pair["sceneIds"] = [_required_text(scene, f"{pair_name}.sceneIds[{index}]") for index, scene in enumerate(scenes)]
    pair["acquisitionDates"] = [
        _strict_date(value, f"{pair_name}.acquisitionDates[{index}]").isoformat()
        for index, value in enumerate(dates)
    ]
    source_value = _required_text(raw["source"], f"{pair_name}.source")
    source_path = Path(source_value).expanduser()
    if not source_path.is_absolute():
        source_path = manifest_path.parent / source_path
    try:
        source_path = source_path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise OSError(f"{pair_name} source file does not exist: {source_path}") from exc
    if not source_path.is_file():
        raise ValueError(f"{pair_name} source must be a ZIP or GeoTIFF file: {source_path}")
    if source_path.suffix.lower() not in {".zip", ".tif", ".tiff"}:
        raise ValueError(f"{pair_name}.source must name a .zip, .tif, or .tiff file: {source_path}")
    pair["source"] = source_value
    return pair, source_path


def _validate_manifest(
    event_id: str, manifest_path: Path, event: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], Path, Path]:
    try:
        with manifest_path.open(encoding="utf-8") as stream:
            manifest = json.load(stream)
    except OSError as exc:
        raise OSError(f"Cannot read input manifest {manifest_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Input manifest {manifest_path} is not valid JSON: {exc}") from exc
    if not isinstance(manifest, dict):
        raise ValueError("Input manifest must contain a JSON object.")
    if manifest.get("event") != event_id:
        raise ValueError(f"Manifest event must be '{event_id}'; received {manifest.get('event')!r}.")

    window = manifest.get("eventWindow")
    if not isinstance(window, dict) or not {"start", "end"}.issubset(window):
        raise ValueError("Manifest eventWindow must contain ISO dates named 'start' and 'end'.")
    window_start = _strict_date(window["start"], "eventWindow.start")
    window_end = _strict_date(window["end"], "eventWindow.end")
    if window_start > window_end:
        raise ValueError("eventWindow.start must be on or before eventWindow.end.")

    data_kind = manifest.get("dataKind")
    if data_kind not in {"observed", "synthetic"}:
        raise ValueError("Manifest dataKind must be 'observed' or 'synthetic'.")
    if data_kind == "synthetic" and event_id != "test_event":
        raise ValueError("Synthetic coherence inputs are allowed only for the registered test_event fixture.")

    pre, pre_path = _validate_pair("pre", manifest.get("pre"), manifest_path)
    co, co_path = _validate_pair("co", manifest.get("co"), manifest_path)
    if pre_path == co_path:
        raise ValueError("pre and co must use distinct source files; identical product inputs are not allowed.")
    if pre["productId"].casefold() == co["productId"].casefold():
        raise ValueError("pre and co productId values must be different.")

    pre_dates = [date.fromisoformat(value) for value in pre["acquisitionDates"]]
    co_dates = [date.fromisoformat(value) for value in co["acquisitionDates"]]
    if not (pre_dates[0] < pre_dates[1] < co_dates[1]) or co_dates[0] != pre_dates[1]:
        raise ValueError("Pair dates must describe A < B < C, with pre [A,B] and co [B,C].")
    if pre["sceneIds"][1] != co["sceneIds"][0]:
        raise ValueError("The second pre scene ID and first co scene ID must identify the shared scene B.")
    if len({pre["sceneIds"][0], pre["sceneIds"][1], co["sceneIds"][1]}) != 3:
        raise ValueError("A, B, and C must be three distinct scene IDs.")
    if any(acq >= window_start for acq in pre_dates):
        raise ValueError("Both pre acquisitions must occur before eventWindow.start.")
    if co_dates[1] <= window_end:
        raise ValueError("The final co acquisition must occur after eventWindow.end.")

    if _normal_orbit(pre["relativeOrbit"], "pre.relativeOrbit") != _normal_orbit(co["relativeOrbit"], "co.relativeOrbit"):
        raise ValueError("pre and co relativeOrbit values must match.")
    if pre["flightDirection"] != co["flightDirection"]:
        raise ValueError("pre and co flightDirection values must match.")
    if pre["polarization"] != co["polarization"]:
        raise ValueError("pre and co polarization values must match.")
    if pre["processingVersion"].casefold() != co["processingVersion"].casefold():
        raise ValueError(
            "pre and co processingVersion values differ; stop for review before extracting comparable products."
        )

    bbox = _validate_event_bbox(event, event_id)
    if not isinstance(event.get("aoi"), str) or not event["aoi"].strip():
        raise ValueError(f"Registered event '{event_id}' must define a non-empty aoi name.")
    return manifest, pre, co, pre_path, co_path


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_member(archive: Path, member: str) -> str:
    digest = hashlib.sha256()
    with zipfile.ZipFile(archive) as zf, zf.open(member, "r") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_raster(path: Path, pair_name: str) -> tuple[str, str | None, str]:
    """Return Rasterio URI, selected ZIP member, and the selected-raster hash."""
    if path.suffix.lower() != ".zip":
        return str(path), None, _sha256_file(path)
    try:
        with zipfile.ZipFile(path) as archive:
            candidates = [
                info.filename for info in archive.infolist()
                if not info.is_dir() and info.filename.casefold().endswith("_corr.tif")
            ]
    except (OSError, zipfile.BadZipFile) as exc:
        raise ValueError(f"{pair_name} source is not a readable ZIP archive: {path}: {exc}") from exc
    if len(candidates) != 1:
        listed = ", ".join(candidates) if candidates else "(none)"
        raise ValueError(
            f"{pair_name} ZIP must contain exactly one *_corr.tif member; found {len(candidates)}: {listed}. "
            "Select a direct single-band TIFF if the archive has multiple candidate layers."
        )
    member = candidates[0]
    try:
        member_hash = _sha256_member(path, member)
    except (OSError, zipfile.BadZipFile, KeyError, RuntimeError) as exc:
        raise ValueError(f"Cannot read {pair_name} coherence member {member!r} in {path}: {exc}") from exc
    uri = f"zip://{path.as_posix()}!{member}"
    return uri, member, member_hash


def _normalized_tag_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _iso_tag_date(value: str) -> str | None:
    text = value.strip()
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        return None


def _compare_embedded_metadata(tags: dict[str, str], pair: dict[str, Any], pair_name: str) -> None:
    normalized = {_normalized_tag_key(key): str(value).strip() for key, value in tags.items()}

    def find(keys: tuple[str, ...]) -> tuple[str, str] | None:
        for key in keys:
            value = normalized.get(key)
            if value:
                return key, value
        return None

    product_tag = find(("productid", "productidentifier"))
    if product_tag and product_tag[1].casefold() != pair["productId"].casefold():
        raise ValueError(
            f"{pair_name} embedded product ID {product_tag[1]!r} conflicts with manifest productId {pair['productId']!r}."
        )

    for aliases, expected, label in (
        (("relativeorbit", "relativeorbitnumber"), _normal_orbit(pair["relativeOrbit"], f"{pair_name}.relativeOrbit"), "relativeOrbit"),
        (("flightdirection", "orbitdirection"), pair["flightDirection"], "flightDirection"),
        (("polarization", "polarisation", "polarizationmode", "polarisationmode"), pair["polarization"], "polarization"),
        (("processingversion", "softwareversion"), pair["processingVersion"].casefold(), "processingVersion"),
    ):
        tag = find(aliases)
        if not tag:
            continue
        actual = tag[1]
        if label == "relativeOrbit":
            actual = _normal_orbit(actual, f"embedded {pair_name}.{label}")
        elif label == "flightDirection":
            try:
                actual = _normal_direction(actual, f"embedded {pair_name}.{label}")
            except ValueError as exc:
                raise ValueError(f"{pair_name} embedded flightDirection metadata is invalid: {tag[1]!r}.") from exc
        elif label == "polarization":
            actual = _normal_polarization(actual, f"embedded {pair_name}.{label}")
        else:
            actual = actual.casefold()
        if actual != expected:
            raise ValueError(f"{pair_name} embedded {label} {tag[1]!r} conflicts with manifest value {pair[label]!r}.")

    expected_scenes = pair["sceneIds"]
    scene_aliases = (
        ("referenceSceneId", expected_scenes[0]),
        ("referenceScene", expected_scenes[0]),
        ("secondarySceneId", expected_scenes[1]),
        ("secondaryScene", expected_scenes[1]),
    )
    for alias, expected in scene_aliases:
        value = normalized.get(_normalized_tag_key(alias))
        if value and value.casefold() != expected.casefold():
            raise ValueError(f"{pair_name} embedded {alias} {value!r} conflicts with manifest scene ID {expected!r}.")
    scenes_tag = find(("sceneids", "inputsceneids", "sourcesceneids"))
    if scenes_tag:
        actual_scenes = [part.strip().strip("[]\"'") for part in re.split(r"[,;|]", scenes_tag[1]) if part.strip()]
        if len(actual_scenes) == 2 and [s.casefold() for s in actual_scenes] != [s.casefold() for s in expected_scenes]:
            raise ValueError(f"{pair_name} embedded sceneIds {actual_scenes!r} conflict with manifest scene IDs {expected_scenes!r}.")

    date_aliases = find(("acquisitiondates", "inputacquisitiondates", "sourceacquisitiondates"))
    if date_aliases:
        actual_dates = [_iso_tag_date(part) for part in re.split(r"[,;|]", date_aliases[1]) if part.strip()]
        expected_dates = pair["acquisitionDates"]
        if len(actual_dates) == 2 and actual_dates != expected_dates:
            raise ValueError(f"{pair_name} embedded acquisitionDates {actual_dates!r} conflict with manifest dates {expected_dates!r}.")
    for alias, expected in (("referenceAcquisitionDate", pair["acquisitionDates"][0]),
                            ("secondaryAcquisitionDate", pair["acquisitionDates"][1])):
        value = normalized.get(_normalized_tag_key(alias))
        parsed = _iso_tag_date(value) if value else None
        if parsed and parsed != expected:
            raise ValueError(f"{pair_name} embedded {alias} {parsed!r} conflicts with manifest date {expected!r}.")
    single_date = find(("acquisitiondate", "inputacquisitiondate", "sourceacquisitiondate"))
    if single_date:
        parsed = _iso_tag_date(single_date[1])
        if parsed and parsed not in pair["acquisitionDates"]:
            raise ValueError(
                f"{pair_name} embedded acquisitionDate {parsed!r} is not one of the manifest pair dates "
                f"{pair['acquisitionDates']!r}."
            )


def _densified_event_polygon(bbox: tuple[float, float, float, float]) -> Polygon:
    west, south, east, north = bbox
    segments = 100
    points: list[tuple[float, float]] = []
    for index in range(segments):
        fraction = index / segments
        points.append((west + (east - west) * fraction, south))
    for index in range(segments):
        fraction = index / segments
        points.append((east, south + (north - south) * fraction))
    for index in range(segments):
        fraction = index / segments
        points.append((east - (east - west) * fraction, north))
    for index in range(segments):
        fraction = index / segments
        points.append((west, north - (north - south) * fraction))
    transformer = Transformer.from_crs("EPSG:4326", TARGET_CRS, always_xy=True)
    projected = [transformer.transform(x, y) for x, y in points]
    polygon = Polygon(projected)
    if polygon.is_empty or not polygon.is_valid or polygon.area <= 0:
        raise ValueError("The registered event bbox could not be transformed into a valid EPSG:32651 boundary.")
    return polygon


def build_aoi_mask(
    bbox: list[float] | tuple[float, float, float, float],
    shape: tuple[int, int],
    transform: Affine,
) -> np.ndarray:
    """Build the canonical event mask on the EPSG:32651 pixel-center grid.

    Each WGS84 bbox edge is sampled at 100 equal intervals before projection.
    ``all_touched=False`` keeps only pixel centers inside that transformed
    boundary. Downstream processing should reuse this function so AOI edge
    counts agree with extraction.
    """
    if len(bbox) != 4:
        raise ValueError("bbox must contain [west,south,east,north].")
    if len(shape) != 2 or shape[0] < 1 or shape[1] < 1:
        raise ValueError("shape must be a non-empty (height,width) tuple.")
    polygon = _densified_event_polygon(tuple(float(value) for value in bbox))
    return _mask_from_polygon(polygon, shape, transform)


def _mask_from_polygon(polygon: Polygon, shape: tuple[int, int], transform: Affine) -> np.ndarray:
    return geometry_mask(
        [mapping(polygon)], out_shape=shape, transform=transform, invert=True, all_touched=False
    )


def _create_grid(aoi_polygon: Polygon, pre_native: tuple[float, float], co_native: tuple[float, float], requested: float | None):
    largest_native = max(*pre_native, *co_native)
    # Avoid turning harmless projection noise such as 30.0000000002 into 31 m.
    default_resolution = float(math.ceil(largest_native - max(1e-6, abs(largest_native) * 1e-6)))
    if default_resolution <= 0 or not math.isfinite(default_resolution):
        raise ValueError("Could not derive a positive projected source resolution.")
    if requested is not None:
        if not math.isfinite(requested) or requested <= 0:
            raise ValueError("resolution must be a finite positive number of metres.")
        if requested < default_resolution - 1e-9:
            raise ValueError(
                f"Requested resolution {requested:g} m is finer than the permitted default {default_resolution:g} m."
            )
        resolution = float(requested)
    else:
        resolution = default_resolution
    minx, miny, maxx, maxy = aoi_polygon.bounds
    left = math.floor(minx / resolution) * resolution
    bottom = math.floor(miny / resolution) * resolution
    right = math.ceil(maxx / resolution) * resolution
    top = math.ceil(maxy / resolution) * resolution
    width = int(round((right - left) / resolution))
    height = int(round((top - bottom) / resolution))
    if width < 1 or height < 1:
        raise ValueError("The event AOI produced an empty target grid.")
    transform = Affine(resolution, 0.0, left, 0.0, -resolution, top)
    inside_aoi = _mask_from_polygon(aoi_polygon, (height, width), transform)
    if not inside_aoi.any():
        raise ValueError("The event AOI contains no target pixel centers at the selected resolution.")
    return transform, width, height, resolution, inside_aoi


def _projected_resolution(src: rasterio.io.DatasetReader) -> tuple[float, float]:
    try:
        projected_transform, _, _ = calculate_default_transform(
            src.crs, TARGET_CRS, src.width, src.height,
            left=src.bounds.left, bottom=src.bounds.bottom,
            right=src.bounds.right, top=src.bounds.top,
        )
    except Exception as exc:
        raise ValueError(f"Cannot calculate the EPSG:32651 nominal resolution for {src.name}: {exc}") from exc
    xres, yres = abs(projected_transform.a), abs(projected_transform.e)
    if not all(math.isfinite(value) and value > 0 for value in (xres, yres)):
        raise ValueError(f"Source raster {src.name} has an invalid projected nominal resolution.")
    return xres, yres


def _source_window(src: rasterio.io.DatasetReader, aoi_polygon: Polygon) -> Window | None:
    back = Transformer.from_crs(TARGET_CRS, src.crs, always_xy=True)
    source_polygon = transform_geometry(back.transform, aoi_polygon)
    left, bottom, right, top = source_polygon.bounds
    try:
        floating = src.window(left, bottom, right, top)
    except Exception as exc:
        raise ValueError(f"Cannot locate the event AOI inside source raster {src.name}: {exc}") from exc
    col_start = max(0, math.floor(floating.col_off) - _WINDOW_MARGIN_PIXELS)
    row_start = max(0, math.floor(floating.row_off) - _WINDOW_MARGIN_PIXELS)
    col_end = min(src.width, math.ceil(floating.col_off + floating.width) + _WINDOW_MARGIN_PIXELS)
    row_end = min(src.height, math.ceil(floating.row_off + floating.height) + _WINDOW_MARGIN_PIXELS)
    if col_end <= col_start or row_end <= row_start:
        return None
    return Window(col_start, row_start, col_end - col_start, row_end - row_start)


def _validate_dataset(src: rasterio.io.DatasetReader, pair: dict[str, Any], pair_name: str) -> tuple[tuple[float, float], dict[str, str]]:
    if src.count != 1:
        raise ValueError(f"{pair_name} coherence GeoTIFF must contain exactly one band; found {src.count}.")
    if src.crs is None:
        raise ValueError(f"{pair_name} source raster has no CRS; georeferencing is required.")
    transform = src.transform
    coeffs = tuple(transform)
    if not all(math.isfinite(float(value)) for value in coeffs) or abs(transform.a * transform.e - transform.b * transform.d) < 1e-15:
        raise ValueError(f"{pair_name} source raster has an invalid georeferencing transform.")
    if transform.almost_equals(Affine.identity()):
        raise ValueError(f"{pair_name} source raster uses an identity transform and appears unreferenced.")
    if src.width < 1 or src.height < 1:
        raise ValueError(f"{pair_name} source raster has empty dimensions.")
    dtype = np.dtype(src.dtypes[0])
    if np.issubdtype(dtype, np.complexfloating):
        raise ValueError(f"{pair_name} source is complex-valued; provide a coherence correlation raster, not phase/SLC data.")
    if not np.issubdtype(dtype, np.number):
        raise ValueError(f"{pair_name} source band must be numeric.")
    scale = src.scales[0] if src.scales else 1.0
    offset = src.offsets[0] if src.offsets else 0.0
    if not math.isclose(float(scale), 1.0, rel_tol=0.0, abs_tol=1e-12) or not math.isclose(float(offset), 0.0, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError(
            f"{pair_name} source applies scale={scale} and offset={offset}; scaled coherence requires a documented adapter."
        )
    tags = dict(src.tags())
    tags.update(src.tags(1))
    descriptors = [src.descriptions[0] or ""]
    try:
        descriptors.append(src.units[0] or "")
    except (AttributeError, IndexError, TypeError):
        pass
    semantic_tag_keys = {
        "description", "imagedescription", "banddescription", "bandname", "datatype",
        "measurement", "producttype", "quantity", "variable", "unit", "units", "unittype",
    }
    descriptors.extend(
        str(value) for key, value in tags.items()
        if (
            _normalized_tag_key(key) in semantic_tag_keys
            or _normalized_tag_key(key).endswith("description")
            or _normalized_tag_key(key).endswith("units")
            or _normalized_tag_key(key).endswith("unittype")
        )
    )
    for descriptor in descriptors:
        lowered = descriptor.casefold()
        if re.search(r"\b(?:unwrapped\s+phase|phase|amplitude|power)\b", lowered):
            raise ValueError(
                f"{pair_name} raster band metadata declares {descriptor!r}; a coherence correlation band is required."
            )
        normalized_unit = re.sub(r"[^a-z]", "", lowered)
        if normalized_unit in {"rad", "radian", "radians", "deg", "degree", "degrees", "db", "decibel", "decibels"}:
            raise ValueError(
                f"{pair_name} raster band metadata declares units {descriptor!r}; expected unitless coherence in [0,1]."
            )
    _compare_embedded_metadata(tags, pair, pair_name)
    return _projected_resolution(src), tags


def _read_source(
    *, pair_name: str, pair: dict[str, Any], path: Path, aoi_polygon: Polygon,
) -> tuple[dict[str, Any], np.ndarray | None, np.ndarray | None, Affine | None, CRS | None, tuple[float, float]]:
    uri, member, selected_hash = _resolve_raster(path, pair_name)
    source_hash = _sha256_file(path)
    try:
        with rasterio.open(uri) as src:
            native_resolution, embedded_tags = _validate_dataset(src, pair, pair_name)
            # Verify that the band can be decoded even if the AOI lies outside it.
            src.read(1, window=Window(0, 0, min(1, src.width), min(1, src.height)))
            window = _source_window(src, aoi_polygon)
            source_grid = {
                "crs": src.crs.to_string(),
                "width": src.width,
                "height": src.height,
                "transform": [float(value) for value in tuple(src.transform)[:6]],
                "resolution": [float(src.res[0]), float(src.res[1])],
                "nodata": None if src.nodata is None else ("NaN" if math.isnan(float(src.nodata)) else float(src.nodata)),
            }
            base_metadata = {
                "source": pair["source"],
                "selectedMember": member,
                "productId": pair["productId"],
                "sceneIds": list(pair["sceneIds"]),
                "acquisitionDates": list(pair["acquisitionDates"]),
                "relativeOrbit": pair["relativeOrbit"],
                "flightDirection": pair["flightDirection"],
                "polarization": pair["polarization"],
                "processingVersion": pair["processingVersion"],
                "durationDays": (
                    date.fromisoformat(pair["acquisitionDates"][1]) - date.fromisoformat(pair["acquisitionDates"][0])
                ).days,
                "sourceSha256": source_hash,
                "selectedRasterSha256": selected_hash,
                "sourceGrid": source_grid,
                "nativeResolutionMetres": {"x": native_resolution[0], "y": native_resolution[1]},
                "embeddedMetadata": embedded_tags,
            }
            if window is None:
                return base_metadata | {
                    "readWindow": None,
                    "readWindowPixelCount": 0,
                    "readWindowValidPixelCount": 0,
                    "readWindowInvalidPixelCount": 0,
                    "readWindowMaskInvalidPixelCount": 0,
                    "readWindowNodataPixelCount": 0,
                    "readWindowNonFinitePixelCount": 0,
                    "readWindowOutOfRangePixelCount": 0,
                }, None, None, None, None, native_resolution

            raw = src.read(1, window=window)
            raster_mask = src.read_masks(1, window=window) != 0
            nodata = src.nodata
            if nodata is None or (isinstance(nodata, float) and math.isnan(nodata)):
                nodata_mask = np.zeros(raw.shape, dtype=bool)
            else:
                nodata_mask = raw == nodata
            finite_mask = np.isfinite(raw)
            range_mask = (raw >= 0) & (raw <= 1)
            if np.issubdtype(raw.dtype, np.integer) and np.any(raster_mask & ~nodata_mask & finite_mask & ~range_mask):
                raise ValueError(
                    f"{pair_name} integer coherence raster contains values outside [0,1]; "
                    "scaled integer coherence requires a documented adapter."
                )
            out_of_range = raster_mask & ~nodata_mask & finite_mask & ~range_mask
            valid = raster_mask & ~nodata_mask & finite_mask & range_mask
            data = np.full(raw.shape, np.nan, dtype=np.float32)
            data[valid] = raw[valid].astype(np.float32, copy=False)
            window_transform = src.window_transform(window)
            read_window = {
                "rowOffset": int(window.row_off), "columnOffset": int(window.col_off),
                "height": int(window.height), "width": int(window.width),
            }
            window_pixels = int(raw.size)
            stats = {
                "readWindow": read_window,
                "readWindowPixelCount": window_pixels,
                "readWindowValidPixelCount": int(valid.sum()),
                "readWindowInvalidPixelCount": int(window_pixels - valid.sum()),
                "readWindowMaskInvalidPixelCount": int((~raster_mask).sum()),
                "readWindowNodataPixelCount": int(nodata_mask.sum()),
                "readWindowNonFinitePixelCount": int((~finite_mask).sum()),
                "readWindowOutOfRangePixelCount": int(out_of_range.sum()),
            }
            return base_metadata | stats, data, valid, window_transform, src.crs, native_resolution
    except rasterio.errors.RasterioError as exc:
        raise ValueError(f"Cannot read {pair_name} coherence raster {member or path.name}: {exc}") from exc
    except zipfile.BadZipFile as exc:
        raise ValueError(f"Cannot read {pair_name} ZIP source {path}: {exc}") from exc


def _warp_coherence(
    source_data: np.ndarray | None,
    source_valid: np.ndarray | None,
    source_transform: Affine | None,
    source_crs: CRS | None,
    output_transform: Affine,
    output_crs: CRS,
    output_shape: tuple[int, int],
    aoi_mask: np.ndarray,
) -> np.ndarray:
    destination = np.full(output_shape, np.nan, dtype=np.float32)
    destination_validity = np.zeros(output_shape, dtype=np.uint8)
    if source_data is not None and source_valid is not None and source_transform is not None and source_crs is not None:
        reproject(
            source=source_data,
            destination=destination,
            src_transform=source_transform,
            src_crs=source_crs,
            src_nodata=np.nan,
            dst_transform=output_transform,
            dst_crs=output_crs,
            dst_nodata=np.nan,
            resampling=Resampling.bilinear,
            init_dest_nodata=True,
        )
        reproject(
            source=source_valid.astype(np.uint8),
            destination=destination_validity,
            src_transform=source_transform,
            src_crs=source_crs,
            src_nodata=0,
            dst_transform=output_transform,
            dst_crs=output_crs,
            dst_nodata=0,
            resampling=Resampling.nearest,
            init_dest_nodata=True,
        )
    valid = (destination_validity != 0) & np.isfinite(destination) & (destination >= 0) & (destination <= 1) & aoi_mask
    destination[~valid] = np.nan
    return destination


def _write_coherence(path: Path, array: np.ndarray, transform: Affine, event_id: str, extraction_id: str, data_kind: str) -> None:
    height, width = array.shape
    with rasterio.open(
        path, "w", driver="GTiff", width=width, height=height, count=1, dtype="float32",
        crs=TARGET_CRS, transform=transform, nodata=np.nan, compress="lzw",
    ) as dst:
        dst.write(array.astype(np.float32, copy=False), 1)
        dst.set_band_description(1, "coherence")
        dst.update_tags(extractionId=extraction_id, event=event_id, dataKind=data_kind)


def _validate_staged_raster(
    path: Path, expected_shape: tuple[int, int], transform: Affine, extraction_id: str, event_id: str, data_kind: str,
) -> None:
    try:
        with rasterio.open(path) as src:
            if src.count != 1 or src.dtypes[0] != "float32" or src.width != expected_shape[1] or src.height != expected_shape[0]:
                raise OSError(f"Staged raster {path.name} has an unexpected band count, type, or shape.")
            if src.crs != TARGET_CRS or not src.transform.almost_equals(transform) or not (isinstance(src.nodata, float) and math.isnan(src.nodata)):
                raise OSError(f"Staged raster {path.name} does not match the requested grid or NaN nodata contract.")
            if src.compression is None or src.compression.value != "LZW":
                raise OSError(f"Staged raster {path.name} is not LZW compressed.")
            if src.descriptions[0] != "coherence":
                raise OSError(f"Staged raster {path.name} has no coherence band description.")
            tags = src.tags()
            if tags.get("extractionId") != extraction_id or tags.get("event") != event_id or tags.get("dataKind") != data_kind:
                raise OSError(f"Staged raster {path.name} is missing extraction provenance tags.")
            values = src.read(1)
            finite = np.isfinite(values)
            if np.any((values[finite] < 0) | (values[finite] > 1)):
                raise OSError(f"Staged raster {path.name} contains coherence values outside [0,1].")
    except rasterio.errors.RasterioError as exc:
        raise OSError(f"Cannot validate staged raster {path}: {exc}") from exc


def _publish_staged(output_dir: Path, stage_dir: Path) -> None:
    """Replace this extractor's files as a rollback-capable, manifest-last set."""
    backup_dir = stage_dir / "previous"
    backup_dir.mkdir()
    backups: dict[str, Path] = {}
    published: list[str] = []
    try:
        for filename in OUTPUT_FILES:
            destination = output_dir / filename
            if destination.exists():
                backup = backup_dir / filename
                os.replace(destination, backup)
                backups[filename] = backup
        for filename in OUTPUT_FILES[:-1]:
            os.replace(stage_dir / filename, output_dir / filename)
            published.append(filename)
        # The manifest is the commit marker and is always made visible last.
        os.replace(stage_dir / OUTPUT_FILES[-1], output_dir / OUTPUT_FILES[-1])
        published.append(OUTPUT_FILES[-1])
    except OSError:
        for filename in reversed(published):
            try:
                (output_dir / filename).unlink(missing_ok=True)
            except OSError:
                pass
        restore_errors: list[str] = []
        for filename, backup in backups.items():
            try:
                os.replace(backup, output_dir / filename)
            except OSError as exc:
                restore_errors.append(f"{filename}: {exc}")
        if restore_errors:
            raise _RollbackError(
                "Output publication failed and rollback could not restore every prior file: "
                + "; ".join(restore_errors)
                + f". Recovery files are preserved in {backup_dir}.",
            )
        raise


def _check_output_intent_and_collisions(
    output_path: Path,
    overwrite: bool,
    protected_inputs: dict[str, Path],
) -> None:
    for filename in OUTPUT_FILES:
        destination = output_path / filename
        resolved_destination = destination.resolve(strict=False)
        for label, source in protected_inputs.items():
            if resolved_destination == source.resolve(strict=False):
                raise ValueError(
                    f"Output {destination} resolves to the {label} {source}; choose a separate output directory."
                )
            if destination.exists() and source.exists():
                try:
                    if os.path.samefile(destination, source):
                        raise ValueError(
                            f"Output {destination} is the same file as the {label} {source}; choose a separate output directory."
                        )
                except OSError:
                    # The resolved-path comparison above still protects normal paths.
                    pass
    existing = [name for name in OUTPUT_FILES if (output_path / name).exists()]
    if existing and not overwrite:
        raise FileExistsError(
            f"Refusing to replace existing coherence output(s) in {output_path}: {', '.join(existing)}. "
            "Choose another --output-dir or pass --overwrite."
        )
    non_files = [name for name in existing if not (output_path / name).is_file()]
    if non_files:
        raise OSError(f"Cannot replace non-file coherence output path(s): {', '.join(non_files)}.")


def extract_pair(
    event_id: str,
    manifest_path: str | Path,
    output_dir: str | Path | None = None,
    resolution: float | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Validate and align one pre/event coherence pair onto the event AOI grid.

    Source file paths are resolved relative to ``manifest_path``. Outputs are
    staged and validated before the manifest is published as the final marker.
    """
    event = load_event(event_id)
    path_manifest = Path(manifest_path).expanduser().resolve()
    manifest, pre, co, pre_path, co_path = _validate_manifest(event_id, path_manifest, event)
    output_path = Path(output_dir).expanduser() if output_dir is not None else ROOT / "data" / "output" / event_id
    output_path = output_path.resolve()
    _check_output_intent_and_collisions(
        output_path,
        overwrite,
        {"input manifest": path_manifest, "pre source": pre_path, "co source": co_path},
    )
    bbox = _validate_event_bbox(event, event_id)
    aoi_polygon = _densified_event_polygon(bbox)

    # Read and validate the two AOI windows first. This limits memory for large
    # geocoded products while retaining a two-pixel interpolation margin.
    pre_info, pre_data, pre_source_valid, pre_src_transform, pre_src_crs, pre_native = _read_source(
        pair_name="pre", pair=pre, path=pre_path, aoi_polygon=aoi_polygon
    )
    co_info, co_data, co_source_valid, co_src_transform, co_src_crs, co_native = _read_source(
        pair_name="co", pair=co, path=co_path, aoi_polygon=aoi_polygon
    )
    if (
        pre_info["sourceSha256"] == co_info["sourceSha256"]
        or pre_info["selectedRasterSha256"] == co_info["selectedRasterSha256"]
    ):
        raise ValueError("pre and co resolve to identical source content; distinct coherence products are required.")
    transform, width, height, selected_resolution, aoi_mask = _create_grid(
        aoi_polygon, pre_native, co_native, resolution
    )
    output_shape = (height, width)
    pre_array = _warp_coherence(
        pre_data, pre_source_valid, pre_src_transform, pre_src_crs, transform, TARGET_CRS, output_shape, aoi_mask
    )
    co_array = _warp_coherence(
        co_data, co_source_valid, co_src_transform, co_src_crs, transform, TARGET_CRS, output_shape, aoi_mask
    )
    pre_valid = np.isfinite(pre_array) & aoi_mask
    co_valid = np.isfinite(co_array) & aoi_mask
    common_valid = pre_valid & co_valid
    aoi_count = int(aoi_mask.sum())
    pre_count = int(pre_valid.sum())
    co_count = int(co_valid.sum())
    common_count = int(common_valid.sum())
    if common_count == 0:
        raise ValueError("The pre and co products have no common valid pixels inside the event AOI.")

    pair_duration_pre = (date.fromisoformat(pre["acquisitionDates"][1]) - date.fromisoformat(pre["acquisitionDates"][0])).days
    pair_duration_co = (date.fromisoformat(co["acquisitionDates"][1]) - date.fromisoformat(co["acquisitionDates"][0])).days
    warnings: list[str] = []
    if pair_duration_pre != pair_duration_co:
        warnings.append(
            f"Pair durations differ (pre {pair_duration_pre} days; co {pair_duration_co} days); compare coherence with caution."
        )
    if pre_count < aoi_count:
        warnings.append(f"Pre coherence has partial AOI coverage ({pre_count}/{aoi_count} pixel centers).")
    if co_count < aoi_count:
        warnings.append(f"Co coherence has partial AOI coverage ({co_count}/{aoi_count} pixel centers).")

    extraction_id = str(uuid.uuid4())
    data_kind = manifest["dataKind"]
    try:
        output_path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OSError(f"Cannot create output directory {output_path}: {exc}") from exc

    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    event_window = {
        "start": manifest["eventWindow"]["start"],
        "end": manifest["eventWindow"]["end"],
    }
    pre_pair = list(pre["acquisitionDates"])
    co_pair = list(co["acquisitionDates"])
    manifest_out: dict[str, Any] = {
        "schemaVersion": "1.0",
        "extractionId": extraction_id,
        "event": event_id,
        "aoi": event["aoi"],
        "bbox": list(bbox),
        "eventWindow": event_window,
        "dataKind": data_kind,
        "prePair": pre_pair,
        "coPair": co_pair,
        "preDates": pre_pair,
        "coDates": co_pair,
        "sources": {"pre": pre_info, "co": co_info},
        "grid": {
            "crs": TARGET_CRS_NAME,
            "width": width,
            "height": height,
            "transform": [float(value) for value in tuple(transform)[:6]],
            "resolutionMetres": selected_resolution,
            "nativeResolutionMetres": {
                "pre": {"x": pre_native[0], "y": pre_native[1]},
                "co": {"x": co_native[0], "y": co_native[1]},
            },
            "bounds": [transform.c, transform.f + transform.e * height,
                       transform.c + transform.a * width, transform.f],
        },
        "coverage": {
            "aoiPixelCount": aoi_count,
            "commonValidPixelCount": common_count,
            "preValidPixelCount": pre_count,
            "coValidPixelCount": co_count,
        },
        "parameters": {
            "waterMaskApplied": False,
            "coherenceRange": [0, 1],
            "continuousResampling": "bilinear",
            "validityResampling": "nearest",
            "aoiMaskUsesPixelCenters": True,
            "resolutionRequestedMetres": resolution,
            "resolutionDefaultMetres": float(
                math.ceil(max(*pre_native, *co_native) - max(1e-6, max(*pre_native, *co_native) * 1e-6))
            ),
            "sourceValidity": {
                "usesRasterMask": True,
                "honorsDeclaredNodata": True,
                "rejectsNonFinite": True,
                "acceptedRange": [0, 1],
                "zeroValidUnlessDeclaredNodata": True,
            },
        },
        "outputs": {},
        "warnings": warnings,
        "createdAt": now,
        "codeVersion": CODE_VERSION,
    }

    stage_dir = Path(tempfile.mkdtemp(prefix=".coherence-stage-", dir=output_path))
    preserve_recovery_files = False
    try:
        _write_coherence(stage_dir / "coh_pre.tif", pre_array, transform, event_id, extraction_id, data_kind)
        _write_coherence(stage_dir / "coh_co.tif", co_array, transform, event_id, extraction_id, data_kind)
        _validate_staged_raster(stage_dir / "coh_pre.tif", output_shape, transform, extraction_id, event_id, data_kind)
        _validate_staged_raster(stage_dir / "coh_co.tif", output_shape, transform, extraction_id, event_id, data_kind)
        manifest_out["outputs"] = {
            filename: {"sha256": _sha256_file(stage_dir / filename)}
            for filename in OUTPUT_FILES[:-1]
        }
        (stage_dir / OUTPUT_FILES[-1]).write_text(
            json.dumps(manifest_out, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        # Re-open the staged metadata before publication to catch serialization errors.
        with (stage_dir / OUTPUT_FILES[-1]).open(encoding="utf-8") as stream:
            staged_manifest = json.load(stream)
        if staged_manifest.get("extractionId") != extraction_id or set(staged_manifest.get("outputs", {})) != set(OUTPUT_FILES[:-1]):
            raise OSError("Staged coherence manifest failed validation.")
        try:
            _publish_staged(output_path, stage_dir)
        except _RollbackError:
            preserve_recovery_files = True
            raise
    finally:
        if not preserve_recovery_files:
            shutil.rmtree(stage_dir, ignore_errors=True)

    print(
        f"Common valid AOI coverage: {common_count}/{aoi_count} pixels; "
        f"pre: {pre_count}, co: {co_count}; native resolution: "
        f"pre {pre_native[0]:.2f}×{pre_native[1]:.2f} m, co {co_native[0]:.2f}×{co_native[1]:.2f} m; "
        f"output {selected_resolution:g} m."
    )
    for warning in warnings:
        print(f"Warning: {warning}")
    return manifest_out
