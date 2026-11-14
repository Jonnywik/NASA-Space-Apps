# Tanaw v5.1 API contract and ownership

The coordinator owns this file. Agents may refine field details **inside their own section** and must keep it accurate. Scope and rationale are in `docs/SUBMISSION_SCOPE.md`.

## Shared constants

| Item | Value |
|---|---|
| Study area id | `camanava_2026` |
| Name | CAMANAVA and the Bulacan coast (Caloocan, Malabon, Navotas, Valenzuela, Obando, Meycauayan, Marilao) |
| Bbox (W, S, E, N; WGS84) | `[120.88, 14.60, 121.04, 14.82]` |
| Representative climate point | lon `120.96`, lat `14.70` |
| Wet season | June–November |
| NISAR default track | 133 descending, frame 081, mode 4005 DHDH (HH+HV), 23 Jun–2 Nov 2026 |
| Climate baseline | 1991–2020 |
| History start | 2000-01-01 |

## Rules for every endpoint

- Prefix `/api/v1`. GET only. JSON in camelCase.
- Every success body carries: `dataKind` (`observed` | `derived` | `outlook` | `scenario` | `synthetic`), `source` (name, URL, version), `generatedAt` or `retrievedAt` (ISO 8601 UTC), `units` where relevant, `nativeResolution`, `warnings: []`, `limitations: []`.
- Errors use the existing shape `{"detail": {"code": "...", "message": "..."}}`. Codes: `data_unavailable` (404), `unknown_area` (404), `invalid_request` (422), `outside_coverage` (404), `upstream_unavailable` (503, with `cachedAt` if a dated cache was served instead).
- Missing values are `null` with a reason. They are never 0.
- **Synthetic data must always carry `dataKind: "synthetic"`.** The frontend shows a badge for it, and the public build refuses it.
- No credentials in code, logs, Git or responses. The Earthdata token is read from the env var `EARTHDATA_TOKEN` only.
- Raster overlays are PNGs with `bounds: [[south, west], [north, east]]`, as in the existing `/api/v1/overlay`.

## Ownership

Agents share one workspace. Edit only your own paths. **Do not run `git commit`, `push`, `checkout`, `stash` or `reset`.** The coordinator commits and registers routers in `backend/app/main.py`. Report any new Python or npm dependencies; do not edit `backend/requirements*.txt`.

| Agent | Owns |
|---|---|
| **B: NISAR** | `backend/processing/nisar_flood/`, `backend/app/nisar_api.py`, `backend/scripts/19_*.py`, `backend/scripts/2[0-2]_nisar_*.py`, `backend/tests/test_nisar_*.py`, `backend/events.json` (add the `camanava_2026` entry only), `docs/NISAR_RUNBOOK.md` |
| **A: Climate and scenarios** | `backend/processing/climate/`, `backend/app/climate_api.py`, `backend/scripts/3[0-9]_*.py`, `backend/tests/test_climate_*.py`, `backend/data/cache/climate/` |
| **D: Places and exposure** | `backend/processing/places/`, `backend/app/places_api.py`, `backend/scripts/4[0-9]_*.py`, `backend/tests/test_places_*.py`, `backend/data/cache/places/` |
| **C: Frontend** | everything under `frontend/` |
| **E: Packaging** | `README.md`, `LICENSE`, `.github/`, `docs/DATA_MANIFEST.md` |
| Coordinator | `backend/app/main.py`, `backend/requirements*.txt`, `docs/SUBMISSION_SCOPE.md`, this file, spot check and briefing (wave 2) |

Each router module exposes `make_router(output_root, read_public_events)`, like `backend/app/p3_api.py`.

## B: NISAR (`nisar_api.py`)

### `GET /nisar/passes?area=camanava_2026`
```json
{
  "area": "camanava_2026", "dataKind": "observed", "sensor": "NISAR L-band SAR",
  "product": "L2 GCOV", "track": 133, "direction": "descending", "frame": 81,
  "polarizations": ["HH", "HV"],
  "rule": {"description": "...", "hhThresholdDb": -18.0, "hvThresholdDb": -26.0, "calibration": "..."},
  "passes": [{
    "id": "20260623", "date": "2026-06-23", "acquisitionTime": "2026-06-23T10:32:20Z",
    "productId": "NISAR_L2_PR_GCOV_...", "maturity": "provisional",
    "floodedKm2": 12.3, "permanentWaterKm2": 40.1, "floodedVegetationKm2": 1.2,
    "validKm2": 380.0, "validFraction": 0.97,
    "overlayUrl": "/api/v1/nisar/overlay/camanava_2026/pass_20260623.png",
    "backscatterUrl": "/api/v1/nisar/overlay/camanava_2026/hh_20260623.png"
  }],
  "bounds": [[14.60, 120.88], [14.82, 121.04]],
  "source": {}, "generatedAt": "...", "warnings": [], "limitations": []
}
```

