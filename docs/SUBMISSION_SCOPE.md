# Tanaw: submission scope v4 (target 48–50)

Written at about 00:00 on 15 Nov (Manila). Coding freezes at 17:00 on 15 Nov. **Team:** one coordinator plus three AI agents. **Video:** 30 seconds. **A Filipino reviewer is available.**

This overrides sections 3, 11 and 16 of `Tanaw-final-development-plan.md`. Its honesty rules apply in full: no silent sample data, no relabelling Sentinel-1 as NISAR, and no number without a source.

**No score is guaranteed.** v4 aims to leave no criterion with a gap a judge could name. If gate G1 fails (no usable NISAR over the area), the realistic total is about 39, whatever else ships.

## 0. What changed from v3, and why

The challenge statement asks for an app that **"uses radar remote sensing data from NISAR to track and visualize one or more types of surface change"**. In v3 the main feature (recurrence) ran on Sentinel-1, which left NISAR as a side panel. v4 inverts this:

- **NISAR is the core.** The headline is a **wet-season NISAR flood time series**, animated across 12-day acquisitions, plus **NISAR InSAR ground motion**.
- **Sentinel-1 is supporting context.** The 2022–2025 C-band history appears as "other sensors / different frequencies", which the challenge explicitly encourages.
- New items cover every challenge "consideration": polarization analysis, human drivers, physical-driver hypotheses, a personal/hometown story, future applications of NISAR, and an accessible explainer for a broad audience.

## 1. The story

> **Every monsoon, Manila Bay's north coast floods and sinks. NASA–ISRO's NISAR watches it happen, every 12 days, through the clouds and under the rice.**

## 2. Mapping the challenge to Tanaw

This table goes into the README and the project page as-is.

| Challenge asks for | Tanaw feature |
|---|---|
| Interactive app using **NISAR** data to track and visualize surface change | **N1** NISAR flood time series and **N3** NISAR ground motion |
| Wetlands/floodplains extending and retracting | **N1**: animated flood extent through the 2026 wet season |
| Coastal subsidence / land deformation | **N3**: InSAR LOS motion over the Bulacan–Pampanga coast |
| Agricultural lands, crop changes | **N2**: L-band flooded-vegetation detection in rice areas, with WorldCover land-cover context |
| Change-detection maps, time-series animations, dashboards | **N1** animation, **C1** recurrence map, **U1** before/after swipe, **U2** spot check |
| Accessible to a broad audience (scientists, managers, educators, decision-makers, public) | **U3** "How radar sees" explainer; **U4** briefings in English and Filipino |
| Open-source, user-friendly, actionable insights | Open licence, public static demo, priority zones, briefing export |
| Pick a study area (hometown, flooded neighbourhood) | Pampanga–Bulacan floodplain, with the team's personal story (**P2**) |
| Download freely available NISAR data | ASF/Earthdata NISAR GCOV and GUNW; manifest with hashes |
| Supplemental optical / GIS layers | ESA WorldCover, WorldPop, OSM buildings, municipal boundaries, NASA POWER rainfall |
| Hypothesize physical drivers | **N5**: labelled hypotheses (groundwater extraction, fishpond conversion, rice cycle, urban growth), each with a reference |
| Which polarizations highlight changes | **N4**: HH vs HV vs ratio, explained on screen |
| Different frequencies from other sensors | **C2**: Sentinel-1 C-band compared with NISAR L-band |
| Time series from different dates, plus ancillary data (population, vegetation) | N1, N3, C1, plus WorldPop and WorldCover |
| Human drivers on natural resources | N5, and C3 exposure |
| Personal context and stories | P2 |
| Interactive summary (sliders, web maps) | U1 swipe and the public web map |
| Future applications of NISAR | P3, a section on the project page |

## 3. Features

### NISAR core (Agent B)

| # | Feature | Done when |
|---|---|---|
| **N1** | **NISAR wet-season flood time series.** Use every available 2026 wet-season GCOV over the area on one track/frame. Apply a water threshold to each date (calibrated on known permanent water, the same rule for all dates). The result is an animated flood extent, with a chart of flooded km² against date and NASA POWER rainfall on the same time axis. | There are at least 3 dates; 5 or more is ideal. The rule, threshold and dates are recorded. The animation can be played, paused and stepped from the keyboard. |
| **N2** | **Flooded vegetation (L-band).** Flag the HH double-bounce brightening in cropland (WorldCover) as possible flooded vegetation. | It is a separate, labelled class: "possible flooded vegetation (L-band HH brightening)". It never adds silently to open-water area. |
| **N3** | **NISAR ground motion.** In order of preference: 6 or more GUNW epochs give an LOS rate (scripts 10–12); fewer pairs give a displacement map only. Click a point to see its series (`PixelChart`). | The source, epochs, reference area and sign convention are shown. Vertical motion appears only with a stated assumption. If NISAR GUNW is unavailable: (a) an openly licensed published subsidence raster, cited, or (b) ASF HyP3 Sentinel-1 jobs started before 01:00, with Sentinel-1 clearly labelled. |
| **N4** | **Polarization view.** An HH / HV / HH÷HV RGB composite toggle for one date, with a 3-line explanation of what each one highlights. | The text has been reviewed for correctness. |
| **N5** | **"Why might this be happening?"** 3–4 hypotheses (groundwater extraction, fishpond and aquaculture conversion, the rice planting cycle, urban expansion), each linked to the map evidence that is consistent with it and to a published reference. | Every item is labelled a hypothesis. There is no causal claim, and each reference is real and checked. |

