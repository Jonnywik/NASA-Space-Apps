# Tanaw: submission scope v3 (target 45+/50)

Written at 23:30 on 14 Nov (Manila). Coding freezes at 17:00 on 15 Nov. **Team:** one coordinator plus three AI agents. **Video:** 30 seconds. **A Filipino reviewer is available.**

This overrides sections 3, 11 and 16 of `Tanaw-final-development-plan.md` for the submission. The rest of that plan becomes the roadmap. Its honesty rules apply in full: no silent sample data, no relabelling Sentinel-1 as NISAR, and no number without a source.

**Target:** 9 or more on every criterion. That is a stretch, and judging is subjective. **Ceiling:** if gate G1 fails (no quantitative NISAR over the area), the realistic total is about 39. If G7 (the subsidence data) also fails, the sinking feature drops to a cited-context card.

## 1. The story

> **Manila Bay's north coast is flooding more often *and* sinking. Radar sees both. NASA's NISAR sees them under the rice.**

| Criterion | What earns a 9 |
|---|---|
| **Impact** | A **recurrence map** shows the places that flooded in all three SAR-observed disasters (2022, 2024, 2025). It adds the people and buildings there, **and whether the ground there is sinking**. Sinking means each flood is a little deeper next time. Municipal DRRM offices get a priority list they can act on. |
| **Creativity** | One radar workflow answers three questions: where it floods (C-band history), where it floods under crops (NISAR L-band), and where the land is sinking (InSAR). A **spot check** answers "what does radar say about *this* place?" in English or Filipino. |
| **Validity** | Flood maps are checked against an independent source. Every number is hand-checked and cited with its date and resolution. Displacement is reported as line-of-sight (LOS), not "sinking", unless converted with a stated assumption. Correlation is never presented as causation. |
| **Relevance** | NISAR is quantitative in two places: L-band water detection, and GUNW interferometric displacement through the existing P3 chain. NASA POWER rainfall supplies the trigger. |
| **Presentation** | A 30-second video with one hook, one visual sequence and one number, plus a public demo link judges can click and a one-page README. |

**Named users:** municipal DRRM officers and provincial planners in Pampanga and Bulacan. Researchers and students are secondary users.

## 2. Features

### Core (must ship)

| # | Feature | Builds on | Done when |
|---|---|---|---|
| S1 | **Recurrence map.** The 2022, 2024 and 2025 flood polygons are combined into a count of how many events flooded each place (1, 2 or 3). Places not observed in every event are marked. | Real outputs in `backend/data/output/*/flood.geojson` | Areas use an equal-area CRS. Unobserved places are never counted as "dry". A unit test covers this. |
| S2 | **Event drill-down.** A before/after SAR swipe for each event, with sensor, dates and threshold shown. | Existing flood routes and UI | The labels say Sentinel-1 C-band VV, and the threshold comes from `02_info.json`. |
| S3 | **Rainfall trigger.** Rainfall during each event window compared with the 1991–2020 baseline for the same window (NASA POWER PRECTOTCORR). | New small adapter and cached JSON | Conversion from mm/day is correct and matches a hand check. The grid-cell caveat is visible. |
| S4 | **Exposure in recurring zones.** Buildings (OSM, script 08) and people (WorldPop 2020) in places that flooded 2 or 3 times, grouped by municipality. | Script 08, gate G4 boundaries | Labelled "exposure", not "damage". Reproducible from recorded snapshots and their hashes. |
| S5 | **NISAR L-band flood panel.** A recent wet-season NISAR GCOV through an HH/HV water threshold. Shows the area flagged as water or flooded vegetation that a C-band map from a similar date does not. | `10_ingest_nisar.py` or rasterio | Both sensors' dates are shown, and the difference is worded "L-band additionally detects". The threshold and its rationale are recorded. |
| **S6** | **Sinking + flooding.** A displacement layer, shown as an LOS rate if there are 6 or more epochs, otherwise as single-pair displacement. It is overlaid on the recurrence map. Headline statistic: the share of the 3/3 flood area where the ground is moving away from the satellite by more than X mm/yr. A click shows that point's time series. | Existing P3 chain (scripts 10, 11, 12) and the `/ground-motion` API, `PixelChart.jsx` | The source, epochs, reference area and sign convention are shown. LOS is converted to vertical only with a stated no-horizontal-motion assumption. The wording is "sinking areas overlap recurring floods" and nothing causal. |
| S7 | **Spot check.** Click any place to get its recurrence count, flood dates, nearest exposure figures, its displacement rate if available, and the event rainfall. The result exports as a one-place briefing. | New small backend endpoint that combines S1, S3, S4 and S6 values | Each value comes with its source and resolution. Missing values say why they're missing. |
| S8 | **Briefing in English and Filipino.** A deterministic template for the area or for a spot-check point. Exports as CSV and HTML (print to PDF). | `BriefingCard` | Every number matches the screen. The Filipino template is signed off by the team's reviewer. |
| S9 | **Validation card.** An independent comparison, as set out in gate G5. | Small script | The method and source are shown, and disagreements are reported. |
| S10 | **Public demo.** A static build on free hosting that serves the cached real JSON. | The offline fallback in `frontend/utils/api.js` | A judge completes the flow in 3 clicks. No synthetic data appears in the public build. |
| S11 | **README, data manifest and method notes.** | Replaces the boilerplate README | Someone else can reproduce the results. Limitations come first. |

