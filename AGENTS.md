# AGENTS.md: instructions for coding agents working on Tanaw

**Current assignments:** Codex works on `docs/CODEX_TASKS.md` (T1–T7, backend and the real NISAR run). Antigravity works on `docs/ANTIGRAVITY_TASKS.md` (A1–A5, small frontend tasks; it owns `frontend/`). Do your own list, not section 5 below, which is the longer-term sequence.

Read this file first, then `docs/SUBMISSION_SCOPE.md` (the plan) and `docs/API_CONTRACT.md` (endpoint shapes and file ownership). Those two documents are the source of truth. If this file and they disagree, they win, and you should fix this file.

**Status as of 15 Nov 2026, about 01:30 Manila time.** Pull the latest commit before you start: other agents were still writing NISAR, climate and frontend code when this was written, so section 4 may be out of date. Check it against the code.

## 1. What Tanaw is

Tanaw is an entry to the 2026 NASA Space Apps Challenge, **"Dancing with the SARs"**. The challenge asks for an interactive, open-source app that uses **NISAR** radar data to track and visualize surface change.

> We grew up wading through CAMANAVA's floods. Every 12 days this monsoon, NASA–ISRO's NISAR watched our streets flood, drain and flood again, and measured the ground moving beneath them.

- **Study area:** CAMANAVA (Caloocan, Malabon, Navotas, Valenzuela) plus the Bulacan coast (Obando, Meycauayan, Marilao). Area id `camanava_2026`, bbox `[120.88, 14.60, 121.04, 14.82]` (W, S, E, N).
- **Core data:** NISAR L2 GCOV (backscatter, for flood detection) and GUNW (interferograms, for ground motion), track 140 ascending, frame 009, mode 4005 DHDH, 23 Jun–2 Nov 2026 (chosen because track 133 D covers only ~35% of the area).
- **Deadlines (Manila time):** coding freeze at 17:00 on 15 Nov, recording ready by 21:00. The video is 30 seconds.
- **Judging:** Impact, Creativity, Validity, Relevance, Presentation. Section 8 of the scope document says what each feature is for.

## 2. Rules that are not negotiable

1. **No fabricated results.** Never invent numbers, dates, product IDs, place names, quotes, stories or references. If data is missing, the feature says so.
2. **Synthetic data is always labelled.** Anything not computed from real source data carries `dataKind: "synthetic"` end to end, and the UI shows a badge. The public demo must refuse synthetic data.
3. **Do not relabel sensors.** Sentinel-1 is never presented as NISAR. The 2022–2025 flood events in `backend/data/output/` are Sentinel-1 C-band.
4. **Wording.** Say "exposure", not "damage". Say "line-of-sight motion", not "sinking", unless vertical motion was actually derived. Scenarios are "conditional scenarios, not predictions". Hypotheses are labelled as hypotheses. Overlap is not causation.
5. **Missing is not zero.** Nodata is never counted as dry, and a missing value is `null` with a reason.
6. **No credentials in the repo.** The Earthdata token is read only from the `EARTHDATA_TOKEN` environment variable. Never commit `.netrc`, tokens or raw NISAR files (`backend/data/raw/` is gitignored).
7. **No paid services, no accounts in the app, no LLM calls at runtime.** Briefings are deterministic templates.
8. **Keep the tests green.** Add tests for every calculation. Do not skip or delete a test to make the suite pass.

## 3. How to run

```bash
python -m venv .venv
```

```bash
.venv/bin/pip install -r backend/requirements-dev.txt
```

```bash
cd backend && ../.venv/bin/python -m unittest discover -s tests
```

```bash
cd backend && ../.venv/bin/python -m uvicorn app.main:app --reload
```

```bash
cd frontend && npm ci && npm run dev
```

On Windows, use `.venv\Scripts\python` in place of `.venv/bin/python`. The frontend reads the API base from `NEXT_PUBLIC_API_URL` (default `http://127.0.0.1:8000`). `NEXT_PUBLIC_USE_FIXTURES=1` turns on synthetic development fixtures, which are for development only.

## 4. What exists now

Verify each row against the code before relying on it.

