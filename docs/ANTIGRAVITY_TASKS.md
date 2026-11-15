# Antigravity task list for 15 Nov 2026 (current: Round 3, A8)

Antigravity: read `AGENTS.md` first for context, rules and how to run. This file gives you a **short list of small, needed tasks** that don't overlap with Codex (`docs/CODEX_TASKS.md`), which is working on the backend and the real NISAR run.

Coding freezes at 17:00 Manila time. Each task is meant to take 30–90 minutes.

## Your boundaries

- **You own:** `frontend/` (all of it), `docs/FIL_REVIEW.md` (new) and `docs/ANTIGRAVITY_STATUS.md` (new).
- **Do not edit:** anything under `backend/`, `README.md`, `AGENTS.md`, `docs/SUBMISSION_SCOPE.md`, `docs/API_CONTRACT.md` or `docs/CODEX_TASKS.md`. If you need a backend change, write it in `docs/ANTIGRAVITY_STATUS.md` under `NEEDS-BACKEND:` and move on.
- **Git (updated 15 Nov):** the main repository is now `Jonnywik/NASA-SA-Final`. For A6, create branch `antigravity/a6-mangrove` from the latest `main`, commit small and often there, and push it. The coordinator reviews and merges it. Run `git pull --rebase` before each push. Never force-push. Don't reuse the old `antigravity/codex-tasks-t3-t7` branch.
- **Before each push:** `cd frontend && npm run lint && npm run build` must pass.
- **Rules from `AGENTS.md` section 2 apply in full.** No invented numbers, stories or references. Synthetic data keeps its badge. Say "exposure", not "damage". Say "line-of-sight motion", not "sinking".
- **Running the app:** start the backend with `cd backend && ../.venv/bin/python -m uvicorn app.main:app --port 8000`, then the frontend with `cd frontend && npm run dev`. Don't use fixture mode for checking; it's for development only.

## Round 3 (15 Nov, about 14:20): A8, final polish on real data. Push by 16:30.

A7 is merged (thank you). The coding freeze is **17:00 Manila**. Work on a new branch **`antigravity/a8-polish`** from the latest `main`, and push after **each** sub-task so the coordinator can merge in pieces. Same boundaries (`frontend/` plus your docs; `docs/RECORDING_SHOTS.md` is also yours this round) and same checks (lint, build, `test:api`). Do them in this order; if time runs out, stop at a pushed sub-task.

### A8.0 See the real data first (10 min)
Your last screenshots were taken against the **synthetic** product (they showed Demo tags and 82.1 km²) and had to be replaced. On the laptop, **first check whether the real product already exists**: `backend/data/output/camanava_2026/nisar/manifest.json` with `"dataKind": "observed"` (Codex generated it there). **If it exists, do NOT regenerate it.** The OPERA validation results (`/api/v1/validation`) are bound to that exact product file's SHA-256, so regenerating it makes the validation card disappear. Only if it is missing, regenerate it with the two commands in the "v6 decision" section of `docs/SUBMISSION_SCOPE.md`, then re-run `python scripts/61_opera_comparison.py` (needs `EARTHDATA_TOKEN`) so validation matches again. Then confirm that `GET /api/v1/nisar/passes` returns `"dataKind": "observed"` and the Flood rhythm headline reads about 0.4 km². **Do not use fixture mode or the synthetic demo for any check this round.**

### A8.1 Future: an honest flood-scenario card (30 min)
The exploratory flood scenario (`/climate/flood-scenario`) is now fitted on the real passes, where NISAR open water goes **down** after rain (ρ = −0.77 with 48 h IMERG rain; see the runbook). Showing it as a "flood scenario" would suggest that wetter months mean less flooding, which is not what it means.
- **Hide the flood-scenario chart** in Future. Replace it with a short card: "No flood scenario: NISAR's open-water layer shrinks after heavy rain (wet ground and rough water look brighter to the radar), so it can't be used to project floods. Rainfall scenarios above are still valid."
- Keep the rainfall outlook and the 12-month rainfall scenarios unchanged.
- Strings in English and Filipino (Filipino pending review).

### A8.2 The key finding as a chart (45 min; most important for the video)
In **Flood rhythm** findings, below "In plain words", add a small scatter plot: **"Open water vs rain before each pass"**.
- **x:** 48-hour rain before the pass, `last48hMm` from `GET /api/v1/climate/imerg/passes?series=false`.
- **y:** open water outside the usual water on that pass, `floodedKm2` from `GET /api/v1/nisar/passes`.
- Join on `date`. One dot per pass, labelled with its date on hover or focus. Drop a dot if either value is null; never plot null as 0.
- **No fitted line and no hard-coded statistic.** Caption: "Each dot is one NISAR pass. Passes after heavy rain show less open water: wet ground and rain-roughened water look brighter to L-band radar. Exploratory, 11 passes." Credit both sources (NASA GPM IMERG; NASA–ISRO NISAR).
- Make it accessible: `role="img"` with an `aria-label` summarising the points, plus a "Show as table" toggle listing date, rain and open water.

