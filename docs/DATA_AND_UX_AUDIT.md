# Data Accuracy & User-Perspective UX Audit (`5df5d74`)

- **Audited commit:** `main` @ `5df5d74` (`Round 5b: rain link not reproduced on the 18:24 NISAR track; copy and docs corrected`)
- **Date:** `2026-11-15`
- **Verification checks run:**
  - Backend unit suite (`python -m unittest discover -s tests -q`): `378` tests passed (`OK`, exit `0`).
  - Frontend contract tests (`npm run test:api`): `3` passed, `0` failed.
  - Live FastAPI (`:8010`) + Next.js (`:3015`) API & UI inspection across desktop (`1440×900`) and mobile (`390×844`).

---

## 1. Data Accuracy & Integrity Findings

### 1.1 SHA-256 Manifest Split Breaks Validation, Cross-Track, and Timelapse (`404`)
- `backend/app/validation_api.py` and `backend/app/downloads_api.py` enforce an exact SHA-256 match against `backend/data/output/camanava_2026/nisar/manifest.json`.
- Committed cache files on `5df5d74` reference **two incompatible manifest hashes**:
  - `b947b54d84f77372536c6202c7e8ac4af2768be2b673a47d8a2ecef2819fedbc` in `backend/data/cache/validation/camanava_2026.json` and `backend/data/cache/nisar/timelapse.json`.
  - `49c00d050b9414f113b7c5311ee8fe2b32696a6623a073871400dfedf4fc990c` in `backend/data/cache/validation/robustness.json` and `backend/data/cache/validation/cross_track.json`.
- A freshly generated local `manifest.json` (`a9a4cb11...`, `generatedAt: "2026-11-15T06:45:26Z"`) matches neither hash, and no single `manifest.json` can satisfy all four committed caches simultaneously.
- **Live effect:**
  - `GET /api/v1/validation`, `GET /api/v1/validation/robustness`, `GET /api/v1/validation/cross-track`, and `GET /api/v1/nisar/timelapse.gif` all return `HTTP 404 (data_unavailable)`.
  - `timelapse.gif` and validation JSON are omitted from `/api/v1/downloads`.
  - `/api/v1/validation` returns `"No observed NISAR and independent reference comparison is available; synthetic products cannot establish validation."` even when observed NISAR data is loaded, misleading users on the Motion and Rhythm tabs.
  - Local `manifest.json` also carries the CLI flag warning `"HDF5 dataset paths, units and CRS have not been verified on a real file for this run (use --layout-verified after checking)."` into the Rhythm UI.

### 1.2 Future Flood Scenario Is Completely Flat (`0.408 km²`) Across All Scenarios
- Across the 11 Track 140A passes, `floodedKm2` has a **negative** raw Theil-Sen slope against NASA POWER `prior7DayMm` (`rawTheilSenSlope: -0.00324`, e.g., `2026-08-10` with `229.47 mm` -> `0.1939 km²` vs `2026-10-21` with `29.48 mm` -> `0.575 km²`).
- `backend/processing/climate/flood.py` floors `slopeKm2PerMm = max(raw_slope, 0.0) = 0.0`.
- **Live effect:** All 4 scenarios (`normal`, `wet_like_2020`, `dry_like_2015`, `wettest_since_2000`) return identical constant `{low: 0.134, base: 0.408, high: 0.575}` (`0.4 km²` in `FuturePanel.jsx`) for any month within the observed `[21.83, 229.47] mm` 7-day range and `null` outside it (e.g., `dry_like_2015` Feb–May; `wet_like_2020` Oct–Nov). `slopeKm2PerMm === 0` is not surfaced to the user in `FuturePanel.jsx`.

