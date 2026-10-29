"""Build a coherence-decrease product from a prepared pre/event raster pair."""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.features import shapes
from scipy import ndimage
from shapely import make_valid
from shapely.geometry import GeometryCollection, mapping, shape
from shapely.ops import transform as transform_geometry
from shapely.ops import unary_union

from .coherence_io import load_event


BACKEND_DIR = Path(__file__).resolve().parents[1]
COHERENCE_FILES = ("coh_pre.tif", "coh_co.tif")
RESULT_FILES = ("change_mask.tif", "change.geojson", "06_change_check.png")
CHANGE_THRESHOLD_TOLERANCE = 1e-6
_SMOOTH_KERNEL = np.ones((3, 3), dtype=np.float64)


class ChangeMapError(ValueError):
    """An input, validation, or publication error suitable for a CLI message."""


def _validate_parameters(pre_min: float, loss_min: float, min_pixels: int, simplify: float) -> None:
    try:
        pre_min = float(pre_min)
        loss_min = float(loss_min)
        simplify = float(simplify)
    except (TypeError, ValueError) as exc:
        raise ChangeMapError("pre_min, loss_min, and simplify must be numeric values") from exc

    if not math.isfinite(pre_min) or not 0 <= pre_min <= 1:
        raise ChangeMapError("pre_min must be finite and in [0, 1]")
    if not math.isfinite(loss_min) or not 0 < loss_min <= 1:
        raise ChangeMapError("loss_min must be finite and in (0, 1]")
    if isinstance(min_pixels, bool) or not isinstance(min_pixels, (int, np.integer)) or min_pixels < 1:
        raise ChangeMapError("min_pixels must be an integer >= 1")
    if not math.isfinite(simplify) or simplify < 0:
        raise ChangeMapError("simplify must be finite and >= 0 metres")


def _compute_change_details(
    pre: np.ndarray,
    co: np.ndarray,
    valid: np.ndarray,
    pre_min: float,
    loss_min: float,
    min_pixels: int,
) -> dict[str, np.ndarray]:
    _validate_parameters(pre_min, loss_min, min_pixels, 0)
    pre_values = np.asarray(pre, dtype=np.float64)
    co_values = np.asarray(co, dtype=np.float64)
    valid_values = np.asarray(valid, dtype=bool)
    if pre_values.ndim != 2 or co_values.shape != pre_values.shape or valid_values.shape != pre_values.shape:
        raise ChangeMapError("pre, co, and valid must be same-shaped 2-D arrays")

    common_valid = (
        valid_values
        & np.isfinite(pre_values)
        & np.isfinite(co_values)
        & (pre_values >= 0)
        & (pre_values <= 1)
        & (co_values >= 0)
        & (co_values <= 1)
    )
    neighbor_count = ndimage.convolve(
        common_valid.astype(np.float64), _SMOOTH_KERNEL, mode="constant", cval=0.0
    )
    supported = common_valid & (neighbor_count >= 5)
    pre_sum = ndimage.convolve(
        np.where(common_valid, pre_values, 0.0), _SMOOTH_KERNEL, mode="constant", cval=0.0
    )
    co_sum = ndimage.convolve(
        np.where(common_valid, co_values, 0.0), _SMOOTH_KERNEL, mode="constant", cval=0.0
    )

    smoothed_pre = np.full(pre_values.shape, np.nan, dtype=np.float64)
    smoothed_co = np.full(pre_values.shape, np.nan, dtype=np.float64)
    smoothed_pre[supported] = pre_sum[supported] / neighbor_count[supported]
    smoothed_co[supported] = co_sum[supported] / neighbor_count[supported]
    loss = np.full(pre_values.shape, np.nan, dtype=np.float64)
    loss[supported] = smoothed_pre[supported] - smoothed_co[supported]

    eligible = supported & (smoothed_pre >= (float(pre_min) - CHANGE_THRESHOLD_TOLERANCE))
    raw_changed = eligible & (loss >= (float(loss_min) - CHANGE_THRESHOLD_TOLERANCE))

    labels, raw_component_count = ndimage.label(raw_changed, structure=np.ones((3, 3), dtype=np.uint8))
    if raw_component_count:
        sizes = np.bincount(labels.ravel())
        keep = sizes >= int(min_pixels)
        keep[0] = False
        changed = keep[labels]
    else:
        changed = np.zeros(pre_values.shape, dtype=bool)
    return {
        "supported": supported,
        "eligible": eligible,
        "loss": loss,
        "changed": changed,
        "rawChanged": raw_changed,
        "smoothedPre": smoothed_pre,
        "smoothedCo": smoothed_co,
    }


