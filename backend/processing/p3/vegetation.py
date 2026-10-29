"""Calibrated NISAR GCOV biomass retrieval and regional motion fusion.

The retrieval is intentionally unavailable until it has independent plot
validation and user supplied acceptance limits.  The supported profile is
limited to positive linear-power HHHH/HVHV terms in one hash-bound GCOV
manifest.  Each term is averaged over the pixels whose centers fall inside an
actual reference-plot polygon, then converted to dB.  A standardized two
feature ridge model (alpha=1, unpenalized intercept) predicts log1p(AGB).

Calibration GeoJSON uses polygon features with ``plotId``, ``agbMgPerHa``,
``agbUnit: "Mg/ha"``, ``split`` (``train`` or ``validation``),
``spatialGroup`` and ``referenceDate`` properties.  The split configuration
must state how spatial independence was established.  Acceptance limits are
provided by the calibration owner; this module deliberately has no default
accuracy threshold.

Regional fusion keeps biomass and LOS-motion summaries side by side with
their independent date ranges and source resolutions.  It does not calculate
a causal effect, a hazard score, or infer vertical motion from LOS.

For fusion, the biomass input may be a published biomass manifest containing
``regionalMetrics``.  The ground-motion input is a JSON wrapper containing
``event``, ``dataKind``, ``runId``, ``nativeResolutionMetres`` and ``regions``;
each region uses the fields returned by ``series.summarize_region``
(``regionId``, ``rateMmPerYear``, ``validRateCellCount``, ``selectedCellCount``
and ``epochs``).  Region IDs are the join key. The independent date ranges are
derived from the motion epochs and the biomass product acquisition dates.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime
import json
import math
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import rasterio
from affine import Affine
from rasterio.features import geometry_mask
from rasterio.warp import transform_geom
from shapely.geometry import shape

from . import core


MODEL_NAME = "nisar-gcov-hhhv-standardized-ridge-log1p-agb"
MODEL_VERSION = "1.0"
FEATURE_NAMES = ("HHHH_dB", "HVHV_dB")
RIDGE_ALPHA = 1.0
MIN_TRAIN_PLOTS = 10
MIN_VALIDATION_PLOTS = 5
AGB_UNITS = "Mg/ha"
POWER_UNITS = {"linear_power", "linear power", "power", "m2/m2", "m^2/m^2", "1", "unitless", "dimensionless"}
SOURCE_BASIS_FIELDS = (
    "sensor", "frequency", "polarization", "orbit", "frame", "processingVersion", "maturity",
)
POWER_CONVENTION = "positive_linear_power; per-plot mean then 10log10; no unit rescaling"


class BiomassError(ValueError):
    """Invalid biomass inputs or calibration evidence."""


class CalibrationUnavailableError(BiomassError):
    """Raised when a quantitative retrieval is not supported by a model."""


@dataclass(frozen=True)
class GcovFeatures:
    manifest: dict[str, Any]
    grid: dict[str, Any]
    power: dict[str, np.ndarray]
    features_db: dict[str, np.ndarray]
    valid_mask: np.ndarray


def _read_json(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    try:
        value = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BiomassError(f"Cannot read JSON input {p}: {exc}") from exc
    if not isinstance(value, dict):
        raise BiomassError(f"Expected a JSON object in {p}")
    return value


def _parse_date(value: Any, description: str) -> date:
    if not isinstance(value, str) or not value.strip():
        raise BiomassError(f"{description} must be an ISO date")
    try:
        # Dates are normally YYYY-MM-DD. Accept UTC timestamps as supplied by
        # product manifests, while keeping the date comparison explicit.
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError as exc:
        raise BiomassError(f"{description} must be an ISO date: {value!r}") from exc


def _source_dates(manifest: Mapping[str, Any]) -> list[str]:
    raw = manifest.get("acquisitionDates")
    if raw is None and manifest.get("acquisitionDate") is not None:
        raw = [manifest["acquisitionDate"]]
    if not isinstance(raw, list) or not raw:
        raise BiomassError("GCOV manifest must declare acquisitionDate(s) for timing provenance")
    dates = []
    for i, value in enumerate(raw):
        dates.append(_parse_date(value, f"GCOV acquisitionDates[{i}]").isoformat())
    return sorted(set(dates))


def _term_units(manifest: Mapping[str, Any], asset: Mapping[str, Any], term: str) -> str | None:
    units = asset.get("units")
    term_units = manifest.get("termUnits")
    if units is None and isinstance(term_units, dict):
        units = term_units.get(term)
    top_level_units = manifest.get("units")
    if units is None and isinstance(top_level_units, dict):
        units = top_level_units.get(term)
    if units is None:
        return None
    return str(units).strip().lower()


def _term_is_linear_power(manifest: Mapping[str, Any], asset: Mapping[str, Any], term: str) -> bool:
    units = _term_units(manifest, asset, term)
    if units not in POWER_UNITS:
        return False
    quantity = asset.get("quantity")
    if quantity is None:
        quantities = manifest.get("termQuantities")
        quantity = quantities.get(term) if isinstance(quantities, dict) else None
    # A units declaration is required and explicit dB/backscatter display
    # values cannot be fed through a second logarithm. A declared quantity is
    # checked when present; the normalized power units themselves remain the
    # minimum contract for legacy normalizers.
    return quantity is None or str(quantity).strip().lower() in {"power", "linear_power", "covariance_power"}


def _source_basis(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Return the exact GCOV retrieval basis required for model portability.

    A shared event or a coincidentally similar raster grid does not establish
    calibration compatibility. Every stable source/profile field is explicit,
    and the radar power units/conversion are versioned with the model.
    """
    if str(manifest.get("product", "")).lower() != "gcov":
        raise BiomassError("Biomass calibration/prediction requires a normalized GCOV product manifest")
    if manifest.get("dataKind") not in {"observed", "derived", "scenario", "synthetic"}:
        raise BiomassError("GCOV manifest must declare a supported dataKind")
    missing = [key for key in SOURCE_BASIS_FIELDS if not isinstance(manifest.get(key), (str, int)) or not str(manifest.get(key)).strip()]
    if missing:
        raise BiomassError("GCOV manifest is missing required sourceBasis fields: " + ", ".join(missing))
    profile = manifest.get("sourceProfile")
    if not isinstance(profile, dict):
        raise BiomassError("GCOV manifest must declare sourceProfile provenance")
    profile_fields = ("id", "version", "adapter")
    profile_missing = [key for key in profile_fields if not isinstance(profile.get(key), str) or not profile[key].strip()]
    if profile_missing:
        raise BiomassError("GCOV sourceProfile is missing required fields: " + ", ".join(profile_missing))
    units = {term: _term_units(manifest, manifest["assets"][term], term) for term in ("HHHH", "HVHV")}
    if units["HHHH"] != units["HVHV"]:
        raise BiomassError("HHHH and HVHV must use the same declared power units")
    return {
        **{key: manifest[key] for key in SOURCE_BASIS_FIELDS},
        "sourceProfile": {key: profile[key] for key in profile_fields},
        "product": "gcov",
        "termUnits": units,
        "powerConvention": POWER_CONVENTION,
    }


