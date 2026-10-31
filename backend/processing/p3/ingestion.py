"""Explicit NISAR GUNW/GCOV ingestion adapters.

The input JSON is a source manifest, not a discovery recipe. It names one
local product file, one versioned profile, every raster dataset, and the
coordinate datasets that define its grid. This module does not download data
or search an HDF5/NetCDF file for plausible-looking arrays.

Minimal source manifest shape::

    {
      "configVersion": "1.0", "event": "pilot_event",
      "productType": "GUNW", "dataKind": "observed",
      "source": {
        "path": "product.h5", "sha256": "<64 lowercase hex chars>",
        "productId": "provider-product-id", "sensor": "NISAR",
        "frequency": "L", "polarization": "HH", "orbit": "...",
        "frame": "...", "processingVersion": "...", "maturity": "...",
        "acquisitionDates": ["...Z", "...Z"],
        "wavelengthMetres": 0.24, "wavelengthUnits": "metre",
        "phaseToAwaySign": 1, "phaseUnits": "radian",
        "correctionsApplied": [], "quality": {}
      },
      "sourceProfile": {
        "id": "provider-layout-v1", "version": "1",
        "adapter": "hdf5", "status": "needs-review", "evidence": [],
        "arrayAxisOrder": "yx",
        "crs": "EPSG:32651",
        "coordinateDatasets": {"x": "/grid/x", "y": "/grid/y"},
        "datasets": {
          "phase": {"path": "/science/phase", "units": "radian"},
          "coherence": {"path": "/science/coherence", "units": "1"},
          "components": {"path": "/science/components", "units": "label"}
        }
      }
    }

GCOV profiles map ``HHHH`` and ``HVHV`` in ``datasets``. Optional GUNW
``corrections`` and ``geometry`` maps name their datasets explicitly. A
``window`` may specify half-open ``rowStart``, ``rowStop``, ``colStart``, and
``colStop`` indices to read a subset. Profile status remains needs-review
unless the source manifest supplies a verified status and evidence references;
publication itself never marks real observations as validated.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import numpy as np
from pyproj import CRS

from . import core


CODE_VERSION = "kobe-p3-ingestion/1.0"
_DATA_KINDS = {"observed", "derived", "scenario", "synthetic"}
_PRODUCT_TYPES = {"GUNW", "GCOV"}
_UNIT_ALIASES = {
    "phase": {"rad", "radian", "radians"},
    "coherence": {"1", "unitless", "dimensionless", "ratio"},
    "components": {"1", "unitless", "dimensionless", "label", "labels", "integer", "int"},
    "qualityMask": {"1", "unitless", "dimensionless", "flag", "flags", "boolean", "bool"},
    "HHHH": {"linear_power", "power", "1", "unitless", "dimensionless"},
    "HVHV": {"linear_power", "power", "1", "unitless", "dimensionless"},
    "wavelength": {"m", "metre", "metres", "meter", "meters"},
}


def _text(value: Any, label: str) -> str:
    if not isinstance(value, (str, int)) or isinstance(value, bool) or not str(value).strip():
        raise ValueError(f"{label} must be a non-empty string or integer")
    return str(value).strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _decode(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="strict")
    if isinstance(value, np.ndarray):
        if value.ndim == 0:
            return _decode(value.item())
        return [_decode(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return _decode(value.item())
    if isinstance(value, (tuple, list)):
        return [_decode(item) for item in value]
    return value


def _parse_timestamp(value: Any, label: str) -> tuple[str, datetime]:
    raw = _text(value, label)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO-8601 timestamp with timezone") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{label} must include a timezone offset")
    utc = parsed.astimezone(timezone.utc)
    return utc.isoformat().replace("+00:00", "Z"), utc


def _dates(value: Any, product_type: str) -> list[str]:
    expected = 2 if product_type == "GUNW" else 1
    if not isinstance(value, list) or len(value) != expected:
        description = "[reference, secondary] timestamps" if product_type == "GUNW" else "one acquisition timestamp"
        raise ValueError(f"source.acquisitionDates must contain {description}")
    parsed = [_parse_timestamp(item, f"source.acquisitionDates[{i}]") for i, item in enumerate(value)]
    if product_type == "GUNW" and parsed[0][1] >= parsed[1][1]:
        raise ValueError("GUNW acquisitionDates must be chronological [reference, secondary]")
    return [item[0] for item in parsed]


def _normal_unit(value: Any) -> str:
    return re.sub(r"\s+", "", str(_decode(value)).strip().lower())


def _check_declared_unit(actual: Any, declared: Any, label: str, kind: str | None = None) -> str:
    if declared is None:
        raise ValueError(f"{label} must declare units in the source profile")
    expected = _normal_unit(declared)
    if not expected:
        raise ValueError(f"{label} units cannot be empty")
    allowed = _UNIT_ALIASES.get(kind) if kind else None
    if allowed and expected not in allowed:
        raise ValueError(f"{label} units {declared!r} are unsupported")
    if actual is not None:
        embedded = _normal_unit(actual)
        if embedded != expected:
            aliases = allowed or {expected}
            generic_groups = (
                {"m", "metre", "metres", "meter", "meters"},
                {"km", "kilometre", "kilometres", "kilometer", "kilometers"},
                {"degree", "degrees", "deg"},
                {"m/s", "mps", "metres/second", "meters/second"},
            )
            equivalent = any(embedded in group and expected in group for group in generic_groups)
            if (embedded not in aliases or expected not in aliases) and not equivalent:
                raise ValueError(f"{label} units in the file ({_decode(actual)!r}) conflict with profile ({declared!r})")
    return str(_decode(declared))


def _resolve_source(config_path: Path, source: Mapping[str, Any]) -> Path:
    raw_path = Path(_text(source.get("path"), "source.path")).expanduser()
    if not raw_path.is_absolute():
        raw_path = config_path.parent / raw_path
    try:
        path = raw_path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise OSError(f"Source product does not exist: {raw_path}") from exc
    if not path.is_file():
        raise ValueError("source.path must refer to a local file")
    expected = source.get("sha256")
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError("source.sha256 must be a lowercase SHA-256 digest")
    actual = _sha256(path)
    if actual != expected:
        raise ValueError("source.sha256 does not match the local provider file")
    return path


def _validate_profile(profile: Any) -> dict[str, Any]:
    if not isinstance(profile, dict):
        raise ValueError("sourceProfile must be an object")
    required = ("id", "version", "adapter", "crs", "coordinateDatasets", "datasets", "arrayAxisOrder")
    absent = [key for key in required if key not in profile]
    if absent:
        raise ValueError("sourceProfile is missing: " + ", ".join(absent))
    adapter = _text(profile["adapter"], "sourceProfile.adapter").lower()
    if adapter not in {"hdf5", "aria-netcdf"}:
        raise ValueError("sourceProfile.adapter must be 'hdf5' or 'aria-netcdf'")
    crs_text = _text(profile["crs"], "sourceProfile.crs")
    try:
        crs = CRS.from_user_input(crs_text)
    except Exception as exc:
        raise ValueError(f"sourceProfile.crs is invalid: {crs_text!r}") from exc
    coordinates = profile["coordinateDatasets"]
    if not isinstance(coordinates, dict) or set(coordinates) != {"x", "y"}:
        raise ValueError("sourceProfile.coordinateDatasets must explicitly name x and y datasets")
    coordinates = {axis: _text(path, f"sourceProfile.coordinateDatasets.{axis}") for axis, path in coordinates.items()}
    if profile["arrayAxisOrder"] != "yx":
        raise ValueError("sourceProfile.arrayAxisOrder must be 'yx'; other layouts need a separately verified adapter")
    datasets = profile["datasets"]
    if not isinstance(datasets, dict):
        raise ValueError("sourceProfile.datasets must be an object mapping normalized asset names to dataset paths")
    status = profile.get("status", "needs-review")
    if status not in {"needs-review", "verified"}:
        raise ValueError("sourceProfile.status must be 'needs-review' or 'verified'")
    evidence = profile.get("evidence", [])
    if not isinstance(evidence, list) or any(not isinstance(item, str) or not item.strip() for item in evidence):
        raise ValueError("sourceProfile.evidence must be an array of non-empty references")
    if status == "verified" and not evidence:
        raise ValueError("A verified source profile requires explicit evidence references")
    return {
        **profile,
        "id": _text(profile["id"], "sourceProfile.id"),
        "version": _text(profile["version"], "sourceProfile.version"),
        "adapter": adapter,
        "crs": crs.to_string(),
        "coordinates": coordinates,
        "arrayAxisOrder": "yx",
        "datasets": datasets,
        "status": status,
        "evidence": [item.strip() for item in evidence],
    }


def _descriptor(raw: Any, label: str, *, required_units: bool = True) -> dict[str, Any]:
    if isinstance(raw, str):
        result: dict[str, Any] = {"path": raw}
    elif isinstance(raw, dict):
        result = dict(raw)
    else:
        raise ValueError(f"{label} must be a dataset path or an object containing path and units")
    result["path"] = _text(result.get("path"), f"{label}.path")
    if required_units and result.get("units") is None:
        raise ValueError(f"{label}.units must be declared explicitly")
    return result


def _window(profile: Mapping[str, Any], height: int, width: int) -> tuple[slice, slice]:
    raw = profile.get("window")
    if raw is None:
        return slice(0, height), slice(0, width)
    if not isinstance(raw, dict):
        raise ValueError("sourceProfile.window must use rowStart/rowStop/colStart/colStop")
    names = ("rowStart", "rowStop", "colStart", "colStop")
    if any(name not in raw for name in names):
        raise ValueError("sourceProfile.window must define all four half-open bounds")
    values = []
    for name in names:
        value = raw[name]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"sourceProfile.window.{name} must be an integer")
        values.append(value)
    row_start, row_stop, col_start, col_stop = values
    if not (0 <= row_start < row_stop <= height and 0 <= col_start < col_stop <= width):
        raise ValueError("sourceProfile.window bounds are empty or outside the source grid")
    return slice(row_start, row_stop), slice(col_start, col_stop)


def _check_regular_axis(values: np.ndarray, name: str) -> float:
    values = np.asarray(values, dtype="float64")
    if values.ndim != 1 or values.size < 2 or not np.all(np.isfinite(values)):
        raise ValueError(f"{name} coordinate dataset must be a finite one-dimensional array of length >= 2")
    differences = np.diff(values)
    step = float(np.median(differences))
    if step == 0 or not np.all(np.sign(differences) == np.sign(step)):
        raise ValueError(f"{name} coordinates must be strictly monotonic")
    tolerance = max(abs(step) * 1e-6, 1e-10)
    if not np.allclose(differences, step, rtol=1e-6, atol=tolerance):
        raise ValueError(f"{name} coordinates are not a regular raster axis")
    return step


def _grid(x: np.ndarray, y: np.ndarray, crs_text: str) -> tuple[dict[str, Any], tuple[bool, bool], dict[str, Any]]:
    dx = _check_regular_axis(x, "x")
    dy = _check_regular_axis(y, "y")
    flip_x = dx < 0
    flip_y = dy > 0
    if flip_x:
        x = x[::-1]
        dx = -dx
    if flip_y:
        y = y[::-1]
        dy = -dy
    grid = {
        "crs": crs_text,
        "transform": [dx, 0.0, float(x[0] - dx / 2), 0.0, dy, float(y[0] - dy / 2)],
        "width": int(x.size),
        "height": int(y.size),
    }
    crs = CRS.from_user_input(crs_text)
    if crs.is_projected:
        axis = crs.axis_info
        factor_x = axis[0].unit_conversion_factor if axis else 1.0
        factor_y = axis[1].unit_conversion_factor if len(axis) > 1 else factor_x
        native_resolution = {"x": abs(dx) * factor_x, "y": abs(dy) * factor_y, "units": "m"}
    elif crs.is_geographic:
        native_resolution = {"x": abs(dx), "y": abs(dy), "units": "degree"}
    else:
        native_resolution = {"x": abs(dx), "y": abs(dy), "units": "crs-unit"}
    return grid, (flip_y, flip_x), native_resolution


def _read_dataset(adapter: Any, raw: Any, label: str, rows: slice, cols: slice) -> tuple[np.ndarray, dict[str, Any]]:
    desc = _descriptor(raw, label)
    data, attrs, shape = adapter.read(desc["path"], rows, cols)
    if len(shape) != 2:
        raise ValueError(f"{label} dataset {desc['path']!r} must be exactly two-dimensional; got shape {shape}")
    if data.ndim != 2:
        raise ValueError(f"{label} dataset {desc['path']!r} did not resolve to a two-dimensional raster")
    unit_kind = label if label in _UNIT_ALIASES else ("phase" if label.startswith("correction ") else None)
    declared_unit = _check_declared_unit(attrs.get("units"), desc.get("units"), f"{label}", unit_kind)
    values = np.asarray(data, dtype="float64")
    valid = np.isfinite(values)
    fill_values = []
    for key in ("_FillValue", "missing_value"):
        if key in attrs:
            fill_values.extend(np.asarray(attrs[key]).reshape(-1).tolist())
    for value in fill_values:
        try:
            if math.isnan(float(value)):
                valid &= np.isfinite(values)
            else:
                valid &= values != float(value)
        except (TypeError, ValueError):
            continue
    scale = float(_decode(attrs.get("scale_factor", 1.0)))
    offset = float(_decode(attrs.get("add_offset", 0.0)))
    if not math.isfinite(scale) or not math.isfinite(offset):
        raise ValueError(f"{label} dataset has non-finite scale_factor/add_offset metadata")
    values = values * scale + offset
    values[~valid] = np.nan
    return values, {"units": declared_unit, "scaleFactor": scale, "addOffset": offset, "sourceDataset": desc["path"]}


class _Hdf5Reader:
    def __init__(self, path: Path):
        try:
            import h5py
        except ImportError as exc:
            raise RuntimeError("HDF5 ingestion requires h5py in the active Python environment") from exc
        self._h5py = h5py
        self._file = h5py.File(path, "r")

    def close(self) -> None:
        self._file.close()

    def _object(self, path: str) -> Any:
        if path not in self._file:
            raise ValueError(f"Explicit HDF5 path {path!r} does not exist in the source file")
        return self._file[path]

    def coordinates(self, paths: Mapping[str, str], rows: slice, cols: slice) -> tuple[np.ndarray, np.ndarray]:
        x = np.asarray(self._object(paths["x"])[cols], dtype="float64")
        y = np.asarray(self._object(paths["y"])[rows], dtype="float64")
        return x, y

    def source_shape(self, paths: Mapping[str, str]) -> tuple[int, int]:
        x = self._object(paths["x"])
        y = self._object(paths["y"])
        if x.ndim != 1 or y.ndim != 1:
            raise ValueError("Explicit HDF5 x/y coordinate datasets must both be one-dimensional")
        return int(y.shape[0]), int(x.shape[0])

    def read(self, path: str, rows: slice, cols: slice) -> tuple[np.ndarray, dict[str, Any], tuple[int, ...]]:
        obj = self._object(path)
        if not isinstance(obj, self._h5py.Dataset):
            raise ValueError(f"Explicit HDF5 path {path!r} must identify a dataset")
        shape = tuple(int(value) for value in obj.shape)
        if len(shape) != 2:
            return np.asarray([]), {key: _decode(value) for key, value in obj.attrs.items()}, shape
        array = np.asarray(obj[rows, cols])
        attrs = {key: _decode(value) for key, value in obj.attrs.items()}
        try:
            # HDF5's implicit/default fill is often zero. It only means missing
            # data when the file explicitly set a user-defined fill value.
            fill_status = obj.id.get_create_plist().fill_value_defined()
            if ("_FillValue" not in attrs
                    and fill_status == self._h5py.h5d.FILL_VALUE_USER_DEFINED
                    and obj.fillvalue is not None):
                attrs["_FillValue"] = _decode(obj.fillvalue)
        except (AttributeError, TypeError):
            pass
        return array, attrs, shape

    def attribute(self, object_path: str, attribute: str) -> Any:
        obj = self._object(object_path)
        if attribute not in obj.attrs:
            raise ValueError(f"Explicit source metadata attribute {object_path}@{attribute} is missing")
        return _decode(obj.attrs[attribute])


class _NetcdfReader:
    def __init__(self, path: Path, coordinate_paths: Mapping[str, str]):
        try:
            import xarray as xr
        except ImportError as exc:
            raise RuntimeError("ARIA NetCDF ingestion requires xarray in the active Python environment") from exc
        try:
            self._dataset = xr.open_dataset(path, decode_cf=False, mask_and_scale=False)
        except Exception as exc:
            raise ValueError(f"Cannot open explicitly selected ARIA NetCDF source: {exc}") from exc
        x = self._variable(coordinate_paths["x"])
        y = self._variable(coordinate_paths["y"])
        if x.ndim != 1 or y.ndim != 1:
            self._dataset.close()
            raise ValueError("Explicit NetCDF x/y coordinate variables must both be one-dimensional")
        self._x_dim = x.dims[0]
        self._y_dim = y.dims[0]

    def close(self) -> None:
        self._dataset.close()

    def _variable(self, path: str) -> Any:
        if path not in self._dataset.variables:
            raise ValueError(f"Explicit NetCDF variable {path!r} does not exist in the source file")
        return self._dataset[path]

    def source_shape(self, paths: Mapping[str, str]) -> tuple[int, int]:
        x, y = self._variable(paths["x"]), self._variable(paths["y"])
        if x.ndim != 1 or y.ndim != 1:
            raise ValueError("Explicit NetCDF x/y coordinate variables must both be one-dimensional")
        return int(y.shape[0]), int(x.shape[0])

    def coordinates(self, paths: Mapping[str, str], rows: slice, cols: slice) -> tuple[np.ndarray, np.ndarray]:
        x, y = self._variable(paths["x"]), self._variable(paths["y"])
        return np.asarray(x.isel({x.dims[0]: cols}).values, dtype="float64"), np.asarray(y.isel({y.dims[0]: rows}).values, dtype="float64")

    def read(self, path: str, rows: slice, cols: slice) -> tuple[np.ndarray, dict[str, Any], tuple[int, ...]]:
        variable = self._variable(path)
        shape = tuple(int(value) for value in variable.shape)
        if len(shape) != 2:
            return np.asarray([]), dict(variable.attrs), shape
        # Profile order is explicitly [y, x]. Do not silently transpose a layout.
        if tuple(variable.dims) != (self._y_dim, self._x_dim):
            raise ValueError(f"NetCDF raster {path!r} dimensions must match explicit [y,x] coordinate dimensions")
        return np.asarray(variable.isel({variable.dims[0]: rows, variable.dims[1]: cols}).values), dict(variable.attrs), shape

    def attribute(self, object_path: str, attribute: str) -> Any:
        if object_path == "/":
            attrs = self._dataset.attrs
        else:
            attrs = self._variable(object_path).attrs
        if attribute not in attrs:
            raise ValueError(f"Explicit source metadata attribute {object_path}@{attribute} is missing")
        return _decode(attrs[attribute])


def _metadata_attr_checks(reader: Any, profile: Mapping[str, Any], source: Mapping[str, Any]) -> None:
    selectors = profile.get("metadataAttributes", {})
    if not isinstance(selectors, dict):
        raise ValueError("sourceProfile.metadataAttributes must be an object")
    for key, selector in selectors.items():
        if key not in source:
            raise ValueError(f"sourceProfile.metadataAttributes maps unknown source field {key!r}")
        if not isinstance(selector, dict) or "object" not in selector or "attribute" not in selector:
            raise ValueError(f"sourceProfile.metadataAttributes.{key} must contain object and attribute")
        actual = reader.attribute(_text(selector["object"], f"metadataAttributes.{key}.object"), _text(selector["attribute"], f"metadataAttributes.{key}.attribute"))
        expected = _decode(source[key])
        if key == "acquisitionDates" and isinstance(actual, (list, tuple)):
            actual = [_parse_timestamp(value, f"embedded {key}")[0] for value in actual]
            matches = actual == expected
        elif isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
            matches = math.isclose(float(actual), float(expected), rel_tol=1e-9, abs_tol=1e-12)
        else:
            matches = actual == expected
        if not matches:
            raise ValueError(f"Embedded source metadata {key!r} conflicts with the input manifest")


def _prepare_inputs(event: str, config_path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], Path, dict[str, Any]]:
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise OSError(f"Cannot read source manifest {config_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Source manifest is not valid JSON: {exc}") from exc
    if not isinstance(config, dict):
        raise ValueError("Source manifest must contain a JSON object")
    if config.get("event") != event:
        raise ValueError(f"Source manifest event must be {event!r}")
    core.safe_name(event)
    product_type = config.get("productType")
    if product_type not in _PRODUCT_TYPES:
        raise ValueError("productType must be GUNW or GCOV")
    data_kind = config.get("dataKind")
    if data_kind not in _DATA_KINDS:
        raise ValueError("dataKind must be observed, derived, scenario, or synthetic")
    source = config.get("source")
    if not isinstance(source, dict):
        raise ValueError("source must be an object containing the provider file and product metadata")
    common = ("productId", "sensor", "frequency", "polarization", "orbit", "frame", "processingVersion", "maturity", "quality")
    missing = [key for key in common if key not in source]
    if missing:
        raise ValueError("source is missing required provenance: " + ", ".join(missing))
    normalized_source = dict(source)
    for key in common[:-1]:
        normalized_source[key] = _text(source[key], f"source.{key}")
    if not isinstance(source["quality"], dict):
        raise ValueError("source.quality must be an object")
    normalized_source["acquisitionDates"] = _dates(source.get("acquisitionDates"), product_type)
    if data_kind != "synthetic" and normalized_source["sensor"].upper() == "NISAR":
        launch = datetime(2025, 7, 30, tzinfo=timezone.utc)
        if any(_parse_timestamp(value, "acquisition date")[1] < launch
               for value in normalized_source["acquisitionDates"]):
            raise ValueError("NISAR observations cannot predate its 2025-07-30 launch; preserve historical sensor identity")
    if product_type == "GUNW":
        wavelength = source.get("wavelengthMetres")
        if isinstance(wavelength, bool) or not isinstance(wavelength, (int, float)) or not math.isfinite(float(wavelength)) or wavelength <= 0:
            raise ValueError("GUNW source.wavelengthMetres must be a positive finite number")
        if _normal_unit(source.get("wavelengthUnits")) not in _UNIT_ALIASES["wavelength"]:
            raise ValueError("GUNW source.wavelengthUnits must identify metres")
        if source.get("phaseToAwaySign") not in (-1, 1) or isinstance(source.get("phaseToAwaySign"), bool):
            raise ValueError("GUNW source.phaseToAwaySign must be explicitly +1 or -1")
        if _normal_unit(source.get("phaseUnits")) not in _UNIT_ALIASES["phase"]:
            raise ValueError("GUNW source.phaseUnits must identify radians")
        applied = source.get("correctionsApplied")
        if not isinstance(applied, list) or any(not isinstance(item, str) or not item.strip() for item in applied):
            raise ValueError("GUNW source.correctionsApplied must be an explicit array of exact correction names")
        normalized_source["wavelengthMetres"] = float(wavelength)
        normalized_source["phaseToAwaySign"] = int(source["phaseToAwaySign"])
        normalized_source["correctionsApplied"] = [item.strip() for item in applied]
    source_path = _resolve_source(config_path, source)
    profile = _validate_profile(config.get("sourceProfile"))
    return config, normalized_source, profile, source_path, {"productType": product_type, "dataKind": data_kind}


def _asset_key(prefix: str, name: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip()).strip("_-")
    if not normalized:
        raise ValueError(f"Cannot derive a safe asset key for {prefix} {name!r}")
    return f"{prefix}_{normalized}"


def _normalize_layer(raw: Any, label: str, reader: Any, rows: slice, cols: slice, flips: tuple[bool, bool]) -> tuple[np.ndarray, dict[str, Any]]:
    values, details = _read_dataset(reader, raw, label, rows, cols)
    if flips[0]:
        values = values[::-1, :]
    if flips[1]:
        values = values[:, ::-1]
    return values, details


def _apply_quality_mask(
    profile: Mapping[str, Any], reader: Any, rows: slice, cols: slice, flips: tuple[bool, bool],
    layers: dict[str, np.ndarray], layer_details: dict[str, dict[str, Any]],
) -> tuple[np.ndarray | None, dict[str, Any] | None]:
    raw_mask = profile.get("qualityMask")
    if raw_mask is None:
        return None, None
    if not isinstance(raw_mask, dict) or "dataset" not in raw_mask:
        raise ValueError("sourceProfile.qualityMask must contain dataset, validValues or invalidValues")
    valid_values, invalid_values = raw_mask.get("validValues"), raw_mask.get("invalidValues")
    if (valid_values is None) == (invalid_values is None):
        raise ValueError("qualityMask must declare exactly one of validValues or invalidValues")
    raw, details = _normalize_layer(raw_mask["dataset"], "qualityMask", reader, rows, cols, flips)
    declared = valid_values if valid_values is not None else invalid_values
    if not isinstance(declared, list) or not declared:
        raise ValueError("qualityMask validValues/invalidValues must be a non-empty array")
    good = np.isfinite(raw)
    if valid_values is not None:
        good &= np.isin(raw, valid_values)
    else:
        good &= ~np.isin(raw, invalid_values)
    applies_to = raw_mask.get("appliesTo")
    if not isinstance(applies_to, list) or any(key not in layers for key in applies_to):
        raise ValueError("qualityMask.appliesTo must name normalized science assets")
    for key in applies_to:
        layers[key][~good] = np.nan
    return raw, {**details, "semantics": {"validValues": valid_values, "invalidValues": invalid_values, "appliesTo": applies_to}}


def _validate_layer(label: str, values: np.ndarray) -> None:
    finite = values[np.isfinite(values)]
    if label == "coherence" and finite.size and (np.any(finite < 0) or np.any(finite > 1)):
        raise ValueError("coherence values must lie in [0,1]")
    if label == "components" and finite.size:
        if np.any(finite < 0) or not np.allclose(finite, np.rint(finite), atol=0, rtol=0):
            raise ValueError("connected-component labels must be non-negative integers")


def _normalize_product(
    event: str, source: Mapping[str, Any], profile: Mapping[str, Any],
    source_path: Path, details: Mapping[str, Any],
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    reader = _Hdf5Reader(source_path) if profile["adapter"] == "hdf5" else _NetcdfReader(source_path, profile["coordinates"])
    try:
        _metadata_attr_checks(reader, profile, source)
        dataset_paths = profile["datasets"]
        coords = profile["coordinates"]
        height, width = reader.source_shape(coords)
        rows, cols = _window(profile, height, width)
        x, y = reader.coordinates(coords, rows, cols)
        grid, flips, native_resolution = _grid(x, y, profile["crs"])
        if source.get("nativeResolution") is not None:
            declared_resolution = source["nativeResolution"]
            if not isinstance(declared_resolution, dict) or not {"x", "y", "units"}.issubset(declared_resolution):
                raise ValueError("source.nativeResolution must contain x, y, and units")
            if _normal_unit(declared_resolution["units"]) != _normal_unit(native_resolution["units"]):
                raise ValueError("source.nativeResolution units conflict with the coordinate CRS")
            for axis in ("x", "y"):
                value = declared_resolution[axis]
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or value <= 0:
                    raise ValueError(f"source.nativeResolution.{axis} must be positive and finite")
                if not math.isclose(float(value), native_resolution[axis], rel_tol=0.02, abs_tol=1e-8):
                    raise ValueError(f"source.nativeResolution.{axis} conflicts with the explicit coordinate grid")

        if details["productType"] == "GUNW":
            required = ("phase", "coherence", "components")
            extras = set(dataset_paths) - set(required)
            if extras:
                raise ValueError("GUNW sourceProfile.datasets may map only phase, coherence, and components; use corrections/geometry for optional layers")
            for name in required:
                if name not in dataset_paths:
                    raise ValueError(f"GUNW sourceProfile.datasets must explicitly map {name}")
            layers: dict[str, np.ndarray] = {}
            layer_details: dict[str, dict[str, Any]] = {}
            units_by_asset: dict[str, str] = {}
            for name in required:
                values, layer_meta = _normalize_layer(dataset_paths[name], name, reader, rows, cols, flips)
                if values.shape != (grid["height"], grid["width"]):
                    raise ValueError(f"{name} dimensions do not match the explicit coordinate grid")
                _validate_layer(name, values)
                layers[name], layer_details[name] = values, layer_meta
                units_by_asset[name] = layer_meta["units"]

            correction_metadata = []
            corrections = profile.get("corrections", {})
            if not isinstance(corrections, dict):
                raise ValueError("sourceProfile.corrections must map exact correction names to datasets")
            for name, raw in corrections.items():
                correction_name = _text(name, "sourceProfile correction name")
                if not isinstance(raw, dict) or raw.get("appliesTo") != "phase" or raw.get("signConvention") not in {"same_as_phase", "opposite_phase"}:
                    raise ValueError(f"Correction {correction_name!r} must explicitly declare appliesTo='phase' and a supported signConvention")
                asset_key = _asset_key("correction", correction_name)
                if asset_key in layers:
                    raise ValueError(f"Correction names produce duplicate asset key {asset_key!r}")
                values, layer_meta = _normalize_layer(raw, f"correction {correction_name}", reader, rows, cols, flips)
                if values.shape != (grid["height"], grid["width"]):
                    raise ValueError(f"correction {correction_name!r} dimensions do not match the coordinate grid")
                units = _check_declared_unit(layer_meta["units"], layer_meta["units"], f"correction {correction_name}", "phase")
                layers[asset_key], layer_details[asset_key] = values, layer_meta
                units_by_asset[asset_key] = units
                correction_metadata.append({
                    "name": correction_name,
                    "assetKey": asset_key,
                    "units": units,
                    "appliesTo": raw["appliesTo"],
                    "signConvention": raw["signConvention"],
                })

            geometry_metadata = []
            geometry = profile.get("geometry", {})
            if not isinstance(geometry, dict):
                raise ValueError("sourceProfile.geometry must map exact geometry layer names to datasets")
            for name, raw in geometry.items():
                geometry_name = _text(name, "sourceProfile geometry name")
                asset_key = _asset_key("geometry", geometry_name)
                if asset_key in layers:
                    raise ValueError(f"Geometry names produce duplicate asset key {asset_key!r}")
                values, layer_meta = _normalize_layer(raw, f"geometry {geometry_name}", reader, rows, cols, flips)
                if values.shape != (grid["height"], grid["width"]):
                    raise ValueError(f"geometry {geometry_name!r} dimensions do not match the coordinate grid")
                layers[asset_key], layer_details[asset_key] = values, layer_meta
                units_by_asset[asset_key] = layer_meta["units"]
                geometry_metadata.append({"name": geometry_name, "assetKey": asset_key, "units": layer_meta["units"]})

            mask, mask_details = _apply_quality_mask(profile, reader, rows, cols, flips, layers, layer_details)
            if mask is not None:
                layers["qualityMask"] = mask
                layer_details["qualityMask"] = mask_details or {}
                units_by_asset["qualityMask"] = (mask_details or {}).get("units", "1")
            for name in required:
                _validate_layer(name, layers[name])
        else:
            required = ("HHHH", "HVHV")
            extras = set(dataset_paths) - set(required)
            if extras:
                raise ValueError("GCOV sourceProfile.datasets may map only HHHH and HVHV in this profile")
            for name in required:
                if name not in dataset_paths:
                    raise ValueError(f"GCOV sourceProfile.datasets must explicitly map {name}")
            layers = {}
            layer_details = {}
            units_by_asset = {}
            for name in required:
                values, layer_meta = _normalize_layer(dataset_paths[name], name, reader, rows, cols, flips)
                if values.shape != (grid["height"], grid["width"]):
                    raise ValueError(f"GCOV {name} dimensions do not match the explicit coordinate grid")
                layers[name], layer_details[name] = values, layer_meta
                units_by_asset[name] = layer_meta["units"]
            mask, mask_details = _apply_quality_mask(profile, reader, rows, cols, flips, layers, layer_details)
            if mask is not None:
                layers["qualityMask"] = mask
                layer_details["qualityMask"] = mask_details or {}
                units_by_asset["qualityMask"] = (mask_details or {}).get("units", "1")
            correction_metadata, geometry_metadata = [], []

        primary_names = ["phase", "coherence", "components"] if details["productType"] == "GUNW" else ["HHHH", "HVHV"]
        joint_valid = np.ones((grid["height"], grid["width"]), dtype=bool)
        for name in primary_names:
            joint_valid &= np.isfinite(layers[name])
        total_pixels = int(joint_valid.size)
        valid_pixels = int(np.count_nonzero(joint_valid))
        coverage = {"validPixelCount": valid_pixels, "totalPixelCount": total_pixels,
                    "validFraction": valid_pixels / total_pixels if total_pixels else 0.0}
        output = {
            "layers": layers,
            "layerDetails": layer_details,
            "units": units_by_asset,
            "grid": grid,
            "nativeResolution": native_resolution,
            "quality": {**dict(source["quality"]), **coverage},
            "validCoverage": coverage,
            "correctionsAvailable": correction_metadata,
            "geometryAvailable": geometry_metadata,
            "window": {"rowStart": rows.start, "rowStop": rows.stop, "colStart": cols.start, "colStop": cols.stop},
            "profileStatus": profile["status"] if profile["evidence"] else "needs-review",
        }
        return layers, output
    finally:
        reader.close()


def ingest(event: str, config_path: str | Path, output_root: str | Path | None = None) -> Path:
    """Normalize one explicitly profiled local GUNW or GCOV source file.

    The returned manifest is immutable under ``<event>/p3/<product>/<runId>``.
    ``core.publish`` leaves observed and derived data at ``needs-review``; only
    synthetic fixture products can move the current pointer automatically.
    """
    path = Path(config_path).expanduser().resolve()
    config, source, profile, source_path, details = _prepare_inputs(event, path)
    layers, normalized = _normalize_product(event, source, profile, source_path, details)
    profile_metadata = {
        "id": profile["id"],
        "version": profile["version"],
        "adapter": profile["adapter"],
        "status": normalized["profileStatus"],
        "evidence": profile["evidence"],
        "datasetPaths": {key: _descriptor(value, f"dataset {key}")["path"] for key, value in profile["datasets"].items()},
        "coordinateDatasets": dict(profile["coordinates"]),
        "crs": profile["crs"],
        "correctionPaths": {key: _descriptor(value, f"correction {key}")["path"] for key, value in profile.get("corrections", {}).items()},
        "geometryPaths": {key: _descriptor(value, f"geometry {key}")["path"] for key, value in profile.get("geometry", {}).items()},
    }
    metadata: dict[str, Any] = {
        "configVersion": _text(config.get("configVersion", "1.0"), "configVersion"),
        "algorithmVersion": _text(config.get("algorithmVersion", CODE_VERSION), "algorithmVersion"),
        "dataKind": details["dataKind"],
        "upstreamRunIds": [],
        "sourceHashes": {"sourceFile": _sha256(source_path)},
        "sourceFile": source_path.name,
        "sourceProfile": profile_metadata,
        "sourceProfileStatus": normalized["profileStatus"],
        "productId": source["productId"],
        "sensor": source["sensor"],
        "frequency": source["frequency"],
        "polarization": source["polarization"],
        "orbit": source["orbit"],
        "frame": source["frame"],
        "processingVersion": source["processingVersion"],
        "maturity": source["maturity"],
        "acquisitionDates": source["acquisitionDates"],
        "grid": normalized["grid"],
        "nativeResolution": normalized["nativeResolution"],
        "quality": normalized["quality"],
        "validCoverage": normalized["validCoverage"],
        "units": normalized["units"],
        "warnings": [],
        "processingNotes": [
            "Explicit windows are read as subsets; full-grid products currently materialize raster layers in memory and are not tiled."
        ],
        "sourceMetadata": {
            "datasetDetails": normalized["layerDetails"],
            "window": normalized["window"],
        },
    }
    if details["productType"] == "GUNW":
        metadata.update(
            wavelengthMetres=source["wavelengthMetres"],
            wavelengthUnits="metre",
            phaseToAwaySign=source["phaseToAwaySign"],
            phaseUnits="radian",
            correctionsApplied=source["correctionsApplied"],
            correctionsAvailable=normalized["correctionsAvailable"],
            geometryAvailable=normalized["geometryAvailable"],
        )
        product = "gunw"
    else:
        product = "gcov"

    if details["dataKind"] != "synthetic" and normalized["profileStatus"] != "verified":
        metadata["warnings"].append("Source profile has no verified provider evidence; data remains needs-review.")
    if details["dataKind"] == "synthetic":
        metadata["syntheticLineage"] = True

    def writer(stage: Path) -> dict[str, str]:
        files = {}
        for key, array in layers.items():
            filename = f"{key}.tif"
            core.write_raster(stage / filename, array, normalized["grid"])
            files[key] = filename
        return files

    return core.publish(event, product, metadata, writer, output_root=output_root)
