"""Read-only validation results; calculations are performed offline."""
import json
import hashlib
from pathlib import Path
from fastapi import APIRouter, HTTPException
from app.product_binding import bound_to_product


def make_router(output_root, read_public_events):
    router = APIRouter(prefix="/api/v1")
    cache = Path(output_root).parent / "cache" / "validation"

    @router.get("/validation")
    def validation(area: str = "camanava_2026"):
        if area not in {event["id"] for event in read_public_events()}:
            raise HTTPException(404, detail={"code": "unknown_area", "message": "Unknown area"})
        path = cache / f"{area}.json"
        if path.is_file():
            try:
                result = json.loads(path.read_text(encoding="utf-8"))
                sources = result.get("source", {})
                product = Path(output_root) / area / "nisar" / "manifest.json"
                if (result.get("area") == area and result.get("dataKind") == "derived"
                        and isinstance(sources, dict) and bound_to_product(sources.get("nisar"), product)
                        and result.get("status") == "partial" and isinstance(sources, dict)
                        and all(isinstance(sources.get(name), dict)
                                and sources[name].get("dataKind") in ("observed", "derived")
                                for name in ("nisar", "reference"))
                        and isinstance(result.get("agreement"), dict)):
                    return result
            except (ValueError, OSError, AttributeError, TypeError):
                pass
        raise HTTPException(404, detail={"code": "data_unavailable",
                                        "message": "No observed NISAR and independent reference comparison is available; synthetic products cannot establish validation."})

    @router.get("/validation/robustness")
    def robustness(area: str = "camanava_2026"):
        """Bootstrap, leave-one-out and permutation checks of the headline findings (script 62)."""
        if area not in {event["id"] for event in read_public_events()}:
            raise HTTPException(404, detail={"code": "unknown_area", "message": "Unknown area"})
        path = cache / "robustness.json"
        product = Path(output_root) / area / "nisar" / "manifest.json"
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
            if (result.get("area") == area and result.get("dataKind") == "derived"
                    and bound_to_product(result, product)
                    and isinstance(result.get("correlations"), list)):
                return result
        except (ValueError, OSError, AttributeError, TypeError):
            pass
        raise HTTPException(404, detail={"code": "data_unavailable",
                                        "message": "No robustness checks match the current observed NISAR product; run scripts/62_robustness.py."})

    @router.get("/validation/cross-track")
    def cross_track(area: str = "camanava_2026"):
        """Independent replication on NISAR track 32 descending plus 10 same-time-of-day OPERA matches (script 63)."""
        if area not in {event["id"] for event in read_public_events()}:
            raise HTTPException(404, detail={"code": "unknown_area", "message": "Unknown area"})
        path = cache / "cross_track.json"
        product = Path(output_root) / area / "nisar" / "manifest.json"
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
            if (result.get("area") == area and result.get("dataKind") == "derived"
                    and bound_to_product(result, product)
                    and isinstance(result.get("geometryAgreement"), dict)):
                return result
        except (ValueError, OSError, AttributeError, TypeError):
            pass
        raise HTTPException(404, detail={"code": "data_unavailable",
                                        "message": "No cross-track check matches the current observed NISAR product; run scripts/63_cross_track.py."})

    return router
