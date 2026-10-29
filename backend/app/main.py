"""
app/main.py  -  the Tanaw API (FastAPI).

Run it (from the tanaw-backend folder):
    uvicorn app.main:app --reload

Then open in your browser:
    http://127.0.0.1:8000/docs                     <- automatic test page
    http://127.0.0.1:8000/api/v1/events
    http://127.0.0.1:8000/api/v1/flood-extent?event=test_event

This API does NOT process radar data. The scripts already did that.
It only reads the result files in data/output/ and sends them out.
"""
import json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from app.p3_api import make_router
from app.coherence_api import make_router as make_coherence_router
from processing.p3.catalog import capabilities

ROOT = Path(__file__).resolve().parent.parent
EVENTS_FILE = ROOT / "events.json"
OUTPUT = ROOT / "data" / "output"

app = FastAPI(title="Tanaw API", version="0.1")

# Make big responses smaller on the wire
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS: without this, the browser BLOCKS the Next.js site (localhost:3000)
# from reading this API (localhost:8000). "*" is fine for a hackathon demo
# because the API is read-only public data.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def read_events():
    with open(EVENTS_FILE, encoding="utf-8") as f:
        return json.load(f)


def has_result(event_id: str) -> bool:
    folder = OUTPUT / event_id
    return (folder / "flood_extent.json").exists() and (folder / "flood.geojson").exists()


@app.get("/health")
def health():
    """Quick check that the server is alive."""
    return {"status": "ok"}


@app.get("/api/v1/events")
def list_events():
    """All events, and whether their results are ready."""
    return [
        {
            "id": e["id"],
            "name": e["name"],
            "aoi": e["aoi"],
            "beforeDate": e["before_date"],
            "afterDate": e["after_date"],
            "ready": has_result(e["id"]),
            "capabilities": capabilities(e["id"], root=OUTPUT),
        }
        for e in read_events()
    ]


@app.get("/api/v1/flood-extent")
def flood_extent(event: Optional[str] = Query(default=None, description="event id, e.g. karding_2022")):
    """Flood shapes + numbers for one event (the frontend map + stats sidebar)."""
    events = read_events()
    known_ids = [e["id"] for e in events]

    if event is None:
        # no event asked for: use the first one that has results
        ready = [i for i in known_ids if has_result(i)]
        if not ready:
            raise HTTPException(status_code=404, detail="No results yet. Run the scripts first.")
        event = ready[0]

    if event not in known_ids:
        raise HTTPException(status_code=404, detail=f"Unknown event '{event}'. Known: {known_ids}")
    if not has_result(event):
        raise HTTPException(status_code=404, detail=f"No results for '{event}' yet. Run scripts 02 and 03.")

    folder = OUTPUT / event
    result = json.loads((folder / "flood_extent.json").read_text())
    result["floodGeojson"] = json.loads((folder / "flood.geojson").read_text())

    # before/after pictures for the slider (made by script 04; null if not made yet)
    overlays = None
    overlays_file = folder / "overlays.json"
    if overlays_file.exists() and (folder / "water_before.png").exists() and (folder / "water_after.png").exists():
        overlays = {
            "beforeUrl": f"/api/v1/overlay/{event}/before",
            "afterUrl": f"/api/v1/overlay/{event}/after",
            "bounds": json.loads(overlays_file.read_text())["bounds"],   # [[south, west], [north, east]]
        }
    result["overlays"] = overlays
    return result


@app.get("/api/v1/overlay/{event}/{which}")
def overlay(event: str, which: str):
    """The see-through water picture (PNG) for the slider. which = before or after."""
    if event not in [e["id"] for e in read_events()]:
        raise HTTPException(status_code=404, detail=f"Unknown event '{event}'.")
    if which not in ("before", "after"):
        raise HTTPException(status_code=404, detail="which must be 'before' or 'after'.")
    path = OUTPUT / event / f"water_{which}.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Picture not made yet. Run scripts/04_export_overlays.py.")
    return FileResponse(path, media_type="image/png")


app.include_router(make_router(OUTPUT, read_events))
app.include_router(make_coherence_router(OUTPUT, read_events))
