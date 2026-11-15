"""Serve the whole Tanaw app from one process: the FastAPI backend plus the static frontend export.

Used by the hosted demo (deploy/huggingface/Dockerfile). Local development does not need it.
    TANAW_STATIC_EXPORT=1 NEXT_PUBLIC_API_URL=same-origin npm run build   (in frontend/, writes frontend/out)
    python deploy/serve.py                                                (from the repository root)
API routes are registered first, so /api/... always reaches the backend; every other path is a static file.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT / "backend")

import uvicorn  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from app.main import app  # noqa: E402

app.mount("/", StaticFiles(directory=ROOT / "frontend" / "out", html=True), name="web")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "7860")))