### Small functions (each takes an hour or less and adds polish)

- **Shareable link.** The URL encodes the event, layer and spot-check point, so judges can open the exact view in the submission.
- **Sensor legend.** A badge on every layer reads `C-band · Sentinel-1`, `L-band · NISAR`, `InSAR LOS` or `NASA POWER`. It doubles as relevance evidence.
- **Keyboard swipe and 1366×768 check.** This covers usability under Validity.
- **"Limits" drawer.** One click lists every caveat in plain language.

## 3. Cut for the submission (roadmap)

- City and barangay selectors, worldwide search, and the Civic Atlas restyle
- 12-month scenarios, forecasts, drought screening, and loss in pesos
- Section 16 of the original plan (Landsat from 2000, ERA5, ASF search)
- Projection and route panels, plus vegetation and biomass. These have synthetic-only data, so hide them from the public build.
- Flood Watch alerts, evacuation planning and rice exposure. These go first on the roadmap.

## 4. Gates (decide by 01:00)

| Gate | Check | Pass | Fail |
|---|---|---|---|
| **G1 NISAR GCOV** (critical) | Wet-season GCOV over 120.55–121.10 E, 14.70–15.25 N, downloadable with a free Earthdata login and readable | S5 as specified | Use GIBS imagery only, or a dry-season scene and drop the "under the rice" claim. Disclose which. |
| **G7 Displacement** (critical for S6) | In order of preference: (a) 6 or more NISAR GUNW epochs on one track/frame over the coast, giving an LOS rate via scripts 10–12; (b) one or more NISAR GUNW pairs, giving displacement only with no rate claim; (c) an openly licensed published subsidence-rate raster for the Manila Bay coast, cited; (d) ASF HyP3 Sentinel-1 InSAR jobs (free, but they take hours: only start them before 01:00) | S6 using the best available option, with the source labelled | S6 becomes a cited-context card: published subsidence rates for the named towns, with references and no map. Disclose this. |
| G2 Rainfall | NASA POWER daily data for 1991–2025 at the event centroids | S3 | Open-Meteo ERA5, labelled as such |
| G3 Population | WorldPop 2020 PHL 100 m clipped to the area | S4 people | Buildings only |
| G4 Boundaries | A licensed municipal boundary dataset (e.g. HDX COD-AB PHL) | Municipal grouping | Group by recurrence class only |
| G5 Validation | An independent flood map (Copernicus EMS, UNOSAT or Sentinel Asia) or an NDRRMC situation report for one of the events | S9 | Compare against JRC Global Surface Water and disclose the limitation |
| G6 Buildings | An OSM building snapshot loads into script 08 | S4 buildings | WorldPop only |

