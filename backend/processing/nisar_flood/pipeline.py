"""Orchestration: passes -> water rule -> permanent water -> rhythm / vegetation -> exports."""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject

from . import CODE_VERSION, gcov, polarization, vegetation, water
from .constants import (AREA_ID, BACKEND_DIR, CALIBRATION_WATER_BBOX, DEFAULT_LAYOUT, DEFAULT_MIN_VALID_PASSES,
                        DEFAULT_PERMANENT_FRACTION, DEFAULT_VEGETATION_LANDCOVER_CLASSES, DEFAULT_VEGETATION_MARGIN_DB,
                        STUDY_BBOX, GcovLayout)
from .export import (backscatter_rgba, mask_rgba, register, rhythm_colors, rhythm_rgba, sha256_path, swap_directory,
                     write_gtiff, write_manifest, write_png_overlay, write_rhythm_legend)
from .geo import Grid, pixel_area_km2, study_mask
from .constants import COLOR_VEGETATION, COLOR_WATER

OUTPUT_DIR = BACKEND_DIR / "data" / "output" / AREA_ID / "nisar"
WINDOW_CACHE_DIR = BACKEND_DIR / "data" / "raw" / "nisar_windows"

LIMITATIONS = [
    "Urban double-bounce: water between buildings is bright in HH, so flooded streets in dense blocks are under-detected. "
    "Flooded area over built-up land is a lower bound.",
    "One fixed HH/HV threshold rule is applied to every pass; wind-roughened water and shadow can still be misclassified.",
    "Passes are about 12 days apart: short floods between passes are not seen, and a pass shows the state at one overpass time.",
    "'Possible flooded vegetation' is HH brightening against the pixel's own season reference. Soil moisture and crop growth also "
    "brighten HH, so it is a possibility, not a confirmed flood.",
    "Pixels outside the radar swath or masked as invalid are nodata. They are excluded from every denominator and never counted as dry.",
]
SOURCE_INFO = {"name": "NASA-ISRO NISAR L2 GCOV (ASF DAAC)", "url": "https://asf.alaska.edu/data-sets/sar-data-sets/nisar/"}


@dataclass
class PassInput:
    id: str  # YYYYMMDD
    date: str
    acquisition_time: str
    product_id: str
    maturity: str
    window: gcov.GcovWindow
    source: dict = field(default_factory=dict)


def window_sha256(window: gcov.GcovWindow) -> str:
    digest = hashlib.sha256()
    digest.update(np.ascontiguousarray(window.hh_db).tobytes())
    digest.update(np.ascontiguousarray(window.hv_db).tobytes())
    digest.update(json.dumps(window.grid.to_dict(), sort_keys=True).encode())
    return digest.hexdigest()


# -- window cache ---------------------------------------------------------
def _cache_key(title: str, bbox, layout: GcovLayout, speckle: int) -> str:
    text = json.dumps([title, list(bbox), layout.__dict__, speckle], sort_keys=True, default=str)
    return hashlib.sha256(text.encode()).hexdigest()[:20]


def save_window(path: Path, window: gcov.GcovWindow) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, hh=window.hh_db, hv=window.hv_db, grid=json.dumps(window.grid.to_dict()), meta=json.dumps(window.meta, default=str))


def load_window(path: Path) -> gcov.GcovWindow:
    with np.load(path, allow_pickle=False) as data:
        return gcov.GcovWindow(data["hh"], data["hv"], Grid.from_dict(json.loads(str(data["grid"]))), json.loads(str(data["meta"])))