### Context, using other sensors and data (Agent A)

| # | Feature | Done when |
|---|---|---|
| C1 | **Recurrence map.** Sentinel-1 2022, 2024 and 2025, plus NISAR 2026 peak extent, giving the count of events that flooded each place. | Places not observed in every event are excluded and marked, with a unit test. Mixed sensors are disclosed, with the statement that C-band under-detects flooded vegetation. |
| C2 | **C-band vs L-band.** The same detection logic on Sentinel-1 and on NISAR, for the closest dates available. Shows where they agree and where they differ. | It gives the date gap, and the wording is "L-band additionally detects", not "more accurate". |
| C3 | **Priority zones.** Places that flooded in 3 or more events **and** have LOS motion away from the satellite above X mm/yr, with the people (WorldPop) and buildings (OSM) inside them, grouped by municipality. | This is the single headline number. It is labelled exposure, not damage, and the threshold X is justified. |
| C4 | **Validation.** Overlap and F1 scores against an independent flood map (Copernicus EMS, UNOSAT or Sentinel Asia) or against NDRRMC reports. A ±1 dB threshold sensitivity test on the recurrence map. | The scores and sensitivity are shown in a validation card and in the README. |

### Usability (Agent C)

| # | Feature | Done when |
|---|---|---|
| U1 | **Before/after swipe and radar lens.** A magnifier that follows the cursor and shows NISAR vs Sentinel-1, or flood vs motion, underneath. | It works with mouse, touch and keyboard. |
| U2 | **Spot check.** Click a place to see its NISAR flood dates, recurrence count, LOS rate, exposure and rainfall, then export a one-place briefing. | Every value shows its source and resolution, and missing values say why. |
| U3 | **"How radar sees"** explainer: 4 short cards (why water looks dark, why flooded rice looks bright, how InSAR measures millimetres, what L-band vs C-band means). | It is aimed at students and the public and opens from a "?" on each layer. |
| U4 | **Briefing in English and Filipino.** Deterministic, built from facts, with CSV and HTML/PDF export. | Every number matches the screen. The Filipino text is signed off by the team's reviewer. |
| U5 | Shareable view URL; a sensor badge on each layer; a "Limits" drawer; 1366×768 and keyboard checks. | Each item is checked. |
| U6 | **Public static demo** on free hosting, serving cached real outputs. | A judge completes the flow in 3 clicks. No synthetic data appears in it. |
| U7 | **Downloads.** Recurrence, priority-zone and NISAR flood layers as GeoJSON, CC-BY licensed. | They link from the app and the README. |

### Presentation and packaging (Coordinator)

| # | Item | Done when |
|---|---|---|
| P1 | README with the challenge mapping table (section 2), a one-command reproduction, the data manifest, limitations, a `LICENSE` file (MIT for code), and CI tests with a status badge. | A fresh clone reproduces the results and CI passes. |
| P2 | **A personal story.** One or two sentences from a team member about flooding in their hometown or family, in the video, the README and the project page. | Written by the team member; true and specific. |
| P3 | **Future of NISAR** section: near-real-time flood alerts for LGUs, nationwide subsidence monitoring, and crop-loss early warning. | It is labelled as future work. |
| P4 | **User validation.** One quote from an MDRRMO or LGU officer, a PAGASA or DOST scientist, or a professor who used the demo. | Used with their permission and attributed as they choose. Leave it out if there isn't one, and never invent one. |
| P5 | **The 30-second video** (section 6) plus a project page with one method diagram. | Tested on 3 people unfamiliar with the project. |

## 4. Cut for the submission (roadmap)

City and barangay selectors, worldwide search, and the Civic Atlas restyle. Twelve-month scenarios, forecasts, drought screening, and loss in pesos. Section 16 of the original plan. Projection and route panels, and vegetation and biomass (these have synthetic data only, so hide them from the public build). Flood Watch alerts and evacuation planning become roadmap items 1 and 2, and P3 mentions them.

## 5. Gates (decide by 01:00)

