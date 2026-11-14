"""Build the inputs that scripts 10, 11 and 12 need for a chain of NISAR GUNW pairs (N3).

Script 10 (``processing.p3.ingestion``) takes one *source manifest* per GUNW file: local path, SHA-256, provenance and an
explicit source profile (dataset paths, CRS, units). Script 11 (``processing.p3.phase``) takes the normalised GUNW manifest from
script 10 plus a *reference config* (stable reference area, coherence threshold). Script 12 (``processing.p3.series``) takes the
LOS-pair manifests from script 11.

Nothing that is not known is invented here. Values that must be checked on the first real GUNW file are either marked in the
written JSON (``_unverified``), or deliberately written as a placeholder that makes script 10/11 refuse to run until a person
sets them (phase sign, reference area).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import h5py
import numpy as np

from .constants import STUDY_BBOX, GcovLayout
from .gcov import _read_crs, sha256_file
from .geo import OutsideGrid, window_for_bbox

EVENT = "camanava_2026"
L_BAND_CENTER_HZ = 1.2575e9  # NISAR L-band nominal centre frequency; confirm against the file's metadata on the first read
SPEED_OF_LIGHT = 299_792_458.0
WAVELENGTH_M = round(SPEED_OF_LIGHT / L_BAND_CENTER_HZ, 4)
SIGN_PLACEHOLDER = "SET-+1-OR--1-AFTER-CHECKING-THE-PRODUCT-SPEC"
SHA_PLACEHOLDER = "PENDING-download-then-rerun-with---fill-hashes"

# Dataset paths follow the public NISAR GUNW spec layout. UNVERIFIED until checked on a real file.
GUNW_BASE = "/science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram"
GUNW_POL = "HH"


def gunw_paths(base: str = GUNW_BASE, pol: str = GUNW_POL) -> dict:
    return {
        "x": f"{base}/xCoordinates", "y": f"{base}/yCoordinates", "projection": f"{base}/projection",
        "phase": f"{base}/{pol}/unwrappedPhase", "coherence": f"{base}/{pol}/coherenceMagnitude",
        "components": f"{base}/{pol}/connectedComponents", "ionosphere": f"{base}/{pol}/ionospherePhaseScreen",
    }


def local_name(row: dict) -> str:
    return f"{row['title']}.h5"


def inspect_local_file(path: Path, paths: dict, bbox=STUDY_BBOX) -> dict:
    """Read CRS and the study-area window from a local GUNW file (coordinates only; no rasters)."""
    layout = GcovLayout(base=paths["x"].rsplit("/", 1)[0], projection="projection", x="xCoordinates", y="yCoordinates")
    with h5py.File(path, "r") as handle:
        for key in ("x", "y", "phase", "coherence", "components"):
            if paths[key] not in handle:
                raise ValueError(f"{paths[key]!r} is not in {path.name}; fix --gunw-base/--gunw-pol after inspecting the file")
        x = np.asarray(handle[paths["x"]][...], dtype="float64")
        y = np.asarray(handle[paths["y"]][...], dtype="float64")
        crs, how = _read_crs(handle, layout)
        try:
            rows, cols, _, info = window_for_bbox(x, y, crs, bbox, pad=8)
        except OutsideGrid:
            return {"crs": crs, "crsSource": how, "window": None, "outside": True, "shape": [int(y.size), int(x.size)]}
        return {"crs": crs, "crsSource": how, "shape": [int(y.size), int(x.size)],
                "window": {"rowStart": rows.start, "rowStop": rows.stop, "colStart": cols.start, "colStop": cols.stop}, "outside": False}


def build_ingest_config(row: dict, *, config_dir: Path, raw_dir: Path, paths: dict, phase_sign=None,
                        corrections_applied: list[str] | None = None, ionosphere_sign: str | None = None,
                        fill_hashes: bool = False, bbox=STUDY_BBOX) -> tuple[dict, dict]:
    """One script-10 source manifest for a GUNW pair row from the script-19 manifest. Returns (config, status)."""
    file_path = Path(raw_dir) / local_name(row)
    present = file_path.is_file()
    status = {"pair": f"{row['referenceDate']}_{row['secondaryDate']}", "file": str(file_path), "downloaded": present, "problems": []}
    sha = SHA_PLACEHOLDER
    inspected = None
    if present:
        if fill_hashes:
            sha = sha256_file(file_path)
        inspected = inspect_local_file(file_path, paths, bbox)
        if inspected.get("outside"):
            status["problems"].append("study bbox is outside this GUNW grid")
    else:
        status["problems"].append("file not downloaded yet")
    if sha == SHA_PLACEHOLDER and present:
        status["problems"].append("sha256 not filled (run with --fill-hashes)")
    if phase_sign not in (-1, 1):
        status["problems"].append("phaseToAwaySign is a placeholder: set --phase-sign after checking the product spec")
    profile = {
        "id": "nisar-gunw-unwrapped-hh", "version": "1", "adapter": "hdf5", "status": "needs-review", "evidence": [],
        "arrayAxisOrder": "yx", "crs": (inspected or {}).get("crs", "EPSG:32651"),
        "coordinateDatasets": {"x": paths["x"], "y": paths["y"]},
        "datasets": {"phase": {"path": paths["phase"], "units": "radian"},
                     "coherence": {"path": paths["coherence"], "units": "1"},
                     "components": {"path": paths["components"], "units": "label"}},
    }
    if inspected and inspected.get("window"):
        profile["window"] = inspected["window"]
    if ionosphere_sign:
        profile["corrections"] = {"ionosphere": {"path": paths["ionosphere"], "units": "radian", "appliesTo": "phase",
                                                 "signConvention": ionosphere_sign}}
    config = {
        "configVersion": "1.0", "event": EVENT, "productType": "GUNW", "dataKind": "observed",
        "source": {
            "path": os.path.relpath(file_path, config_dir), "sha256": sha, "productId": row["title"], "sensor": "NISAR",
            "frequency": "L", "polarization": "/".join(row.get("frequencyAPolarizations") or ["HH"]),
            "orbit": f"track {row['track']} {'descending' if row['direction'] == 'D' else 'ascending'}", "frame": str(row["frame"]),
            "processingVersion": str(row.get("productVersion") or row["collectionShortName"]), "maturity": row["maturity"],
            "acquisitionDates": [row["referenceTime"], row["secondaryTime"]],
            "wavelengthMetres": WAVELENGTH_M, "wavelengthUnits": "metre",
            "phaseToAwaySign": phase_sign if phase_sign in (-1, 1) else SIGN_PLACEHOLDER, "phaseUnits": "radian",
            "correctionsApplied": list(corrections_applied or []),
            "quality": {"cmrBboxCoverageFraction": row.get("bboxCoverageFraction"), "pairDays": row.get("pairDays")},
        },
        "sourceProfile": profile,
        "_unverified": [
            "dataset paths, units and CRS follow the public spec and have not been read from a real file",
            f"wavelength {WAVELENGTH_M} m is c / {L_BAND_CENTER_HZ / 1e9} GHz; confirm against the file's centre-frequency metadata",
            "correctionsApplied is the empty list unless --corrections-applied was given; check what the provisional GUNW already applied",
        ],
    }
    return config, status


def reference_polygon(bbox: tuple[float, float, float, float]) -> dict:
    west, south, east, north = bbox
    return {"type": "Polygon", "coordinates": [[[west, south], [east, south], [east, north], [west, north], [west, south]]]}


# A neutral candidate in the north-east corner of the study bbox. It was NOT chosen from data: replace it after looking at the
# coherence map and choosing hard, stable ground away from the Manila Bay coast.
CANDIDATE_REFERENCE_BBOX = (121.00, 14.76, 121.04, 14.82)


def build_reference_config(track_label: str, bbox: tuple | None = None, min_coherence: float = 0.3) -> tuple[dict, bool]:
    placeholder = bbox is None
    config = {
        "referenceId": f"camanava-ref-{track_label}",
        "reference": {"polygonWgs84": reference_polygon(bbox or CANDIDATE_REFERENCE_BBOX)},
        "minCoherence": min_coherence, "minimumReferencePixels": 5, "correctionsToSubtract": [],
        "_status": ("PLACEHOLDER reference area chosen without data. Replace it with --reference-bbox after checking coherence and "
                    "known stable ground." if placeholder else "operator-chosen reference area"),
    }
    return config, placeholder


def chain_shell_script(track_label: str, ingest_files: list[str], reference_file: str, root_hint: str = "data/output") -> str:
    lines = ["#!/usr/bin/env bash", f"# GUNW chain for {EVENT} ({track_label}). Run from the backend folder. Generated by scripts/21_nisar_gunw_chain.py.",
             "set -euo pipefail", f'OUT="{root_hint}"', 'LOS=()']
    for cfg in ingest_files:
        lines += [f'GUNW=$(python scripts/10_ingest_nisar.py {EVENT} --inputs "{cfg}" --output-root "$OUT" | tail -n 1)',
                  f'python scripts/11_phase_to_los.py {EVENT} --inputs "$GUNW" --config "{reference_file}" --output-root "$OUT"',
                  f'LOS+=("$(ls -dt "$OUT/{EVENT}/p3/los-pair"/*/manifest.json | head -n 1)")']
    lines += ["ARGS=()", 'for p in "${LOS[@]}"; do ARGS+=(--pair "$p"); done',
              f'python scripts/12_motion_series.py {EVENT} "${{ARGS[@]}}" --output-root "$OUT"',
              'echo "Done. Review the ground-motion product, then promote it (scripts/17_review_product.py) before the API serves it."']
    return "\n".join(lines) + "\n"


def write_chain(manifest: dict, out_dir: Path, raw_dir: Path, *, paths: dict, phase_sign=None, corrections_applied=None,
                ionosphere_sign=None, fill_hashes=False, reference_bbox=None, max_pairs: int | None = None,
                bbox=STUDY_BBOX) -> dict:
    """Write ingest_*.json, reference_*.json and run_gunw_chain.sh. Returns a summary including per-pair problems."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = manifest["gunw"][:max_pairs] if max_pairs else manifest["gunw"]
    if not rows:
        raise ValueError("The manifest has no GUNW pairs; run script 19 first")
    sel = manifest["selection"]
    label = f"t{sel['track']:03d}_{sel['direction']}_f{sel['frame']:03d}"
    files, statuses = [], []
    for row in rows:
        config, status = build_ingest_config(row, config_dir=out_dir, raw_dir=raw_dir, paths=paths, phase_sign=phase_sign,
                                             corrections_applied=corrections_applied, ionosphere_sign=ionosphere_sign,
                                             fill_hashes=fill_hashes, bbox=bbox)
        name = f"ingest_{row['referenceDate'].replace('-', '')}_{row['secondaryDate'].replace('-', '')}.json"
        (out_dir / name).write_text(json.dumps(config, indent=2) + "\n")
        files.append(name)
        statuses.append(status)
    reference, placeholder = build_reference_config(label, reference_bbox)
    ref_name = f"reference_{label}.json"
    (out_dir / ref_name).write_text(json.dumps(reference, indent=2) + "\n")
    rel = lambda n: str((out_dir / n).resolve())  # noqa: E731  (absolute: the script is machine-specific)
    script = chain_shell_script(label, [rel(n) for n in files], rel(ref_name))
    (out_dir / "run_gunw_chain.sh").write_text(script)
    gaps = manifest.get("gunwChainGaps") or []
    return {"outDir": str(out_dir), "ingestConfigs": files, "referenceConfig": ref_name, "referenceIsPlaceholder": placeholder,
            "shellScript": "run_gunw_chain.sh", "pairs": statuses, "chainGaps": gaps,
            "downloadGB": round(sum(r.get("sizeBytes") or 0 for r in rows) / 1e9, 1)}


def blocking_problems(summary: dict) -> list[str]:
    problems = []
    if summary["referenceIsPlaceholder"]:
        problems.append("reference area is a placeholder (pass --reference-bbox)")
    for pair in summary["pairs"]:
        for problem in pair["problems"]:
            problems.append(f"{pair['pair']}: {problem}")
    return problems