def compute_change(
    pre: np.ndarray,
    co: np.ndarray,
    valid: np.ndarray,
    pre_min: float = 0.5,
    loss_min: float = 0.3,
    min_pixels: int = 10,
) -> dict[str, np.ndarray]:
    """Return the mask-aware 3x3 coherence change calculation for unit tests."""
    details = _compute_change_details(pre, co, valid, pre_min, loss_min, min_pixels)
    return {key: details[key] for key in ("supported", "eligible", "loss", "changed", "rawChanged")}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _metadata_hash(outputs: Any, filename: str) -> str:
    if not isinstance(outputs, dict) or filename not in outputs:
        raise ChangeMapError(f"coherence_info.json has no output hash for {filename}")
    value = outputs[filename]
    digest = value.get("sha256") if isinstance(value, dict) else None
    if not isinstance(digest, str) or len(digest) != 64:
        raise ChangeMapError(f"coherence_info.json has an invalid SHA-256 for {filename}")
    try:
        int(digest, 16)
    except ValueError as exc:
        raise ChangeMapError(f"coherence_info.json has an invalid SHA-256 for {filename}") from exc
    return digest.lower()


def _read_coherence(path: Path, metadata: dict[str, Any], filename: str, expected_crs: CRS):
    if not path.is_file():
        raise ChangeMapError(f"Prepared coherence raster is missing: {path}")
    expected_hash = _metadata_hash(metadata.get("outputs"), filename)
    actual_hash = _sha256(path)
    if actual_hash != expected_hash:
        raise ChangeMapError(f"SHA-256 mismatch for {path.name}; rerun extraction or restore the matching raster")

    try:
        with rasterio.open(path) as src:
            if src.count != 1 or src.dtypes[0] != "float32":
                raise ChangeMapError(f"{path.name} must be a single-band float32 GeoTIFF")
            if src.nodata is None or not math.isnan(float(src.nodata)):
                raise ChangeMapError(f"{path.name} must declare NaN nodata")
            if src.crs is None or src.crs != expected_crs:
                raise ChangeMapError(f"{path.name} CRS does not match coherence_info.json grid.crs")

            grid = metadata["grid"]
            if src.width != int(grid["width"]) or src.height != int(grid["height"]):
                raise ChangeMapError(f"{path.name} dimensions do not match coherence_info.json grid")
            expected_transform = tuple(float(value) for value in grid["transform"])
            actual_transform = tuple(src.transform)[:6]
            if len(expected_transform) != 6 or not np.allclose(
                actual_transform, expected_transform, rtol=1e-10, atol=1e-8
            ):
                raise ChangeMapError(f"{path.name} affine transform does not match coherence_info.json grid")

            tags = src.tags()
            for tag_name, expected in (
                ("extractionId", metadata["extractionId"]),
                ("event", metadata["event"]),
                ("dataKind", metadata["dataKind"]),
            ):
                if tags.get(tag_name) != str(expected):
                    raise ChangeMapError(f"{path.name} tag {tag_name} does not match coherence_info.json")
            units = tags.get("units", grid.get("units"))
            if units is not None and str(units).strip().lower() not in {"1", "unitless", "dimensionless"}:
                raise ChangeMapError(f"{path.name} declares unsupported coherence units: {units}")

            values = src.read(1).astype(np.float64)
            raster_valid = src.read_masks(1) > 0
    except ChangeMapError:
        raise
    except Exception as exc:
        raise ChangeMapError(f"Cannot read prepared raster {path}: {exc}") from exc

    valid = raster_valid & np.isfinite(values) & (values >= 0) & (values <= 1)
    return values, valid


