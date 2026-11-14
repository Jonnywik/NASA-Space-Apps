# Tanaw: submission scope v5

Written at about 00:30 on 15 Nov (Manila). Coding freezes at 17:00 on 15 Nov. **Team:** one coordinator plus three AI agents; everyone is from Metro Manila. **Video:** 30 seconds. **A Filipino reviewer is available. There is no external expert.**

This overrides sections 3, 11 and 16 of `Tanaw-final-development-plan.md`. Its honesty rules apply in full: no silent sample data, no relabelling Sentinel-1 as NISAR, and no number without a source.

**Target:** close every gap a judge could name. No score is guaranteed.

## 0. What changed in v5

1. **The NISAR gates pass at the catalogue level** (section 5). NASA's catalogue (CMR) has a full 2026 wet-season NISAR time series over CAMANAVA and the Bulacan coast, for both GCOV (backscatter) and GUNW (interferograms), on four tracks. Reading the actual files is the next step; downloads need a free Earthdata login.
2. **The study area is now the team's home.** CAMANAVA (Caloocan, Malabon, Navotas, Valenzuela) plus the Bulacan coast to its north (Obando, Meycauayan, Marilao). This is one of the most flood-prone and fastest-sinking urban coasts in the Philippines. The existing 2022–2025 Pampanga outputs barely overlap it, so they become regional context.
3. **The main feature is pure NISAR.** "Flood rhythm" counts how many of the ~11 NISAR passes in the 2026 season saw each place flooded. This replaces the multi-year Sentinel-1 recurrence. It matches the challenge's own words ("patterns and rhythms of Earth's surface at different time steps") and removes the mixed-sensor problem.
4. **Ascending and descending tracks are both available.** If time allows, the two viewing geometries can separate vertical sinking from east–west motion, instead of assuming it.
5. **New features:** a guided Story Mode, "Find my barangay" search, "Our stories" pins, a rain-to-flood response chart and a timelapse export. The expert quote is dropped and replaced by a 3-person user test.

## 1. The story

> **We grew up wading through CAMANAVA's floods. Every 12 days this monsoon, NASA–ISRO's NISAR watched our streets flood, drain and flood again, and measured the ground sinking beneath them.**

## 2. Mapping the challenge to Tanaw

This table goes into the README and the project page.

| Challenge asks for | Tanaw |
|---|---|
| Interactive app using **NISAR** to track and visualize surface change | N1 Flood rhythm, N2 animation, N3 ground motion: all NISAR |
| Floodplains extending and retracting | N1 and N2: flood extent on every pass, June–November 2026 |
| Coastal subsidence and land deformation | N3: GUNW InSAR over the Manila Bay coast |
| Agricultural lands and crop changes | N4: L-band flooded vegetation in the Bulacan fields and fishponds |
| Change maps, time-series animations, dashboards | N2 animation, U1 swipe, U2 spot check, U3 story mode |
| Accessible to a broad audience | U3 story mode, U5 "How radar sees", U6 briefings in English and Filipino, U4 barangay search |
| Open-source and actionable | MIT licence, public demo, priority zones, briefing export, downloads |
| Study area such as a hometown or flooded neighbourhood | The team's own CAMANAVA, with P2 personal stories |
| Free NISAR data | ASF NISAR GCOV and GUNW (Provisional/V1), recorded in a manifest |
| Supplemental optical and GIS layers | WorldCover, WorldPop, OSM buildings, municipal boundaries, NASA POWER rainfall, Sentinel-1 history |
| Hypothesize physical drivers | N6: labelled hypotheses, each with a checked reference |
| Which polarizations show the change | N5: HH vs HV vs ratio, explained |
| Other frequencies from other sensors | C2: Sentinel-1 C-band context |
| Time series plus ancillary population and vegetation data | N1–N3 with WorldPop and WorldCover |
| Human drivers | N6 (groundwater pumping, reclamation, fishponds), C1 exposure |
| Personal context and stories | P2 and U7 "Our stories" pins |
| Interactive summary | U1 swipe, U3 story mode, the public web map |
| Future NISAR applications | P3 |

## 3. Features

### NISAR core (Agent B)

