"""Publish mapped OSM footprint overlap with a normalized hazard product."""

import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from processing.building_exposure import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
