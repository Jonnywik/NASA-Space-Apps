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
| NISAR default track | **140 ascending, frame 009**, mode 4005 DHDH (HH+HV), 11 GCOV dates 23 Jun–2 Nov 2026, 9 GUNW pairs; ~100% bbox coverage by catalogue footprint (133 D covered only ~35%) |
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
| **E: Packaging** | `README.md`, `LICENSE`, `.github/`, `docs/data/DATA_MANIFEST.md` |
| Coordinator | `backend/app/main.py`, `backend/requirements*.txt`, `docs/SUBMISSION_SCOPE.md`, this file, spot check and briefing (wave 2) |

Each router module exposes `make_router(output_root, read_public_events)`, like `backend/app/p3_api.py`.

## B: NISAR (`nisar_api.py`)

Served from `<output>/camanava_2026/nisar/manifest.json` (written by scripts 20 or 22). `area` defaults to `camanava_2026`. Until a product exists every route returns 404 `data_unavailable`. A synthetic product returns `dataKind: "synthetic"` on every route and `warnings[0]` starts with `SYNTHETIC DEMO DATA`. Every body also carries `source`, `generatedAt`, `nativeResolution`, `units`, `warnings`, `limitations`.

**Resolved (15 Nov):** the default stack is now 140 A / frame 9, because 133 D / frame 81 covers only about 35 % of the bbox. Stacks 032 D / frame 81 and 140 A / frame 9 cover 100 %. See `docs/NISAR_RUNBOOK.md` section 0. `track`, `frame` and the dates below come from the manifest, so they follow whichever stack is run.

### `GET /nisar/passes?area=camanava_2026`
```json
{
  "area": "camanava_2026", "dataKind": "observed", "sensor": "NISAR L-band SAR",
  "product": "L2 GCOV", "track": 133, "direction": "descending", "frame": 81, "mode": "4005",
  "polarizations": ["HH", "HV"],
  "rule": {"description": "...", "hhThresholdDb": -18.0, "hvThresholdDb": -26.0,
           "calibration": {"status": "calibrated | uncalibrated-default", "method": "...", "knownWater": "...", "waterPixels": 0}},
  "permanentWater": {"fraction": 0.9, "minValidPasses": 3},
  "possibleFloodedVegetation": {"marginDb": 3.0, "label": "possible flooded vegetation (L-band)", "landCoverMask": null},
  "verification": {"layout": "unverified | verified | synthetic", "evidence": []},
  "studyAreaKm2": 419.5,
  "legend": [{"id": "flood_water", "label": "Flood water", "color": "#0072B2"},
             {"id": "possible_flooded_vegetation", "label": "Possible flooded vegetation", "color": "#E69F00"}],
  "passes": [{
    "id": "20260623", "date": "2026-06-23", "acquisitionTime": "2026-06-23T10:32:20Z",
    "acquisitionTimeManila": "2026-06-23T18:32:20+08:00",
    "productId": "NISAR_L2_PR_GCOV_...", "maturity": "provisional | v1 | synthetic",
    "floodedKm2": 12.3, "permanentWaterKm2": 40.1, "floodedVegetationKm2": 1.2,
    "validKm2": 380.0, "validFraction": 0.97, "missingReason": null,
    "overlayUrl": "/api/v1/nisar/overlay/camanava_2026/pass_20260623.png",
    "backscatterUrl": "/api/v1/nisar/overlay/camanava_2026/hh_20260623.png",
    "floodedVegetationUrl": "/api/v1/nisar/overlay/camanava_2026/veg_20260623.png",
    "polarizationUrl": "/api/v1/nisar/overlay/camanava_2026/pol_20260623.png"
  }],
  "bounds": [[14.60, 120.88], [14.82, 121.04]],
  "source": {}, "generatedAt": "...", "warnings": [], "limitations": []
}
```
`date` is the UTC date. Areas cover only pixels inside the bbox; `validFraction` is valid area over bbox area. A pass with no valid pixels has `floodedKm2: null` and a `missingReason`. `permanentWaterKm2` is the permanent-water area seen as water on that pass.