### A8.3 Story tour matches the real story (30 min)
Review all story steps against the v6 story ("what NISAR sees, what it can't see yet, what's next"):
- **No step may promise ground motion results or priority zones.** Change the ground-motion step to "The ground beneath: not measurable yet (ionospheric noise in 4 months of data)", or merge it into "what's next".
- Add or reuse a step for **"What NISAR can't see"** that points at the explainer card.
- The last step stays "Find my barangay".
- Keep the facts driven by the API (`story.fact.*`). Remove `story.fact.priority` from the tour if priority zones are unavailable.

### A8.4 Spot card on real data (20 min)
- When `floodCount` is 0, write "No open water outside the usual water on any of the 11 passes" rather than "Flooded on 0 of 11".
- Make sure the spot card shows the IMERG line ("Rain in the 24 h before the selected pass: X mm, NASA GPM IMERG, ~11 km cell"), with null as "incomplete data".
- Check the Malabon point (lon 120.957, lat 14.665) and one point in the north-west fishpond area (about lon 120.89, lat 14.80).

### A8.5 Recording kit (20 min)
Write **`docs/RECORDING_SHOTS.md`** for the team's 30-second video: an ordered list of shots, each with its exact app URL (using the URL parameters `mode`, `pass`, `lon`, `lat`, `lang`), what to click or hover, and how long to hold, following the v6 story:
1. Title and study area.
2. A NISAR pass with the IMERG rain card (10 Aug).
3. The Flood rhythm headline.
4. The new rain-vs-open-water chart.
5. "What NISAR can and can't see".
6. Find my barangay, then the spot card and briefing.

Use only numbers the app shows. Add a checklist: 1920×1080 browser window, zoom 100 %, real product loaded, no Demo tags visible.

### A8.6 Final check and screenshots (20 min, start by 16:00)
Walk every mode at 1366×768 and 390×844 on the real data. Fix only real defects. Then replace `frontend/screenshots/v2-real/` with screenshots **from your laptop**, which shows the street basemap; the coordinator's set has a blank basemap. Check that no Demo or SYNTHETIC text is visible. Record the status in `docs/ANTIGRAVITY_STATUS.md`.

**Done when:** A8.1–A8.6 are pushed on `antigravity/a8-polish` by **16:30**, lint, build and `test:api` pass, and no Demo or synthetic text appears anywhere on real data.

## Round 2 (15 Nov, about 13:15): A7, the real-data copy and new layers. (DONE, merged)

A6 is merged into `main` (thank you). The app now serves **real NISAR data**; read the "v6 decision" section at the top of `docs/SUBMISSION_SCOPE.md` first. Work on a new branch **`antigravity/a7-real-data`** from the latest `main`. Same boundaries as before (`frontend/` only, plus your status and Filipino review docs). Same checks before each push: lint, build, `test:api`.

To see real data locally you need the real product. Regenerate it with the two commands in that section (needs `EARTHDATA_TOKEN`), or ask the coordinator.

### A7.1 Wording (do first; about 30 min)
- **Rename the layer.** The real data shows NISAR's "flood rhythm" area *shrinks* after rain (ρ = −0.77 with 48 h IMERG rain; see the runbook). In the UI, call it **"Open water outside the usual water"** (mode name can stay "Flood rhythm", but the headline, legend title and plain words must not call it flooding). Add one line in plain words: "This layer gets smaller after heavy rain, because wet ground and rain-roughened water look brighter to the radar."
- Remove every claim that NISAR shows **flooded streets**. Flood rhythm describes "open water on land that is usually dry"; e.g. the plain-words text "darker blue shows streets that flooded again and again" must change.
- Generate the findings headline and "In plain words" from the API values. Never hard-code numbers. With the real data, the headline reads like "0.37 km² of usually-dry land had open water on half or more of NISAR's passes".
- Search `i18n.js` and the components for "street", "flooded streets", "damage" and "sinking", and fix each, in both English and Filipino (Filipino marked pending review).

### A7.2 "What NISAR can and can't see" (about 45 min)
Add a fifth card to "How radar sees" and a short note in the Flood rhythm findings, opened from the "?":
- Calm open water reflects the radar away and looks **dark**.
- In a flooded street, the radar bounces off the water and then a wall straight back to the satellite (**double-bounce**), so the street looks **bright**, not dark. Narrow streets, building shadows and layover also hide the street surface.
- NISAR passes CAMANAVA at about **05:30 Manila time** every 12 days, so floods that rise in the afternoon and drain overnight are missed.
- The radar does see the whole area get "wetter" after rainy weeks: built-up and open land brighten together (Spearman ρ = 0.80 with 7-day rain, n = 11). This is general wetness, not a flood map.