### 1.3 Coherence-Loss Area Discrepancy Across Modules
- `backend/data/cache/nisar/extra/coherence_change.json` (`scripts/26_nisar_extras.py`) reports `landKm2: 396.6`, `km2DropOver03: 4.76`, `km2DropOver03IntervalCorrected: 0.09`.
- `backend/data/cache/validation/robustness.json` (`scripts/62_robustness.py`) reports `landKm2: 275.1`, `naiveKm2DropOver03: 3.17`, `intervalCorrectedKm2DropOver03: 0.04` (calm 12-day pairs drop up to `1.54 km²`).
- Different land/valid masking (`lcc == 80` only vs finite `med12` and `lcc > 0`) creates conflicting numbers when both map overlay and validation panel are active.

### 1.4 Detected Persistent Open Water Is Rural/Coastal Cropland; `0` Buildings Exposed
- On `rhythm_half.tif` (`3,723` pixels = `0.3723 km²`), ESA WorldCover 2021 pixel distribution is:
  - `40 Cropland`: `2,420` (`65%`)
  - `30 Grassland`: `723`
  - `90 Herbaceous wetland`: `421`
  - `10 Tree cover`: `123`
  - `95 Mangroves`: `30`
  - `60 Bare / sparse`: `6`
  - **`50 Built-up`: `0`**
- Against `427,220` cached OSM building centroids, `/api/v1/places/exposure` reports **`buildings: 0`** across all 9 zones, and `216` of `223` exposed people (`0.3666 / 0.3723 km²`) fall in **Bulacan / Balagtas** (`Bambang`, `Matungao`, `Perez`, `Panginay`, `Santa Ana`, `Taliptip`), outside `STUDY_CITY_CODES` in `backend/processing/places/__init__.py`.

### 1.5 Climate & Soil Moisture Limitations
- **NASA POWER vs ERA5/SEAS5:** `/api/v1/climate/rainfall/era5-compare` shows POWER 1991–2020 Dec–Apr means (`395.7, 148.8, 151.2, 121.4, 100.7 mm`) read **3–10× wetter** than ERA5 (`117.9, 36.5, 34.6, 32.6, 38.0 mm`), and the `normal` Dec bar (`385.18 mm`) towers over the ECMWF SEAS5 Dec mean (`32.3 mm`). `getEra5Compare` in `frontend/utils/api.js` is not rendered in any `.jsx` panel.
- **SME2 Soil Moisture:** Recommended retrievals cover only `5.1%–6.5%` of study cells (peripheral farmland; none in dense city), are absent on `2026-10-21` and `2026-11-02`, and show an exploratory inverse correlation (`rho = -0.333`, `p = 0.3807`) against 7-day POWER rain.
- **Track 32D nuance (`5df5d74`):** The `Rain response (ρ)` overlay card notes the `05:30` rain-brightness relationship (`rho = 0.655`) did not hold on `18:24` Track 32D (`rho = -0.152`), but `RhythmPanel.jsx` `"In plain words"` still asserts an unqualified inverse rain link while `/validation/cross-track` returns `404`.

---

## 2. User-Perspective Analytical Effectiveness

### Strengths
- **Scientific transparency:** Explicitly labels `"exposure, not damage"`, double-bounce blind spots, 24-day Markov coherence adjustment (`4.76 km² -> 0.09 km²`), and refuses to show synthetic InSAR ground motion on the Motion tab.
- **Point Spot Check + IMERG context:** Clicking any coordinate returns 11-pass HH/HV history, barangay lookup, 48h half-hourly IMERG sparkline, and bilingual EN/FIL briefing + CSV export.
- **Interactive diagnostics:** Before/After swipe, `Polarization RGB` false-colour guide, and `Sources and limits` drawer.

