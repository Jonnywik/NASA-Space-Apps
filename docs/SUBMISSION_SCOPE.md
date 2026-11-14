# Tanaw: submission scope

Written at 23:00 on 14 Nov (Manila). Coding freezes at 17:00 on 15 Nov, about 18 working hours away. This document overrides the scope in `Tanaw-final-development-plan.md` sections 3, 11 and 16 for the submission. The rest of that plan becomes the post-submission roadmap. Its honesty rules still apply in full: no silent sample data, no relabelling Sentinel-1 as NISAR, no number without a source.

## 1. The one story

> **Where will the next monsoon flood hit people in Manila Bay's north coast, and can NISAR see it?**

The 60–90 s demo follows one thread on one event:

1. **Why.** NASA POWER rainfall for July 2024 against the 1991–2020 July baseline gives the anomaly. Carina and the habagat brought an extreme month.
2. **What SAR saw.** The before/after radar comparison and flood extent come from the existing pipeline, so they are real outputs already in `backend/data/output/carina_2024`.
3. **Who was exposed.** Buildings and population overlap the flood polygon. The method and its sources stay visible.
4. **NISAR now.** A recent NISAR L-band observation of the same area goes through the same water-detection method, or is shown as a dated image if only imagery is available (gate G1).
5. **Briefing.** A deterministic briefing reports the numbers from steps 1–4 with their sources, and exports as CSV and HTML.

Rainfall is context; SAR is the evidence. Relevance depends on that ordering.

**Users named in the pitch:** municipal and city DRRM offices and planners. Researchers and students are secondary users.

## 2. In scope (must ship)

| # | Capability | Builds on | Done when |
|---|---|---|---|
| S1 | Event workspace for `carina_2024`: map, before/after SAR swipe, flood polygon, legend, dates and sensor label | Existing flood routes and frontend | It loads from the real backend, and its labels state the sensor (Sentinel-1 C-band) |
| S2 | July rainfall anomaly card and chart for one representative coordinate (NASA POWER) | New small backend adapter with a cached JSON file | Monthly total = mm/day × days. The baseline, anomaly and grid-cell caveat are shown, and the result matches a hand check |
| S3 | Exposure for the flood polygon: building count from the OSM snapshot via script 08, and population from WorldPop if gate G3 passes | Existing `08_building_exposure.py` | The count is reproducible from a recorded snapshot, and it is labelled "exposure", not "damage" |
| S4 | NISAR panel: a recent NISAR observation over the AOI | Gate G1 decides the variant | Variant A: GCOV water mask through the same threshold method. Variant B: dated GIBS imagery, labelled as imagery only |
| S5 | Deterministic briefing combining S1–S4, with CSV and HTML export | Existing `BriefingCard` and the briefing template pattern | Every number in the briefing matches a value on screen |
| S6 | README covering setup, data manifest, sources and limitations | Replaces the boilerplate README | Another person can start the backend and frontend and see S1–S5 |
| S7 | Recorded demo and submission text | — | Done by the time in section 5 |

## 3. Out of scope for the submission

These move to the roadmap and are not demoed:
- Metro Manila city selector, barangays and worldwide navigation (section 4 of the original plan)
- 12-month conditional scenarios, seasonal forecasts and drought screening
- Agricultural and property loss in pesos
- Landsat from 2000, ERA5, ASF Sentinel-1 search, and token or STAC handling (all of section 16)
- Ground-motion and LOS panels, plus Tier 3 and Tier 4 routes and projections. These have synthetic-only data, so hide them or keep them behind a clearly marked "demo pipeline" toggle. They must not appear in the recording as results.
- The Civic Atlas restyle. Keep the current UI and fix only what blocks the demo.

## 4. Gates (decide by 01:00)

| Gate | Check | If it passes | If it fails |
|---|---|---|---|
| **G1 NISAR** | Find a NISAR GCOV or GUNW product, or a GIBS layer, that intersects the Carina bbox (120.60–121.10 E, 14.70–15.00 N), with its date, mode and access route | Variant A if a GCOV file can be downloaded with a free Earthdata account and read by `10_ingest_nisar.py` or rasterio; otherwise variant B | Say so plainly: "NISAR coverage for this AOI is not yet public; the pipeline is NISAR-ready (P3 ingest)." Relevance takes the hit, and that is disclosed rather than faked |
| **G2 Rainfall** | NASA POWER monthly PRECTOTCORR for July 1991–2024 at one coordinate | Ship S2 | Use Open-Meteo ERA5 for the same series, labelled as such |
| **G3 Population** | A WorldPop 2020 PHL 100 m tile clipped to the bbox is under about 50 MB and readable | Population exposure is included in S3 | Building count only |
| **G4 Buildings** | An OSM building snapshot for the bbox loads into script 08 | S3 as specified | Report flood area in km² only |

## 5. Schedule (Manila time)

| Time | Work | Exit condition |
|---|---|---|
| 23:00–01:00 | Run the backend tests and frontend build to get a baseline; run gates G1–G4 | Each gate has a recorded pass or fail |
| 01:00–04:00 | S2 rainfall adapter and card; S3 exposure run | Both return real, cached numbers |
| 04:00–08:00 | S4 NISAR panel (variant A or B) | It shows a dated NISAR source |
| 08:00–11:00 | S5 briefing and exports; hide out-of-scope panels | The full flow works end to end |
| 11:00–14:00 | Check the numbers by hand; S6 README | The README reproduces the demo |
| 14:00–17:00 | Bug fixes only; rehearse the recording | Freeze at 17:00 and tag the commit |
| 17:00–21:00 | Record S7; write the submission text with the AI-use disclosure | Recording is ready by 21:00 |

If the schedule slips, protect S1, S2, S4 and S5, then S3. Cut variant A down to variant B before cutting anything else.

## 6. Expected effect on the rubric (rough estimate, not a guarantee)

| Criterion | Original plan | This scope | Main reason |
|---|---|---|---|
| Impact | 7 | 7.5 | Named users and one concrete exposure number |
| Creativity | 6 | 7 | The same detection method applied to C-band history and NISAR L-band now |
| Validity | 7.5 | 8.5 | Built on outputs that exist, and fits the time available |
| Relevance | 5 | 7–8 | SAR is the evidence; 8 needs variant A |
| Presentation | 6.5 | 7.5 | One story with a hook |

## 7. Work split across agents

Each agent gets its own branch from `main`. Only the coordinator merges.
- **Agent A (backend):** gates G2–G4, the S2 adapter, the S3 exposure run and the briefing data.
- **Agent B (NISAR):** gate G1, then S4 in variant A or B.
- **Agent C (frontend):** S1 polish, hiding out-of-scope panels, S2/S4 cards, S5 export UI.
- **Coordinator (this session):** gate decisions, merge order, the number check and the README.