def _validate_metadata(event: dict[str, Any], input_dir: Path) -> tuple[dict[str, Any], CRS, Path, Path]:
    info_path = input_dir / "coherence_info.json"
    if not info_path.is_file():
        raise ChangeMapError(f"Missing extraction metadata: {info_path}")
    try:
        metadata = json.loads(info_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ChangeMapError(f"Cannot read {info_path}: {exc}") from exc
    if not isinstance(metadata, dict):
        raise ChangeMapError("coherence_info.json must contain a JSON object")

    required = (
        "schemaVersion", "extractionId", "event", "aoi", "bbox", "eventWindow", "dataKind",
        "prePair", "coPair", "sources", "grid", "coverage", "parameters", "outputs", "warnings",
    )
    missing = [key for key in required if key not in metadata]
    if missing:
        raise ChangeMapError("coherence_info.json is missing required fields: " + ", ".join(missing))
    if str(metadata["schemaVersion"]) != "1.0":
        raise ChangeMapError(f"Unsupported coherence metadata schemaVersion: {metadata['schemaVersion']}")
    if metadata["event"] != event["id"]:
        raise ChangeMapError(
            f"coherence_info.json event {metadata['event']!r} does not match requested event {event['id']!r}"
        )
    if metadata["aoi"] != event.get("aoi"):
        raise ChangeMapError("coherence_info.json AOI does not match the registered event")
    if metadata["dataKind"] not in {"observed", "synthetic"}:
        raise ChangeMapError("coherence_info.json dataKind must be 'observed' or 'synthetic'")
    try:
        uuid.UUID(str(metadata["extractionId"]))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ChangeMapError("coherence_info.json extractionId must be a UUID") from exc
    if not isinstance(metadata["eventWindow"], dict) or not {"start", "end"}.issubset(metadata["eventWindow"]):
        raise ChangeMapError("coherence_info.json eventWindow must contain start and end")
    window_dates = []
    for name in ("start", "end"):
        value = metadata["eventWindow"][name]
        try:
            parsed = datetime.fromisoformat(value)
        except (TypeError, ValueError) as exc:
            raise ChangeMapError(f"coherence_info.json eventWindow.{name} must be an ISO date") from exc
        if parsed.date().isoformat() != value:
            raise ChangeMapError(f"coherence_info.json eventWindow.{name} must use YYYY-MM-DD")
        window_dates.append(parsed.date())
    if window_dates[0] > window_dates[1]:
        raise ChangeMapError("coherence_info.json eventWindow.start must be on or before end")
    pair_dates = {}
    for pair_name in ("prePair", "coPair"):
        pair = metadata[pair_name]
        if not isinstance(pair, list) or len(pair) != 2 or not all(isinstance(item, str) for item in pair):
            raise ChangeMapError(f"coherence_info.json {pair_name} must contain two acquisition dates")
        parsed_pair = []
        for value in pair:
            try:
                parsed = datetime.fromisoformat(value)
            except ValueError as exc:
                raise ChangeMapError(f"coherence_info.json {pair_name} contains a non-ISO date") from exc
            if parsed.date().isoformat() != value:
                raise ChangeMapError(f"coherence_info.json {pair_name} dates must use YYYY-MM-DD")
            parsed_pair.append(parsed.date())
        pair_dates[pair_name] = parsed_pair
    if not isinstance(metadata["sources"], dict) or not isinstance(metadata["warnings"], list):
        raise ChangeMapError("coherence_info.json sources must be an object and warnings must be a list")
    source_pairs = metadata["sources"]
    for pair_name in ("pre", "co"):
        source_pair = source_pairs.get(pair_name)
        date_key = f"{pair_name}Pair"
        if not isinstance(source_pair, dict):
            raise ChangeMapError(f"coherence_info.json sources.{pair_name} must contain pair details")
        source_dates = source_pair.get("acquisitionDates")
        scene_ids = source_pair.get("sceneIds")
        if source_dates != metadata[date_key] or not isinstance(scene_ids, list) or len(scene_ids) != 2:
            raise ChangeMapError(f"coherence_info.json sources.{pair_name} pair details do not match {date_key}")
    if pair_dates["prePair"][0] >= pair_dates["prePair"][1]:
        raise ChangeMapError("coherence_info.json prePair dates must be increasing")
    if pair_dates["prePair"][1] != pair_dates["coPair"][0] or pair_dates["coPair"][0] >= pair_dates["coPair"][1]:
        raise ChangeMapError("coherence_info.json pair dates must share scene B and be ordered A < B < C")
    if pair_dates["prePair"][1] >= window_dates[0] or pair_dates["coPair"][1] <= window_dates[1]:
        raise ChangeMapError("coherence_info.json pair dates do not bracket the event window")
    if source_pairs["pre"]["sceneIds"][1] != source_pairs["co"]["sceneIds"][0]:
        raise ChangeMapError("coherence_info.json source pairs do not share scene B")

    bbox = metadata["bbox"]
    event_bbox = event.get("bbox")
    try:
        bbox_values = np.asarray(bbox, dtype=float)
        event_bbox_values = np.asarray(event_bbox, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ChangeMapError("coherence_info.json bbox must contain numeric coordinates") from exc
    if (
        not isinstance(bbox, list)
        or len(bbox) != 4
        or not isinstance(event_bbox, (list, tuple))
        or len(event_bbox) != 4
        or not np.all(np.isfinite(bbox_values))
        or not np.allclose(bbox_values, event_bbox_values, rtol=0, atol=1e-8)
    ):
        raise ChangeMapError("coherence_info.json bbox does not match the registered event bbox")
    if not (bbox_values[0] < bbox_values[2] and bbox_values[1] < bbox_values[3]):
        raise ChangeMapError("coherence_info.json bbox must be [west, south, east, north]")

    grid = metadata["grid"]
    if not isinstance(grid, dict):
        raise ChangeMapError("coherence_info.json grid must be an object")
    try:
        grid_crs = CRS.from_user_input(grid["crs"])
        width_value, height_value = grid["width"], grid["height"]
        width, height = int(width_value), int(height_value)
        affine = tuple(float(value) for value in grid["transform"])
        resolution = float(grid["resolutionMetres"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ChangeMapError("coherence_info.json has an invalid grid definition") from exc
    if grid_crs != CRS.from_epsg(32651) or not grid_crs.is_projected:
        raise ChangeMapError("coherence grid must use EPSG:32651 so pixel area is measured in metres")
    if (
        isinstance(width_value, bool)
        or isinstance(height_value, bool)
        or not isinstance(width_value, int)
        or not isinstance(height_value, int)
        or width < 1
        or height < 1
        or len(affine) != 6
    ):
        raise ChangeMapError("coherence_info.json grid dimensions or transform are invalid")
    if not math.isfinite(resolution) or resolution <= 0:
        raise ChangeMapError("coherence_info.json resolutionMetres must be finite and positive")
    pixel_width = math.hypot(affine[0], affine[3])
    pixel_height = math.hypot(affine[1], affine[4])
    if not np.allclose([pixel_width, pixel_height], resolution, rtol=1e-8, atol=1e-6):
        raise ChangeMapError("coherence_info.json resolutionMetres does not match the affine transform")
    if not math.isfinite(abs(affine[0] * affine[4] - affine[1] * affine[3])):
        raise ChangeMapError("coherence_info.json affine transform has no measurable pixel area")

    coverage = metadata["coverage"]
    required_coverage = ("aoiPixelCount", "commonValidPixelCount", "preValidPixelCount", "coValidPixelCount")
    if not isinstance(coverage, dict) or any(name not in coverage for name in required_coverage):
        raise ChangeMapError("coherence_info.json coverage is missing required pixel counts")
    for name in required_coverage:
        count = coverage[name]
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ChangeMapError(f"coherence_info.json coverage.{name} must be a nonnegative integer")
    if coverage["aoiPixelCount"] > width * height:
        raise ChangeMapError("coherence_info.json AOI pixel count exceeds the grid size")

    pre_path = input_dir / "coh_pre.tif"
    co_path = input_dir / "coh_co.tif"
    return metadata, grid_crs, pre_path, co_path


def _polygon_parts(geometry):
    if geometry.is_empty:
        return []
    if geometry.geom_type == "Polygon":
        return [geometry]
    if geometry.geom_type == "MultiPolygon":
        return list(geometry.geoms)
    if isinstance(geometry, GeometryCollection):
        parts = []
        for member in geometry.geoms:
            parts.extend(_polygon_parts(member))
        return parts
    return []


def _component_geometries(
    labels: np.ndarray,
    loss: np.ndarray,
    transform: rasterio.Affine,
    simplify_tolerance: float,
    pixel_area_m2: float,
) -> tuple[list[dict[str, Any]], list[str]]:
    polygon_groups: dict[int, list[Any]] = {}
    for geom_json, value in shapes(
        labels.astype(np.int32, copy=False),
        mask=labels > 0,
        transform=transform,
        connectivity=4,
    ):
        component_id = int(value)
        polygon_groups.setdefault(component_id, []).append(shape(geom_json))

    component_count = int(labels.max()) if labels.size else 0
    pixel_counts = np.bincount(labels.ravel(), minlength=component_count + 1)
    loss_sums = np.bincount(
        labels.ravel(),
        weights=np.where(labels > 0, loss, 0.0).ravel(),
        minlength=component_count + 1,
    )
    warnings: list[str] = []
    features: list[dict[str, Any]] = []
    from pyproj import Transformer

    transformer = Transformer.from_crs("EPSG:32651", "EPSG:4326", always_xy=True)
    to_wgs84 = transformer.transform

    for component_id in sorted(polygon_groups):
        pieces = polygon_groups[component_id]
        if not pieces:
            raise ChangeMapError(f"Cannot polygonize retained component {component_id}; no geometry was produced")
        projected = unary_union(pieces)
        if not projected.is_valid:
            projected = make_valid(projected)
            warnings.append(f"Repaired invalid polygon geometry for component {component_id}")
        polygonal_parts = _polygon_parts(projected)
        if not polygonal_parts:
            raise ChangeMapError(f"Repair produced no polygonal geometry for component {component_id}")
        projected = unary_union(polygonal_parts)
        if not projected.is_valid or projected.is_empty:
            raise ChangeMapError(f"Component {component_id} geometry is still invalid after repair")
        if projected.geom_type not in {"Polygon", "MultiPolygon"}:
            raise ChangeMapError(f"Component {component_id} did not produce Polygon or MultiPolygon geometry")

        pixel_count = int(pixel_counts[component_id])
        expected_area = pixel_count * pixel_area_m2
        measured_area = float(projected.area)
        area_tolerance = max(1e-5, pixel_area_m2 * 1e-9)
        if not math.isfinite(measured_area) or abs(measured_area - expected_area) > area_tolerance:
            raise ChangeMapError(
                f"Polygon area for component {component_id} does not match its retained pixel area"
            )

        display_geometry = projected
        if simplify_tolerance > 0:
            simplified = projected.simplify(simplify_tolerance, preserve_topology=True)
            if simplified.is_empty:
                warnings.append(f"Kept unsimplified geometry for component {component_id}; simplification collapsed it")
            elif not simplified.is_valid or simplified.geom_type not in {"Polygon", "MultiPolygon"}:
                warnings.append(f"Kept unsimplified geometry for component {component_id}; simplified geometry was invalid")
            else:
                display_geometry = simplified

        display_geometry = transform_geometry(to_wgs84, display_geometry)
        if not display_geometry.is_valid or display_geometry.is_empty:
            # Projection should preserve topology; fail rather than emit invalid GeoJSON.
            raise ChangeMapError(f"Exported EPSG:4326 geometry is invalid for component {component_id}")
        if display_geometry.geom_type not in {"Polygon", "MultiPolygon"}:
            raise ChangeMapError(f"Exported geometry is not Polygon or MultiPolygon for component {component_id}")

        features.append(
            {
                "type": "Feature",
                "id": f"component-{component_id:06d}",
                "geometry": mapping(display_geometry),
                "properties": {
                    "componentId": f"component-{component_id:06d}",
                    "pixelCount": pixel_count,
                    "areaKm2": measured_area / 1_000_000.0,
                    "meanLoss": float(loss_sums[component_id] / pixel_count),
                },
            }
        )
    return features, warnings


def _configure_matplotlib():
    if not os.environ.get("MPLCONFIGDIR"):
        os.environ["MPLCONFIGDIR"] = tempfile.mkdtemp(prefix="coherence-mpl-")
    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt
    return plt


def _pair_dates(pair: list[str]) -> str:
    return f"{pair[0]} to {pair[1]}"


def _write_qa(
    path: Path,
    event: dict[str, Any],
    metadata: dict[str, Any],
    details: dict[str, np.ndarray],
    changed: np.ndarray,
    km2_changed: float,
):
    plt = _configure_matplotlib()
    from matplotlib.colors import TwoSlopeNorm
    from matplotlib import colormaps
    from matplotlib.patches import Patch

    supported = details["supported"]
    sample_step = max(1, int(math.ceil(max(supported.shape) / 1800)))
    sample = (slice(None, None, sample_step), slice(None, None, sample_step))
    sampled_supported = supported[sample]
    missing_color = "#d2d2d2"
    coherence_cmap = colormaps["viridis"].copy()
    coherence_cmap.set_bad(missing_color)
    diverging_cmap = colormaps["RdBu_r"].copy()
    diverging_cmap.set_bad(missing_color)
    detection_cmap = colormaps["Reds"].resampled(2).copy()
    detection_cmap.set_bad(missing_color)

    fig, axes = plt.subplots(2, 2, figsize=(13, 10), constrained_layout=True)
    plots = (
        (details["smoothedPre"], "Pre coherence", coherence_cmap, 0, 1),
        (details["smoothedCo"], "Event coherence", coherence_cmap, 0, 1),
    )
    for ax, (array, label, cmap, low, high) in zip(axes.flat[:2], plots):
        image = ax.imshow(
            np.ma.masked_where(~sampled_supported, array[sample]), cmap=cmap, vmin=low, vmax=high
        )
        ax.set_title(label)
        ax.set_axis_off()
        fig.colorbar(image, ax=ax, fraction=0.046, pad=0.025, label="Coherence (unitless)")

    loss = details["loss"]
    sampled_loss = loss[sample]
    finite_loss = np.abs(sampled_loss[sampled_supported])
    loss_limit = max(float(finite_loss.max()) if finite_loss.size else 0.0, 1e-6)
    loss_image = axes.flat[2].imshow(
        np.ma.masked_where(~sampled_supported, sampled_loss),
        cmap=diverging_cmap,
        norm=TwoSlopeNorm(vmin=-loss_limit, vcenter=0.0, vmax=loss_limit),
    )
    axes.flat[2].set_title("Signed loss: pre − event")
    axes.flat[2].set_axis_off()
    fig.colorbar(loss_image, ax=axes.flat[2], fraction=0.046, pad=0.025, label="Coherence loss (unitless)")

    axes.flat[3].imshow(
        np.ma.masked_where(~sampled_supported, changed[sample].astype(np.uint8)),
        cmap=detection_cmap,
        vmin=0,
        vmax=1,
    )
    axes.flat[3].set_title("Retained detections")
    axes.flat[3].set_axis_off()
    axes.flat[3].legend(
        handles=[Patch(facecolor="#fff5f0", edgecolor="#777777", label="No retained change"),
                 Patch(facecolor="#a50f15", edgecolor="#777777", label="Change")],
        loc="lower right",
        framealpha=0.9,
    )
    title = (
        f"{event['name']} · {km2_changed:.4f} km² detected\n"
        f"Pre { _pair_dates(metadata['prePair']) } · Event { _pair_dates(metadata['coPair']) }"
    )
    fig.suptitle(title, fontsize=13)
    if metadata["dataKind"] == "synthetic":
        fig.text(
            0.5, 0.5, "SYNTHETIC DATA", ha="center", va="center", rotation=30,
            fontsize=34, color="#b00020", alpha=0.19, weight="bold",
        )
    fig.savefig(path, dpi=120, facecolor="white")
    plt.close(fig)


def _write_mask(
    path: Path,
    mask: np.ndarray,
    transform: rasterio.Affine,
    crs: CRS,
    event_id: str,
    extraction_id: str,
    data_kind: str,
):
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=mask.shape[0],
        width=mask.shape[1],
        count=1,
        dtype="uint8",
        crs=crs,
        transform=transform,
        nodata=255,
        compress="lzw",
    ) as dst:
        dst.write(mask.astype(np.uint8), 1)
        dst.update_tags(
            event=event_id,
            extractionId=extraction_id,
            dataKind=data_kind,
            productType="coherence-change-mask",
            units="class",
        )


def _publish_staged(stage: Path, output_dir: Path, filenames: tuple[str, ...], metadata_filename: str):
    # The extent JSON is replaced last so consumers can verify every referenced hash.
    for filename in filenames:
        if filename != metadata_filename:
            os.replace(stage / filename, output_dir / filename)
    os.replace(stage / metadata_filename, output_dir / metadata_filename)


def create_change_map(
    event_id: str,
    input_dir: str | Path | None = None,
    output_dir: str | Path | None = None,
    pre_min: float = 0.5,
    loss_min: float = 0.3,
    min_pixels: int = 10,
    simplify: float = 15,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Create change mask, GeoJSON, summary, and QA image for a prepared event pair.

    The function returns the `change_extent.json` metadata after publishing a staged,
    hash-linked output set. It raises :class:`ChangeMapError` for invalid inputs.
    """
    _validate_parameters(pre_min, loss_min, min_pixels, simplify)
    try:
        event = load_event(event_id)
    except SystemExit as exc:
        raise ChangeMapError(str(exc)) from exc
    except Exception as exc:
        raise ChangeMapError(f"Cannot load event {event_id!r}: {exc}") from exc

    default_dir = BACKEND_DIR / "data" / "output" / event_id
    in_folder = Path(input_dir).expanduser().resolve() if input_dir is not None else default_dir
    out_folder = Path(output_dir).expanduser().resolve() if output_dir is not None else default_dir
    if not in_folder.is_dir():
        raise ChangeMapError(f"Input directory does not exist: {in_folder}")

    metadata, grid_crs, pre_path, co_path = _validate_metadata(event, in_folder)
    pre, pre_valid = _read_coherence(pre_path, metadata, "coh_pre.tif", grid_crs)
    co, co_valid = _read_coherence(co_path, metadata, "coh_co.tif", grid_crs)
    with rasterio.open(pre_path) as src:
        transform = src.transform

    # Extraction has already applied the authoritative densified AOI center mask.
    # Reprojecting the boundary here could produce different edge pixels.
    actual_aoi_count = metadata["coverage"]["aoiPixelCount"]
    if actual_aoi_count == 0:
        raise ChangeMapError("The extraction metadata reports no AOI pixels on the prepared grid")
    common_valid = pre_valid & co_valid
    actual_coverage = {
        "preValidPixelCount": int(pre_valid.sum()),
        "coValidPixelCount": int(co_valid.sum()),
        "commonValidPixelCount": int(common_valid.sum()),
    }
    for name, actual in actual_coverage.items():
        if actual != metadata["coverage"][name]:
            raise ChangeMapError(
                f"{name} is {actual} on the prepared rasters but coherence_info.json records "
                f"{metadata['coverage'][name]}"
            )
        if actual > actual_aoi_count:
            raise ChangeMapError(f"{name} exceeds the extraction AOI pixel count")
    if not np.any(common_valid):
        raise ChangeMapError("No common valid pre/event coherence pixels; this is not a zero-change result")

    details = _compute_change_details(pre, co, common_valid, pre_min, loss_min, min_pixels)
    supported_count = int(details["supported"].sum())
    eligible_count = int(details["eligible"].sum())
    if eligible_count == 0:
        raise ChangeMapError("No eligible pixels remain after baseline threshold and smoothing support checks")

    pixel_area_m2 = abs(transform.a * transform.e - transform.b * transform.d)
    if not math.isfinite(pixel_area_m2) or pixel_area_m2 <= 0:
        raise ChangeMapError("Prepared grid has an invalid affine pixel area")
    area_per_pixel_km2 = pixel_area_m2 / 1_000_000.0
    raw_changed = details["rawChanged"]
    changed = details["changed"]
    raw_labels, raw_component_count = ndimage.label(raw_changed, structure=np.ones((3, 3), dtype=np.uint8))
    component_labels, component_count = ndimage.label(changed, structure=np.ones((3, 3), dtype=np.uint8))
    features, geometry_warnings = _component_geometries(
        component_labels, details["loss"], transform, float(simplify), pixel_area_m2
    )
    warnings = [str(item) for item in metadata["warnings"]]
    if metadata["coverage"]["commonValidPixelCount"] < actual_aoi_count:
        warnings.append(
            "Common valid coverage is partial; mapped area describes only observed valid overlap within the AOI"
        )
    warnings.extend(geometry_warnings)

    mask = np.full(pre.shape, 255, dtype=np.uint8)
    mask[details["supported"]] = 0
    mask[changed] = 1

    output_dir_path = out_folder
    output_dir_path.mkdir(parents=True, exist_ok=True)
    existing = [name for name in (*RESULT_FILES, "change_extent.json") if (output_dir_path / name).exists()]
    if existing and not overwrite:
        raise ChangeMapError(
            "Change outputs already exist (" + ", ".join(existing) + "); use --overwrite or another output directory"
        )

    run_id = str(uuid.uuid4())
    valid_area_km2 = float(common_valid.sum() * area_per_pixel_km2)
    supported_area_km2 = float(supported_count * area_per_pixel_km2)
    eligible_area_km2 = float(eligible_count * area_per_pixel_km2)
    changed_area_km2 = float(changed.sum() * area_per_pixel_km2)
    raw_count = int(raw_changed.sum())
    changed_count = int(changed.sum())

    output_metadata: dict[str, Any] = {
        "schemaVersion": "1.0",
        "codeVersion": "coherence-change-1.0",
        "event": event["id"],
        "aoi": event["aoi"],
        "prePair": metadata["prePair"],
        "coPair": metadata["coPair"],
        "extractionId": metadata["extractionId"],
        "runId": run_id,
        "dataKind": metadata["dataKind"],
        "eventWindow": metadata["eventWindow"],
        "bbox": metadata["bbox"],
        "stats": {
            "km2Changed": changed_area_km2,
            "validAreaKm2": valid_area_km2,
            "supportedAreaKm2": supported_area_km2,
            "eligibleAreaKm2": eligible_area_km2,
            "rawChangedPixelCount": raw_count,
            "changedPixelCount": changed_count,
            "rawComponentCount": int(raw_component_count),
            "componentCount": int(component_count),
            "polygonCount": len(features),
        },
        "coverage": {
            "aoiPixelCount": actual_aoi_count,
            "preValidPixelCount": actual_coverage["preValidPixelCount"],
            "coValidPixelCount": actual_coverage["coValidPixelCount"],
            "commonValidPixelCount": actual_coverage["commonValidPixelCount"],
            "supportedPixelCount": supported_count,
            "eligiblePixelCount": eligible_count,
            "validAreaKm2": valid_area_km2,
            "supportedAreaKm2": supported_area_km2,
            "eligibleAreaKm2": eligible_area_km2,
            "commonValidCoveragePercent": 100.0 * actual_coverage["commonValidPixelCount"] / actual_aoi_count,
            "eligibleCoveragePercent": 100.0 * eligible_count / actual_aoi_count,
        },
        "parameters": {
            "preMin": float(pre_min),
            "lossMin": float(loss_min),
            "minPixels": int(min_pixels),
            "simplifyToleranceMetres": float(simplify),
            "smoothingKernel": "3x3",
            "minimumValidNeighbors": 5,
            "thresholdTolerance": CHANGE_THRESHOLD_TOLERANCE,
            "connectivity": 8,
        },
        "grid": {
            "crs": grid_crs.to_string(),
            "width": int(pre.shape[1]),
            "height": int(pre.shape[0]),
            "transform": [float(value) for value in tuple(transform)[:6]],
            "resolutionMetres": float(metadata["grid"]["resolutionMetres"]),
            "pixelAreaM2": float(pixel_area_m2),
        },
        "sources": metadata["sources"],
        "preparedRasters": {
            filename: {"sha256": _metadata_hash(metadata["outputs"], filename)}
            for filename in COHERENCE_FILES
        },
        "warnings": warnings,
        "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }

    stage_name = None
    try:
        with tempfile.TemporaryDirectory(prefix=".change-stage-", dir=output_dir_path) as stage_name:
            stage = Path(stage_name)
            mask_path = stage / "change_mask.tif"
            geojson_path = stage / "change.geojson"
            qa_path = stage / "06_change_check.png"
            extent_path = stage / "change_extent.json"

            _write_mask(
                mask_path,
                mask,
                transform,
                grid_crs,
                event["id"],
                metadata["extractionId"],
                metadata["dataKind"],
            )
            geojson = {"type": "FeatureCollection", "features": features}
            geojson_path.write_text(json.dumps(geojson, allow_nan=False, separators=(",", ":")), encoding="utf-8")
            _write_qa(qa_path, event, metadata, details, changed, changed_area_km2)

            output_metadata["outputs"] = {
                filename: {"sha256": _sha256(stage / filename)} for filename in RESULT_FILES
            }
            extent_path.write_text(json.dumps(output_metadata, indent=2, allow_nan=False) + "\n", encoding="utf-8")

            with rasterio.open(mask_path) as check:
                if check.count != 1 or check.dtypes[0] != "uint8" or check.nodata != 255:
                    raise ChangeMapError("Staged change_mask.tif failed output validation")
                if check.width != pre.shape[1] or check.height != pre.shape[0] or check.crs != grid_crs:
                    raise ChangeMapError("Staged change_mask.tif grid does not match prepared coherence rasters")
                if not np.allclose(tuple(check.transform)[:6], tuple(transform)[:6], rtol=1e-10, atol=1e-8):
                    raise ChangeMapError("Staged change_mask.tif transform does not match prepared coherence rasters")
            staged_geojson = json.loads(geojson_path.read_text(encoding="utf-8"))
            if staged_geojson.get("type") != "FeatureCollection" or len(staged_geojson.get("features", [])) != len(features):
                raise ChangeMapError("Staged change.geojson failed output validation")
            for feature in staged_geojson.get("features", []):
                geometry = shape(feature.get("geometry"))
                if geometry.is_empty or not geometry.is_valid or geometry.geom_type not in {"Polygon", "MultiPolygon"}:
                    raise ChangeMapError("Staged change.geojson contains invalid polygon geometry")
            from PIL import Image

            with Image.open(qa_path) as image:
                if image.format != "PNG":
                    raise ChangeMapError("Staged 06_change_check.png is not a PNG image")
                image.verify()
            staged_extent = json.loads(extent_path.read_text(encoding="utf-8"))
            for filename in RESULT_FILES:
                if _sha256(stage / filename) != staged_extent["outputs"][filename]["sha256"]:
                    raise ChangeMapError(f"Staged hash validation failed for {filename}")

            _publish_staged(stage, output_dir_path, (*RESULT_FILES, "change_extent.json"), "change_extent.json")
    except ChangeMapError:
        raise
    except Exception as exc:
        raise ChangeMapError(f"Failed to stage or publish change outputs: {exc}") from exc

    return output_metadata