### A7.3 IMERG rain timing (about 60 min; after the coordinator adds the endpoint)
`GET /api/v1/climate/imerg/passes?area=camanava_2026` (see `docs/API_CONTRACT.md`) returns, for each NISAR pass, the half-hourly NASA GPM IMERG rain over the 48 hours before the pass, with totals and "hours since the last rain".
- **Season:** in the findings for the selected pass, add a card "Rain before this pass (NASA GPM IMERG)" with the last-24 h and last-48 h totals, the peak and when it was, and "last heavy rain N h before the pass". Add a small half-hourly bar sparkline ending at the pass time, marked "pass 05:30".
- **Spot card:** one line, "Rain in the 24 h before this pass: X mm (GPM IMERG, ~11 km cell)".
- Badge: "NASA GPM IMERG". Show the API's limitations in the Limits drawer. A null total means "incomplete data", not 0.

### A7.4 Ground motion and priority zones (about 30 min)
- **Ground motion:** a clear unavailable state: "Not available yet. Four months of NISAR interferograms are dominated by ionospheric noise; ground motion needs a longer record and ionosphere correction." Keep the "How radar sees" InSAR card.
- If you add literature context, use only references already verified in `docs/HYPOTHESES_SOURCES.md` (the Codex section, e.g. Eco et al. 2020). Label it "Published study (not NISAR)" and give no numbers that aren't in that file.
- **Priority zones:** "Not available: needs ground motion."

### A7.5 Real-data screenshots (about 20 min)
Re-take every mode at 1366×768, plus the phone view, against the real product, into `frontend/screenshots/v2-real/`. Check that no Demo tags remain on NISAR values.

**Done when:** no copy claims flooded streets; the explainer card exists in English and Filipino; IMERG timing shows in Season and the spot card; Ground motion and priority zones show honest unavailable states; real screenshots are committed; lint, build and `test:api` pass; and `docs/ANTIGRAVITY_STATUS.md` is updated. Push the branch and tell the owner; the coordinator reviews and merges.

## Status update (15 Nov, coordinator): do A6, then A2 and A5

