"""Cache files plus a manifest (query, retrievedAt, sha256) under data/cache/climate/."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .constants import CACHE_DIR


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _manifest_path(cache_dir: Path) -> Path:
    return cache_dir / "manifest.json"


def read_manifest(cache_dir: Path = CACHE_DIR) -> dict:
    try:
        return json.loads(_manifest_path(cache_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def write_cache(name: str, payload: dict, query: dict, *, cache_dir: Path = CACHE_DIR,
                retrieved_at: str | None = None) -> dict:
    """Write payload as <name>.json and record it in the manifest. Returns the manifest entry."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    path = cache_dir / f"{name}.json"
    path.write_bytes(body)
    entry = {"file": path.name, "query": query, "retrievedAt": retrieved_at or utcnow(),
             "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)}
    manifest = read_manifest(cache_dir)
    manifest[name] = entry
    _manifest_path(cache_dir).write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return entry


def record_error(name: str, message: str, *, cache_dir: Path = CACHE_DIR) -> None:
    """Remember that a refresh failed without discarding the previous cache."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    manifest = read_manifest(cache_dir)
    entry = manifest.setdefault(name, {})
    entry["lastRefreshError"] = {"message": message[:300], "at": utcnow()}
    _manifest_path(cache_dir).write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


def read_cache(name: str, *, cache_dir: Path = CACHE_DIR):
    """Return (payload, manifest_entry) or (None, None) when absent or the hash does not match."""
    entry = read_manifest(cache_dir).get(name)
    path = cache_dir / f"{name}.json"
    if not entry or "sha256" not in entry or not path.exists():
        return None, None
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != entry["sha256"]:
        return None, None
    return json.loads(body), entry