### `GET /nisar/flood-rhythm?area=`
```json
{
  "area": "camanava_2026", "dataKind": "derived", "passCount": 11,
  "overlayUrl": "/api/v1/nisar/overlay/camanava_2026/rhythm.png",
  "bounds": [[14.60, 120.88], [14.82, 121.04]],
  "legend": [{"count": 1, "color": "#..."}],
  "km2ByCount": [{"count": 1, "km2": 5.2}],
  "halfOrMoreKm2": 3.4, "permanentWaterMasked": true,
  "method": "count of passes classified as water, over the count of valid passes, per pixel; permanent water excluded",
  "source": {}, "generatedAt": "...", "warnings": [], "limitations": []
}
```

### `GET /nisar/point?area=&lon=&lat=`
Returns `{ "lon", "lat", "cellCenter", "floodCount", "validCount", "permanentWater": false, "perPass": [{"date": "2026-06-23", "state": "water" | "dry" | "nodata", "hhDb": -19.2, "hvDb": -27.0}], "dataKind" }`. Outside coverage gives 404 `outside_coverage`.

### `GET /nisar/overlay/{area}/{name}.png`
Serves a PNG. `name` must come from a registered manifest; arbitrary paths are refused.

### `GET /nisar/polarization?area=&date=`
Returns `{ "rgbUrl", "bounds", "channels": {"r": "HH", "g": "HV", "b": "HH/HV"}, "explanation": ["...", "...", "..."] }`.

### Ground motion
This reuses the existing P3 routes with `event=camanava_2026`: `/ground-motion` and `/ground-motion/point`. B registers the event and provides `scripts/21_nisar_gunw_chain.py`, which builds the pair configs for scripts 10–12 from the CMR listing.

## A: Climate, history, outlook, scenarios (`climate_api.py`)

### `GET /climate/rainfall/monthly?area=`
`{ "point": {"lon", "lat"}, "units": "mm", "baseline": {"period": "1991-2020", "monthlyMeanMm": [12 values]}, "series": [{"year": 2000, "month": 1, "totalMm": 12.1, "anomalyMm": -3.0, "anomalyPct": -20.0, "missingDays": 0}], "source", "nativeResolution": "0.5° x 0.625°", "dataKind": "derived", "retrievedAt", "limitations": ["one grid cell, not a city average"] }`

### `GET /climate/rainfall/daily?area=&start=YYYY-MM-DD&end=YYYY-MM-DD`
`{ "units": "mm/day", "days": [{"date", "mm": 12.3}] }`, with `mm: null` when missing.

### `GET /climate/rainfall/season-rank?area=&year=2026`
`{ "season": "Jun-Nov", "year": 2026, "totalMm", "rank": 3, "of": 27, "complete": false, "seasons": [{"year", "totalMm", "complete"}] }`

### `GET /climate/rainfall/trend?area=`
`{ "method": "linear fit on monthly anomalies, seasonal cycle removed", "period": "2000-2026", "slopeMmPerDecade", "ci95": [lo, hi], "n", "significant": false, "limitations": [] }`

### `GET /climate/pass-rainfall?area=&dates=2026-06-23,2026-07-05`
`{ "passes": [{"date", "prior3DayMm", "prior7DayMm", "sameDayMm"}] }`. If `dates` is omitted, the dates come from the NISAR pass list when it is available.

### `GET /climate/outlook?area=`
`{ "dataKind": "outlook", "model", "runDate", "nativeResolution", "months": [{"year", "month", "meanMm", "memberMinMm", "memberMaxMm", "anomalyVsModelClimatologyMm": null, "members": 51}], "horizonMonths": 6, "limitations": [] }`. If the provider fails, return 503 `upstream_unavailable`, or a dated cache.

### `GET /climate/scenarios?area=`
`{ "dataKind": "scenario", "startMonth": "2026-12", "scenarios": [{"id": "normal", "label": "A normal year (1991-2020 mean)", "basis": "...", "months": [{"year", "month", "rainfallMm", "status": "outlook" | "scenario"}]}, {"id": "wet_like_YYYY"}, {"id": "wettest_since_2000"}, {"id": "dry_like_YYYY"}], "limitations": ["conditional scenario, not a prediction"] }`