def read_gcov_features(manifest_path: str | Path) -> GcovFeatures:
    """Read and validate co-gridded HHHH/HVHV linear-power assets.

    Raster payloads are loaded through the shared hash-verifying ``core``
    manifest reader.  Nonpositive or nodata power is marked invalid instead
    of being replaced by zero or passed through a logarithm.
    """
    try:
        manifest = core.load_manifest(manifest_path)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
        raise BiomassError(f"Invalid GCOV manifest: {exc}") from exc
    assets = manifest.get("assets")
    if not isinstance(assets, dict):
        raise BiomassError("GCOV manifest is missing its assets object")
    power: dict[str, np.ndarray] = {}
    features_db: dict[str, np.ndarray] = {}
    grids: dict[str, dict[str, Any]] = {}
    declared_units: dict[str, str] = {}
    for term in ("HHHH", "HVHV"):
        asset = assets.get(term)
        if not isinstance(asset, dict):
            raise BiomassError(f"GCOV manifest is missing required {term} term")
        if not _term_is_linear_power(manifest, asset, term):
            units = _term_units(manifest, asset, term)
            raise BiomassError(
                f"{term} must declare supported linear-power units; got {units!r}"
            )
        declared_units[term] = _term_units(manifest, asset, term) or ""
        try:
            values, grid = core.read_raster(manifest, term)
        except (OSError, KeyError, ValueError, rasterio.errors.RasterioError) as exc:
            raise BiomassError(f"Cannot read GCOV {term} raster: {exc}") from exc
        values = np.asarray(values, dtype="float64")
        values[~np.isfinite(values) | (values <= 0)] = np.nan
        power[term] = values
        with np.errstate(divide="ignore", invalid="ignore"):
            features_db[term + "_dB"] = 10.0 * np.log10(values)
        grids[term] = grid
    if declared_units["HHHH"] != declared_units["HVHV"]:
        raise BiomassError(
            "HHHH and HVHV must use the same declared linear-power units; "
            f"got {declared_units['HHHH']!r} and {declared_units['HVHV']!r}"
        )
    try:
        core.same_grid(grids["HHHH"], grids["HVHV"])
    except ValueError as exc:
        raise BiomassError(f"HHHH and HVHV grids differ: {exc}") from exc
    valid = np.isfinite(power["HHHH"]) & np.isfinite(power["HVHV"])
    for name in FEATURE_NAMES:
        features_db[name] = np.where(valid, features_db[name], np.nan)
    return GcovFeatures(manifest, grids["HHHH"], power, features_db, valid)


def _geojson_crs(collection: Mapping[str, Any], config: Mapping[str, Any]) -> str:
    declared = config.get("plotCrs")
    if declared:
        return str(declared)
    crs = collection.get("crs")
    if isinstance(crs, dict):
        props = crs.get("properties", {})
        name = props.get("name") if isinstance(props, dict) else None
        if name:
            return str(name)
    # RFC 7946 GeoJSON uses WGS84 longitude/latitude when no legacy CRS member
    # is present. A non-standard CRS must be stated in config.
    return "EPSG:4326"


def _geometry_to_raster_crs(geometry: Mapping[str, Any], source_crs: str, target_crs: str) -> dict[str, Any]:
    try:
        parsed = shape(geometry)
    except Exception as exc:
        raise BiomassError(f"Invalid reference plot geometry: {exc}") from exc
    if parsed.geom_type not in {"Polygon", "MultiPolygon"} or parsed.is_empty or parsed.area <= 0 or not parsed.is_valid:
        raise BiomassError("Reference plots must be valid, nonempty Polygon or MultiPolygon geometries")
    try:
        return transform_geom(source_crs, target_crs, dict(geometry), precision=-1)
    except Exception as exc:
        raise BiomassError(f"Cannot transform reference plot geometry to raster CRS: {exc}") from exc


