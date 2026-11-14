# Tanaw: submission scope (target 45+/50)

Written at 23:00 on 14 Nov (Manila). Coding freezes at 17:00 on 15 Nov. This overrides sections 3, 11 and 16 of `Tanaw-final-development-plan.md` for the submission. The rest of that plan becomes the roadmap. Its honesty rules apply in full: no silent sample data, no relabelling Sentinel-1 as NISAR, and no number without a source.

**Target:** 9 or more on every criterion. That is a stretch, and judging is subjective. **Hard ceiling:** if gate G1 fails (no quantitative NISAR over the area), Relevance and Creativity cap near 7, so the realistic total is about 40. G1 is the most important thing to settle tonight.

## 1. The story

> **The same farms and towns flood every monsoon. Radar has seen it three years running, and NISAR can now see it under the rice.**

**Why this wins each criterion**

| Criterion | What earns a 9 |
|---|---|
| **Impact** | It gives a list of places that flooded in **all three** SAR-observed events (2022, 2024, 2025), with buildings and people in them. That is a concrete, reusable priority list for municipal DRRM offices, not a single-event picture. |
| **Creativity** | **L-band sees flooded vegetation.** C-band misses water under rice canopy and trees; NISAR's L-band picks up the double-bounce signal there. Tanaw shows the extra flood area NISAR reveals compared with C-band. It also offers a **Filipino-language briefing** alongside English. |
| **Validity** | The flood maps are checked against an independent source (gate G5). Every number is hand-checked and comes with its source, date and resolution. The demo is a three-click flow anyone can open (hosted static demo). |
| **Relevance** | NISAR is quantitative and central: L-band imagery runs through the same detection method as C-band. NASA POWER/GPM rainfall supplies the trigger. NASA data is the method, not decoration. |
| **Presentation** | It opens on one striking number, then shows the before/after swipe, the recurrence map, the L-band reveal and the briefing. Captions, under 2 minutes, and a public link judges can click. |

**Named users:** municipal and city DRRM officers, and provincial planners in Pampanga and Bulacan. Researchers and students are secondary users.

## 2. Must ship

| # | Capability | Builds on | Done when |
|---|---|---|---|
| S1 | **Recurrence map.** Overlay the flood polygons for `karding_2022`, `carina_2024` and `habagat_2025`, coloured by how many events flooded each place (1, 2 or 3). Cells that are only partly covered across events are marked. | Existing real outputs in `backend/data/output/*/flood.geojson` | Areas are computed in an equal-area CRS. The recurrence count only uses cells observed in every event, so missing coverage is not counted as "dry". A unit test covers this. |
| S2 | **Event drill-down.** A before/after SAR swipe for any of the three events, with sensor, dates and threshold shown. | Existing flood routes and frontend | Labels say Sentinel-1 C-band VV, and the threshold value comes from `02_info.json`. |
| S3 | **Rainfall trigger.** For each event, rainfall during the event window compared with the 1991–2020 baseline for the same window, from NASA POWER (PRECTOTCORR). | New small adapter and cached JSON | Conversion from mm/day is correct, and the result matches a hand check. The "one grid cell, about 50 km" caveat is visible. |
| S4 | **Exposure in recurring zones.** Buildings (OSM snapshot, script 08) and people (WorldPop 2020) in places flooded 2 or 3 times. Results are grouped by municipality where boundaries are available. | Script 08; boundaries from gate G4 | Labelled "exposure", not "damage". It is reproducible from the recorded snapshot and its hashes. |
| S5 | **NISAR L-band panel.** Take the most recent wet-season NISAR GCOV over the area and apply a water threshold (HH/HV, calibrated on known open water). Show the area NISAR flags as water or flooded vegetation that a C-band map from a similar date does not. | `10_ingest_nisar.py` adapter, or rasterio on the GCOV GeoTIFF | The dates of both sensors are shown. Differences are called "detected by L-band only", not proof of better accuracy. The threshold and its rationale are recorded. |
| S6 | **Briefing in English and Filipino.** A deterministic template fed by the S1–S5 facts. Export as CSV and HTML (print to PDF). | Existing `BriefingCard` | Every number matches the screen. The Filipino template is reviewed by a native speaker on the team. |
| S7 | **Validation card.** A comparison with an independent flood record (gate G5): agreement by municipality, or overlap percentage with a published flood map. | New small script | The method and source are shown. Disagreements are reported, not hidden. |
| S8 | **Public demo.** A static frontend build on free hosting (Vercel Hobby or GitHub Pages) that serves the cached real JSON. Its label reads "snapshot of published results; run the backend locally for analysis". | The existing offline fallback path in `frontend/utils/api.js` | A judge opens the link and completes the flow in 3 clicks. No synthetic data appears on the public build. |
| S9 | **README, data manifest and method notes.** One page judges can skim, with limitations up front. | Replaces the boilerplate README | Someone else can reproduce S1–S7 locally. |
| S10 | **Recording and submission text.** | — | See sections 5 and 6. |

## 3. Cut for the submission (roadmap)

- Metro Manila city selector, barangays, worldwide search, and the Civic Atlas restyle. Keep the current UI and polish only what appears in the recording.
- 12-month scenarios, seasonal forecasts, drought screening, and loss in pesos.
- All of section 16 (Landsat from 2000, ERA5, ASF search, token handling).
- Ground-motion, LOS, projection and route panels. These have synthetic-only data. Hide them from the public build, and locally keep them behind a toggle labelled "pipeline preview – synthetic".