| Area | State | Where |
|---|---|---|
| Original app (Sentinel-1 flood events, coherence change, P3 NISAR ingest/phase/series/projection/briefing modules) | Working; 119 tests passed at baseline. P3 modules are verified on synthetic fixtures only | `backend/app/main.py`, `backend/processing/`, `backend/scripts/01`–`18` |
| Places: barangay search, boundaries, point lookup, exposure per barangay | **Done, real data, registered in the API**, 26 tests | `backend/processing/places/`, `backend/app/places_api.py`, `backend/scripts/40_fetch_places.py`, `backend/data/cache/places/` |
| Climate: NASA POWER rainfall history, anomalies, trend, season rank, seasonal outlook, 12-month scenarios, flood scenario, timeline availability | **Done, real data, registered**, 73 tests. Decision: scenarios stay on NASA POWER with an inline dry-season caveat (POWER over-reads Dec–Apr rain here); do not switch them to ERA5 | `backend/processing/climate/`, `backend/app/climate_api.py`, `backend/scripts/30_fetch_climate.py`, `backend/data/cache/climate/` |
| NISAR: catalogue search, windowed GCOV reader, water rule, flood rhythm, flooded vegetation, polarization view, synthetic demo, API | **Done and registered, 93 tests, but SYNTHETIC output only**: no real NISAR file read yet (needs Earthdata). Default stack 140 A / frame 9 | `backend/processing/nisar_flood/`, `backend/app/nisar_api.py`, `backend/scripts/19`–`22`, `docs/NISAR_RUNBOOK.md`, `backend/data/cache/nisar/` |
| Frontend CAMANAVA workspace: Story, Season, Flood rhythm, Ground motion, History, Future, spot check, search, explainer cards, EN/FIL toggle, Limits drawer | **Done; integrated with the real NISAR API (shows the synthetic product until Codex T1). Frontend agent is finished, but check `docs/CODEX_TASKS.md` before editing `frontend/`** | `frontend/components/CamanavaWorkspace.jsx` and the other new components, `frontend/utils/` |
| Packaging: MIT licence, CI, README, data manifest | Done | `LICENSE`, `.github/workflows/ci.yml`, `README.md`, `docs/DATA_MANIFEST.md` |

Real facts already established:
- NASA's catalogue (CMR) lists 11 NISAR GCOV dates (9 provisional, 2 V1) on track 140 A / frame 009 over the area, and about 9 consecutive 12-day GUNW pairs. Files are 2–5 GB each and need a free Earthdata login to download.
- Study-area totals: 5.22 million people (WorldPop 2020), 427,220 OSM building footprints (12 Oct 2026 snapshot), 7 study cities and 300 barangays (HDX COD-AB).

## 5. What to do next, in order

Work top to bottom. Each step has a "done when". Commit after each step with a clear message.

### Step 1: Get to a green, integrated baseline
1. Pull the latest. Run the backend tests and `npm run lint && npm run build` in `frontend/`.
2. Finish anything left incomplete in the climate, NISAR and frontend work listed in section 4. Compare each against its section in `docs/API_CONTRACT.md` and its feature in `docs/SUBMISSION_SCOPE.md`.
3. Register the routers in `backend/app/main.py`, following the existing pattern: `make_router(OUTPUT, read_public_events)` from `app.climate_api` and `app.nisar_api`.
4. Make sure `backend/scripts/21_nisar_gunw_chain.py` and `docs/NISAR_RUNBOOK.md` exist (see the NISAR section of the contract). Write them if they are missing.

**Done when:** all tests pass, the frontend builds, and every endpoint in the contract answers (with data, or with `data_unavailable`).

### Step 2: The real NISAR run (the most important step)
This must run on a machine with an Earthdata login.
1. Create a free account at urs.earthdata.nasa.gov, generate a user token, and set it as `EARTHDATA_TOKEN` in the shell. Do not write it to any file in the repo.
2. Run `backend/scripts/19_nisar_search.py` to refresh the granule manifest.
3. Read **one** GCOV file first. Verify the HDF5 dataset paths, units, projection and nodata against what `backend/processing/nisar_flood/gcov.py` assumes. Fix the reader if the real layout differs. Read only the study-area window; do not download all eleven full files unless the windowed read cannot work.
4. Run `backend/scripts/20_nisar_flood_rhythm.py` over all dates on track 140 A. Calibrate the water thresholds on open water in Manila Bay and record the calibration.
5. Look at the results critically. Does permanent water match the bay and the fishponds? Are flood counts plausible? Is anything obviously an artefact (layover, urban double-bounce)? Write what you find in the limitations.
6. Run the GUNW chain: script `21`, then the existing `10_ingest_nisar.py`, `11_phase_to_los.py` and `12_motion_series.py` for event `camanava_2026`. Check the reference area, the sign convention and the correction state. Report cumulative line-of-sight displacement over the season; do not present a 4-month result as an annual rate without marking it as an extrapolation.
7. Remove or replace the synthetic demo outputs so the API serves `dataKind: "observed"` or `"derived"` for NISAR layers.