Record every result, with URL, retrieval time, version and hash, in `docs/DATA_MANIFEST.md`.

## 5. Agent assignments and schedule (Manila time)

| Time | Agent A: data/backend | Agent B: NISAR + InSAR | Agent C: frontend | Coordinator (you + this session) |
|---|---|---|---|---|
| 23:30–01:00 | Gates G2–G6 | Gates G1 and G7; submit HyP3 jobs immediately if G7(d) is the fallback | Baseline build; hide synthetic panels; sensor badges | Baseline tests; gate decisions at 01:00 |
| 01:00–05:00 | S1 recurrence and its test; S3 | S5 ingest and threshold | Recurrence layer, event switcher, shareable URL | Review the S1 coverage logic |
| 05:00–09:00 | S4 exposure; S7 spot-check endpoint | S6 through scripts 10–12, or the context card | S3/S5/S6 panels and the spot-check UI | Hand-check the numbers |
| 09:00–12:00 | S8 facts and templates (EN/FIL); S9 | S6 statistic; method notes | S8 UI and exports; validation card | Filipino review; merge S1 → S3 → S4 → S5 → S6 → S7 → S8 → S9 |
| 12:00–14:00 | Data manifest | Assist where needed | S10 static deploy; keyboard and layout check | S11 README; run the full flow end to end |
| 14:00–17:00 | Bug fixes only | Bug fixes only | Bug fixes only | Rehearse the video; freeze and tag at 17:00 |
| 17:00–21:00 | — | — | — | Record; write the submission text and AI disclosure; test the public link in a private window |

**If time slips, cut in this order:** S9 → shareable link → S10 → the S6 time-series chart (keep the map and statistic) → municipal grouping → population. Protect S1, S2, S5, S6 (map and statistic), S7 and S8 to the end.

## 6. The 30-second video

| Time | On screen | Caption / voice |
|---|---|---|
| 0–4 s | The recurrence map fades in, with the 3/3 zones in deep blue | "Flooded three monsoons running." |
| 4–10 s | Swipe a 2024 radar before/after | "Radar sees through the storm clouds." |
| 10–16 s | NISAR L-band panel: extra water appears under the rice | "NASA's NISAR sees flooding under the crops." |
| 16–22 s | Displacement layer over the 3/3 zones, with the statistic | "And much of it is sinking: X% of the worst zone." |
| 22–27 s | Spot-check click, then the briefing toggles EN → FIL | "Any town, one click, in English or Filipino." |
| 27–30 s | Logo and link | "Tanaw. Free, open, built on NASA data." |

Use only verified values. Captions are burned in, and the video is 1080p. The project page and README carry the methods and limitations the video can't.

## 7. Score expectations (estimates, not guarantees)

| Criterion | Original | v2 | **v3, G1 + G7 pass** | v3, G1 passes, G7 fails | v3, both fail |
|---|---|---|---|---|---|
| Impact | 7 | 9 | **9.5** | 9 | 8.5 |
| Creativity | 6 | 9 | **9.5** | 9 | 7 |
| Validity | 7.5 | 9 | **9** | 9 | 8.5 |
| Relevance | 5 | 9 | **9.5** | 9 | 6.5 |
| Presentation | 6.5 | 9 | **9** | 9 | 8.5 |
| **Total** | 32 | 45 | **46.5** | 45 | 39 |

## 8. Biggest risks

1. **Scope.** Three agents covering 11 items in 18 hours is aggressive. S6 and S5 share Agent B and the same NISAR data access, which concentrates both the risk and the speed-up. Respect the cut order.
2. **NISAR coverage (G1 and G7).** Check it first. If both fail, re-centre the pitch on recurrence plus exposure.
3. **Wording of the sinking claim.** LOS is not vertical motion, a single pair is not a rate, and overlap is not causation. Any of these in the 30-second captions would cost Validity.
4. **The recurrence coverage bug.** An unobserved place counted as "dry" would undermine the headline number. S1's test must catch it.
5. **The 30-second video.** It only works if the numbers are final by 14:00. Plan the shots before the freeze.