| # | Feature | Done when |
|---|---|---|
| **N1** | **Flood rhythm.** For each place, how many of the season's NISAR passes saw water (e.g. "flooded on 7 of 11 passes"). Built from one track (default **133 D, frame 081, 4005 DHDH**, 10–11 dates, 23 Jun–2 Nov), so the geometry stays consistent. | Each date has a water mask from one fixed rule (HH/HV thresholds calibrated on Manila Bay and known permanent ponds, with the NISAR_WATERMASK reference). Missing or invalid pixels are excluded from the denominator, with a unit test. Permanent water is masked out so the bay isn't counted as "flooded". |
| **N2** | **Season animation and chart.** Play, pause and step through each pass's flood extent. Below it, a chart of flooded km² by date, with NASA POWER daily rainfall on the same axis. | Keyboard operable, dates labelled, the exact acquisition time shown, and an optional GIF/MP4 export. |
| **N3** | **NISAR ground motion.** A chain of 12-day GUNW pairs on the same track gives cumulative LOS displacement from June to October, with a time series per point (`PixelChart`). Uses existing scripts 10–12. | The reference area, sign, ionospheric/tropospheric correction state, and number of epochs are shown. It is labelled "cumulative LOS displacement over 4 months". Any annualised figure is marked as an extrapolation and placed next to published long-term rates. |
| N3+ | *Stretch:* **true vertical motion.** Combine an ascending track (140 A) and a descending track (133 D) to separate vertical from east–west motion. | Both tracks cover the same dates and reference area. If not done, LOS is shown, with "vertical only if no horizontal motion" stated. |
| N4 | **Flooded vegetation and fishponds.** Mark HH double-bounce brightening in cropland and wetland (WorldCover) as a separate class. | Labelled "possible flooded vegetation (L-band)". It never adds silently to open water. |
| N5 | **Polarization view.** HH / HV / ratio RGB with a 3-line explanation. | The explanation is checked. |
| N6 | **"Why might this be happening?"** Hypotheses: groundwater over-extraction, reclamation and land loading, fishpond conversion, river and tide backflow, urban runoff. Each one links to its map evidence and a verified reference. | Each is labelled a hypothesis. There are no causal claims and no unverified citations. |

### Context and analysis (Agent A)

| # | Feature | Done when |
|---|---|---|
| C1 | **Priority zones.** Places flooded on half or more of the passes **and** where cumulative LOS motion shows sinking beyond the noise threshold. Gives people (WorldPop), buildings (OSM) and municipality or barangay (COD-AB) for those places. **This is the headline number.** | Labelled exposure, not damage. The thresholds are justified in the method notes and tested at ±1 dB and ±noise. |
| C2 | **Then and now.** The existing Sentinel-1 Carina 2024 flood extent where it overlaps the area, compared with NISAR 2026. | It is labelled as a different sensor, a different year and different sensitivity, with no numeric merge. |
| C3 | **Rain-to-flood response.** For each pass, flooded km² against rainfall in the prior 3 and 7 days (NASA POWER). | It is labelled "exploratory, n≈11" with no model fitted. It flags whether flooding persists after rain stops, which is consistent with drainage problems and subsidence (stated as a hypothesis). |
| C4 | **Validation.** Accuracy against an independent map: the 2026 NDRRMC/MMDA flood reports or barangay lists, Copernicus EMS or UNOSAT for any 2026 event, or the OPERA DSWx-S1 product (NASA, on a nearby date). Compare N3 with published CAMANAVA subsidence rates. | Scores and differences are shown in a validation card and in the README. |
| C5 | Spot-check and briefing facts endpoint; data manifest. | Every value carries its source, date and resolution. |

### Experience (Agent C)