| Gate | Check | Fail path |
|---|---|---|
| **G1 NISAR GCOV** (critical) | 3 or more wet-season (Jun–Oct 2026) GCOV acquisitions over 120.55–121.10 E, 14.70–15.25 N on one track, downloadable with free Earthdata and readable | 1–2 dates: N1 becomes a before/after pair. Dry season only: drop N2. None: GIBS imagery only. Disclose which, and accept a ceiling near 39. |
| **G7 NISAR GUNW** (critical for N3) | 6 or more epochs on one track/frame over the coast; failing that, 1 or more pairs | A published raster, or HyP3 Sentinel-1 jobs submitted before 01:00. Label which. |
| G2 Rainfall | NASA POWER daily data for 1991–2026 | Open-Meteo ERA5, labelled as such |
| G3 Population | WorldPop 2020 PHL 100 m | Buildings only |
| G4 Boundaries | HDX COD-AB PHL municipal layer | Group by recurrence class only |
| G5 Validation | An independent flood map or NDRRMC report for one event | JRC Global Surface Water comparison; disclose |
| G6 Buildings | OSM snapshot loads into script 08 | WorldPop only |
| G8 Land cover | ESA WorldCover 10 m tile for the area | Drop the crop masking from N2 and disclose |

Record every result in `docs/DATA_MANIFEST.md` with its URL, retrieval time, version and hash.

## 6. The 30-second video

| Time | On screen | Caption / voice |
|---|---|---|
| 0–4 s | Team member's hometown, a street photo (theirs), then the map | "My town floods every monsoon." (P2) |
| 4–11 s | N1 animation: NISAR flood extent pulsing across 12-day dates, rainfall bars below | "NASA–ISRO's NISAR radar watched it, every 12 days, through the clouds." |
| 11–16 s | Radar lens over rice fields: flooded vegetation lights up | "L-band even sees water under the rice." |
| 16–22 s | N3 motion layer over the priority zones, with the headline number | "And the land is sinking: N people live where it floods *and* sinks." |
| 22–27 s | Spot-check click, then the briefing switches EN → FIL | "Any town, one click, in English or Filipino." |
| 27–30 s | Logo and link | "Tanaw. Open, free, built on NISAR." |

Use only verified values. Captions are burned in and the video is 1080p. The project page carries the methods, validation and limitations.

## 7. Schedule (Manila time)

| Time | Agent A | Agent B | Agent C | Coordinator |
|---|---|---|---|---|
| 00:00–01:00 | G2–G6, G8 | **G1 and G7; submit HyP3 jobs if needed** | Baseline build; hide synthetic panels | Baseline tests; gate decisions at 01:00 |
| 01:00–05:00 | C1 and its test; rainfall series | N1 download, ingest, threshold, per-date masks | N1 animation player and chart; sensor badges | Review C1 and N1 logic |
| 05:00–09:00 | C3 priority zones; C4 validation | N3 via scripts 10–12; N2 | U1 lens; U2 spot check; N4 toggle | Hand-check numbers; draft N5 and P3 with references |
| 09:00–12:00 | C2; U4 facts and templates | N4; method notes | U3 explainer; U4 UI and exports; U5 | Filipino review; merge in order C1 → N1 → N3 → C3 → U2 → U4 |
| 12:00–14:00 | Data manifest; U7 | Assist where needed | U6 deploy | P1 README, licence and CI; full end-to-end run |
| 14:00–17:00 | Bug fixes only | Bug fixes only | Bug fixes only | Freeze and tag at 17:00 |
| 17:00–21:00 | — | — | — | P4 follow-up, P5 recording and page, AI disclosure, private-window link test |

**If time slips, cut in this order:** U1 lens → N4 → C2 → U7 → U5 shareable URL → C4 sensitivity (keep the F1 score) → U6. **Never cut:** N1, N3 (in whatever form passes its gate), C3 headline, U2, U4, P1, P2, P5.

## 8. Score estimate (not a guarantee)

| Criterion | v3 | **v4, G1 + G7 pass** | Remaining risk |
|---|---|---|---|
| Impact | 9.5 | **10** | Needs P4 or a strong P2 |
| Creativity | 9.5 | **9.5–10** | The judges' taste |
| Validity | 9 | **9.5–10** | C4 scores need to be respectable |
| Relevance | 9.5 | **10** | Depends on G1 |
| Presentation | 9 | **9.5–10** | Execution of the 30-second video |
| **Total** | 46.5 | **48.5–50** | |

## 9. Biggest risks

1. **NISAR data (G1, G7).** Everything rides on it. Check it first.
2. **Workload.** This is the maximum for three agents. Hold the cut order.
3. **Cross-sensor recurrence.** C-band and L-band detect differently, so mixing them in C1 must be disclosed and tested.
4. **Wording of the claims.** LOS is not vertical motion, overlap is not causation, hypotheses are not findings, and "L-band additionally detects" is not "more accurate".
5. **Invented content.** P2 and P4 must be real. Leave them out rather than fake them.