def passes_from_cmr_manifest(manifest: dict, *, max_dates: int | None = None, dates: list[str] | None = None,
                             local_dir: Path | None = None, token: str | None = None, allow_download: bool = False,
                             layout: GcovLayout = DEFAULT_LAYOUT, speckle_window: int = 3, bbox=STUDY_BBOX,
                             cache_dir: Path | None = WINDOW_CACHE_DIR, reuse_cache: bool = True, log=print) -> list[PassInput]:
    """Read the study window of every selected GCOV granule in a CMR manifest (script 19 output)."""
    rows = list(manifest["gcov"])
    if dates:
        rows = [r for r in rows if r["date"] in set(dates)]
    if max_dates:
        rows = rows[:max_dates]
    if not rows:
        raise ValueError("No GCOV granules selected from the manifest")
    passes: list[PassInput] = []
    for index, row in enumerate(rows, start=1):
        log(f"[{index}/{len(rows)}] {row['date']} {row['title']}")
        key = _cache_key(row["title"], bbox, layout, speckle_window)
        cache_path = (cache_dir / f"{row['date'].replace('-', '')}_{key}.npz") if cache_dir else None
        if reuse_cache and cache_path and cache_path.is_file():
            window = load_window(cache_path)
            access = {"mode": "cache", "cache": cache_path.name}
            log("  using cached window")
        else:
            if local_dir is not None:
                source = str(Path(local_dir) / f"{row['title']}.h5")
            else:
                source = row["url"]
            window, access = gcov.read_window_from_source(
                source, token=token, allow_download=allow_download, bbox=bbox, layout=layout, speckle_window=speckle_window,
                expected_size=row.get("sizeBytes"), expected_md5=row.get("md5"), log=log)
            if cache_path:
                save_window(cache_path, window)
            log(f"  read {window.grid.width}x{window.grid.height} px via {access['mode']}"
                + (f", {access.get('bytesFetched', 0) / 1e6:.0f} MB over {access.get('requests', 0)} requests" if access["mode"] == "remote-range" else "")
                + f", valid {window.meta['validFractionOfWindow']:.0%}")
        passes.append(PassInput(
            id=row["date"].replace("-", ""), date=row["date"], acquisition_time=row["acquisitionTime"],
            product_id=row["title"], maturity=row["maturity"], window=window,
            source={"title": row["title"], "url": row.get("url"), "collection": row.get("collectionShortName"),
                    "productVersion": row.get("productVersion"), "sizeBytes": row.get("sizeBytes"), "md5": row.get("md5"),
                    "acquisitionTimeManila": row.get("acquisitionTimeManila"), "bboxCoverageFraction": row.get("bboxCoverageFraction"),
                    "access": access, "windowSha256": window_sha256(window), "window": window.meta.get("window")}))
    return passes


# -- helpers ----------------------------------------------------------------
def align_to_grid(array: np.ndarray, src: Grid, dst: Grid) -> np.ndarray:
    out = np.full((dst.height, dst.width), np.nan, dtype="float32")
    reproject(source=array.astype("float32"), destination=out, src_transform=src.affine, src_crs=src.crs, src_nodata=np.nan,
              dst_transform=dst.affine, dst_crs=dst.crs, dst_nodata=np.nan, resampling=Resampling.nearest)
    return out


def raster_on_grid(path: Path, grid: Grid) -> np.ndarray:
    """Read band 1 of any raster onto ``grid`` (nearest neighbour). Nodata becomes NaN."""
    out = np.full((grid.height, grid.width), np.nan, dtype="float32")
    with rasterio.open(path) as src:
        reproject(source=rasterio.band(src, 1), destination=out, src_transform=src.transform, src_crs=src.crs,
                  src_nodata=src.nodata, dst_transform=grid.affine, dst_crs=grid.crs, dst_nodata=np.nan, resampling=Resampling.nearest)
    return out


def save_rule(path: Path, rule: water.WaterRule) -> None:
    path.write_text(json.dumps({"hhThresholdDb": rule.hh_db, "hvThresholdDb": rule.hv_db, "calibration": rule.calibration}, indent=1) + "\n")


def load_rule(path: Path) -> water.WaterRule:
    data = json.loads(Path(path).read_text())
    return water.WaterRule(float(data["hhThresholdDb"]), float(data["hvThresholdDb"]), data.get("calibration") or {"status": "loaded", "from": str(path)})


@dataclass
class Analysis:
    grid: Grid
    bbox: tuple
    in_area: np.ndarray
    area_km2: np.ndarray
    passes: list[PassInput]
    rule: water.WaterRule
    hh: list[np.ndarray]
    hv: list[np.ndarray]
    valid: list[np.ndarray]
    water: list[np.ndarray]
    flooded: list[np.ndarray]
    veg: list[np.ndarray]
    reference: np.ndarray
    permanent: np.ndarray
    permanent_info: dict
    rhythm: water.Rhythm
    pass_stats: list[dict]
    rhythm_stats: dict
    veg_info: dict
    warnings: list[str]