| # | Feature | Done when |
|---|---|---|
| U1 | **Swipe and radar lens.** Before/after for any two passes, plus a magnifier that shows flood vs motion under the cursor. | It works with mouse, touch and keyboard. |
| U2 | **Spot check.** Click a place to get its flood count, flood dates, LOS series, exposure and rainfall, and to export a one-place briefing. | Missing values say why. |
| **U3** | **Story Mode.** A guided 6-step tour that drives the map: our streets → the season animation → flood rhythm → sinking → priority zones → "check your barangay". The judges' walkthrough and the video script are the same thing. | It opens on first visit, can be skipped, and is keyboard operable. |
| **U4** | **Find my barangay.** Search barangay or city names (from the COD-AB gazetteer) and fly to the spot check. | Works offline from a bundled list, with no external geocoder needed. |
| U5 | **"How radar sees"**: 4 cards (why water looks dark, why flooded rice looks bright, how InSAR measures millimetres, what L-band vs C-band means). | Opens from a "?" on each layer. |
| U6 | **Briefings in English and Filipino**, with CSV and HTML/PDF export. | Every number matches the screen, and the Filipino text is signed off. |
| **U7** | **"Our stories" pins.** Each team member's barangay, with 1–2 true sentences and their own photo (optional), linked to that spot's NISAR record. | The text is written by each person. Nothing is invented. |
| U8 | Shareable URL, sensor badges, a "Limits" drawer, a colour-blind-safe palette, and a 1366×768 check. | Each item is checked. |
| U9 | **Public static demo** with cached real outputs on free hosting. | Judges complete the flow in 3 clicks. There's no synthetic data and no login. |
| U10 | **Downloads**: flood rhythm, per-pass masks, LOS displacement and priority zones as GeoTIFF/GeoJSON, CC-BY licensed. | They link from the app and the README. |

### Packaging (Coordinator)

| # | Item | Done when |
|---|---|---|
| P1 | README with the challenge table, a one-command reproduction, the manifest, limitations up front, an MIT `LICENSE` (there is none now), and CI tests with a badge | A fresh clone reproduces the results and CI is green |
| P2 | Personal stories, the same as U7, used in the video and on the project page | True and specific |
| P3 | **Future of NISAR**: near-real-time flood alerts for LGUs, nationwide subsidence monitoring, and crop-loss warning. Flood Watch and evacuation planning are roadmap items 1 and 2. | Labelled as future work |
| P4 | **User test.** Three people from outside the team (family, neighbours, classmates) try the public demo cold. Record what confused them, fix the top two issues, and report it in the README. | Done honestly; no quotes are invented |
| P5 | The 30-second video plus a project page with a method diagram (NISAR → masks / InSAR → rhythm / motion → priority zones → briefing) | Tested on the P4 people |

## 4. Cut (roadmap)

City-wide and worldwide selectors, and the Civic Atlas restyle. Twelve-month scenarios, forecasts, drought screening, and loss in pesos. Section 16 of the original plan. Projection, route, vegetation and biomass panels (synthetic data only, hidden from the public build). Sentinel-1 reprocessing of past events over CAMANAVA. Flood Watch and evacuation planning.

## 5. Gates

Searched NASA CMR at about 00:20 on 15 Nov for the area 120.85–121.10 E, 14.55–14.95 N.

| Gate | Result | Next check |
|---|---|---|
| **G1 GCOV** | **Passes (catalogue).** `NISAR_L2_GCOV_PROVISIONAL_V1` plus `V1`: track 133 D/081 4005 DHDH has 10 Provisional dates (23 Jun–21 Oct) plus 1 V1 date (2 Nov). Tracks 032 D, 039 A and 140 A have about 9–11 each. Granules are about 3.6–5 GB each. | Read one granule over CAMANAVA with Earthdata auth. **Use windowed or remote HDF5 reads (h5py over fsspec, or a range-request download), not full files**: 11 full files would be about 40 GB. |
| **G7 GUNW** | **Passes (catalogue).** `NISAR_L2_GUNW_PROVISIONAL_V1`: about 9 consecutive 12-day pairs per track on 133 D, 140 A, 032 D and 039 A (Jun–Oct), each about 2.2 GB | Confirm the pairs chain without gaps on 133 D. Check unwrapped phase, connected components and correction layers, and that the existing `10_ingest_nisar.py` profile matches the product spec (NASA SDS L2 GUNW spec) |
| G2 Rainfall | NASA POWER API reachable (HTTP 200) | Daily PRECTOTCORR for Jun–Nov 2026 plus the 1991–2020 baseline |
| G3 Population | Not yet checked | WorldPop 2020 PHL 100 m |
| G4 Boundaries | Not yet checked | HDX COD-AB PHL, barangay level, for U4 |
| G5 Validation | Not yet checked | 2026 NDRRMC or MMDA flood reports; OPERA DSWx-S1; published CAMANAVA subsidence rates |
| G6 Buildings | Not yet checked | OSM via Overpass for the area |
| G8 Land cover | Not yet checked | ESA WorldCover tile |

**Access:** NISAR data downloads redirect to Earthdata Login. They run on the coordinator's laptop with the team's own free Earthdata account (`~/.netrc` or an EDL token in an environment variable). Credentials are never committed or included in exports. The search and the browse PNGs need no login.

