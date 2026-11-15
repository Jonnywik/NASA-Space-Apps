"""Bind offline results (validation, robustness, cross-track, timelapse) to the NISAR product they were computed from.

The product manifest's raw SHA-256 differs on every machine that regenerates the product (it holds generatedAt, and
GeoTIFF/PNG bytes are not reproducible across library versions), even when the science is identical. A result is
therefore accepted when EITHER the raw file hash matches (same machine) OR the content fingerprint matches: the passes,
their granules and areas, the water rule and the rhythm area, which are what the result actually depends on.
"""
import hashlib
import json
from pathlib import Path


def _digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def product_fingerprint(manifest: dict) -> str | None:
    try:
        rule = manifest["rule"]
        return _digest({
            "area": manifest["area"], "dataKind": manifest["dataKind"],
            "rule": [round(float(rule["hhThresholdDb"]), 2), round(float(rule["hvThresholdDb"]), 2)],
            "passes": sorted([p["id"], p["productId"], round(float(p["floodedKm2"]), 3),
                              round(float(p["permanentWaterKm2"]), 3), round(float(p["validKm2"]), 2)]
                             for p in manifest["passes"]),
            "halfOrMoreKm2": round(float(manifest["rhythm"]["halfOrMoreKm2"]), 3),
        })
    except (KeyError, TypeError, ValueError):
        return None


def imerg_fingerprint(doc: dict) -> str | None:
    try:
        return _digest(sorted([p["date"], p.get("last48hMm"), p.get("last24hMm"), p.get("last6hMm")] for p in doc["passes"]))
    except (KeyError, TypeError):
        return None


def bound_to_product(recorded: dict, manifest_path: Path) -> bool:
    """True if `recorded` (a dict holding productManifestSha256 and/or productFingerprint) matches the current product."""
    if not isinstance(recorded, dict):
        return False
    try:
        raw = Path(manifest_path).read_bytes()
    except OSError:
        return False
    if recorded.get("productManifestSha256") and recorded["productManifestSha256"] == hashlib.sha256(raw).hexdigest():
        return True
    try:
        fp = product_fingerprint(json.loads(raw))
    except ValueError:
        return False
    return bool(fp) and recorded.get("productFingerprint") == fp


def bound_to_imerg(recorded: dict, imerg_path: Path) -> bool:
    try:
        raw = Path(imerg_path).read_bytes()
    except OSError:
        return False
    if recorded.get("imergCacheSha256") and recorded["imergCacheSha256"] == hashlib.sha256(raw).hexdigest():
        return True
    try:
        fp = imerg_fingerprint(json.loads(raw))
    except ValueError:
        return False
    return bool(fp) and recorded.get("imergFingerprint") == fp