### `GET /nisar/flood-rhythm?area=`
```json
{
  "area": "camanava_2026", "dataKind": "derived", "passCount": 11, "minValidPasses": 3,
  "overlayUrl": "/api/v1/nisar/overlay/camanava_2026/rhythm.png",
  "legendUrl": "/api/v1/nisar/overlay/camanava_2026/rhythm_legend.png",
  "bounds": [[14.60, 120.88], [14.82, 121.04]],
  "legend": [{"count": 1, "color": "#..."}],
  "km2ByCount": [{"count": 1, "km2": 5.2}],
  "halfOrMoreKm2": 3.4, "countableKm2": 250.0, "floodedAtLeastOnceKm2": 20.1,
  "byValidPasses": [{"validPasses": 11, "km2": 240.0, "floodedAtLeastOnceKm2": 19.0}],
  "permanentWaterMasked": true,
  "method": "count of passes classified as water, over the count of valid passes, per pixel; permanent water excluded",
  "source": {}, "generatedAt": "...", "warnings": [], "limitations": []
}
```
`halfOrMoreKm2` uses each pixel's own valid-pass count as the denominator. Pixels with fewer than `minValidPasses` valid passes, and permanent water, are not counted. The legend is viridis (colour-blind safe); permanent water is drawn grey in the PNG.