## 4. Gates (decide by 01:00; the results set the final story)

| Gate | Check | Pass | Fail |
|---|---|---|---|
| **G1 NISAR** (critical) | A NISAR GCOV product intersects 120.55–121.10 E, 14.70–15.25 N during a wet season (Jun–Oct 2025 or later), is downloadable with a free Earthdata login, and is readable | S5 as specified | Fallback 1: GIBS NISAR imagery, shown as imagery only. Fallback 2: a dry-season scene, which shows the L-band detects water but drops the "under the rice" claim. Disclose which fallback is used. The score ceiling drops to about 40. |
| **G2 Rainfall** | NASA POWER daily PRECTOTCORR 1991–2025 at the event centroids | S3 | Open-Meteo ERA5, labelled as such |
| **G3 Population** | WorldPop 2020 PHL 100 m clipped to the area is readable | S4 people | Buildings only |
| **G4 Boundaries** | A licensed municipal boundary dataset (e.g. HDX COD-AB for the Philippines) covers the area | Grouping by municipality in S4 | Report by recurrence class only |
| **G5 Validation** | Either an independent flood map (Copernicus EMS, UNOSAT or Sentinel Asia) for one of the three events, or an NDRRMC situation report listing flooded barangays or municipalities | S7 | Validate internally: compare the flood polygons with JRC Global Surface Water permanent water, and disclose that no independent event map was found |
| **G6 Buildings** | An OSM building snapshot for the area loads into script 08 | S4 buildings | WorldPop only |

Record every gate result, including source URL, retrieval time, version and hash, in `docs/DATA_MANIFEST.md`.

## 5. Schedule (Manila time)

| Time | Agent A: data/backend | Agent B: NISAR | Agent C: frontend | Coordinator |
|---|---|---|---|---|
| 23:00–01:00 | G2–G6 | G1 | Baseline build; hide out-of-scope panels | Baseline tests; gate decisions at 01:00 |
| 01:00–05:00 | S1 recurrence and its test; S3 rainfall | S5 download, ingest, threshold | Recurrence layer and event switcher (S1/S2 UI) | Reviews S1 for the missing-coverage logic |
| 05:00–09:00 | S4 exposure; S7 validation | S5 comparison with C-band and export | S3/S5 panels, validation card | Hand-checks numbers as they land |
| 09:00–12:00 | S6 facts and templates (EN/FIL) | Help with S6 and the NISAR method note | S6 briefing UI and exports | Merges in order S1 → S3 → S4 → S5 → S6 → S7 |
| 12:00–14:00 | Data manifest | — | S8 static build and deploy | S9 README; run the full flow end to end |
| 14:00–17:00 | Bug fixes only | Bug fixes only | Bug fixes only; 1366×768 and keyboard check | Rehearse the recording; freeze and tag at 17:00 |
| 17:00–21:00 | — | — | — | Record S10; write the submission text and AI disclosure; check that the public link works in a private window |

**If time slips, cut in this order:** S7 → Filipino template → S8 → municipal grouping (G4) → population. Protect S1, S5, S2, S3 and S6 (English) to the end.

## 6. Demo script (about 90 s; check the official limit first)

| Time | On screen | Narration (draft) |
|---|---|---|
| 0–8 s | Recurrence map; the headline number | "N thousand people live where radar has seen flooding in all three of the last monsoon disasters." |
| 8–25 s | Swipe the 2024 before/after; then the rainfall card | "Carina dropped X% more rain than a normal July. Sentinel-1 radar sees through the clouds…" |
| 25–45 s | Switch events, and the recurrence builds | "…and the same places flooded in 2022 and 2025." |
| 45–65 s | NISAR L-band panel | "NASA's NISAR uses L-band, which reaches under the rice canopy. It flags Y km² that C-band misses." |
| 65–80 s | Briefing, toggle to Filipino, export | "One click gives a sourced briefing in English or Filipino for the municipal DRRM office." |
| 80–90 s | Validation card; public link | "Checked against <source>. Open source, free, try it now." |

Fill in N, X, Y and the source only from verified results. Burn in captions, and record at 1080p.

## 7. Score expectations (estimates, not guarantees)

| Criterion | Original plan | v1 scope | This scope (G1 passes) | This scope (G1 fails) |
|---|---|---|---|---|
| Impact | 7 | 7.5 | 9 | 8.5 |
| Creativity | 6 | 7 | 9 | 7 |
| Validity | 7.5 | 8.5 | 9 | 8.5 |
| Relevance | 5 | 7–8 | 9 | 6.5 |
| Presentation | 6.5 | 7.5 | 9 | 8.5 |
| **Total** | **32** | **37–39** | **45** | **39** |

## 8. Biggest risks

1. **NISAR coverage or access (G1).** Mitigation: check it first; if it fails, re-centre the pitch on recurrence and impact.
2. **Scope for 18 hours.** S1, S2, S3 and S6 reuse real outputs and are small, but S5 and S8 are the uncertain parts. Respect the cut order.
3. **Recurrence logic.** The three events have different bounding boxes and coverage. A wrong "never flooded" in an unobserved cell would undermine Validity. S1's test must catch it.
4. **The L-band versus C-band claim.** The scenes are from different dates and conditions. Present the difference as "L-band additionally detects", backed by evidence from a known vegetated or paddy area. Never claim it as accuracy.