**Done when:** the app shows real NISAR flood rhythm and ground motion for CAMANAVA with no synthetic badge, and `docs/DATA_MANIFEST.md` lists the exact granules used with hashes.

**If this step fails,** do not fake it. Keep the synthetic badge, say plainly in the README what could not be read and why, and continue with the steps below.

### Step 3: Wave 2 backend (owned by the coordinator in the contract)
1. **Priority zones (C1):** pixels flooded on half or more of valid passes **and** with line-of-sight motion away from the satellite beyond a justified noise threshold. Write the mask as `priority_mask.tif` next to the rhythm raster, and report people and buildings per barangay through `processing/places/exposure.py::exposure_for_mask`. Test the thresholds for sensitivity.
2. **Spot check:** `GET /api/v1/spot-check?lon=&lat=` combining the NISAR point result, the containing barangay, pass rainfall, exposure and the line-of-sight series. Every value carries its source; missing values say why.
3. **Briefing:** `GET /api/v1/briefing/place?lon=&lat=&lang=en|fil`, a deterministic template fed by the spot-check facts, plus CSV and HTML export. Every number must match the screen. The Filipino text needs sign-off from a native speaker on the team.
4. **Validation (C4):** compare the flood masks with an independent source (2026 NDRRMC or MMDA flood reports, Copernicus EMS, UNOSAT, or NASA's OPERA DSWx-S1), and compare the motion with published CAMANAVA subsidence rates. Report agreement and disagreement honestly in a validation card and the README.
5. **Rain-to-flood (C3) and the flood scenario (F5):** confirm the climate endpoints use the real pass list once step 2 is done.

### Step 4: Frontend completion
1. Point every mode at the real API and remove any dependence on fixtures in the default build.
2. Wire the spot check, briefing export, priority zones and validation card.
3. Fill `frontend/public/hypotheses.json` (N6) only with hypotheses that have a real, checked reference. Fill `frontend/public/stories.json` (U7) only with text the team members wrote themselves.
4. Check 1366×768, keyboard operation, focus states, and that no status relies on colour alone.
5. Build the public static demo (U9) from cached real outputs. It must contain no synthetic data.

### Step 5: Packaging and submission
1. Update `README.md`: set each row of the challenge table to its true status, put limitations first, and document one-command reproduction.
2. Fill `docs/DATA_MANIFEST.md` for every dataset.
3. Run a user test with three people outside the team, fix the top two problems, and record what happened in the README.
4. Record the 30-second video following section 6 of the scope document, using verified numbers only. Write the AI-use disclosure for the submission page.

## 6. If time runs short

Cut in this order (from the scope document): N3+ vertical motion → radar lens → Landsat then-and-now → polarization view → Sentinel-1 then-and-now → downloads → GIF export → shareable URL → validation accuracy scores (keep the subsidence comparison) → reduce the timeline to POWER plus NISAR → public demo.

**Never cut:** flood rhythm, the season animation, line-of-sight motion, priority zones, the rain-to-flood chart, rainfall history, the outlook, the 12-month scenarios, spot check, Story Mode, barangay search, the bilingual briefing, the stories, the README and the video.

## 7. Working conventions

- Backend routers live in `backend/app/<name>_api.py` and expose `make_router(output_root, read_public_events)`. Processing code lives in `backend/processing/<name>/`. Scripts are numbered in `backend/scripts/`.
- Responses use camelCase and always include `dataKind`, `source`, a timestamp, `warnings` and `limitations`. Errors use `{"detail": {"code", "message"}}`.
- Small derived products and caches (a few MB) may be committed under `backend/data/cache/`. Large rasters and raw downloads may not.
- When you change an endpoint, update its section in `docs/API_CONTRACT.md` in the same commit.
- When you finish a step, update section 4 of this file so the next agent starts from the truth.