Files other modules read in the same folder: `rhythm.tif` (band 1 = passes flooded, int16, nodata −1), `rhythm_half.tif` (1 = half or more of the pixel's own valid passes, nodata 255), and `manifest.json` with top-level `dataKind`, `passCount`, `version` and `passes[{date, floodedKm2}]`. Note: `places/exposure?mask=rhythm_half` currently thresholds `rhythm.tif` at `ceil(passCount / 2)`, which differs from `halfOrMoreKm2` where some passes are nodata; `rhythm_half.tif` is the matching mask.

### `GET /nisar/point?area=&lon=&lat=`
Returns `{ "lon", "lat", "cellCenter": {"lon", "lat"}, "floodCount", "validCount", "floodCountReason", "permanentWater": false, "possibleFloodedVegetationPasses": 0, "perPass": [{"date": "2026-06-23", "state": "water" | "dry" | "nodata", "hhDb": -19.2, "hvDb": -27.0, "possibleFloodedVegetation": false, "reason": null}], "dataKind" }`. `floodCount` is `null` with `floodCountReason` for permanent water and for pixels with too few valid passes. Missing or non-numeric `lon`/`lat` gives 422 `invalid_request`. A point outside the bbox or grid gives 404 `outside_coverage`.

### `GET /nisar/overlay/{area}/{name}.png`
Serves a PNG whose `name` is registered in the manifest as an overlay and whose SHA-256 still matches. Registered names: `pass_<id>`, `hh_<id>`, `veg_<id>`, `pol_<id>`, `rhythm`, `rhythm_legend`. Anything else: 404 `data_unavailable` (unknown, missing or failed hash) or 422 `invalid_request` (malformed name). Response header `X-Tanaw-Data-Kind` repeats the data kind.

### `GET /nisar/polarization?area=&date=YYYY-MM-DD`
Returns `{ "date", "acquisitionTime", "rgbUrl", "bounds", "channels": {"r": "HH", "g": "HV", "b": "HH/HV"}, "stretchDb": {"r": [-25, 0], "g": [-35, -10], "b": [0, 20]}, "explanation": ["...", "...", "..."], "dataKind" }`. Missing or malformed `date`: 422 `invalid_request`. No pass on that date: 404 `data_unavailable` with `availableDates`. The explanation text still needs reviewer sign-off (flagged in `warnings`).

### Ground motion
This reuses the existing P3 routes with `event=camanava_2026`: `/ground-motion` and `/ground-motion/point`. B registers the event and provides `scripts/21_nisar_gunw_chain.py`, which builds the script-10 source manifests, the script-11 reference config and a run script for 10 → 11 → 12 from the CMR listing. No GUNW file has been read yet; the phase sign and the reference area must be set by a person (runbook section 6). Real products stay `needs-review` until promoted with `scripts/17_review_product.py`.

## A: Climate, history, outlook, scenarios (`climate_api.py`)

Implemented and tested (`backend/tests/test_climate_*.py`). Every endpoint takes `area=camanava_2026` (the default; anything else is 404 `unknown_area`) and serves from `backend/data/cache/climate/`, which `backend/scripts/30_fetch_climate.py` fills (`../.venv/bin/python scripts/30_fetch_climate.py [--force] [--skip-era5]`). A request never calls a provider. If a cache is missing or fails its sha256 check the answer is 503 `upstream_unavailable` (`cachedAt: null`). If a refresh failed but an older cache exists, the older cache is served with a `warnings` entry. Query parameters are validated by hand, so every error uses the `{"detail": {"code", "message"}}` shape. All success bodies carry `dataKind`, `source {name, url, version}`, `retrievedAt`, `nativeResolution`, `warnings`, `limitations`, and `units` where relevant.

Rainfall source: NASA POWER daily `PRECTOTCORR` (mm/day, 0.5° x 0.625° MERRA-2 cell) at lon 120.96, lat 14.70, 1991-01-01 to the last published day. The fill value -999 is missing (null), never 0. A month or season is `complete` only if every day was observed (`MISSING_TOLERANCE_DAYS = 0`); an incomplete month has `totalMm: null`, a `partialMm` and no anomaly. **Data caveats found live:** from 2026-10-01 POWER serves GEOS-IT (near-real-time) instead of MERRA-2 (the responses warn about this), and the POWER cell reads much wetter than ERA5 in the dry months (see `era5-compare`).

### `GET /climate/rainfall/monthly?area=&since=2000`
`{ "point", "units": "mm", "baseline": {"period": "1991-2020", "monthlyMeanMm": [12], "yearsUsedPerMonth": [12], "rule"}, "series": [{"year", "month", "totalMm", "anomalyMm", "anomalyPct", "missingDays", "complete", "partialMm"}], "lastObservedDay", "method", "dataKind": "derived", ... }`. `anomalyPct` is null when the baseline mean is 0.

### `GET /climate/rainfall/daily?area=&start=YYYY-MM-DD&end=YYYY-MM-DD`
`{ "units": "mm/day", "days": [{"date", "mm", "reason"?}], "coveredFrom", "coveredThrough", "lastObservedDay", "dataKind": "observed" }`. `mm: null` (with `reason`) when missing. Maximum 3700 days. 422 `invalid_request` for bad or reversed dates, 404 `outside_coverage` if the range is wholly outside the cache.

### `GET /climate/rainfall/season-rank?area=&year=2026`
`{ "season": "Jun-Nov", "year", "totalMm", "toDateMm", "partialMm", "observedThrough", "rank", "of", "rankBasis", "rankMeaning": "1 = wettest", "complete", "seasons": [{"year", "totalMm", "toDateMm", "complete"}] }`. For an incomplete season `totalMm` is null and the rank compares `toDateMm` (1 Jun to `observedThrough`) with the same window in every other year (`rankBasis: "to_date_same_window"`); a complete season ranks on its full total (`full_season_total`). Seasons run from 2000. 404 `outside_coverage` for years without data.

### `GET /climate/rainfall/trend?area=`
`{ "method", "period": "2000-2026", "slopeMmPerDecade", "ci95": [lo, hi], "n", "effectiveN", "lag1Autocorrelation", "significant", "limitations" }`. OLS on monthly anomalies (1991-2020 calendar-month means removed), complete months only, interval widened for lag-1 autocorrelation. `significant` means the 95% interval excludes 0. No causal claim.

### `GET /climate/pass-rainfall?area=&dates=2026-06-23,2026-07-05`
`{ "passes": [{"date", "sameDayMm", "prior3DayMm", "prior7DayMm", "reasons": {}}], "windowDefinition" }`. Prior windows are the 3 or 7 days before the pass day (the pass day is excluded); a window with any missing day is null and `reasons` names the days. If `dates` is omitted the dates come from the NISAR pass list, else 404 `data_unavailable`. Maximum 60 dates.

### `GET /climate/outlook?area=`
`{ "dataKind": "outlook", "model": null, "modelRequested": "ecmwf_seas5", "modelNote", "runDate": null, "runDateReason", "firstForecastDate", "lastForecastDate", "nativeResolution", "gridCell", "ensembleMembers": 50, "anomaly": {"available", "reason", "basis"}, "months": [{"year", "month", "coveredDays", "monthDays", "fullMonth", "members", "meanMm", "memberMinMm", "memberMaxMm", "anomalyVsModelClimatologyMm", "providerMonthlyMeanMm"}], "horizonMonths", "fullMonths" }`.
Open-Meteo's response names neither the model nor the run date, so `model` and `runDate` are null with the reason, and `firstForecastDate` (the first day returned, equal to the retrieval day) is given instead. `months` holds only the months the response returns, as the sum of daily rainfall per ensemble member, then mean/min/max across members; the first and last months are partial (`fullMonth: false`). `anomalyVsModelClimatologyMm` is the provider's own `precipitation_anomaly` (model-native, against the model's climatology, not comparable with the POWER baseline); it is null with a reason if the monthly block was not returned. `horizonMonths` counts the calendar months touched (including the partial ones).

### `GET /climate/scenarios?area=`
`{ "dataKind": "scenario", "startMonth": "2026-12", "lastObservedMonth", "scenarios": [{"id", "label", "basis", "months": [{"year", "month", "rainfallMm", "rainfallSource": "scenario_value", "status": "outlook" | "scenario", "outlook"?: {"meanMm", "memberMinMm", "memberMaxMm", "members", "anomalyVsModelClimatologyMm"}}]}] }`. Ids: `normal` (1991-2020 monthly means), `wet_like_YYYY` and `dry_like_YYYY` (the observed Dec(Y-1) to Nov(Y) monthly sequence ending with the wettest or driest complete Jun-Nov season since 2000; `analogYear`, `analogSeasonTotalMm`), `wettest_since_2000` (per-calendar-month maximum since 2000, `isEnvelope: true`, not a real year). `status` is `outlook` only for a month the seasonal run covers in full; `rainfallMm` is still the scenario's own value and the outlook figures sit alongside. The 12 months start after the month of the last observed day.

### `GET /climate/flood-scenario?area=&scenarioId=`
Exploratory. `{ "scenarioId", "relationship": {"n", "method", "points": [{"date", "prior7DayMm", "floodedKm2"}], "slopeKm2PerMm", "rawTheilSenSlope", "residualRangeKm2", "observedPrior7DayRangeMm"}, "months": [{"year", "month", "rainfallMm", "status", "equivalent7DayMm", "expectedFloodedKm2": {"low", "base", "high"} | null, "reason"?}], "exploratory": true, "nisarDataKind" }`. Method: Theil-Sen line of flooded km² on prior-7-day rainfall, slope floored at 0, low/high = base plus the smallest/largest residual seen (a full-range envelope, not a probability). Monthly rainfall becomes an average 7-day total (month x 7 / days). Months outside the rainfall range seen on the passes are null with a reason, never extrapolated. Needs at least 8 usable passes. `dataKind` is `scenario`, or `synthetic` if the NISAR pass list says so. Errors: 404 `data_unavailable` (no NISAR pass list, or fewer than 8 passes), 422 `invalid_request` (missing or unknown `scenarioId`; `validIds` is listed).
**Dependency on B:** the API reads `<output>/camanava_2026/nisar/manifest.json` (or `passes.json`), a JSON object with `passes: [{"date", "floodedKm2"}]` and an optional `dataKind`. B should keep that shape (or tell A).

### `GET /climate/rainfall/era5-compare?area=` (extra)
ERA5 daily rainfall via the Open-Meteo archive API, kept separate from POWER: `{ "series": [{"year", "month", "era5Mm", "powerMm"}], "meanByCalendarMonth2000to2020": [{"month", "era5MeanMm", "powerMeanMm"}], "gridCell" }`. Never merged or averaged with POWER.

### `GET /timeline/availability?area=`
`{ "datasets": [{"id", "label", "kind": "climate" | "optical" | "sar_c" | "sar_l" | "insar", "start", "end", "cadence", "access", "status": "integrated" | "catalogue_only", "verified"}] }`. Dates come from live searches cached by script 30: NASA POWER and ERA5 from the cached series, NISAR GCOV from CMR (collections C2854338529-ASF and C3622241360-ASF), Sentinel-1 from CMR (A, B and C SLC), Landsat from the Planetary Computer STAC (`landsat-c2-l2`, first scene since 2000 and latest). Only POWER and ERA5 (and NISAR once B's pass list exists) are `integrated`; Landsat and Sentinel-1 are `catalogue_only`.

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

## Spot check and briefing (Codex T4)

- `GET /api/v1/spot-check?lon=&lat=` returns `{area,lon,lat,streams,dataKind,source,generatedAt,warnings,limitations}`. Streams are `place`, `nisar`, `rainfall`, `motion`, `priority`, and `exposure`; each carries `{value,reason,source,dataKind,nativeResolution,units}` and an available source timestamp. Missing parts have null values and a reason. Any synthetic stream makes the full response synthetic. Outside the study bbox gives 404 `outside_coverage`; invalid coordinates give 422 `invalid_request`.
- `GET /api/v1/briefing/place?lon=&lat=&lang=en|fil&format=json|csv|html` returns a deterministic briefing. JSON contains `{language,translationStatus,dataKind,sentences,facts,source,generatedAt,warnings,limitations}`. CSV columns are `field,value,units,source,dataKind`. HTML is self-contained, printable, escaped, and explicitly labels synthetic content. Filipino translation remains `pending native-speaker review`. There is no runtime LLM. The spot-check frontend now consumes the composed facts and provides EN/FIL HTML and CSV export buttons; exported errors follow the normal unavailable-state handling.

The validation cache is tied to `source.nisar.productManifestSha256`. The endpoint returns `data_unavailable` when the current NISAR manifest is absent or its SHA-256 differs. Comparison records also expose `temporalMatch` (calendar days, elapsed hours and whether within 48 hours); two-calendar-day near matches exceeding 48 hours carry a warning. `comparisons` contains the per-pass results, and `sensitivity` reports the coupled HH/HV ±1 dB calculation. These are inter-product total-water comparisons, not ground-truth flood accuracy.

## Priority and validation integration (Codex T3/T5)

Script `50_priority_zones.py` writes `priority_mask.tif` (0/1, nodata 255) and `priority_manifest.json` alongside the NISAR product. The manifest binds the output and source hashes, motion run, threshold, sensitivity and exposure. Both spot-check and `/places/exposure?mask=priority` require intact priority provenance and reject changed flood/motion inputs. Synthetic provenance propagates from either input. The script rejects upsampling a coarser flood mask onto a finer motion grid; preparing a coarser common motion product is required for that case.

`GET /api/v1/validation?area=camanava_2026` reads offline comparison results. A valid measured comparison returns `dataKind: derived`, `status: partial`, `agreement` (confusion matrix, validPixels, overallAgreement, F1 and IoU), source metadata, generatedAt, nativeResolution, units, warnings and limitations. Missing/invalid/literature-only caches return 404 `data_unavailable`; unknown area returns 404 `unknown_area`. Literature context and synthetic fixtures do not establish observed validation. Script `60_validation.py` requires normalized binary rasters, compatible north-up CRS grids and documented independent-source provenance. Acquisition dates must be within two days.

## IMERG rain before NISAR passes (coordinator, 15 Nov)

### `GET /climate/imerg/passes?area=camanava_2026&series=true|false`
Served from `backend/data/cache/climate/imerg_passes.json`, which `scripts/31_fetch_imerg_passes.py` writes. It needs `EARTHDATA_TOKEN` and the owner's GES DISC data-use approval; the file is committed, so the API needs no token. Returns 404 `data_unavailable` if the file is absent.

```json
{
  "schemaVersion": "1.0", "area": "camanava_2026", "dataKind": "observed", "retrievedAt": "...",
  "source": {"name": "NASA GPM IMERG Late Run half-hourly V07 (GPM_3IMERGHHL)", "url": "...", "doi": "10.5067/GPM/IMERG/3B-HH-L/07", "provider": "NASA GES DISC"},
  "units": {"rate": "mm/hr", "totals": "mm"},
  "nativeResolution": "0.1 degree (about 11 km), 30 minutes",
  "spatialAggregation": "mean of the 0.1-degree cells overlapping the study bbox [...] (N cells)",
  "hoursBeforePass": 48, "rainThresholdMmHr": 1.0,
  "passes": [{
    "date": "2026-08-10", "acquisitionTime": "2026-08-10T21:30:32Z", "acquisitionTimeManila": "2026-08-11T05:30:32+08:00",
    "last3hMm": 0.0, "last6hMm": 0.0, "last12hMm": 0.4, "last24hMm": 3.1, "last48hMm": 20.6,
    "peakMmHr": 6.2, "peakAt": "2026-08-09T...Z",
    "hoursSinceRain": 30.5, "hoursSinceRainNote": "hours since the last half-hour with an area-mean rate >= 1.0 mm/hr",
    "missingHalfHours": 0,
    "series": [{"start": "...Z", "end": "...Z", "meanMmHr": 0.2, "maxCellMmHr": 0.9}]
  }],
  "limitations": ["..."], "warnings": []
}
```
- The values above are illustrative of the shape only; read the real file.
- **Totals are `null` if any half-hour in the window is missing.** `hoursSinceRain` is `null` when no half-hour reached the threshold; the note says which.
- `series=false` drops the half-hourly series and keeps only the totals.

## Round 4 additions (15 Nov, about 14:45; freeze moved to 18:00)

All of these serve **small committed caches** under `backend/data/cache/`, so they work on any machine without a token. Each response has the usual `dataKind`, `source`, `generatedAt`, `nativeResolution`, `warnings` and `limitations`. Overlay PNGs are RGBA with `bounds: [[S, W], [N, E]]`.

### Coordinator: `nisar_api.py`
- **`GET /nisar/rain-response?area=`** returns a map of how strongly NISAR HH backscatter follows rain. It is the per-pixel Spearman ρ between HH dB and the 48-hour IMERG rain before each of the 11 passes. Fields: `overlayUrl`, `bounds`, `legend: [{value, color}]` (diverging, ρ −1 to +1), `nPasses`, `stats: {medianRho, shareAbove05, shareBelowMinus05}`, `byLandCover: [{class, name, medianRho, cells}]`, `method`. Exploratory, `dataKind: "derived"`.
- **`GET /nisar/coherence-change?area=`** returns the interferometric coherence drop on the pair spanning the 8 Aug storm (17 Jul → 10 Aug), compared with the median coherence of the other 8 pairs, at 80 m. Fields: `stormPair: {reference, secondary}`, `calmPairs: [...]`, `overlayUrl`, `bounds`, `legend`, `stats: {km2DropOver03, medianDrop}`, `byLandCover`, `method`. Exploratory. A drop can come from water, vegetation change, construction or noise; it is never called "flooding".
- **`GET /nisar/soil-moisture?area=`** returns the SME2 per-pass statistics and overlays (`passes[].overlayUrl`, `legend`, `bounds`, `rainComparison`).
- **`GET /nisar/extra/{name}.png`** serves only the overlay names listed by the three endpoints above.

### Codex: new `downloads_api.py` plus briefing updates
- **`GET /downloads?area=`** lists the downloadable real layers: `[{id, title, format: "GeoTIFF"|"GeoJSON"|"CSV"|"JSON"|"GIF", sizeBytes, licence: "CC-BY-4.0", attribution, dataKind, url}]`. Missing, synthetic or hash-mismatched products are omitted. The validation JSON uses the same product-manifest guard as `/validation`; the GIF is bound to the current product manifest and IMERG cache by `timelapse.json`.
- **`GET /downloads/{id}`** returns the file, with the right `Content-Disposition`. Only listed ids are served.
- **`GET /nisar/timelapse.gif?area=`** (registered from `downloads_api.py`) returns an animated GIF of the 11 real passes: HH backscatter with the open-water overlay, a date and Manila-time caption, and a small IMERG 48-hour rain bar. Built by `scripts/28_nisar_timelapse.py` into `backend/data/cache/nisar/timelapse.gif` (keep it under about 8 MB).
- **Briefing** (`/briefing/place`): update to the v6 story, adding the IMERG rain facts for the latest pass. No "flooding" wording for the open-water layer.

## Round 5 additions (15 Nov, coordinator): robustness and cross-track validation

Both are read-only, offline results bound to the canonical product manifest SHA-256 (`productManifestSha256`); a mismatch or missing file returns 404 `data_unavailable`, an unknown area 404 `unknown_area`.

- **`GET /validation/robustness?area=`** (script 62): `correlations: [{label, n, rho, pPermutation, bootstrap95: [lo, hi], leaveOneOut: [min, max], signHoldsWithoutAnyOnePass}]`, `rainResponseField: {cells, observedMedianRho, observedShareAbove05, nullMedianRho95, nullShareAbove05_95, nullShareAbove05Mean, pFieldMedian, pFieldShare, permutations}`, `coherenceLoss: {landKm2, naiveKm2DropOver03, intervalCorrectedKm2DropOver03, intervalCorrectedMedian, calmPairsKm2DropOver03, byLandCoverCorrected}`.
- **`GET /validation/cross-track?area=`** (script 63): `ascending` and `descending` summaries (`track, passes, localTime, rule, halfOrMoreKm2, openWaterKm2Range`; descending also `series` and `rainCorrelation`), `geometryAgreement: {ascendingKm2, descendingKm2, exactOverlapKm2, toleranceM, shareAscendingNearDescending, shareDescendingNearAscending, chanceShareMean, chanceShareMax, byLandCoverOverlapKm2, builtUpOverlapKm2}`, `operaMatches: [{nisarDate, referenceTime, referenceGranule, hoursApart, validPixels, overallAgreement, f1, iou, nisarRecall, nisarPrecision}]`, `operaSummary`, `limitations`.
- `GET /nisar/coherence-change` `stats` gains `km2DropOver03IntervalCorrected`.

### Product binding (15 Nov, after the Antigravity audit)
Offline results (`/validation`, `/validation/robustness`, `/validation/cross-track`, `/nisar/timelapse.gif` and the validation/timelapse downloads) are accepted when **either** the recorded `productManifestSha256` matches the current manifest file **or** the recorded `productFingerprint` matches its content fingerprint (`app/product_binding.py`: area, dataKind, water rule, each pass's id/productId/areas, and the rhythm area; not `generatedAt`, warnings or asset bytes). Regenerating the product on another machine no longer breaks validation; changing the science still does. The timelapse also checks `imergFingerprint` (per-pass rain totals, not `retrievedAt`). Scripts 28, 61, 62 and 63 write both fields.
