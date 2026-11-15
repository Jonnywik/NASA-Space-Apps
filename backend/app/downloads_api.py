"""Read-only downloads of published real products and cached observations."""
import csv
import hashlib
import io
import json
import re
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from app.validation_api import make_router as validation_router
from app.product_binding import bound_to_imerg, bound_to_product

PREFIX = "/api/v1"
AREA = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def make_router(output_root, read_public_events):
    router = APIRouter(prefix=PREFIX)
    root = Path(output_root)
    cache = root.parent / "cache"
    validation = validation_router(root, read_public_events).routes[0].endpoint

    def error(code, message):
        return HTTPException(404, detail={"code": code, "message": message})

    def read_json(path):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def csv_bytes(rows, fields):
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow([name for name, _ in fields])
        for row in rows:
            writer.writerow([row.get(key) for _, key in fields])
        return stream.getvalue().encode("utf-8")

    def catalog(area):
        if not AREA.fullmatch(area) or area not in {e["id"] for e in read_public_events()}:
            raise error("unknown_area", "Unknown area")
        files = {}

        def add(id, title, fmt, filename, content, attribution, kind):
            files[id] = ({"id": id, "title": title, "format": fmt, "sizeBytes": len(content),
                          "licence": "CC-BY-4.0", "attribution": attribution, "dataKind": kind,
                          "url": f"{PREFIX}/downloads/{id}?area={quote(area)}"}, filename, content)

        product_dir = (root / area / "nisar").resolve()
        manifest_path = product_dir / "manifest.json"
        manifest = read_json(manifest_path)
        if not isinstance(manifest, dict) or manifest.get("kind") != "nisar-flood-rhythm" or manifest.get("area") != area or manifest.get("dataKind") not in ("observed", "derived"):
            manifest = None
        if manifest:
            assets = manifest.get("assets", {})
            for id, key, filename, title in (
                ("rhythm", "rhythm_tif", "rhythm.tif", "Open-water rhythm count"),
                ("rhythm-half", "rhythm_half_tif", "rhythm_half.tif", "Open water on half or more passes"),
            ):
                entry = assets.get(key, {}) if isinstance(assets, dict) else {}
                try:
                    path = (product_dir / entry["path"]).resolve()
                    if path.is_relative_to(product_dir) and path.name == filename and entry.get("kind") == "geotiff":
                        content = path.read_bytes()
                        if hashlib.sha256(content).hexdigest() == entry.get("sha256"):
                            add(id, title, "GeoTIFF", filename, content, "NASA–ISRO NISAR via ASF", "derived")
                except (OSError, TypeError, KeyError, ValueError, AttributeError):
                    pass
            passes = manifest.get("passes")
            if isinstance(passes, list) and passes and all(isinstance(p, dict) and all(k in p for k in ("date", "floodedKm2", "validFraction", "maturity", "productId")) for p in passes):
                rows = [{**p, "floodedKm2": p["floodedKm2"] if p.get("validKm2") else None} for p in passes]
                content = csv_bytes(rows, [("date", "date"), ("openWaterKm2", "floodedKm2"), ("validFraction", "validFraction"), ("maturity", "maturity"), ("productId", "productId")])
                add("open-water-passes", "Open water outside usual water by pass", "CSV", "open_water_passes.csv", content, "NASA–ISRO NISAR via ASF", "derived")

        for id, path, title, filename, fields, attribution in (
            ("imerg-passes", cache / "climate" / "imerg_passes.json", "IMERG rainfall by pass", "imerg_passes.csv",
             [(k, k) for k in ("date", "acquisitionTime", "last3hMm", "last6hMm", "last12hMm", "last24hMm", "last48hMm", "peakMmHr", "peakAt", "hoursSinceRain", "missingHalfHours")], "NASA GPM IMERG via NASA GES DISC"),
            ("soil-moisture-passes", cache / "nisar" / "soil_moisture" / "manifest.json", "NISAR soil moisture by pass", "soil_moisture_passes.csv",
             [(k, k) for k in ("date", "acquisitionTime", "productId", "maturity", "medianM3M3", "meanM3M3", "p10M3M3", "p90M3M3", "medianUncertaintyM3M3", "recommendedPixels", "studyPixels", "recommendedFraction", "prior3DayMm")], "NASA–ISRO NISAR via ASF"),
        ):
            doc = read_json(path)
            if isinstance(doc, dict) and doc.get("area") == area and doc.get("dataKind") in ("observed", "derived") and isinstance(doc.get("passes"), list) and doc["passes"] and all(isinstance(p, dict) and p.get("date") for p in doc["passes"]):
                add(id, title, "CSV", filename, csv_bytes(doc["passes"], fields), attribution, doc["dataKind"])

        try:
            validation(area)
            content = (cache / "validation" / f"{area}.json").read_bytes()
            add("validation", "NISAR and OPERA validation", "JSON", "validation.json", content, "NASA–ISRO NISAR via ASF; NASA OPERA DSWx-S1 via PO.DAAC", "derived")
        except (HTTPException, OSError):
            pass

        sidecar = read_json(cache / "nisar" / "timelapse.json")
        if manifest and isinstance(sidecar, dict) and sidecar.get("dataKind") == "derived":
            try:
                gif = (cache / "nisar" / "timelapse.gif").read_bytes()
                if (hashlib.sha256(gif).hexdigest() == sidecar.get("gifSha256")
                        and bound_to_product(sidecar, manifest_path)
                        and bound_to_imerg(sidecar, cache / "climate" / "imerg_passes.json")):
                    add("timelapse", "NISAR season timelapse", "GIF", "timelapse.gif", gif, "NASA–ISRO NISAR via ASF; NASA GPM IMERG via NASA GES DISC", "derived")
            except OSError:
                pass
        return files

    @router.get("/downloads")
    def list_downloads(area: str = "camanava_2026"):
        return [item[0] for item in catalog(area).values()]

    @router.get("/downloads/{id}")
    def download(id: str, area: str = "camanava_2026"):
        item = catalog(area).get(id)
        if item is None:
            raise error("data_unavailable", "Download is unavailable")
        meta, filename, content = item
        media = {"GeoTIFF": "image/tiff", "CSV": "text/csv", "JSON": "application/json", "GIF": "image/gif"}[meta["format"]]
        return Response(content, media_type=media, headers={"Content-Disposition": f'attachment; filename="{filename}"', "X-Tanaw-Data-Kind": meta["dataKind"]})

    @router.get("/nisar/timelapse.gif")
    def timelapse(area: str = "camanava_2026"):
        response = download("timelapse", area)
        response.headers["Content-Disposition"] = 'inline; filename="timelapse.gif"'
        return response

    return router
