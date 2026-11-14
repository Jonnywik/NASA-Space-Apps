# Antigravity task list: small frontend tasks for 15 Nov 2026

Antigravity: read `AGENTS.md` first for context, rules and how to run. This file gives you a **short list of small, needed tasks** that don't overlap with Codex (`docs/CODEX_TASKS.md`), which is working on the backend and the real NISAR run.

Coding freezes at 17:00 Manila time. Each task is meant to take 30–90 minutes.

## Your boundaries

- **You own:** `frontend/` (all of it), `docs/FIL_REVIEW.md` (new) and `docs/ANTIGRAVITY_STATUS.md` (new).
- **Do not edit:** anything under `backend/`, `README.md`, `AGENTS.md`, `docs/SUBMISSION_SCOPE.md`, `docs/API_CONTRACT.md` or `docs/CODEX_TASKS.md`. If you need a backend change, write it in `docs/ANTIGRAVITY_STATUS.md` under `NEEDS-BACKEND:` and move on.
- **Git:** commit small and often to `claude/kind-pascal-93n7ns`. Run `git pull --rebase` before each push. Never force-push.
- **Before each push:** `cd frontend && npm run lint && npm run build` must pass.
- **Rules from `AGENTS.md` section 2 apply in full.** No invented numbers, stories or references. Synthetic data keeps its badge. Say "exposure", not "damage". Say "line-of-sight motion", not "sinking".
- **Running the app:** start the backend with `cd backend && ../.venv/bin/python -m uvicorn app.main:app --port 8000`, then the frontend with `cd frontend && npm run dev`. Don't use fixture mode for checking; it's for development only.

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
3. Check that every number on screen has its source and data-kind badge, and that the SYNTHETIC banner appears whenever any layer in view is synthetic.
4. Save screenshots of every mode to `frontend/screenshots/` (create it; commit them). The team will use them for the project page.
5. List anything you couldn't fix in `docs/ANTIGRAVITY_STATUS.md`.

**Done when:** there are no console errors, the screenshots are committed, and lint and build pass.

## What to send back

In `docs/ANTIGRAVITY_STATUS.md`, add one line per task: its status (done / partial / blocked), the commit hash, any `NEEDS-BACKEND:` request, and anything you couldn't verify.