## 6. The 30-second video

| Time | On screen | Caption / voice |
|---|---|---|
| 0–4 s | A team member's own flood photo from CAMANAVA, then the map | "Every year, our streets in CAMANAVA flood." |
| 4–11 s | N2: NISAR passes animate, the water spreads and drains, rainfall bars below | "This monsoon, NASA–ISRO's NISAR watched it every 12 days, through the clouds." |
| 11–16 s | N1 flood-rhythm map | "Some streets flooded on 7 of 11 passes." (Use the real number.) |
| 16–22 s | N3 motion over the same streets, then the priority-zone count | "And the ground beneath them is sinking. N people live where both happen." |
| 22–27 s | "Find my barangay", spot check, briefing switches EN → FIL | "Check your barangay, in English or Filipino." |
| 27–30 s | Logo and link | "Tanaw. Open, free, built on NISAR." |

Captions are burned in and the video is 1080p. Only verified values are used.

## 7. Schedule (Manila time)

| Time | Agent A | Agent B | Agent C | Coordinator |
|---|---|---|---|---|
| 00:30–02:00 | G2–G6, G8; rainfall cache | **Earthdata auth; windowed read of one GCOV and one GUNW over CAMANAVA; finalize track choice** | Baseline build; hide synthetic panels; Story Mode skeleton | Baseline tests; collect U7/P2 stories from the team |
| 02:00–06:00 | C5 facts endpoint; boundary gazetteer for U4 | N1 per-pass masks; N2 data; flood rhythm with its test | N2 player and chart; U4 search; sensor badges | Review the N1 threshold and denominator logic |
| 06:00–10:00 | C1 priority zones; C3 response chart | N3 via scripts 10–12 (133 D chain); N4 | U1 swipe and lens; U2 spot check; U7 pins | Hand-check numbers; draft N6 and P3 with verified references |
| 10:00–12:30 | C4 validation; C2; U6 templates (EN/FIL) | N5; method notes; N3+ if ahead | U3 Story Mode wired to real data; U5 cards; U6 UI | Filipino review; merge in order N1 → N2 → N3 → C1 → U2 → U3 → U6 |
| 12:30–14:30 | Manifest; U10 downloads | Assist where needed | U9 deploy; U8 checks | P1 README, licence and CI; **P4 user test (3 people)** |
| 14:30–17:00 | Fixes only | Fixes only | Fixes from P4 | Freeze and tag at 17:00 |
| 17:00–21:00 | — | — | — | P5 video and page; AI disclosure; private-window link test; submit |

**If time slips, cut in this order:** N3+ → U1 lens → N5 → C2 → U10 → GIF export → U8 shareable URL → C3 → C4 accuracy (keep the subsidence comparison) → U9. **Never cut:** N1, N2, N3 (LOS), C1, U2, U3, U4, U6, U7, P1, P5.

## 8. Score estimate (not a guarantee)

| Criterion | v4 | **v5** | Why |
|---|---|---|---|
| Impact | 10 | **10** | The team's own neighbourhoods, a barangay-level priority list, and a bilingual tool for the public |
| Creativity | 9.5–10 | **10** | Flood rhythm, story mode, and our streets seen by radar every 12 days |
| Validity | 9.5–10 | **9.5–10** | Single-sensor time series with no mixed-sensor issue, external validation, a user test; vertical motion if N3+ is done |
| Relevance | 10 | **10** | Every core feature is NISAR, and every line of the challenge is mapped |
| Presentation | 9.5–10 | **10** | Personal opening, story mode equals the video, tested on real people |
| **Total** | 48.5–50 | **49–50** if the file reads and N1/N3 ship | |

## 9. Biggest risks

1. **Reading the NISAR files.** The catalogue passes, but the HDF5 layout of the Provisional products versus the repo's ingest profile, and the download size, are still unverified. Do the windowed read before anything else.
2. **Workload.** This is the maximum for three agents. Hold the cut order.
3. **The InSAR physics.** L-band ionospheric effects, wet-season moisture and 4 months of data. Be explicit about the correction state, and don't over-claim the rate.
4. **The threshold.** Urban double-bounce can hide street flooding in dense areas. State this as a limitation; flooding in narrow streets may be under-detected.
5. **Invented content.** Stories, references and validation must be real. Leave them out rather than fake them.
