"""Shared constants for the NISAR flood-rhythm chain.

The study area, bbox and default track come from ``docs/API_CONTRACT.md``.
Dataset paths inside NISAR HDF5 files are configuration, not discovery: they
follow the public GCOV/GUNW product specification and MUST be verified on the
first real file (see docs/NISAR_RUNBOOK.md, "First real file").
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]

AREA_ID = "camanava_2026"
STUDY_BBOX = (120.88, 14.60, 121.04, 14.82)  # W, S, E, N (WGS84)
# Wider box used in the 15 Nov catalogue check (docs/SUBMISSION_SCOPE.md, section 5).
CATALOGUE_CHECK_BBOX = (120.85, 14.55, 121.10, 14.95)

# Contract default track. NOTE: the real CMR footprints show this track covers
# only about a third of STUDY_BBOX (see data/cache/nisar manifests and the runbook).
DEFAULT_TRACK = 133
DEFAULT_DIRECTION = "D"
DEFAULT_FRAME = 81
DEFAULT_MODE = "4005"

# NASA CMR collections (verified 15 Nov 2026).
CMR_GRANULES_URL = "https://cmr.earthdata.nasa.gov/search/granules.umm_json"
GCOV_COLLECTIONS = {
    "C2854338529-ASF": ("NISAR_L2_GCOV_PROVISIONAL_V1", "provisional"),
    "C3622241360-ASF": ("NISAR_L2_GCOV_V1", "v1"),
}
GUNW_COLLECTIONS = {
    "C2854335566-ASF": ("NISAR_L2_GUNW_PROVISIONAL_V1", "provisional"),
    "C3622247503-ASF": ("NISAR_L2_GUNW_V1", "v1"),
}

# Water rule defaults (contract values). They are provisional defaults until
# calibrate_rule() has been run on a real pass; the manifest says which.
DEFAULT_HH_THRESHOLD_DB = -18.0
DEFAULT_HV_THRESHOLD_DB = -26.0
DEFAULT_PERMANENT_FRACTION = 0.90
DEFAULT_MIN_VALID_PASSES = 3
DEFAULT_VEGETATION_MARGIN_DB = 3.0
DEFAULT_VEGETATION_LANDCOVER_CLASSES = (40, 90, 95)  # WorldCover: cropland, herbaceous wetland, mangroves

# Manila Bay open water inside STUDY_BBOX, used to calibrate the water rule once.
# Chosen from map knowledge (well offshore of the Navotas / Obando shoreline),
# NOT from SAR data: verify on an overlay before trusting the calibration.
CALIBRATION_WATER_BBOX = (120.885, 14.62, 120.897, 14.70)

RGB_STRETCH_DB = {"r": (-25.0, 0.0), "g": (-35.0, -10.0), "b": (0.0, 20.0)}

# Colour-blind-safe palette (Okabe-Ito).
COLOR_WATER = "#0072B2"
COLOR_VEGETATION = "#E69F00"
COLOR_PERMANENT = "#999999"

EARTHDATA_TOKEN_ENV = "EARTHDATA_TOKEN"


@dataclass(frozen=True)
class GcovLayout:
    """HDF5 dataset paths for a GCOV product. Verify on the first real file."""

    base: str = "/science/LSAR/GCOV/grids/frequencyA"
    hh: str = "HHHH"
    hv: str = "HVHV"
    x: str = "xCoordinates"
    y: str = "yCoordinates"
    projection: str = "projection"
    mask: str | None = None  # optional validity layer (value > 0 means valid); off by default
    # Coordinates are pixel centres in the NISAR spec; verify on the first file.
    coordinates_are: str = "center"
    # CRS fallback when the file's projection dataset has no EPSG attribute.
    crs_fallback: str | None = None

    def path(self, name: str) -> str:
        return f"{self.base.rstrip('/')}/{name}"


DEFAULT_LAYOUT = GcovLayout()