### UX Gaps, Visual Bugs & Friction
1. **City-scale flood visibility & urban insight gap:** At default zoom, `0.2–0.4 km²` blue open-water pockets disappear under dense OSM streets and barangay outlines, while `Exposure by barangay` shows `0 buildings` and mostly Bulacan farmland.
2. **Misleading Future scenario presentation:** Top KPI displays `Flood scenario, 2027-08: 0.4 km²` identically for all scenarios without flagging zero slope; `ScenarioRainChart` colors months 1–5 (`scenario_value` POWER bars up to `385 mm`) as `"Outlook months"` beside `32 mm` SEAS5 dots; and the map shows `"Exploratory flood scenario"` even though no flood raster updates when selecting forecast months.
3. **Chart & timeline collisions:**
   - Desktop bottom timeline legend (`Daily rain (NASA POWER)` / `NISAR pass`) overlaps right-side pass chips (`09-15 | 09-27 | 10-09`).
   - History `Monthly rainfall anomalies` `<YAxis width={48}>` clips `"1050 mm"` to `"050 mm"`.
4. **Map tools dropdown obstructs map:** Selecting `Rain response (ρ)` or `8 Aug coherence loss` leaves the `Map tools` panel open over Navotas/Malabon/Caloocan until manually closed.
5. **Search disambiguation & Downloads discoverability:** Searching `"Bambang"` resolves to `Bambang, Bocaue` (permanent water) rather than #1 exposed `Bambang, Bulacan`; GeoTIFF/CSV downloads are buried at the bottom of `LimitsDrawer.jsx` (`NASA GPM IMERG` is also missing from `data-credits`).
6. **EN/FIL & mobile (`390×844`) polish:** `HypothesesPanel.jsx` renders `"Hypothesis · Hypothesis: ..."` duplicate prefix; FIL mode leaves WorldCover classes and Spot Check `reason` fields in English; mobile header truncates `"2026 wet sea..."` and sticky bottom scrubber crowds Spot Check buttons (`Briefing | CSV | Full details`).

---

## 3. Recommended Next Actions
1. Re-run `28_nisar_timelapse.py`, `61_opera_comparison.py`, `62_robustness.py`, and `63_cross_track.py` (plus `--layout-verified` on `20_nisar_flood_rhythm.py`) against a single canonical `manifest.json` so `/validation*`, `cross-track`, and `timelapse.gif` return `200`.
2. Surface `slopeKm2PerMm === 0` explicitly in `FuturePanel.jsx`, separate SEAS5 outlook bars from NASA POWER scenario bars, and render `era5-compare` in History/Future.
3. Fix desktop timeline legend overlap, widen `Monthly rainfall anomalies` YAxis (`width={56}`), auto-collapse `Map tools` on overlay select, add a top-level Downloads trigger, and align `26_nisar_extras.py` land masking with `62_robustness.py`.

---

## Coordinator response (15 Nov, 17:15)
- **1.1 fixed** in `6c87a1f`: results are bound to the product's content fingerprint as well as the manifest hash (`app/product_binding.py`); all four endpoints return 200 on a regenerated product.
- **1.2:** the flat Future flood scenario now carries a note explaining why it is flat (`future.flood.flat`, shown when `slopeKm2PerMm === 0`). The owner dismissed hiding the chart (A8.1).
- **1.3:** left as is; the two coherence numbers use different land masks and both are labelled exploratory.
- **1.5:** "In plain words" now qualifies the rain link (`6c87a1f`).
- **UX:** rainfall y-axes widened (no more "050 mm"); Map tools close after choosing an overlay; duplicate "Hypothesis ·" prefix removed; NASA GPM IMERG and OPERA DSWx-S1 added to data credits; "Learn more about the radar" links (ASF NISAR guides, NASA ARSET) added to Sources and limits (Codex proposal item 2).
- **Cosmetic follow-ups (17:40):** timeline legend no longer hides the last pass chips (compact legend below 1536 px); header **Download data** button opens the drawer at the downloads; search labels a town that shares its province name ("Bulacan town") and marks places outside CAMANAVA; WorldCover class names and Spot Check reasons translated in Filipino mode; phone header shows the full subtitle; Spot Check no longer shows a raw Python error for points outside any barangay.
