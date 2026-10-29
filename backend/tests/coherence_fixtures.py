"""Small, disposable raster and manifest fixtures for the coherence tests."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import transform_bounds


EVENT_ID = "test_event"
EVENT = {
    "id": EVENT_ID,
    "name": "Synthetic coherence test event",
    "aoi": "Small synthetic test area",
    "before_date": "2024-01-01",
    "after_date": "2024-01-13",
    "bbox": [120.0, 14.0, 120.01, 14.01],
}


def write_event_catalog(path: Path, event: dict | None = None) -> Path:
    path.write_text(json.dumps([event or EVENT]), encoding="utf-8")
    return path


def write_geotiff(
    path: Path,
    values: np.ndarray,
    *,
    crs: str = "EPSG:32651",
    transform=None,
    nodata: float | int | None = None,
    tags: dict[str, str] | None = None,
) -> Path:
    values = np.asarray(values)
    if values.ndim != 2:
        raise ValueError("fixture raster must be two-dimensional")
    profile = {
        "driver": "GTiff",
        "height": values.shape[0],
        "width": values.shape[1],
        "count": 1,
        "dtype": values.dtype,
        "crs": crs,
        "transform": transform or from_origin(500000, 1700000, 30, 30),
        "compress": "LZW",
    }
    if nodata is not None:
        profile["nodata"] = nodata
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(values, 1)
        if tags:
            dst.update_tags(**tags)
    return path


def pair_record(
    source: str,
    product_id: str,
    scene_ids: tuple[str, str],
    dates: tuple[str, str],
    *,
    relative_orbit: int = 123,
    direction: str = "ASCENDING",
    polarization: str = "VV",
    processing_version: str = "fixture-1",
) -> dict:
    return {
        "source": source,
        "productId": product_id,
        "sceneIds": list(scene_ids),
        "acquisitionDates": list(dates),
        "relativeOrbit": relative_orbit,
        "flightDirection": direction,
        "polarization": polarization,
        "processingVersion": processing_version,
    }


def valid_manifest(
    pre_source: str,
    co_source: str,
    *,
    event_id: str = EVENT_ID,
    event_window: tuple[str, str] = ("2024-01-10", "2024-01-12"),
) -> dict:
    return {
        "event": event_id,
        "eventWindow": {"start": event_window[0], "end": event_window[1]},
        "dataKind": "synthetic",
        "pre": pair_record(
            pre_source,
            "SYNTH-PRE-001",
            ("SYNTH-A", "SYNTH-B"),
            ("2024-01-01", "2024-01-05"),
        ),
        "co": pair_record(
            co_source,
            "SYNTH-CO-001",
            ("SYNTH-B", "SYNTH-C"),
            ("2024-01-05", "2024-01-15"),
        ),
    }


def write_zip(path: Path, members: dict[str, Path]) -> Path:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for archive_name, source_path in members.items():
            archive.write(source_path, archive_name)
    return path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prepared_pair(
    directory: Path,
    pre: np.ndarray,
    co: np.ndarray,
    *,
    valid_pre: np.ndarray | None = None,
    valid_co: np.ndarray | None = None,
    transform=None,
    crs: str = "EPSG:32651",
    extraction_id: str = "00000000-0000-4000-8000-000000000001",
) -> Path:
    """Write a coherent prepared pair plus its hash-bound metadata."""
    directory.mkdir(parents=True, exist_ok=True)
    pre = np.asarray(pre, dtype=np.float32)
    co = np.asarray(co, dtype=np.float32)
    if pre.shape != co.shape:
        raise ValueError("prepared pair arrays must have the same shape")
    if transform is None:
        west, south, east, north = transform_bounds(
            "EPSG:4326", crs, *EVENT["bbox"], densify_pts=21
        )
        transform = from_origin(west + 30, north - 30, 30, 30)
    if valid_pre is not None:
        pre = np.where(valid_pre, pre, np.nan).astype(np.float32)
    if valid_co is not None:
        co = np.where(valid_co, co, np.nan).astype(np.float32)
    tags = {
        "extractionId": extraction_id,
        "event": EVENT_ID,
        "dataKind": "synthetic",
    }
    pre_path = write_geotiff(
        directory / "coh_pre.tif", pre, crs=crs, transform=transform,
        nodata=np.nan, tags={**tags, "pair": "pre"},
    )
    co_path = write_geotiff(
        directory / "coh_co.tif", co, crs=crs, transform=transform,
        nodata=np.nan, tags={**tags, "pair": "co"},
    )
    metadata = {
        "schemaVersion": "1.0",
        "extractionId": extraction_id,
        "event": EVENT_ID,
        "aoi": EVENT["aoi"],
        "bbox": EVENT["bbox"],
        "eventWindow": {"start": "2024-01-10", "end": "2024-01-12"},
        "dataKind": "synthetic",
        "prePair": ["2024-01-01", "2024-01-05"],
        "coPair": ["2024-01-05", "2024-01-15"],
        "sources": {
            "pre": {
                "productId": "SYNTH-PRE-001",
                "source": "fixture",
                "selectedMember": "fixture_pre_corr.tif",
                "sceneIds": ["SYNTH-A", "SYNTH-B"],
                "acquisitionDates": ["2024-01-01", "2024-01-05"],
                "relativeOrbit": 123,
                "flightDirection": "ASCENDING",
                "polarization": "VV",
                "processingVersion": "fixture-1",
                "durationDays": 4,
            },
            "co": {
                "productId": "SYNTH-CO-001",
                "source": "fixture",
                "selectedMember": "fixture_co_corr.tif",
                "sceneIds": ["SYNTH-B", "SYNTH-C"],
                "acquisitionDates": ["2024-01-05", "2024-01-15"],
                "relativeOrbit": 123,
                "flightDirection": "ASCENDING",
                "polarization": "VV",
                "processingVersion": "fixture-1",
                "durationDays": 10,
            },
        },
        "grid": {
            "crs": crs,
            "width": pre.shape[1],
            "height": pre.shape[0],
            "transform": list(transform[:6]),
            "resolutionMetres": 30,
        },
        "coverage": {
            "aoiPixelCount": int(pre.size),
            "commonValidPixelCount": int((np.isfinite(pre) & np.isfinite(co)).sum()),
            "preValidPixelCount": int(np.isfinite(pre).sum()),
            "coValidPixelCount": int(np.isfinite(co).sum()),
        },
        "parameters": {"waterMaskApplied": False},
        "outputs": {
            "coh_pre.tif": {"sha256": sha256(pre_path)},
            "coh_co.tif": {"sha256": sha256(co_path)},
        },
        "warnings": [],
        "createdAt": "2026-10-27T00:00:00Z",
        "codeVersion": "test-fixture",
    }
    info_path = directory / "coherence_info.json"
    info_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return info_path