### `GET /climate/flood-scenario?area=&scenarioId=`
Exploratory. It combines the observed pass rainfall with flooded km² (from B's pass list) to give `{ "relationship": {"n", "method", "points": [{"date", "prior7DayMm", "floodedKm2"}]}, "months": [{"year", "month", "rainfallMm", "expectedFloodedKm2": {"low", "base", "high"}, "status"}], "exploratory": true }`. It returns 404 `data_unavailable` until the NISAR passes exist.

### `GET /timeline/availability?area=`
`{ "datasets": [{"id": "nasa_power_rainfall", "label", "kind": "climate" | "optical" | "sar_c" | "sar_l" | "insar", "start": "2000-01-01", "end": "...", "cadence", "access": "...", "status": "integrated" | "catalogue_only"}] }`

## D: Places and exposure (`places_api.py`)

All endpoints are bundled and offline at request time (cache in `backend/data/cache/places/`, built by `backend/scripts/40_fetch_places.py`). Every success body also carries `dataKind`, `retrievedAt`, `source`, `warnings`, `limitations`. Missing cache gives 404 `data_unavailable`. Place ids are COD-AB p-codes (`PH1307502` city, `PH1307502010` barangay). Names are the official COD-AB names, so cities read "City of Malabon", "Caloocan City", "Marilao".

### `GET /places/search?q=&limit=10`
`{ "query", "results": [{"id", "name", "level": "barangay" | "city", "city", "province", "lon", "lat", "bbox": [w, s, e, n], "inStudyArea": true}] }`. Case-insensitive; ignores "Brgy.", "Barangay", "City of" and accents (n with tilde matches n); ranks exact, then prefix, word prefix, substring, then "name + city"; study-area places first on ties. `limit` 1-50, `q` required (422 `invalid_request`). Metro Manila places carry `province: "Metro Manila"`.

### `GET /places/boundaries?level=city|barangay`
A GeoJSON FeatureCollection (simplified to about 5 m, 5 decimals) with `properties: {id, name, level, city, province, region, inStudyArea}` (barangays also `cityId`), plus `source`, `license`, `level`. It covers every COD-AB city and barangay that intersects the study bbox, which includes neighbours outside the seven study cities; filter on `inStudyArea`.

### `GET /places/locate?lon=&lat=`
`{ "lon", "lat", "barangay": {"id", "name"} | null, "city": {"id", "name", "province"} | null }`. 404 `outside_coverage` outside the study bbox; 200 with nulls and a warning inside the bbox but outside every polygon (open water).

### `GET /places/exposure?area=camanava_2026&mask=rhythm_half|priority&level=barangay|city`
`{ "dataKind": "derived" | "synthetic", "area", "mask", "level", "passCount", "zones": [{"placeId", "name", "city", "areaKm2", "population": 1234, "buildings": 321}], "totals": {"population", "buildings", "areaKm2", "unassignedAreaKm2"}, "populationSource": {"name", "year": 2020, "url", "license"}, "buildingSource": {"name", "snapshotDate", "completeness": "unknown", "url", "license"}, "populationUnavailableReason", "buildingsUnavailableReason", "limitations": ["exposure, not damage", ...] }`. Zones list only places with exposed area, sorted by population. `population`/`buildings` are `null` (with the reason field) when the clip is absent. `unassignedAreaKm2` is exposed area outside every barangay polygon (for example sea).

Inputs expected from B (under `output_root/camanava_2026/nisar/`): `rhythm.tif`, a single-band count raster (flooded-pass count per pixel, nodata declared in the file or NaN); and `manifest.json` (or `rhythm_manifest.json`) with `passCount` and `dataKind`. `rhythm_half` means count >= ceil(0.5 x passCount). `dataKind: "synthetic"` in the manifest is propagated. `mask=priority` reads `priority_mask.tif` in the same folder (coordinator, wave 2). Missing raster gives 404 `data_unavailable`; unknown area 404 `unknown_area`; bad `mask`/`level` 422 `invalid_request`. The rhythm raster may be in any CRS (geographic or projected metres).

Python entry point: `processing.places.exposure.exposure_for_mask(mask, level="barangay", *, transform=None, crs=None, nodata=None, threshold=None)`, where `mask` is a path, an array with `transform`, or `(array, transform[, crs])`; helper `rhythm_mask(path, pass_count, min_fraction)`. Method and partial-cell rules are in the module docstring: pixel-centre assignment to places, equal-area pixel areas, WorldPop density resampled onto the mask grid (people spread evenly in each 100 m cell), building centroid-in-pixel.

Data and licences (full detail with sha256 in `backend/data/cache/places/manifest.json`): boundaries HDX COD-AB PHL v03 (valid 2025-02-13, CC BY-IGO); buildings OpenStreetMap via the HOT export on HDX (snapshot 2026-10-12, ODbL; completeness unknown; Overpass was unreachable from the build environment); population WorldPop 2020 constrained 100 m BSGM (CC BY 4.0; cells without built settlement count as zero); land cover ESA WorldCover 2021 v200 10 m (CC BY 4.0), clip `esa_worldcover_2021_clip.tif`, uint8, classes 10 tree, 20 shrub, 30 grass, 40 crop, 50 built-up, 60 bare, 80 water, 90 herbaceous wetland, 95 mangrove.

## Coordinator, wave 2

`GET /spot-check?lon=&lat=`, `GET /briefing/place?lon=&lat=&lang=en|fil`, and priority zones (rhythm ≥ half AND LOS sinking).
