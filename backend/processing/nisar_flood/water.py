"""Per-pass open-water rule, one-off calibration, permanent water, and flood rhythm.

THE RULE (same for every date). A pixel is open water on a pass when BOTH
    HH backscatter < hh_db   AND   HV backscatter < hv_db   (dB, gamma0/sigma0 as published).

Why fixed thresholds, one rule for all dates: a per-date automatic threshold (e.g. Otsu) moves with
the scene content. A wetter date has more water, so its threshold would shift and flooded area would
change for reasons unrelated to the ground. A rule calibrated once and applied unchanged makes every
pass comparable, so a change in flooded km2 between dates is a change in the scene.

Why HH and HV together: smooth open water returns very little energy in both channels (specular
reflection away from the sensor). Using both reduces false water from radar shadow and from dark
dry surfaces (e.g. smooth tarmac, bare sand) that are low in HH but not in HV.

LIMITATIONS (stated in the product): (1) urban double-bounce. Water between buildings produces a bright
HH return, so flooded streets in dense urban blocks are NOT detected and are counted as dry. The
result is a lower bound over built-up areas. (2) Wind-roughened water can exceed the thresholds.
(3) Dense emergent vegetation over water raises HH (that is the separate flooded-vegetation class).
(4) Thresholds are only as good as the calibration, which is recorded in the manifest and starts
as a placeholder until calibrate_rule() has been run on a real pass.

NODATA. A pixel with no valid HH or HV on a pass is "nodata". It is excluded from the denominator and is
never counted as dry.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .constants import (DEFAULT_HH_THRESHOLD_DB, DEFAULT_HV_THRESHOLD_DB, DEFAULT_MIN_VALID_PASSES,
                        DEFAULT_PERMANENT_FRACTION)

RULE_DESCRIPTION = (
    "Open water where HH < hhThresholdDb and HV < hvThresholdDb on the same pixel. One fixed rule is applied "
    "to every pass. Pixels without valid HH and HV are nodata, not dry. Water in dense urban blocks is under-detected "
    "because double-bounce makes streets bright.")


@dataclass(frozen=True)
class WaterRule:
    hh_db: float = DEFAULT_HH_THRESHOLD_DB
    hv_db: float = DEFAULT_HV_THRESHOLD_DB
    calibration: dict = field(default_factory=lambda: {
        "status": "uncalibrated-default",
        "note": "Contract default thresholds. Not yet calibrated on a real NISAR pass; run scripts/20_nisar_flood_rhythm.py "
                "--calibrate on the first real file and re-run."})

    def to_dict(self) -> dict:
        return {"description": RULE_DESCRIPTION, "hhThresholdDb": self.hh_db, "hvThresholdDb": self.hv_db,
                "calibration": self.calibration}


def classify(hh_db: np.ndarray, hv_db: np.ndarray, rule: WaterRule) -> tuple[np.ndarray, np.ndarray]:
    """Return (water, valid) boolean arrays. ``water`` implies ``valid``; nodata is neither water nor dry."""
    valid = np.isfinite(hh_db) & np.isfinite(hv_db)
    with np.errstate(invalid="ignore"):
        water = valid & (hh_db < rule.hh_db) & (hv_db < rule.hv_db)
    return water, valid


def calibrate_rule(hh_db_passes: list[np.ndarray], hv_db_passes: list[np.ndarray], known_water: np.ndarray, *,
                   known_land: np.ndarray | None = None, quantile: float = 0.95, description: str = "",
                   pass_ids: list[str] | None = None, round_to: float = 0.5, min_pixels: int = 500) -> tuple[WaterRule, dict]:
    """Derive the fixed HH/HV thresholds once from pixels known to be open water (e.g. Manila Bay).

    Each threshold is the ``quantile`` of the known-water dB distribution pooled over the given passes,
    rounded to ``round_to`` dB. If ``known_land`` is given, the separation (land 5th percentile minus the
    threshold) is recorded and a warning is raised when it is not positive. Returns the rule and the record.
    """
    hh = np.concatenate([p[known_water & np.isfinite(p)] for p in hh_db_passes])
    hv = np.concatenate([p[known_water & np.isfinite(p)] for p in hv_db_passes])
    if hh.size < min_pixels or hv.size < min_pixels:
        raise ValueError(f"Only {hh.size} known-water pixels with valid data; need at least {min_pixels} to calibrate")

    def snap(value: float) -> float:
        return float(np.round(value / round_to) * round_to)

    t_hh, t_hv = snap(np.quantile(hh, quantile)), snap(np.quantile(hv, quantile))
    record = {
        "status": "calibrated",
        "method": f"{quantile:.0%} quantile of known open-water dB, pooled over passes, rounded to {round_to} dB",
        "knownWater": description,
        "passes": pass_ids or [],
        "waterPixels": int(hh.size),
        "waterHhDb": {"p05": float(np.quantile(hh, 0.05)), "p50": float(np.median(hh)), "p95": float(np.quantile(hh, 0.95))},
        "waterHvDb": {"p05": float(np.quantile(hv, 0.05)), "p50": float(np.median(hv)), "p95": float(np.quantile(hv, 0.95))},
        "warnings": [],
    }
    if known_land is not None:
        land_hh = np.concatenate([p[known_land & np.isfinite(p)] for p in hh_db_passes])
        land_hv = np.concatenate([p[known_land & np.isfinite(p)] for p in hv_db_passes])
        if land_hh.size and land_hv.size:
            record["landHhP05Db"] = float(np.quantile(land_hh, 0.05))
            record["landHvP05Db"] = float(np.quantile(land_hv, 0.05))
            if record["landHhP05Db"] <= t_hh or record["landHvP05Db"] <= t_hv:
                record["warnings"].append("Known land overlaps the water threshold in at least one channel; check the reference areas.")
    return WaterRule(t_hh, t_hv, record), record


def permanent_water(water: list[np.ndarray], valid: list[np.ndarray], *, fraction: float = DEFAULT_PERMANENT_FRACTION,
                    min_valid_passes: int = DEFAULT_MIN_VALID_PASSES, external: np.ndarray | None = None) -> tuple[np.ndarray, dict]:
    """Pixels that are water on at least ``fraction`` of their valid passes (and have enough valid passes).

    ``external`` is an optional boolean mask on the same grid (e.g. a reference water mask) that is added.
    Returns (mask, info).
    """
    water_count = np.sum(water, axis=0, dtype="int32")
    valid_count = np.sum(valid, axis=0, dtype="int32")
    with np.errstate(divide="ignore", invalid="ignore"):
        share = np.where(valid_count > 0, water_count / np.maximum(valid_count, 1), 0.0)
    mask = (valid_count >= min_valid_passes) & (share >= fraction)
    from_data = int(mask.sum())
    if external is not None:
        if external.shape != mask.shape:
            raise ValueError("External permanent-water mask must be on the pass grid")
        mask = mask | external.astype(bool)
    info = {"fraction": fraction, "minValidPasses": min_valid_passes, "pixelsFromPasses": from_data,
            "pixelsTotal": int(mask.sum()), "externalMaskUsed": external is not None}
    return mask, info


@dataclass
class Rhythm:
    flood_count: np.ndarray  # int16; -1 where not countable
    valid_count: np.ndarray  # int16; passes with valid data (permanent water and outside-area: 0)
    countable: np.ndarray  # bool: inside area, not permanent water, enough valid passes
    pass_count: int
    min_valid_passes: int


def compute_rhythm(flooded: list[np.ndarray], valid: list[np.ndarray], permanent: np.ndarray, in_area: np.ndarray, *,
                   min_valid_passes: int = DEFAULT_MIN_VALID_PASSES) -> Rhythm:
    """Per pixel: passes flooded / passes valid. Invalid passes leave the denominator and are never dry.

    ``flooded`` must already exclude permanent water and be a subset of ``valid`` (see ``flooded_from``).
    """
    if len(flooded) != len(valid) or not flooded:
        raise ValueError("flooded and valid must be non-empty lists of equal length")
    flood_count = np.sum(flooded, axis=0, dtype="int16")
    valid_count = np.sum(valid, axis=0, dtype="int16")
    countable = in_area & ~permanent & (valid_count >= max(1, min_valid_passes))
    out = np.where(countable, flood_count, -1).astype("int16")
    return Rhythm(out, np.where(countable, valid_count, 0).astype("int16"), countable, len(flooded), min_valid_passes)


def flooded_from(water: np.ndarray, valid: np.ndarray, permanent: np.ndarray) -> np.ndarray:
    """Flooded = water on this pass and not permanent water (and valid on this pass)."""
    return water & valid & ~permanent


def rhythm_stats(rhythm: Rhythm, area_km2: np.ndarray) -> dict:
    """Areas (km2) by flood count, and for pixels flooded on half or more of their valid passes."""
    countable = rhythm.countable
    fc, vc = rhythm.flood_count, rhythm.valid_count
    km2_by_count = []
    for count in range(1, rhythm.pass_count + 1):
        sel = countable & (fc == count)
        km2_by_count.append({"count": count, "km2": round(float(area_km2[sel].sum()), 4)})
    half = countable & (fc >= 1) & (2 * fc >= vc)
    by_denominator = []
    for denominator in sorted(int(v) for v in np.unique(vc[countable])):
        sel = countable & (vc == denominator)
        by_denominator.append({"validPasses": denominator, "km2": round(float(area_km2[sel].sum()), 4),
                               "floodedAtLeastOnceKm2": round(float(area_km2[sel & (fc >= 1)].sum()), 4)})
    return {
        "passCount": rhythm.pass_count,
        "minValidPasses": rhythm.min_valid_passes,
        "km2ByCount": km2_by_count,
        "halfOrMoreKm2": round(float(area_km2[half].sum()), 4),
        "countableKm2": round(float(area_km2[countable].sum()), 4),
        "floodedAtLeastOnceKm2": round(float(area_km2[countable & (fc >= 1)].sum()), 4),
        "byValidPasses": by_denominator,
    }


def pass_stats(water: np.ndarray, valid: np.ndarray, permanent: np.ndarray, in_area: np.ndarray, area_km2: np.ndarray,
               vegetation: np.ndarray | None = None) -> dict:
    """Per-pass areas inside the study area. validFraction is valid pixels / pixels in the study area."""
    area_total = float(area_km2[in_area].sum())
    valid_in = valid & in_area
    flooded = flooded_from(water, valid, permanent) & in_area
    out = {
        "floodedKm2": round(float(area_km2[flooded].sum()), 4),
        "permanentWaterKm2": round(float(area_km2[water & valid_in & permanent].sum()), 4),
        "validKm2": round(float(area_km2[valid_in].sum()), 4),
        "studyAreaKm2": round(area_total, 4),
        "validFraction": round(float(area_km2[valid_in].sum() / area_total), 4) if area_total else None,
    }
    if vegetation is not None:
        out["floodedVegetationKm2"] = round(float(area_km2[vegetation & valid_in].sum()), 4)
    return out