def analyse(passes: list[PassInput], *, bbox=STUDY_BBOX, rule: water.WaterRule | None = None, calibrate: bool = False,
            calibration_bbox=CALIBRATION_WATER_BBOX, permanent_fraction: float = DEFAULT_PERMANENT_FRACTION,
            min_valid_passes: int = DEFAULT_MIN_VALID_PASSES, permanent_mask_path: Path | None = None,
            landcover_path: Path | None = None, landcover_classes=DEFAULT_VEGETATION_LANDCOVER_CLASSES,
            vegetation_margin_db: float = DEFAULT_VEGETATION_MARGIN_DB, reference_min_passes: int = 3,
            log=print) -> Analysis:
    if not passes:
        raise ValueError("At least one pass is required")
    passes = sorted(passes, key=lambda p: p.acquisition_time)
    if len({p.id for p in passes}) != len(passes):
        raise ValueError("Two passes share the same date id; select one granule per date")
    warnings: list[str] = []
    grid = passes[0].window.grid
    hh, hv = [], []
    for p in passes:
        w = p.window
        if w.grid.same_as(grid):
            hh.append(w.hh_db); hv.append(w.hv_db)
        else:
            warnings.append(f"{p.date}: window grid differed from the first pass; resampled (nearest) onto it.")
            hh.append(align_to_grid(w.hh_db, w.grid, grid)); hv.append(align_to_grid(w.hv_db, w.grid, grid))
    in_area = study_mask(grid, bbox)
    area = pixel_area_km2(grid)

    if calibrate:
        lon, lat = grid.pixel_center_lonlat()
        known = (lon >= calibration_bbox[0]) & (lon <= calibration_bbox[2]) & (lat >= calibration_bbox[1]) & (lat <= calibration_bbox[3])
        rule, record = water.calibrate_rule(
            hh, hv, known, pass_ids=[p.id for p in passes],
            description=f"Manila Bay open water, box {list(calibration_bbox)} (WGS84), chosen from map knowledge, not from SAR data")
        log(f"calibrated: HH < {rule.hh_db} dB, HV < {rule.hv_db} dB from {record['waterPixels']} bay pixels")
        warnings.extend(record["warnings"])
    rule = rule or water.WaterRule()
    if rule.calibration.get("status") != "calibrated":
        warnings.append("Water thresholds are the contract defaults and have not been calibrated on a real pass.")

    classified = [water.classify(a, b, rule) for a, b in zip(hh, hv)]
    water_masks = [c[0] & in_area for c in classified]
    valid = [c[1] & in_area for c in classified]
    external = None
    if permanent_mask_path is not None:
        external = raster_on_grid(permanent_mask_path, grid)
        external = np.nan_to_num(external, nan=0.0) > 0
    permanent, perm_info = water.permanent_water(water_masks, valid, fraction=permanent_fraction,
                                                 min_valid_passes=min_valid_passes, external=external)
    permanent &= in_area
    flooded = [water.flooded_from(w, v, permanent) for w, v in zip(water_masks, valid)]
    rhythm = water.compute_rhythm(flooded, valid, permanent, in_area, min_valid_passes=min_valid_passes)

    landcover = None
    if landcover_path is not None:
        landcover = raster_on_grid(landcover_path, grid)
    candidate = vegetation.landcover_candidate_mask(None if landcover is None else np.nan_to_num(landcover, nan=-1), landcover_classes)
    reference = vegetation.dry_reference_db(hh, water_masks, min_reference_passes=reference_min_passes)
    veg = [vegetation.flooded_vegetation(h, reference, w, permanent, in_area, margin_db=vegetation_margin_db, candidate=candidate)
           for h, w in zip(hh, water_masks)]
    veg_info = {
        "marginDb": vegetation_margin_db, "referenceMinPasses": reference_min_passes,
        "referenceMethod": "per-pixel median HH dB over valid passes that were not open water",
        "landCoverMask": ({"path": Path(landcover_path).name, "classes": list(landcover_classes), "sha256": sha256_path(Path(landcover_path))}
                          if landcover_path else None),
        "label": "possible flooded vegetation (L-band)",
    }
    if landcover_path is None:
        warnings.append("No land-cover mask supplied: possible-flooded-vegetation pixels are not restricted to cropland/wetland classes.")
    pstats = [water.pass_stats(w, v, permanent, in_area, area, vegetation=g) for w, v, g in zip(water_masks, valid, veg)]
    return Analysis(grid, tuple(bbox), in_area, area, passes, rule, hh, hv, valid, water_masks, flooded, veg, reference, permanent, perm_info,
                    rhythm, pstats, water.rhythm_stats(rhythm, area), veg_info, warnings)