def aggregate_reference_plots(
    gcov: GcovFeatures,
    plots_path: str | Path,
    config: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Aggregate linear power within actual GeoJSON plot polygons.

    Pixel-center inclusion is used consistently (``all_touched=False``). Each
    plot's mean positive linear power is converted to dB only after spatial
    aggregation. Plots without at least one common valid pixel are excluded
    and their reason is retained in the timing/sampling report.
    """
    path = Path(plots_path)
    try:
        collection = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BiomassError(f"Cannot read reference plot GeoJSON {path}: {exc}") from exc
    if not isinstance(collection, dict) or collection.get("type") != "FeatureCollection":
        raise BiomassError("Reference plots must be a GeoJSON FeatureCollection")
    features = collection.get("features")
    if not isinstance(features, list) or not features:
        raise BiomassError("Reference plot FeatureCollection is empty")
    source_crs = _geojson_crs(collection, config)
    grid_transform = Affine(*gcov.grid["transform"])
    out_shape = (gcov.grid["height"], gcov.grid["width"])
    samples: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    ref_dates: list[str] = []
    for index, feature in enumerate(features):
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            raise BiomassError(f"Reference feature {index} is not a GeoJSON Feature")
        properties = feature.get("properties")
        geometry = feature.get("geometry")
        if not isinstance(properties, dict) or not isinstance(geometry, dict):
            raise BiomassError(f"Reference feature {index} needs properties and polygon geometry")
        plot_id = properties.get("plotId")
        if not isinstance(plot_id, str) or not plot_id.strip() or plot_id in seen_ids:
            raise BiomassError(f"Reference feature {index} needs a unique nonempty plotId")
        seen_ids.add(plot_id)
        try:
            agb = float(properties["agbMgPerHa"])
        except (KeyError, TypeError, ValueError) as exc:
            raise BiomassError(f"Plot {plot_id} needs numeric agbMgPerHa") from exc
        if properties.get("agbUnit") != AGB_UNITS:
            raise BiomassError(f"Plot {plot_id} agbUnit must be exactly {AGB_UNITS!r}")
        if not math.isfinite(agb) or agb < 0:
            raise BiomassError(f"Plot {plot_id} AGB must be finite and nonnegative")
        split = properties.get("split")
        if split not in {"train", "validation"}:
            raise BiomassError(f"Plot {plot_id} split must be 'train' or 'validation'")
        group = properties.get("spatialGroup")
        if not isinstance(group, str) or not group.strip():
            raise BiomassError(f"Plot {plot_id} needs an explicit spatialGroup")
        reference_date = _parse_date(properties.get("referenceDate"), f"Plot {plot_id} referenceDate").isoformat()
        ref_dates.append(reference_date)
        raster_geometry = _geometry_to_raster_crs(geometry, source_crs, gcov.grid["crs"])
        inside = geometry_mask([raster_geometry], out_shape=out_shape, transform=grid_transform, invert=True, all_touched=False)
        valid = inside & gcov.valid_mask
        count = int(valid.sum())
        if count == 0:
            excluded.append({"plotId": plot_id, "reason": "no_common_valid_pixel_inside_polygon"})
            continue
        hhhh_mean = float(np.mean(gcov.power["HHHH"][valid]))
        hvhv_mean = float(np.mean(gcov.power["HVHV"][valid]))
        if hhhh_mean <= 0 or hvhv_mean <= 0:
            excluded.append({"plotId": plot_id, "reason": "nonpositive_mean_power"})
            continue
        sample = {
            "plotId": plot_id,
            "spatialGroup": group,
            "split": split,
            "agbMgPerHa": agb,
            "featuresDb": {
                "HHHH_dB": 10.0 * math.log10(hhhh_mean),
                "HVHV_dB": 10.0 * math.log10(hvhv_mean),
            },
            "validPixelCount": count,
            "referenceDate": reference_date,
        }
        samples.append(sample)
    report = {
        "plotFeatureCount": len(features),
        "usablePlotCount": len(samples),
        "excludedPlots": excluded,
        "plotCrs": source_crs,
        "referenceDateRange": [min(ref_dates), max(ref_dates)] if ref_dates else None,
        "aggregation": "mean_positive_linear_power_then_10log10; pixel-center polygon inclusion; common HHHH/HVHV valid pixels",
    }
    return samples, report


def _validate_acceptance_limits(value: Any) -> dict[str, float] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise BiomassError("acceptanceLimits must be an object with owner-supplied thresholds")
    expected = ("maxAbsBiasMgPerHa", "maxRmseMgPerHa")
    if set(value) != set(expected):
        raise BiomassError("acceptanceLimits must contain exactly maxAbsBiasMgPerHa and maxRmseMgPerHa")
    limits: dict[str, float] = {}
    for key in expected:
        try:
            number = float(value[key])
        except (TypeError, ValueError) as exc:
            raise BiomassError(f"acceptanceLimits.{key} must be numeric") from exc
        if not math.isfinite(number) or number < 0:
            raise BiomassError(f"acceptanceLimits.{key} must be finite and nonnegative")
        limits[key] = number
    return limits


def _metrics(predicted: np.ndarray, observed: np.ndarray) -> dict[str, float]:
    error = np.asarray(predicted, dtype="float64") - np.asarray(observed, dtype="float64")
    return {"biasMgPerHa": float(np.mean(error)), "rmseMgPerHa": float(np.sqrt(np.mean(error ** 2)))}


def _predict_samples(model: Mapping[str, Any], samples: Sequence[Mapping[str, Any]]) -> np.ndarray:
    x = np.asarray([[float(row["featuresDb"][name]) for name in FEATURE_NAMES] for row in samples], dtype="float64")
    mean = np.asarray(model["standardization"]["mean"], dtype="float64")
    scale = np.asarray(model["standardization"]["std"], dtype="float64")
    coef = np.asarray(model["coefficients"], dtype="float64")
    log_prediction = float(model["interceptLog1pAgb"]) + ((x - mean) / scale) @ coef
    return _inverse_log_agb(log_prediction)


def _inverse_log_agb(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype="float64")
    if not np.isfinite(values).all():
        raise BiomassError("Model produced a nonfinite log1p(AGB) prediction")
    with np.errstate(over="raise", invalid="raise"):
        try:
            result = np.expm1(values)
        except FloatingPointError as exc:
            raise BiomassError("Model prediction overflows the Mg/ha output range") from exc
    # A log-link model can predict below log(1) for sparse canopy. Truncate at
    # the physical lower bound of zero Mg/ha and record this in the model.
    return np.maximum(result, 0.0)


def fit_calibration_model(
    samples: Sequence[Mapping[str, Any]],
    *,
    config: Mapping[str, Any],
    source_provenance: Mapping[str, Any] | None = None,
    timing_provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Fit and independently validate the fixed two-feature ridge profile."""
    if not isinstance(config.get("splitProvenance"), str) or not config["splitProvenance"].strip():
        raise BiomassError("Calibration config must document splitProvenance")
    if not isinstance(config.get("referenceTimingNotes"), str) or not config["referenceTimingNotes"].strip():
        raise BiomassError("Calibration config must document referenceTimingNotes, including mismatch handling")
    limits = _validate_acceptance_limits(config.get("acceptanceLimits"))
    by_split: dict[str, list[Mapping[str, Any]]] = {"train": [], "validation": []}
    seen_ids: set[str] = set()
    for i, row in enumerate(samples):
        if not isinstance(row, Mapping):
            raise BiomassError(f"Calibration sample {i} is not an object")
        plot_id = row.get("plotId")
        group = row.get("spatialGroup")
        split = row.get("split")
        if not isinstance(plot_id, str) or not plot_id.strip() or plot_id in seen_ids:
            raise BiomassError(f"Calibration sample {i} needs a unique nonempty plotId")
        seen_ids.add(plot_id)
        if not isinstance(group, str) or not group.strip():
            raise BiomassError(f"Calibration sample {plot_id} needs an explicit spatialGroup")
        if split not in by_split:
            raise BiomassError(f"Calibration sample {plot_id} split must be 'train' or 'validation'")
        try:
            agb = float(row["agbMgPerHa"])
            values = [float(row["featuresDb"][name]) for name in FEATURE_NAMES]
        except (KeyError, TypeError, ValueError) as exc:
            raise BiomassError(f"Calibration sample {plot_id} is missing a feature or AGB value") from exc
        if not math.isfinite(agb) or agb < 0 or not np.isfinite(values).all():
            raise BiomassError(f"Calibration sample {plot_id} contains invalid numeric values")
        by_split[split].append(row)
    train = by_split["train"]
    validation = by_split["validation"]
    if len(train) < MIN_TRAIN_PLOTS:
        raise BiomassError(f"At least {MIN_TRAIN_PLOTS} usable training plots are required; got {len(train)}")
    if len(validation) < MIN_VALIDATION_PLOTS:
        raise BiomassError(f"At least {MIN_VALIDATION_PLOTS} independent validation plots are required; got {len(validation)}")
    train_groups = {row["spatialGroup"] for row in train}
    validation_groups = {row["spatialGroup"] for row in validation}
    overlap = train_groups & validation_groups
    if overlap:
        raise BiomassError("Training and validation spatial groups overlap: " + ", ".join(sorted(overlap)))

    x_train = np.asarray([[float(row["featuresDb"][name]) for name in FEATURE_NAMES] for row in train], dtype="float64")
    y_train = np.log1p(np.asarray([float(row["agbMgPerHa"]) for row in train], dtype="float64"))
    means = x_train.mean(axis=0)
    scales = x_train.std(axis=0, ddof=0)
    if not np.isfinite(scales).all() or np.any(scales <= np.finfo("float64").eps):
        raise BiomassError("Training features must both vary; standardized feature design is rank deficient")
    z_train = (x_train - means) / scales
    design = np.column_stack([np.ones(len(train)), z_train])
    rank = int(np.linalg.matrix_rank(design))
    if rank != len(FEATURE_NAMES) + 1:
        raise BiomassError(f"Training feature design is not full rank (rank {rank}, expected 3)")
    penalty = np.diag([0.0, RIDGE_ALPHA, RIDGE_ALPHA])
    try:
        parameters = np.linalg.solve(design.T @ design + penalty, design.T @ y_train)
    except np.linalg.LinAlgError as exc:
        raise BiomassError("Ridge calibration solve failed") from exc
    model: dict[str, Any] = {
        "model": MODEL_NAME,
        "modelVersion": MODEL_VERSION,
        "features": list(FEATURE_NAMES),
        "featureUnits": {name: "dB" for name in FEATURE_NAMES},
        "inputProfile": "positive HHHH and HVHV linear power from one compatible GCOV product",
        "target": "log1p(AGB_Mg_per_ha)",
        "outputUnits": AGB_UNITS,
        "inverseTransform": "max(0, expm1(predicted_log1p_AGB))",
        "ridgeAlpha": RIDGE_ALPHA,
        "interceptUnpenalized": True,
        "standardization": {"mean": means.tolist(), "std": scales.tolist(), "ddof": 0},
        "interceptLog1pAgb": float(parameters[0]),
        "coefficients": [float(v) for v in parameters[1:]],
        "calibratedFeatureRangeDb": {
            name: {"min": float(x_train[:, i].min()), "max": float(x_train[:, i].max())}
            for i, name in enumerate(FEATURE_NAMES)
        },
        "ridgeFeatureDesignRank": rank,
        "splitProvenance": config["splitProvenance"],
        "spatialSplit": {
            "trainPlotCount": len(train),
            "validationPlotCount": len(validation),
            "trainSpatialGroups": sorted(train_groups),
            "validationSpatialGroups": sorted(validation_groups),
            "groupsDisjoint": True,
            "trainPlotIds": [str(row["plotId"]) for row in train],
            "validationPlotIds": [str(row["plotId"]) for row in validation],
        },
        "referenceTiming": {
            "notes": config["referenceTimingNotes"],
            **dict(timing_provenance or {}),
        },
        "acceptanceLimits": limits,
        "sourceProvenance": dict(source_provenance or {}),
    }
    train_predictions = _predict_samples(model, train)
    validation_predictions = _predict_samples(model, validation)
    train_observed = np.asarray([float(row["agbMgPerHa"]) for row in train], dtype="float64")
    validation_observed = np.asarray([float(row["agbMgPerHa"]) for row in validation], dtype="float64")
    metrics = {
        "train": {**_metrics(train_predictions, train_observed), "plotCount": len(train)},
        "validation": {**_metrics(validation_predictions, validation_observed), "plotCount": len(validation)},
    }
    reasons: list[str] = []
    if limits is None:
        reasons.append("acceptance_limits_not_supplied")
    else:
        validation_metrics = metrics["validation"]
        if abs(validation_metrics["biasMgPerHa"]) > limits["maxAbsBiasMgPerHa"]:
            reasons.append("validation_abs_bias_exceeds_limit")
        if validation_metrics["rmseMgPerHa"] > limits["maxRmseMgPerHa"]:
            reasons.append("validation_rmse_exceeds_limit")
    model["validationMetrics"] = metrics
    model["accepted"] = not reasons
    model["acceptanceFailureReasons"] = reasons
    model["quantitativePublicationAllowed"] = model["accepted"]
    return model


def _timing_provenance(gcov_dates: Sequence[str], samples: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    plot_dates = sorted({str(sample["referenceDate"]) for sample in samples if sample.get("referenceDate")})
    deltas = []
    if gcov_dates and plot_dates:
        g_dates = [_parse_date(value, "GCOV acquisition date") for value in gcov_dates]
        for sample in samples:
            if not sample.get("referenceDate"):
                continue
            plot_date = _parse_date(str(sample["referenceDate"]), "plot reference date")
            nearest_delta = min(abs((plot_date - gcov_date).days) for gcov_date in g_dates)
            deltas.append({"plotId": str(sample["plotId"]), "nearestGcovDeltaDays": nearest_delta})
    return {
        "gcovAcquisitionDates": list(gcov_dates),
        "plotReferenceDateRange": [plot_dates[0], plot_dates[-1]] if plot_dates else None,
        "perPlotNearestGcovDeltaDays": deltas,
        "maxAbsoluteDateOffsetDays": max((entry["nearestGcovDeltaDays"] for entry in deltas), default=None),
    }


def _gcov_provenance(features: GcovFeatures, gcov_manifest_path: str | Path, plot_path: str | Path | None = None) -> dict[str, Any]:
    manifest = features.manifest
    provenance = {
        "sourceBasis": _source_basis(manifest),
        "gcovManifest": {
            "event": manifest.get("event"),
            "runId": manifest.get("runId"),
            "product": manifest.get("product"),
            "productId": manifest.get("productId"),
            "sensor": manifest.get("sensor"),
            "frequency": manifest.get("frequency"),
            "processingVersion": manifest.get("processingVersion"),
            "acquisitionDates": _source_dates(manifest),
            "manifestSha256": core.digest(gcov_manifest_path),
            "assets": {
                term: {"path": manifest["assets"][term].get("path"), "sha256": manifest["assets"][term]["sha256"], "units": _term_units(manifest, manifest["assets"][term], term)}
                for term in ("HHHH", "HVHV")
            },
        },
    }
    if plot_path is not None:
        provenance["referencePlots"] = {"sha256": core.digest(plot_path), "filename": Path(plot_path).name}
    return provenance


def _synthetic_sources(*kinds_and_lineage: tuple[Any, Any]) -> list[Any]:
    found: list[Any] = []
    for kind, lineage in kinds_and_lineage:
        if kind == "synthetic":
            found.append({"dataKind": "synthetic"})
        if isinstance(lineage, list):
            found.extend(lineage)
        elif lineage is True:
            found.append({"dataKind": "synthetic"})
        elif isinstance(lineage, (str, dict)) and lineage:
            found.append(lineage)
    return found


def train_calibration(
    gcov_manifest_path: str | Path,
    plots_path: str | Path,
    config_path: str | Path,
    *,
    output_root: str | Path | None = None,
) -> Path:
    """Aggregate reference polygons, train/validate, and publish a model report."""
    config = _read_json(config_path)
    gcov = read_gcov_features(gcov_manifest_path)
    event = gcov.manifest.get("event")
    if not isinstance(event, str) or not event.strip():
        raise BiomassError("GCOV manifest must identify the event used for calibration")
    source_basis = _source_basis(gcov.manifest)
    gcov_dates = _source_dates(gcov.manifest)
    samples, sampling = aggregate_reference_plots(gcov, plots_path, config)
    timing = _timing_provenance(gcov_dates, samples)
    provenance = _gcov_provenance(gcov, gcov_manifest_path, plots_path)
    model = fit_calibration_model(samples, config=config, source_provenance=provenance, timing_provenance=timing)
    model["samplingReport"] = sampling
    model["event"] = event
    model["sourceBasis"] = source_basis
    synthetic_sources = _synthetic_sources(
        (gcov.manifest.get("dataKind"), gcov.manifest.get("syntheticLineage")),
        (config.get("dataKind"), config.get("syntheticLineage")),
    )
    data_kind = "synthetic" if synthetic_sources else "derived"
    metadata = {
        "dataKind": data_kind,
        "syntheticLineage": synthetic_sources,
        "upstreamRunIds": [gcov.manifest.get("runId")] if gcov.manifest.get("runId") else [],
        "sourceHashes": {
            "gcovManifest": core.digest(gcov_manifest_path),
            "referencePlots": core.digest(plots_path),
            "config": core.digest(config_path),
        },
        "algorithm": MODEL_NAME,
        "algorithmVersion": MODEL_VERSION,
        "event": event,
        "units": {"inputFeatures": "dB", "target": AGB_UNITS},
        "modelAccepted": model["accepted"],
        "validationMetrics": model["validationMetrics"],
        "acceptanceLimits": model["acceptanceLimits"],
        "warnings": model["acceptanceFailureReasons"],
    }

    def writer(stage: Path) -> dict[str, str]:
        (stage / "model.json").write_text(json.dumps(model, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        return {"model": "model.json"}

    manifest_path = core.publish(
        event, "biomass_calibration", metadata, writer,
        output_root=output_root, review=False,
    )
    return Path(manifest_path)


def _load_calibration_model(path: str | Path) -> tuple[dict[str, Any], dict[str, Any]]:
    if not Path(path).is_file():
        raise CalibrationUnavailableError(f"Calibration unavailable: model manifest not found at {path}")
    try:
        manifest = core.load_manifest(path)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
        raise CalibrationUnavailableError(f"Calibration unavailable: invalid model manifest ({exc})") from exc
    if "model" not in manifest.get("assets", {}):
        raise CalibrationUnavailableError("Calibration unavailable: model asset is missing")
    try:
        model = _read_json(core.asset_path(manifest, "model"))
    except (OSError, BiomassError, ValueError) as exc:
        raise CalibrationUnavailableError(f"Calibration unavailable: cannot read model asset ({exc})") from exc
    if model.get("model") != MODEL_NAME or model.get("modelVersion") != MODEL_VERSION:
        raise CalibrationUnavailableError("Calibration unavailable: unsupported biomass model profile/version")
    if model.get("accepted") is not True or model.get("quantitativePublicationAllowed") is not True:
        reasons = model.get("acceptanceFailureReasons") or ["model_not_accepted"]
        raise CalibrationUnavailableError("Calibration unavailable: model did not pass its documented acceptance limits (" + ", ".join(map(str, reasons)) + ")")
    if not isinstance(model.get("validationMetrics"), dict) or not isinstance(model.get("acceptanceLimits"), dict):
        raise CalibrationUnavailableError("Calibration unavailable: independent validation or owner-supplied acceptance limits are missing")
    return model, manifest


def _predict_array(gcov: GcovFeatures, model: Mapping[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    if tuple(model.get("features", ())) != FEATURE_NAMES:
        raise CalibrationUnavailableError("Calibration unavailable: model does not contain the required HHHH/HVHV features")
    feature_arrays = [gcov.features_db[name] for name in FEATURE_NAMES]
    domain = gcov.valid_mask.copy()
    ranges = model.get("calibratedFeatureRangeDb")
    if not isinstance(ranges, dict):
        raise CalibrationUnavailableError("Calibration unavailable: model has no calibrated feature ranges")
    for index, name in enumerate(FEATURE_NAMES):
        feature_range = ranges.get(name)
        if not isinstance(feature_range, dict):
            raise CalibrationUnavailableError(f"Calibration unavailable: calibrated range for {name} is missing")
        try:
            lower, upper = float(feature_range["min"]), float(feature_range["max"])
        except (KeyError, TypeError, ValueError) as exc:
            raise CalibrationUnavailableError(f"Calibration unavailable: calibrated range for {name} is invalid") from exc
        if not math.isfinite(lower) or not math.isfinite(upper) or lower > upper:
            raise CalibrationUnavailableError(f"Calibration unavailable: calibrated range for {name} is invalid")
        values = feature_arrays[index]
        domain &= np.isfinite(values) & (values >= lower) & (values <= upper)
    result = np.full(gcov.valid_mask.shape, np.nan, dtype="float64")
    if domain.any():
        means = np.asarray(model["standardization"]["mean"], dtype="float64")
        scales = np.asarray(model["standardization"]["std"], dtype="float64")
        coefficients = np.asarray(model["coefficients"], dtype="float64")
        if means.shape != (2,) or scales.shape != (2,) or coefficients.shape != (2,) or not np.isfinite(means).all() or not np.isfinite(scales).all() or np.any(scales <= 0) or not np.isfinite(coefficients).all():
            raise CalibrationUnavailableError("Calibration unavailable: model coefficients or standardization values are invalid")
        x = np.column_stack([feature_arrays[i][domain] for i in range(2)])
        log_prediction = float(model["interceptLog1pAgb"]) + ((x - means) / scales) @ coefficients
        result[domain] = _inverse_log_agb(log_prediction)
    return result, domain


def _regional_metrics(
    regions_path: str | Path | None,
    biomass: np.ndarray,
    applicability: np.ndarray,
    gcov: GcovFeatures,
) -> list[dict[str, Any]]:
    if regions_path is None:
        return []
    path = Path(regions_path)
    try:
        collection = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BiomassError(f"Cannot read biomass region GeoJSON {path}: {exc}") from exc
    if not isinstance(collection, dict) or collection.get("type") != "FeatureCollection" or not isinstance(collection.get("features"), list):
        raise BiomassError("Biomass regions must be a GeoJSON FeatureCollection")
    source_crs = _geojson_crs(collection, {})
    transform = Affine(*gcov.grid["transform"])
    shape_out = (gcov.grid["height"], gcov.grid["width"])
    dates = _source_dates(gcov.manifest)
    native_resolution = gcov.manifest.get("nativeResolution")
    resolution = gcov.manifest.get("nativeResolutionMetres") or gcov.manifest.get("resolutionMetres")
    if resolution is None and isinstance(native_resolution, dict) and str(native_resolution.get("units", "")).lower() in {"m", "metre", "meter", "metres", "meters"}:
        resolution = {axis: native_resolution[axis] for axis in ("x", "y") if axis in native_resolution}
    if resolution is None:
        try:
            raster_crs = rasterio.crs.CRS.from_string(gcov.grid["crs"])
            if raster_crs.is_projected and raster_crs.linear_units.lower() in {"metre", "meter", "metres", "meters"}:
                resolution = [abs(float(transform.a)), abs(float(transform.e))]
        except Exception:
            resolution = None
    results = []
    ids: set[str] = set()
    for index, feature in enumerate(collection["features"]):
        if not isinstance(feature, dict) or not isinstance(feature.get("properties"), dict) or not isinstance(feature.get("geometry"), dict):
            raise BiomassError(f"Biomass region feature {index} needs properties and polygon geometry")
        region_id = feature["properties"].get("regionId")
        if not isinstance(region_id, str) or not region_id.strip() or region_id in ids:
            raise BiomassError("Biomass regions need unique nonempty regionId values")
        ids.add(region_id)
        raster_geometry = _geometry_to_raster_crs(feature["geometry"], source_crs, gcov.grid["crs"])
        inside = geometry_mask([raster_geometry], out_shape=shape_out, transform=transform, invert=True, all_touched=False)
        valid = inside & applicability & np.isfinite(biomass)
        count = int(valid.sum())
        if count:
            metric: float | None = float(np.median(biomass[valid]))
            reason = None
        else:
            metric = None
            reason = "no_valid_calibrated_pixels_inside_region"
        results.append({
            "regionId": region_id,
            "medianMgPerHa": metric,
            "units": AGB_UNITS,
            "validPixelCount": count,
            "totalPixelCount": int(inside.sum()),
            "observationStartDate": dates[0],
            "observationEndDate": dates[-1],
            "resolutionMetres": resolution,
            "sourceRunId": gcov.manifest.get("runId"),
            "reason": reason,
        })
    return results


def predict_biomass(
    gcov_manifest_path: str | Path,
    calibration_manifest_path: str | Path,
    *,
    output_root: str | Path | None = None,
    regions_path: str | Path | None = None,
) -> Path:
    """Publish calibrated Mg/ha estimates only inside the model's domain."""
    model, calibration_manifest = _load_calibration_model(calibration_manifest_path)
    gcov = read_gcov_features(gcov_manifest_path)
    gcov_event = gcov.manifest.get("event")
    if not isinstance(gcov_event, str) or not gcov_event.strip() or gcov_event != calibration_manifest.get("event") or gcov_event != model.get("event"):
        raise CalibrationUnavailableError(
            "Calibration unavailable: GCOV event does not match the event and source dataset recorded by the calibration"
        )
    try:
        current_basis = _source_basis(gcov.manifest)
    except BiomassError as exc:
        raise CalibrationUnavailableError(f"Calibration unavailable: invalid GCOV source basis ({exc})") from exc
    trained_basis = model.get("sourceBasis")
    if not isinstance(trained_basis, dict):
        raise CalibrationUnavailableError("Calibration unavailable: model does not record its GCOV source basis")
    if current_basis != trained_basis:
        differing = sorted(key for key in set(current_basis) | set(trained_basis) if current_basis.get(key) != trained_basis.get(key))
        raise CalibrationUnavailableError(
            "Calibration unavailable: GCOV source basis differs from the calibration in " + ", ".join(differing)
        )
    biomass, applicability = _predict_array(gcov, model)
    regional_metrics = _regional_metrics(regions_path, biomass, applicability, gcov)
    valid_values = biomass[applicability]
    stats: dict[str, Any]
    if valid_values.size:
        stats = {
            "validPixelCount": int(valid_values.size),
            "minMgPerHa": float(np.min(valid_values)),
            "medianMgPerHa": float(np.median(valid_values)),
            "maxMgPerHa": float(np.max(valid_values)),
        }
    else:
        stats = {"validPixelCount": 0, "minMgPerHa": None, "medianMgPerHa": None, "maxMgPerHa": None}
    source_kind = gcov.manifest.get("dataKind")
    synthetic_sources = _synthetic_sources(
        (source_kind, gcov.manifest.get("syntheticLineage")),
        (calibration_manifest.get("dataKind"), calibration_manifest.get("syntheticLineage")),
    )
    metadata = {
        "dataKind": "synthetic" if synthetic_sources else "derived",
        "syntheticLineage": synthetic_sources,
        "upstreamRunIds": [v for v in (gcov.manifest.get("runId"), calibration_manifest.get("runId")) if v],
        "sourceHashes": {
            "gcovManifest": core.digest(gcov_manifest_path),
            "calibrationManifest": core.digest(calibration_manifest_path),
            **{f"gcov_{term}": gcov.manifest["assets"][term]["sha256"] for term in ("HHHH", "HVHV")},
        },
        "algorithm": MODEL_NAME,
        "algorithmVersion": MODEL_VERSION,
        "calibrationRunId": calibration_manifest.get("runId"),
        "calibrationEvent": model["event"],
        "sourceBasis": current_basis,
        "calibrationModelName": model["model"],
        "validationMetrics": model["validationMetrics"],
        "acceptanceLimits": model["acceptanceLimits"],
        "acceptanceDecision": "accepted",
        "units": {"biomassMgPerHa": AGB_UNITS, "applicabilityMask": "1=inside calibrated feature range; 0=outside/no valid input"},
        "featureNames": list(FEATURE_NAMES),
        "calibratedFeatureRangeDb": model["calibratedFeatureRangeDb"],
        "applicabilityRule": "Both positive HHHH/HVHV dB terms must be within the training-plot feature ranges; invalid and out-of-range pixels are nodata in biomassMgPerHa.",
        "grid": gcov.grid,
        "nativeResolution": gcov.manifest.get("nativeResolution"),
        "nativeResolutionMetres": gcov.manifest.get("nativeResolutionMetres"),
        "validCoverage": {"validPixelCount": int(applicability.sum()), "totalPixelCount": int(applicability.size)},
        "statistics": stats,
        "regionalMetrics": regional_metrics,
        "sources": _gcov_provenance(gcov, gcov_manifest_path),
        "warnings": [] if applicability.any() else ["No pixels are both valid and inside the calibrated feature range; published biomass coverage is empty."],
    }
    event = gcov.manifest.get("event") or calibration_manifest.get("event") or "unregistered_event"

    def writer(stage: Path) -> dict[str, str]:
        core.write_raster(stage / "biomass_mg_per_ha.tif", biomass.astype("float32"), gcov.grid)
        core.write_raster(stage / "applicability_mask.tif", applicability.astype("float32"), gcov.grid)
        return {"biomassMgPerHa": "biomass_mg_per_ha.tif", "applicabilityMask": "applicability_mask.tif"}

    manifest_path = core.publish(str(event), "biomass", metadata, writer, output_root=output_root, review=False)
    return Path(manifest_path)


def _load_region_records(path: str | Path, expected_name: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    data = _read_json(path)
    if "assets" in data:
        # If the biomass side is an actual product manifest, verify all of its
        # published hashes before trusting embedded regional summaries.
        try:
            data = core.load_manifest(path)
        except (OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
            raise BiomassError(f"Invalid {expected_name} product manifest: {exc}") from exc
    records = data.get("regionalMetrics", data.get("regions", data.get("regionStats")))
    if not isinstance(records, list):
        raise BiomassError(f"{expected_name} must contain regionalMetrics, regions, or regionStats")
    ids = set()
    normalized = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise BiomassError(f"{expected_name} record {index} must be an object")
        region = record.get("regionId")
        if not isinstance(region, str) or not region.strip() or region in ids:
            raise BiomassError(f"{expected_name} needs unique nonempty regionId values")
        ids.add(region)
        normalized.append(dict(record))
    return normalized, data


def _validated_date_range(record: Mapping[str, Any], stream: str) -> tuple[str, str]:
    start = record.get("observationStartDate")
    end = record.get("observationEndDate")
    if start is None and end is None and stream == "ground motion":
        epochs = record.get("epochs")
        if isinstance(epochs, list) and epochs:
            parsed = [_parse_date(epoch, "ground-motion epoch") for epoch in epochs]
            return min(parsed).isoformat(), max(parsed).isoformat()
    start_date = _parse_date(start, f"{stream} observationStartDate")
    end_date = _parse_date(end, f"{stream} observationEndDate")
    if start_date > end_date:
        raise BiomassError(f"{stream} observation date range is reversed")
    return start_date.isoformat(), end_date.isoformat()


def fuse_regional_metrics(
    biomass_regions: Sequence[Mapping[str, Any]],
    ground_motion_regions: Sequence[Mapping[str, Any]],
    *,
    biomass_source: Mapping[str, Any] | None = None,
    ground_motion_source: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Join independently sourced regional biomass and LOS-rate summaries."""
    biomass_by_id: dict[str, dict[str, Any]] = {}
    motion_by_id: dict[str, dict[str, Any]] = {}
    for stream, records, target in (
        ("biomass", biomass_regions, biomass_by_id),
        ("ground motion", ground_motion_regions, motion_by_id),
    ):
        for record in records:
            region = record.get("regionId")
            if not isinstance(region, str) or not region.strip() or region in target:
                raise BiomassError(f"{stream} regional statistics need unique regionId values")
            _validated_date_range(record, stream)
            target[region] = dict(record)
    rows = []
    for region in sorted(set(biomass_by_id) | set(motion_by_id)):
        biomass = biomass_by_id.get(region)
        motion = motion_by_id.get(region)
        biomass_record = None
        motion_record = None
        if biomass is not None:
            metric = biomass.get("medianMgPerHa")
            if metric is not None and (not isinstance(metric, (int, float)) or not math.isfinite(float(metric)) or float(metric) < 0):
                raise BiomassError(f"Biomass region {region} medianMgPerHa must be nonnegative or null")
            biomass_record = {
                "medianMgPerHa": metric,
                "units": AGB_UNITS,
                "validPixelCount": biomass.get("validPixelCount"),
                "observationStartDate": biomass["observationStartDate"],
                "observationEndDate": biomass["observationEndDate"],
                "resolutionMetres": biomass.get("resolutionMetres"),
                "sourceRunId": biomass.get("sourceRunId"),
                "reason": biomass.get("reason") if metric is None else None,
            }
        if motion is not None:
            metric = motion.get("medianLosRateMmPerYear")
            if metric is not None and (not isinstance(metric, (int, float)) or not math.isfinite(float(metric))):
                raise BiomassError(f"Ground-motion region {region} rateMmPerYear must be finite or null")
            if metric is None:
                metric = motion.get("rateMmPerYear")
                if metric is not None and (not isinstance(metric, (int, float)) or not math.isfinite(float(metric))):
                    raise BiomassError(f"Ground-motion region {region} rateMmPerYear must be finite or null")
            motion_start, motion_end = _validated_date_range(motion, "ground motion")
            motion_record = {
                "medianLosRateMmPerYear": metric,
                "units": "mm/year LOS (positive away from satellite)",
                "validPixelCount": motion.get("validPixelCount", motion.get("validRateCellCount")),
                "selectedCellCount": motion.get("selectedCellCount"),
                "observationStartDate": motion_start,
                "observationEndDate": motion_end,
                "resolutionMetres": motion.get("resolutionMetres"),
                "sourceRunId": motion.get("sourceRunId"),
                "reason": motion.get("reason") if metric is None else None,
            }
        rows.append({"regionId": region, "biomass": biomass_record, "groundMotionLOS": motion_record})
    return {
        "schemaVersion": "1.0",
        "product": "roots_faults_regional_fusion",
        "interpretation": "Side-by-side regional summaries from independent biomass and ground-motion observations. Association only; no causal attribution, combined hazard score, or vertical-motion inference.",
        "biomassSource": dict(biomass_source or {}),
        "groundMotionSource": dict(ground_motion_source or {}),
        "regions": rows,
    }


def publish_regional_fusion(
    event: str,
    biomass_regions_path: str | Path,
    ground_motion_regions_path: str | Path,
    *,
    output_root: str | Path | None = None,
) -> Path:
    """Publish a joined, lineage-preserving regional summary table."""
    biomass_regions, biomass_source = _load_region_records(biomass_regions_path, "biomass regional statistics")
    motion_regions, motion_source = _load_region_records(ground_motion_regions_path, "ground-motion region stats")
    for stream_name, source in (("biomass", biomass_source), ("ground motion", motion_source)):
        if source.get("event") != event:
            raise BiomassError(f"{stream_name} source event must match requested fusion event {event!r}")
        if source.get("dataKind") not in {"observed", "derived", "scenario", "synthetic"}:
            raise BiomassError(f"{stream_name} source must declare dataKind")
    motion_resolution = motion_source.get("nativeResolutionMetres")
    biomass_resolution = biomass_source.get("nativeResolutionMetres")
    biomass_regions = [
        {**row, "resolutionMetres": row.get("resolutionMetres", biomass_resolution), "sourceRunId": row.get("sourceRunId", biomass_source.get("runId"))}
        for row in biomass_regions
    ]
    motion_regions = [
        {**row, "resolutionMetres": row.get("resolutionMetres", motion_resolution), "sourceRunId": row.get("sourceRunId", motion_source.get("runId"))}
        for row in motion_regions
    ]
    result = fuse_regional_metrics(
        biomass_regions, motion_regions,
        biomass_source={k: biomass_source.get(k) for k in ("runId", "dataKind", "observationDates", "sourceHashes") if k in biomass_source},
        ground_motion_source={k: motion_source.get(k) for k in ("runId", "dataKind", "observationDates", "sourceHashes") if k in motion_source},
    )
    synthetic_sources = _synthetic_sources(
        (biomass_source.get("dataKind"), biomass_source.get("syntheticLineage")),
        (motion_source.get("dataKind"), motion_source.get("syntheticLineage")),
    )
    result["event"] = event
    result["dataKind"] = "synthetic" if synthetic_sources else "derived"
    metadata = {
        "dataKind": result["dataKind"],
        "syntheticLineage": synthetic_sources,
        "upstreamRunIds": [v for v in (biomass_source.get("runId"), motion_source.get("runId")) if v],
        "sourceHashes": {"biomassRegionStats": core.digest(biomass_regions_path), "groundMotionRegionStats": core.digest(ground_motion_regions_path)},
        "algorithm": "region_id_join_side_by_side_v1",
        "algorithmVersion": "1.0",
        "event": event,
        "units": {"biomass": AGB_UNITS, "groundMotionLOS": "mm/year"},
        "regionalFusion": result,
        "warnings": ["Association only; no causal attribution or combined hazard score is produced."],
    }

    def writer(stage: Path) -> dict[str, str]:
        (stage / "regional_fusion.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        return {"regionalFusion": "regional_fusion.json"}

    return Path(core.publish(event, "roots_faults_fusion", metadata, writer, output_root=output_root, review=False))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Calibrate, predict, or fuse validated GCOV biomass and regional LOS summaries.")
    sub = parser.add_subparsers(dest="command", required=True)
    train = sub.add_parser("train", help="aggregate reference polygons and train/validate the fixed GCOV ridge profile")
    train.add_argument("--gcov", required=True, help="hash-bound normalized GCOV product manifest with HHHH/HVHV rasters")
    train.add_argument("--plots", required=True, help="GeoJSON FeatureCollection of polygon reference plots")
    train.add_argument("--config", required=True, help="JSON with splitProvenance, referenceTimingNotes, and owner-supplied acceptanceLimits")
    train.add_argument("--output-root", help="product root (default backend/data/output)")
    predict = sub.add_parser("predict", help="publish Mg/ha only from a passing calibration model")
    predict.add_argument("--gcov", required=True, help="hash-bound normalized GCOV product manifest")
    predict.add_argument("--calibration", required=True, help="published biomass calibration manifest")
    predict.add_argument("--regions", help="optional GeoJSON region polygons for finite regional biomass summaries")
    predict.add_argument("--output-root", help="product root (default backend/data/output)")
    fuse = sub.add_parser("fuse", help="join independent biomass and ground-motion regional stats")
    fuse.add_argument("--event", required=True, help="registered event ID")
    fuse.add_argument("--biomass-regions", required=True, help="JSON wrapper with regions and observation date ranges")
    fuse.add_argument("--ground-motion-regions", required=True, help="JSON wrapper with regions and observation date ranges")
    fuse.add_argument("--output-root", help="product root (default backend/data/output)")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "train":
            result = train_calibration(args.gcov, args.plots, args.config, output_root=args.output_root)
        elif args.command == "predict":
            result = predict_biomass(args.gcov, args.calibration, output_root=args.output_root, regions_path=args.regions)
        else:
            result = publish_regional_fusion(args.event, args.biomass_regions, args.ground_motion_regions, output_root=args.output_root)
    except (BiomassError, CalibrationUnavailableError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(result)
    return 0


__all__ = [
    "AGB_UNITS",
    "BiomassError",
    "CalibrationUnavailableError",
    "FEATURE_NAMES",
    "GcovFeatures",
    "aggregate_reference_plots",
    "fit_calibration_model",
    "fuse_regional_metrics",
    "main",
    "predict_biomass",
    "publish_regional_fusion",
    "read_gcov_features",
    "train_calibration",
]
