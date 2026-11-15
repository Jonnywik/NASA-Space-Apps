"""Read-only NISAR flood-rhythm API (N1, N2, N4, N5). Processing happens in scripts 19-22, never in a request.

Serves the product in ``<output_root>/<area>/nisar/manifest.json``. Synthetic products always carry
``dataKind: "synthetic"``. Overlay names must be registered in the manifest; nothing else is served.
"""
import hashlib
import json
import math
import re
from datetime import date as _date
from pathlib import Path

import numpy as np
import rasterio
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from processing.nisar_flood import polarization
from processing.nisar_flood.geo import Grid
from processing.nisar_flood.constants import COLOR_VEGETATION, COLOR_WATER

PREFIX = "/api/v1"
NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
AREA_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
STATE_TEXT = {0: "dry", 1: "water", 2: "water", 3: "dry"}


def _error(status, code, message, **extra):
    return HTTPException(status, detail={"code": code, "message": message, **extra})


def make_router(output_root, read_public_events):
    router = APIRouter(prefix=PREFIX)
    root = Path(output_root)
    manifest_cache = {}
    hash_cache = {}

    # -- helpers ------------------------------------------------------------
    def known_area(area):
        if not isinstance(area, str) or not AREA_RE.match(area) or area not in {e["id"] for e in read_public_events()}:
            raise _error(404, "unknown_area", f"Unknown area {area!r}")
        return area

    def product_dir(area):
        return root / area / "nisar"

    def load(area):
        known_area(area)
        path = product_dir(area) / "manifest.json"
        try:
            stat = path.stat()
        except OSError:
            raise _error(404, "data_unavailable",
                         "No NISAR flood product is published for this area yet. Run scripts/22_nisar_synthetic_demo.py (synthetic) "
                         "or scripts/20_nisar_flood_rhythm.py (real).") from None
        key = (stat.st_mtime_ns, stat.st_size)
        cached = manifest_cache.get(area)
        if cached and cached[0] == key:
            return cached[1]
        try:
            manifest = json.loads(path.read_text())
        except (OSError, ValueError):
            raise _error(404, "data_unavailable", "The NISAR product manifest is unreadable") from None
        if manifest.get("kind") != "nisar-flood-rhythm" or manifest.get("area") != area or "passes" not in manifest:
            raise _error(404, "data_unavailable", "The NISAR product manifest is not a flood-rhythm product for this area")
        manifest_cache[area] = (key, manifest)
        return manifest

    def asset_file(area, manifest, key):
        entry = manifest["assets"].get(key)
        if entry is None:
            raise _error(404, "data_unavailable", "Unknown product asset")
        base = product_dir(area).resolve()
        path = (base / entry["path"]).resolve()
        if not path.is_relative_to(base) or not path.is_file():
            raise _error(404, "data_unavailable", "Product asset is missing")
        return path, entry

    def verified_png(area, manifest, key):
        path, entry = asset_file(area, manifest, key)
        if entry.get("kind") != "overlay-png":
            raise _error(404, "data_unavailable", "Unknown overlay")
        stat = path.stat()
        token = (str(path), stat.st_mtime_ns, stat.st_size)
        if hash_cache.get(token) != entry["sha256"]:
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            if digest.hexdigest() != entry["sha256"]:
                raise _error(404, "data_unavailable", "Overlay failed its integrity check against the manifest")
            hash_cache[token] = entry["sha256"]
        return path

    def overlay_url(area, key):
        return f"{PREFIX}/nisar/overlay/{area}/{key}.png"

    def common(manifest, derived_kind):
        synthetic = manifest["dataKind"] == "synthetic"
        return {
            "area": manifest["area"],
            "dataKind": "synthetic" if synthetic else derived_kind,
            "source": manifest["source"],
            "generatedAt": manifest["generatedAt"],
            "nativeResolution": manifest["nativeResolution"],
            "warnings": list(manifest.get("warnings", [])),
            "limitations": list(manifest.get("limitations", [])),
        }

    def float_or_none(value):
        value = float(value)
        return value if math.isfinite(value) else None

    # -- endpoints ----------------------------------------------------------
    @router.get("/nisar/passes")
    def passes(area: str = Query("camanava_2026")):
        manifest = load(area)
        entries = []
        for p in manifest["passes"]:
            no_data = not p.get("validKm2")
            reason = "no valid pixels on this pass inside the study area" if no_data else None
            assets = p["assets"]
            entries.append({
                "id": p["id"], "date": p["date"], "acquisitionTime": p["acquisitionTime"],
                "acquisitionTimeManila": p.get("acquisitionTimeManila"),
                "productId": p["productId"], "maturity": p["maturity"],
                "floodedKm2": None if no_data else p["floodedKm2"],
                "permanentWaterKm2": None if no_data else p["permanentWaterKm2"],
                "floodedVegetationKm2": None if no_data else p.get("floodedVegetationKm2"),
                "validKm2": p["validKm2"], "validFraction": p["validFraction"],
                "missingReason": reason,
                "overlayUrl": overlay_url(area, assets["overlay"]),
                "backscatterUrl": overlay_url(area, assets["backscatter"]),
                "floodedVegetationUrl": overlay_url(area, assets["vegetation"]),
                "polarizationUrl": overlay_url(area, assets["polarization"]),
            })
        return {
            **common(manifest, "observed"),
            "sensor": manifest["sensor"], "product": manifest["product"],
            "track": manifest["track"].get("track"), "direction": {"D": "descending", "A": "ascending"}.get(manifest["track"].get("direction"), manifest["track"].get("direction")),
            "frame": manifest["track"].get("frame"), "mode": manifest["track"].get("mode"),
            "polarizations": manifest["polarizations"],
            "rule": {**{k: manifest["rule"][k] for k in ("description", "hhThresholdDb", "hvThresholdDb", "calibration")}},
            "permanentWater": manifest["permanentWater"],
            "possibleFloodedVegetation": manifest["vegetation"],
            "verification": manifest.get("verification"),
            "studyAreaKm2": manifest["passes"][0].get("studyAreaKm2") if manifest["passes"] else None,
            "units": {"area": "km2", "backscatter": "dB"},
            "legend": [
                {"id": "flood_water", "label": "Flood water", "color": COLOR_WATER},
                {"id": "possible_flooded_vegetation", "label": "Possible flooded vegetation", "color": COLOR_VEGETATION},
            ],
            "passes": entries,
            "bounds": manifest["bounds"],
        }

    @router.get("/nisar/flood-rhythm")
    def flood_rhythm(area: str = Query("camanava_2026")):
        manifest = load(area)
        r = manifest["rhythm"]
        return {
            **common(manifest, "derived"),
            "passCount": r["passCount"], "minValidPasses": r["minValidPasses"],
            "overlayUrl": overlay_url(area, r["overlay"]), "legendUrl": overlay_url(area, r["legendImage"]),
            "bounds": manifest["bounds"],
            "legend": r["legend"], "km2ByCount": r["km2ByCount"], "halfOrMoreKm2": r["halfOrMoreKm2"],
            "countableKm2": r["countableKm2"], "floodedAtLeastOnceKm2": r["floodedAtLeastOnceKm2"],
            "byValidPasses": r["byValidPasses"],
            "permanentWaterMasked": r["permanentWaterMasked"], "permanentWater": manifest["permanentWater"],
            "units": {"area": "km2"}, "method": r["method"],
        }

    @router.get("/nisar/point")
    def point(area: str = Query("camanava_2026"), lon: str | None = Query(None), lat: str | None = Query(None)):
        manifest = load(area)
        try:
            lon_v, lat_v = float(lon), float(lat)
        except (TypeError, ValueError):
            raise _error(422, "invalid_request", "lon and lat are required numbers (WGS84 degrees)") from None
        if not (math.isfinite(lon_v) and math.isfinite(lat_v) and -180 <= lon_v <= 180 and -90 <= lat_v <= 90):
            raise _error(422, "invalid_request", "lon must be within [-180, 180] and lat within [-90, 90]")
        west, south, east, north = manifest["studyBbox"]
        grid = Grid.from_dict(manifest["grid"])
        row_f, col_f = grid.lonlat_to_rowcol(lon_v, lat_v)
        row, col = int(np.floor(row_f)), int(np.floor(col_f))
        if not (west <= lon_v <= east and south <= lat_v <= north) or not (0 <= row < grid.height and 0 <= col < grid.width):
            raise _error(404, "outside_coverage", "The point is outside the NISAR study area covered by this product")
        window = rasterio.windows.Window(col, row, 1, 1)

        def read_pixel(key):
            path, _ = asset_file(area, manifest, key)
            with rasterio.open(path) as ds:
                return ds.read(window=window)[:, 0, 0]

        permanent = bool(read_pixel("permanent_water")[0] == 1)
        counts = read_pixel("rhythm_counts")
        countable = int(counts[1]) > 0
        per_pass = []
        valid = flooded = veg = 0
        for p in manifest["passes"]:
            state = int(read_pixel(p["assets"]["state"])[0])
            db = read_pixel(p["assets"]["db"])
            nodata = state == 255
            if not nodata:
                valid += 1
                flooded += state == 1
                veg += state == 3
            per_pass.append({
                "date": p["date"], "state": "nodata" if nodata else STATE_TEXT[state],
                "hhDb": None if nodata else float_or_none(db[0]), "hvDb": None if nodata else float_or_none(db[1]),
                "possibleFloodedVegetation": state == 3,
                "reason": "no valid HH/HV at this pixel on this pass (outside swath or invalid)" if nodata else None,
            })
        lon_c, lat_c = grid.rowcol_to_lonlat(row, col)
        if permanent:
            flood_count, reason = None, "permanent water is excluded from the flood rhythm"
        elif not countable:
            flood_count, reason = None, f"fewer than {manifest['rhythm']['minValidPasses']} valid passes at this pixel"
        else:
            flood_count, reason = int(counts[0]), None
        return {
            "area": area, "dataKind": "synthetic" if manifest["dataKind"] == "synthetic" else "derived",
            "lon": lon_v, "lat": lat_v, "cellCenter": {"lon": float(lon_c), "lat": float(lat_c)},
            "floodCount": flood_count, "validCount": valid,
            "floodCountReason": reason, "permanentWater": permanent,
            "possibleFloodedVegetationPasses": int(veg),
            "perPass": per_pass,
            "source": manifest["source"], "generatedAt": manifest["generatedAt"], "nativeResolution": manifest["nativeResolution"],
            "units": {"backscatter": "dB"},
            "warnings": list(manifest.get("warnings", [])), "limitations": list(manifest.get("limitations", [])),
        }

    @router.get("/nisar/overlay/{area}/{filename}")
    def overlay(area: str, filename: str):
        manifest = load(area)
        if not filename.endswith(".png") or not NAME_RE.match(filename[:-4]):
            raise _error(422, "invalid_request", "Overlay names look like pass_YYYYMMDD.png")
        path = verified_png(area, manifest, filename[:-4])
        return FileResponse(path, media_type="image/png",
                            headers={"X-Tanaw-Data-Kind": manifest["dataKind"], "Cache-Control": "public, max-age=300"})

    @router.get("/nisar/polarization")
    def polarization_view(area: str = Query("camanava_2026"), date: str | None = Query(None)):
        manifest = load(area)
        try:
            when = _date.fromisoformat(date or "")
        except ValueError:
            raise _error(422, "invalid_request", "date is required as YYYY-MM-DD") from None
        match = next((p for p in manifest["passes"] if p["date"] == when.isoformat()), None)
        if match is None:
            raise _error(404, "data_unavailable", f"No NISAR pass on {when.isoformat()}",
                         availableDates=[p["date"] for p in manifest["passes"]])
        return {
            **common(manifest, "derived"),
            "date": match["date"], "acquisitionTime": match["acquisitionTime"],
            "rgbUrl": overlay_url(area, match["assets"]["polarization"]), "bounds": manifest["bounds"],
            "channels": dict(polarization.CHANNELS), "explanation": list(polarization.EXPLANATION),
            "units": {"backscatter": "dB"},
            "stretchDb": {"r": [-25, 0], "g": [-35, -10], "b": [0, 20]},
            "warnings": list(manifest.get("warnings", [])) + ["The explanation is general radar-physics text and still needs reviewer sign-off."],
        }

    return router