def state_codes(a: Analysis, k: int) -> np.ndarray:
    """0 dry, 1 flooded open water, 2 permanent water, 3 possible flooded vegetation, 255 nodata."""
    state = np.full(a.grid.height * a.grid.width, 255, dtype="uint8").reshape(a.grid.height, a.grid.width)
    ok = a.valid[k] & a.in_area
    state[ok] = 0
    state[a.veg[k] & ok] = 3
    state[a.flooded[k] & ok] = 1
    state[a.permanent & ok] = 2
    return state


def _public_stats(stats: dict) -> dict:
    """A pass with no valid pixels has unknown flooded area: null with a reason, never 0."""
    if stats.get("validKm2"):
        return dict(stats)
    out = dict(stats)
    for key in ("floodedKm2", "permanentWaterKm2", "floodedVegetationKm2"):
        if key in out:
            out[key] = None
    out["missingReason"] = "no valid pixels on this pass inside the study area"
    return out


def export_product(a: Analysis, out_dir: Path, *, data_kind: str, source: dict, extra_warnings: list[str] | None = None,
                   provenance: dict | None = None, verification: dict | None = None, track: dict | None = None) -> Path:
    """Write every asset plus manifest.json into ``out_dir`` (atomically replacing a previous product)."""
    if data_kind not in ("observed", "synthetic"):
        raise ValueError("data_kind must be 'observed' or 'synthetic'")
    out_dir = Path(out_dir)
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    stage = out_dir.parent / f".nisar-stage-{uuid.uuid4().hex[:8]}"
    stage.mkdir()
    try:
        assets: dict = {}
        pass_entries = []
        bounds = None
        pass_total = len(a.passes)
        for k, p in enumerate(a.passes):
            pid = p.id
            state = state_codes(a, k)
            hh_show = np.where(a.valid[k] & a.in_area, a.hh[k], np.nan)
            hv_show = np.where(a.valid[k] & a.in_area, a.hv[k], np.nan)
            bounds = write_png_overlay(mask_rgba(a.flooded[k] & a.in_area, COLOR_WATER), a.grid, stage / f"pass_{pid}.png")
            write_png_overlay(backscatter_rgba(hh_show), a.grid, stage / f"hh_{pid}.png", max_side=1400)
            write_png_overlay(mask_rgba(a.veg[k], COLOR_VEGETATION, 210), a.grid, stage / f"veg_{pid}.png")
            write_png_overlay(polarization.polarization_rgba(hh_show, hv_show), a.grid, stage / f"pol_{pid}.png", max_side=1400)
            write_gtiff(stage / "tif" / f"state_{pid}.tif", state, a.grid, nodata=255, dtype="uint8",
                        descriptions=["0 dry, 1 flooded open water, 2 permanent water, 3 possible flooded vegetation, 255 nodata"])
            write_gtiff(stage / "tif" / f"db_{pid}.tif", np.stack([hh_show, hv_show]).astype("float32"), a.grid, nodata=float("nan"),
                        dtype="float32", descriptions=["HH dB", "HV dB"])
            for key, rel, kind in ((f"pass_{pid}", f"pass_{pid}.png", "overlay-png"), (f"hh_{pid}", f"hh_{pid}.png", "overlay-png"),
                                   (f"veg_{pid}", f"veg_{pid}.png", "overlay-png"), (f"pol_{pid}", f"pol_{pid}.png", "overlay-png"),
                                   (f"state_{pid}", f"tif/state_{pid}.tif", "geotiff"), (f"db_{pid}", f"tif/db_{pid}.tif", "geotiff")):
                register(assets, stage, key, rel, kind)
            pass_entries.append({
                "id": pid, "date": p.date, "acquisitionTime": p.acquisition_time,
                "acquisitionTimeManila": p.source.get("acquisitionTimeManila"),
                "productId": p.product_id, "maturity": p.maturity, **_public_stats(a.pass_stats[k]),
                "assets": {"overlay": f"pass_{pid}", "backscatter": f"hh_{pid}", "vegetation": f"veg_{pid}", "polarization": f"pol_{pid}",
                           "state": f"state_{pid}", "db": f"db_{pid}"},
                "source": p.source})
        rhythm_png = rhythm_rgba(a.rhythm.flood_count, a.rhythm.countable, a.permanent, a.rhythm.pass_count)
        write_png_overlay(rhythm_png, a.grid, stage / "rhythm.png")
        register(assets, stage, "rhythm", "rhythm.png", "overlay-png")
        half_text = "Pixels flooded on half or more of their valid passes are the headline zone."
        write_rhythm_legend(stage / "rhythm_legend.png", a.rhythm.pass_count, half_text, data_kind)
        register(assets, stage, "rhythm_legend", "rhythm_legend.png", "overlay-png")
        write_gtiff(stage / "tif" / "rhythm_counts.tif", np.stack([a.rhythm.flood_count, a.rhythm.valid_count]).astype("int16"), a.grid,
                    nodata=-1, dtype="int16", descriptions=["passes flooded (-1 = not countable)", "valid passes (0 = not countable)"])
        register(assets, stage, "rhythm_counts", "tif/rhythm_counts.tif", "geotiff")
        # Names other modules read: rhythm.tif (band 1 = passes flooded, -1 = nodata) for the exposure endpoint.
        write_gtiff(stage / "rhythm.tif", a.rhythm.flood_count.astype("int16"), a.grid, nodata=-1, dtype="int16",
                    descriptions=["passes flooded (-1 = nodata: permanent water, outside area or too few valid passes)"])
        register(assets, stage, "rhythm_tif", "rhythm.tif", "geotiff")
        fc, vc = a.rhythm.flood_count, a.rhythm.valid_count
        half = np.where(a.rhythm.countable, ((fc >= 1) & (2 * fc >= vc)).astype("uint8"), 255).astype("uint8")
        write_gtiff(stage / "rhythm_half.tif", half, a.grid, nodata=255, dtype="uint8",
                    descriptions=["1 = flooded on half or more of the pixel's own valid passes, 0 = not, 255 = nodata"])
        register(assets, stage, "rhythm_half_tif", "rhythm_half.tif", "geotiff")
        write_gtiff(stage / "tif" / "permanent_water.tif", a.permanent.astype("uint8"), a.grid, nodata=255, dtype="uint8")
        register(assets, stage, "permanent_water", "tif/permanent_water.tif", "geotiff")
        write_gtiff(stage / "tif" / "hh_dry_reference.tif", a.reference, a.grid, nodata=float("nan"), dtype="float32")
        register(assets, stage, "hh_dry_reference", "tif/hh_dry_reference.tif", "geotiff")

        warnings = list(a.warnings) + list(extra_warnings or [])
        if data_kind == "synthetic":
            warnings.insert(0, "SYNTHETIC DEMO DATA. Generated by scripts/22_nisar_synthetic_demo.py. These are not NISAR observations and "
                               "must not be published as real.")
        manifest = {
            "schemaVersion": "1.0", "kind": "nisar-flood-rhythm", "area": AREA_ID, "dataKind": data_kind,
            "codeVersion": CODE_VERSION, "version": CODE_VERSION, "passCount": a.rhythm.pass_count, "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sensor": "NISAR L-band SAR" if data_kind == "observed" else "SYNTHETIC GCOV-like fixture (not NISAR)",
            "product": "L2 GCOV", "polarizations": ["HH", "HV"],
            "track": track or {}, "source": source,
            "studyBbox": list(a.bbox), "bounds": bounds, "grid": a.grid.to_dict(), "nativeResolution": a.grid.native_resolution(),
            "areaMethod": "per-pixel area from a Lambert azimuthal equal-area projection centred on the grid",
            "rule": a.rule.to_dict(), "permanentWater": a.permanent_info,
            "rhythm": {**a.rhythm_stats, "legend": [{"count": c, "color": col} for c, col in enumerate(rhythm_colors(a.rhythm.pass_count), start=1)],
                       "permanentWaterMasked": True, "overlay": "rhythm", "legendImage": "rhythm_legend", "counts": "rhythm_counts",
                       "method": "count of passes classified as water, over the count of valid passes, per pixel; permanent water excluded"},
            "vegetation": a.veg_info,
            "passes": pass_entries,
            "verification": verification or {"layout": "unverified", "evidence": []},
            "provenance": provenance or {},
            "warnings": warnings, "limitations": LIMITATIONS,
            "assets": assets,
        }
        write_manifest(stage / "manifest.json", manifest)
    except BaseException:
        import shutil
        shutil.rmtree(stage, ignore_errors=True)
        raise
    swap_directory(stage, out_dir)
    return out_dir / "manifest.json"