- **A1, A3 and A4 are already done by Codex** and merged to `main`: `docs/FIL_REVIEW.md` exists, the pass legend uses shared colours, and the briefing buttons are wired. Don't redo them. A1 now only waits for the native-speaker corrections.
- **Your order now:** **A6** (the redesign, below) → **A2** (base map, as part of A6's Map tools "Map mode") → **A5** (final UI check on the new design).

## A6: Restyle the app to the approved "Mangrove" design (main task; about 4–6 h)

**Why:** the owner approved a new interface design. It is calm civic with a map-first layout, a left mode rail, a Map tools panel and a spot card on the map. It aims at the Presentation and Impact scores.

**Spec:** **`docs/DESIGN_SPEC_V2.md`**. Read all of it first. The board sources are in `docs/design/v2-mangrove/` for exact structure and styles.

**Steps:**
1. **Tokens and fonts.** Add the Mangrove CSS variables and Tailwind names, and switch the fonts to Inter plus Source Serif 4 via `next/font/google` (spec §2).
2. **Shell.** Header, left mode rail, map with floating search, findings panel, footer timeline (§3). First view: **Flood rhythm**.
3. **Map tools.** Map mode, overlay (one at a time, following the mode by default) and layers, with reset and a live summary (§4.3). Base-map tiles: free and key-less only; this is where A2 lands.
4. **Spot card** at the bottom-left of the map, using the existing `/spot-check` and briefing wiring (§4.5).
5. **Findings panel pattern:** eyebrow, serif headline built from API fields, stat cards, "In plain words", source line (§4.6). Add all new strings to `i18n.js` in English and Filipino (Filipino marked pending review).
6. **Timeline:** stepper plus a slider with real daily rain bars and pass dots. History has the data ribbon; Future has the observed/outlook/scenario band (§4.8).
7. **Demo tags replace the yellow banner,** on every synthetic number and overlay legend, driven by `dataKind` (§4.9).
8. **The five modes** per §5, including UTC + Manila time on passes and the POWER caveat under the Future chart.
9. **Phone layout** below 900px: bottom sheet and bottom tab bar (§6).
10. **Motion rules and reduce-motion** (§7). Work through the accessibility checklist (§8).

**Don't:** change API calls, analysis or wording rules; touch `backend/`; invent numbers; remove any existing feature. Move features, don't delete them: Story tour, Limits, Radar cards, Regional context, Pipeline preview and briefing exports must all remain reachable.

**Done when:** every item in spec §10 passes, screenshots are in `frontend/screenshots/v2/`, and lint, build and `test:api` pass. Log the status and any `NEEDS-BACKEND:` lines in `docs/ANTIGRAVITY_STATUS.md`.

## A1: Filipino review sheet (do first; about 30 min)

**Why:** a native speaker on the team must sign off the Filipino text before the video. They need it in a form they can read quickly.

1. Write `docs/FIL_REVIEW.md` from `frontend/utils/i18n.js`: a table with the key, the English text, the current Filipino text, and an empty "Corrected Filipino" column. Group the rows by screen (Story, Season, Flood rhythm, Ground motion, History, Future, Spot check, Limits, Radar cards).
2. Put the strings most likely to appear in the video at the top: the story steps, the mode names, the spot-check labels and the scenario caveat.
3. Add a short instruction at the top for the reviewer: correct the meaning, keep `{placeholders}` unchanged, and flag anything that sounds machine-translated.
4. After the reviewer fills it in, copy the corrections back into `i18n.js`, and remove the "pending native review" marker only for the keys that were reviewed.

**Done when:** the sheet exists and covers every `fil` key. When the corrections come back, they are applied.

## A2: Base map and attribution on the laptop (about 30 min)

**Why:** the base map was blank in the cloud test because the tiles were blocked. Judges need to see streets.

1. Run the app on the laptop and confirm the base-map tiles load in the CAMANAVA workspace and the regional view.
2. Make sure the tile provider's **attribution** is visible (OpenStreetMap contributors, or whichever provider is used), as its licence requires. Also make sure the NISAR/ASF, NASA POWER, WorldPop, ESA WorldCover and HDX credits are reachable from the map, for example in a "Sources" link in the footer or the Limits drawer.
3. Check that the CAMANAVA study-area outline and the NISAR overlays line up with the coastline in Navotas and Malabon. If they are visibly offset, record it in `docs/ANTIGRAVITY_STATUS.md` under `NEEDS-BACKEND:` with a screenshot path; don't "fix" it by shifting things in the frontend.
4. If the default tile server is slow or rate-limits, switch to another **free, no-key** provider whose terms allow this use, and update the attribution.

**Done when:** a screenshot at 1366×768 shows streets under the overlays with the correct attribution.

## A3: Pass legend from the API (about 20 min; after Codex adds the field)

**Why:** the colours for the water and flooded-vegetation overlays are hard-coded in the frontend. They match today, but would drift silently if the backend changes them.

1. Check whether `GET /api/v1/nisar/passes?area=camanava_2026` returns a top-level `legend: [{id, label, color}]`. The frontend already uses it if present, so confirm that it does.
2. If the field is still missing, add a `NEEDS-BACKEND:` line asking for it, and leave the fallback in place.

**Done when:** the Season legend colours come from the API, or the request is logged.

## A4: Briefing export buttons (about 60 min; after Codex task T4 lands)

**Why:** the bilingual briefing is a never-cut feature. Codex is building the API (`GET /api/v1/briefing/place?lon=&lat=&lang=en|fil&format=json|csv|html`; see the "Spot check and briefing" section of `docs/API_CONTRACT.md` once Codex adds it).

1. In the spot-check card, add buttons for **"Briefing (EN)"**, **"Briefing (FIL)"** and **"Download CSV"**. The HTML briefing opens in a new tab, ready to print; the CSV downloads.
2. Use the existing `request`/`ApiError` pattern in `frontend/utils/api.js`, and show the existing unavailable state if the endpoint returns 404.
3. If the briefing response has `dataKind: "synthetic"` or `translationStatus: "pending native-speaker review"`, show that next to the buttons.

**Done when:** for the Malabon test point (lon 120.957, lat 14.665) both languages open and the CSV downloads, against the real backend.

## A5: Final UI check before the freeze (about 60 min; at about 14:00)

**Why:** this is the last chance to catch anything that would look broken in the video or to a judge.

1. Walk through Story Mode and every mode at **1366×768** and at a phone width (390×844) on the real backend.
2. Fix only real defects: overlapping text, cut-off labels, controls you can't reach with the keyboard, missing focus outlines, any status shown by colour alone, and console errors.
3. Check that every number on screen has its source, and that every synthetic number and overlay carries a **Demo** tag. The yellow banner is retired in the v2 design.
4. Save screenshots of every mode to `frontend/screenshots/v2/` (create it; commit them). The team will use them for the project page.
5. List anything you couldn't fix in `docs/ANTIGRAVITY_STATUS.md`.

**Done when:** there are no console errors, the screenshots are committed, and lint and build pass.

## What to send back

In `docs/ANTIGRAVITY_STATUS.md`, add one line per task: its status (done / partial / blocked), the commit hash, any `NEEDS-BACKEND:` request, and anything you couldn't verify.
