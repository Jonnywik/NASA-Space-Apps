"""Read-only validation results; calculations are performed offline."""
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException


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
                if (result.get("area") == area and result.get("dataKind") == "derived"
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

    return router
