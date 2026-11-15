# Codex task list: parallel work for 15 Nov 2026

Codex: read `AGENTS.md` first (context, rules, how to run). This file gives you **specific tasks that run in parallel with work already in progress**, and the boundaries that keep you from colliding with it.

Written 15 Nov 2026, about 01:30 Manila time. Coding freezes at 17:00.

## Round 3 (15 Nov, about 14:45): freeze moved to 18:00. Push everything by 17:15.

Round 2 is reviewed and good (thank you). **Push to a branch `codex/round3`, not to `main`**; the coordinator merges. Boundaries: backend and docs only. The coordinator is editing `backend/app/nisar_api.py` and `backend/processing/nisar_flood/` this round, so **don't edit those**; put your routes in a new `backend/app/downloads_api.py`. Register it in `main.py` with one import and one `include_router` line. The full backend suite must pass before each push. See "Round 4 additions" at the end of `docs/API_CONTRACT.md` for the shapes.

**Don't regenerate the real NISAR product** on the laptop: the validation results are bound to its manifest hash (see the v6 section).

### R3.1 Briefings tell the real story (about 45 min)
- Update `backend/processing/briefing_place/` (EN and FIL templates) to the v6 framing. The NISAR layer is "open water outside the usual water", never "flooding".
- Add one IMERG sentence for the latest pass, from `data/cache/climate/imerg_passes.json`: rain in the last 24 h and 48 h and hours since heavy rain.
- Add one sentence on what NISAR can't see (flooded streets look bright; passes at about 05:30 Manila).
- Ground motion: "not available yet".
- Every number must trace to a fact field. Update the tests in `tests/test_spot_briefing.py`. Mark FIL as pending review.

### R3.2 Downloads (about 45 min)
`GET /downloads` and `GET /downloads/{id}` in `downloads_api.py`. List and serve, read-only, with a whitelist:
- the flood-rhythm count and half-mask GeoTIFFs (from the real product folder, if present; otherwise omit the entry, never fake it);
- the per-pass open-water CSV (date, km², valid fraction, maturity, product ID);
- the IMERG pass CSV;
- the soil-moisture pass CSV;
- the validation JSON;
- the timelapse GIF (R3.3).

Each entry has a CC-BY-4.0 licence line and attribution (NASA–ISRO NISAR via ASF, NASA GPM IMERG, NASA OPERA, and so on), plus `dataKind`. Add tests.

### R3.3 Season timelapse GIF (about 45 min)
`scripts/28_nisar_timelapse.py` builds `data/cache/nisar/timelapse.gif` from the **real** product's `hh_<date>.png` and `pass_<date>.png`. Each frame shows the HH backscatter in greyscale with the open-water overlay, a caption ("NISAR L-band · 10 Aug 2026 · 05:30 Manila"), a bar for the 48-hour IMERG rain before the pass, and an attribution line. About 1.2 s per frame, 11 frames, at most about 8 MB. If the real product is missing, exit with a clear message; never use the synthetic demo. Serve it at `GET /api/v1/nisar/timelapse.gif` from `downloads_api.py`.

### R3.4 CI is green on GitHub (about 15 min)
Check the GitHub Actions runs for `main` in Jonnywik/NASA-SA-Final (`.github/workflows/ci.yml`). Fix the workflow if it fails, for example on the Python version, missing system packages or `npm run test:api`. Don't skip tests.

## Round 2 (15 Nov, about 13:15) (DONE, reviewed)

**State:** T1 was run by the coordinator on real data and is published. T2 was attempted and stopped: ionosphere noise, undocumented phase sign, 4-month record. NISAR soil moisture and NASA GPM IMERG rain were added. Antigravity's A6 redesign is merged. Read the "v6 decision" section of `docs/SUBMISSION_SCOPE.md` and the runbook sections "Real run results", "Ground motion (T2)" and "Soil moisture" first. Work on `main` in `Jonnywik/NASA-SA-Final`, backend and docs only (Antigravity owns `frontend/`). Pull before you start, and run the full backend suite before each push.

The real NISAR product is not in git (376 MB). Regenerate it with the two commands in the v6 section (needs `EARTHDATA_TOKEN`).

### R2.1 Fix the GUNW wavelength (15 min)
`backend/processing/nisar_flood/gunw_chain.py` hard-codes 1.2575 GHz → 0.2384 m. The real GUNW file's `science/LSAR/GUNW/grids/frequencyA/centerFrequency` is **1.239 GHz → 0.2420 m**. Read the centre frequency from the file in `inspect_local_file`/`build_ingest_config` and use it. Fall back to the constant only if absent, with a warning. Add a test.

### R2.2 T5 validation with OPERA DSWx-S1 (about 90 min)
The catalogue (CMR `C2949811996-POCLOUD`) has 40 DSWx-S1 granules on tile T51PTS matching 10 of the 11 NISAR passes within ±2 days (see `docs/SOURCE_REVIEW.md`).
- **Access:** downloads are at PO.DAAC (`archive.podaac.earthdata.nasa.gov`) behind Earthdata Login. If you work in a cloud session, ask the owner to add the token for that host and allow its redirect host. On a laptop, `EARTHDATA_TOKEN` works if the PO.DAAC app is approved in the owner's Earthdata profile.
- Normalise DSWx classes to open water / not water / nodata using the product spec, crop to the study bbox and reproject to the coarser grid. Compare with the **total open water** per pass (NISAR water including permanent water, not the flood-only mask) using `processing/validation/metrics.compare_rasters`.
- Report agreement, F1, IoU and confusion per pass, plus a **±1 dB threshold sensitivity** for NISAR. Write `docs/VALIDATION.md` honestly, including disagreements, and serve the result at `/api/v1/validation`.

### R2.3 T7 README truth pass (about 60 min; must be done before 16:30)
- Rewrite the README's top story to the v6 framing.
- Put **Limitations first**: no visible street flooding, 05:30 passes, ground motion not available, provisional products.
- Set each row of the challenge table to **real / real-but-limited / unavailable / cut**.
- Fill `docs/DATA_MANIFEST.md` with the exact NISAR GCOV, GUNW and SME2 granules used (from the manifests in `backend/data/cache/nisar/`), plus IMERG, POWER, WorldPop, WorldCover, COD-AB, OSM, Open-Meteo and OPERA. Include product IDs, versions and retrieval dates.
- Add a "Reproduce" section with the exact command sequence (scripts 19, 23, 20, 25, 31, then the API and frontend).

### R2.4 After the freeze (not today)
The T2 research path: get the GUNW phase sign from the RIFG/RUNW spec or ISCE3, confirm the ionosphere-screen sign, apply tropospheric correction, and wait for a longer record.

## 0. Who is working on what right now

| Worker | Owns | Status |
|---|---|---|
| Frontend agent (Claude) | — | Finished: the CAMANAVA workspace runs on the real API. |
| **Antigravity** | **everything under `frontend/`**, `docs/FIL_REVIEW.md`, `docs/ANTIGRAVITY_STATUS.md` | Small UI tasks in `docs/ANTIGRAVITY_TASKS.md`. **Do not edit `frontend/`.** |
| Coordinator (Claude) | `backend/app/main.py`, `docs/SUBMISSION_SCOPE.md`, `docs/API_CONTRACT.md` sections 0–2 (shared constants and rules), `AGENTS.md` | Integration and review |
| **Codex (you)** | **The files listed in each task below, and nothing else** | Tasks T1–T7 |

Already done and on this branch, so build on them rather than rewriting them:
- **NISAR pipeline:** `backend/processing/nisar_flood/`, scripts 19–22, `backend/app/nisar_api.py`, and `docs/NISAR_RUNBOOK.md`. It is tested, but has only run on synthetic data.
- **Climate:** `backend/processing/climate/` and `backend/app/climate_api.py`, using real NASA POWER and Open-Meteo data.
- **Places:** `backend/processing/places/` and `backend/app/places_api.py`, using real boundaries, buildings, WorldPop and WorldCover.
- **Test suite:** all routers are registered in `main.py`, and the suite is at **311 tests, OK**.

**Default NISAR stack: track 140 ascending, frame 9, mode 4005 DHDH.** It has 11 GCOV dates (23 Jun–2 Nov 2026) and 9 GUNW pairs. Track 133 D covers only about 35% of the area, so do not use it.

## 1. Rules for parallel work

1. **Stay inside your files.** If a task needs a change outside its file list, for example a new route in `main.py` or a contract change, write the change as a short note in your commit message under `NEEDS-COORDINATOR:` and leave it out. The one exception is registering your own new router in `backend/app/main.py`: add one import line and one `include_router` line at the bottom, and nothing else.
2. **Commit small and often** to branch `claude/kind-pascal-93n7ns` with clear messages. Pull (`git pull --rebase`) before every push. Never force-push, rewrite history, or delete other people's files.
3. **Follow every rule in `AGENTS.md` section 2.** Above all: never fabricate data, references or stories; synthetic data is always labelled; missing values are not zero.
4. **Run the full backend test suite before each push:** `cd backend && ../.venv/bin/python -m unittest discover -s tests`. It must stay green.
5. **Each task ends with a "done when".** If you cannot meet it honestly, stop, write down what blocked you in `docs/CODEX_STATUS.md`, and move to the next task.
6. **Record progress in `docs/CODEX_STATUS.md`** (you own this file): one line per task with its status, the commit hash, and any blocker.

## 2. Tasks, in priority order

### T1: Real NISAR flood rhythm (highest priority; needs the laptop and an Earthdata login)

**Why:** this is the core of the submission. Everything in the app is synthetic until this runs.

**Files you own:** `backend/processing/nisar_flood/` (fixes only), `backend/scripts/19`–`22`, `backend/tests/test_nisar_*.py`, `backend/data/cache/nisar/`, `docs/NISAR_RUNBOOK.md`, and the NISAR rows of `docs/DATA_MANIFEST.md`.

**Steps:**
1. Create a free account at https://urs.earthdata.nasa.gov, then go to **Profile → Generate Token**. In your shell, set `EARTHDATA_TOKEN=<token>`. Never write it to a file in the repo, never echo it, and never paste it into a commit.
2. Follow `docs/NISAR_RUNBOOK.md` exactly, using the 140 A manifest. From `backend/`:

```bash
python scripts/19_nisar_search.py --track 140 --direction A --frame 9
```

```bash
python scripts/20_nisar_flood_rhythm.py --manifest data/cache/nisar/nisar_manifest_t140_A_f009_m4005.json --max-dates 2 --calibrate --min-valid-passes 1 --out-dir /tmp/nisar_trial
```

3. **Check the first real file before going further** (runbook section 3):
   - It reads with no `LayoutError`. If you get one, find the real HDF5 paths with `h5py` (`f.visit(print)`) and pass `--layout-base/--layout-hh/--layout-hv`. If the default paths are wrong, fix them in `gcov.py` and add a test.
   - The printed valid fraction of the study area is close to 100%.
   - Manila Bay HH in `water_rule.json` is roughly −20 to −30 dB. A value near 0 means a scaling or unit bug.
   - `hh_<date>.png` lines up with the Navotas and Malabon shoreline on a basemap. Check this by eye and write what you saw in the runbook.
4. Run all 11 dates with `--calibrate --layout-verified "checked by Codex on <date>: <what you checked>"`. If range reads fail, add `--allow-download`. Each file is about 5.4 GB, so check disk space first.
5. **Sanity-check the result and write it down** in a new section of `docs/NISAR_RUNBOOK.md` called "Real run results":
   - Does permanent water match the bay, rivers and fishponds?
   - Is the per-pass flooded km² plausible against the rainfall? Use `GET /api/v1/climate/pass-rainfall`.
   - Name any obvious artefacts: layover, radar shadow, urban double-bounce, wind-roughened water.
6. Fill the NISAR rows of `docs/DATA_MANIFEST.md` with the exact granule IDs used, their MD5/SHA-256 and the retrieval time.

**Done when:** `GET /api/v1/nisar/passes?area=camanava_2026` returns `dataKind` other than `"synthetic"`, with real product IDs, and the runbook has the "Real run results" section.

**If blocked** (no access, unreadable layout, or the disk can't hold it): leave the synthetic product in place, record exactly what failed in `docs/CODEX_STATUS.md`, and move on to T2.

### T2: Real NISAR ground motion (laptop; after T1, or in parallel if bandwidth allows)

**Files you own:** the same as T1, plus `backend/data/raw/nisar/gunw_chain/` (gitignored).

**Steps:**
1. Run `python scripts/21_nisar_gunw_chain.py --manifest data/cache/nisar/nisar_manifest_t140_A_f009_m4005.json --download`.
2. Open one GUNW file and confirm the unwrapped-phase, coherence and connected-component dataset paths, the wavelength (about 0.2384 m for L-band) and which corrections are already applied.
3. Choose the **phase sign** from the product specification, not by guessing; cite the spec section in the runbook. Choose a **stable reference area**: a small box on ground believed stable, such as older bedrock-founded areas east of the study area if the frame covers them. If it doesn't, use the most coherent, stable-looking area in the frame, and state the choice and why.
4. Run `--fill-hashes --phase-sign <±1> --reference-bbox W S E N`, then the generated `run_gunw_chain.sh` (scripts 10 → 11 → 12).
5. Report **cumulative line-of-sight displacement from June to October 2026**. Do not present it as an annual rate. If you show an annualised figure, label it "extrapolated from 4 months".

**Done when:** `GET /api/v1/ground-motion?event=camanava_2026` returns a real product, and the runbook records the reference area, sign, corrections and epochs. The product stays `needs-review`, because the team promotes it with script 17 after looking at it.

### T3: Priority zones (backend; no laptop needed; start immediately)

**Why:** this gives the headline number: people living where it floods often **and** the ground is moving.

**Files you own:** `backend/processing/priority/` (new), `backend/scripts/50_priority_zones.py` (new), `backend/tests/test_priority_*.py` (new).

**Specification:**
- **Inputs:**
  - `backend/data/output/camanava_2026/nisar/rhythm_half.tif`: 1 means flooded on half or more of the valid passes, 0 means not, 255 means nodata. Read `manifest.json` in the same folder for `dataKind` and `passCount`.
  - The ground-motion product: cumulative line-of-sight displacement in mm, read through `processing/p3` (see `backend/app/p3_api.py` for how the API finds the current run for `camanava_2026`).
- **Output mask:** `backend/data/output/camanava_2026/nisar/priority_mask.tif`. 1 where the rhythm is ≥ half **and** the cumulative LOS motion is away from the satellite by more than `T` mm; 0 elsewhere; 255 where either input is nodata. Use the motion grid's resolution or coarser (never finer), and resample the categorical mask with nearest neighbour.
- **Threshold `T`:** derive it from the noise. Default to 2× the standard deviation of displacement inside the reference area, or an explicit `--threshold-mm`. Record the method and value in a `priority_manifest.json` next to the mask, with `dataKind` propagated (synthetic if either input is synthetic).
- **Sensitivity:** also compute the totals at T×0.5 and T×2 and store them in the manifest. Judges will ask whether the threshold is arbitrary.
- **Exposure:** call `processing.places.exposure.exposure_for_mask(mask_path, level="barangay")` and store the per-barangay results in the manifest. The existing `GET /api/v1/places/exposure?mask=priority` then works with no API change, because it already reads `priority_mask.tif`.
- **If no ground-motion product exists** (T2 not done), the script exits with a clear message. Do **not** substitute a fake motion field. For tests, build tiny synthetic rasters inside the test.

**Done when:**
- Tests cover the AND logic, nodata propagation, the threshold and sensitivity maths, the resampling direction, and `dataKind` propagation.
- With the synthetic demo products, the script runs end to end and `GET /api/v1/places/exposure?area=camanava_2026&mask=priority` returns 200 with `dataKind: "synthetic"`.

### T4: Spot check and bilingual briefing API (backend; no laptop needed; start immediately)

**Files you own:** `backend/processing/briefing_place/` (new), `backend/app/spot_api.py` (new; register it in `main.py` as rule 1 allows), `backend/tests/test_spot_*.py` (new).

**Endpoints** (add a section "Spot check and briefing" at the end of `docs/API_CONTRACT.md`; this is the only part of that file you may edit):
1. `GET /api/v1/spot-check?lon=&lat=` combines, by calling the existing processing functions directly (do not call the HTTP API from inside the backend):
   - the NISAR point result (`nisar_api` / `processing.nisar_flood`): flood count, valid count, per-pass states;
   - the barangay and city (`processing.places.gazetteer.locate`);
   - pass rainfall for the pass dates (`processing.climate`);
   - the line-of-sight series at the point, if a ground-motion product exists;
   - whether the point is in a priority zone, if `priority_mask.tif` exists.

   Every value carries `source`, `dataKind` and `nativeResolution`. Missing parts are `null` with a `reason`. If any part is synthetic, the response's top-level `dataKind` is `"synthetic"`. Outside the bbox, return 404 `outside_coverage`.
2. `GET /api/v1/briefing/place?lon=&lat=&lang=en|fil&format=json|csv|html`: a **deterministic template** built only from the spot-check facts.
   - It has no runtime LLM and no number that isn't in the facts. Every sentence that contains a number must be traceable to a field.
   - Write it as `templates_en.py` and `templates_fil.py`, with the same fields and the same order.
   - **Filipino text:** write natural Tagalog, and mark it in a header comment and in the response (`"translationStatus": "pending native-speaker review"`). The team will review it.
   - HTML is a single self-contained printable page with sources and limitations at the bottom. CSV is one row per fact: field, value, units, source, dataKind.
   - Wording rules: "exposure", not "damage"; "line-of-sight motion", not "sinking"; hypotheses labelled as hypotheses; synthetic content flagged at the top in bold.

**Done when:** tests prove that every number in the EN and FIL text appears in the facts, that missing facts produce "not available because …" sentences rather than zeros, and that the synthetic flag propagates. Test CSV and HTML too. The endpoints answer for a point in Malabon (lon 120.957, lat 14.665) using the current products.

### T5: Validation data (research plus backend; no laptop needed)

**Files you own:** `backend/processing/validation/` (new), `backend/scripts/60_validation.py` (new), `backend/tests/test_validation_*.py` (new), `backend/data/cache/validation/` (new), `docs/VALIDATION.md` (new).

**Steps:**
1. **Find independent flood evidence for CAMANAVA, June–November 2026**, in this order of preference:
   - NASA OPERA DSWx-S1 (CMR collection `OPERA_L3_DSWX-S1_V1`) on dates within ±2 days of the NISAR passes;
   - Copernicus EMS or UNOSAT activations for Philippine floods in 2026;
   - NDRRMC situation reports or MMDA flood advisories listing flooded barangays or streets.

   Record every source with URL, date and licence. **Use only what you actually find and can cite.** If nothing usable exists, say so in `docs/VALIDATION.md`.
2. **Agreement metrics:** where a raster source exists (for example DSWx), compute agreement with the NISAR per-pass water masks on the coarser common grid: overall agreement, F1, intersection over union, and the confusion matrix. Exclude nodata in either source. Where only barangay lists exist, compute barangay-level hit rate. Store the results in `backend/data/cache/validation/` and add `GET /api/v1/validation?area=camanava_2026` in a new `backend/app/validation_api.py` (register it as rule 1 allows).
3. **Threshold sensitivity:** re-run the flood rhythm with HH/HV thresholds ±1 dB and report how much the "half or more" area changes. Use the pipeline functions in memory; do not overwrite the published product.
4. **Subsidence comparison:** find **published, peer-reviewed or agency** subsidence rates for CAMANAVA or the Bulacan coast (InSAR studies of Metro Manila). Record the citation, method, period and rate exactly as published. Do not paraphrase numbers you haven't seen in the source. Compare them qualitatively with T2's line-of-sight result: same sign and pattern? Remember LOS vs vertical and 4 months vs years.

**Done when:** `docs/VALIDATION.md` states each comparison, its result and its limitations honestly, including disagreements, and the endpoint serves the numbers. If T1 is not done, run the metrics on nothing and say so; do not compute against the synthetic product and present it as validation.

### T6: Hypotheses with real references (research; no laptop needed)

**File you own:** `docs/HYPOTHESES_SOURCES.md` (new). Hand the final JSON to the coordinator through it. **Do not edit `frontend/public/hypotheses.json`**, which belongs to the frontend agent's folder; the coordinator will copy it in.

**Task:** for each hypothesis below, find 1–2 **real, checkable** references (peer-reviewed papers, government reports such as MGB, NWRB, PAGASA or DPWH, or reputable agency pages). Give the full citation and URL. Say what the source actually states, quoting a sentence where possible.
1. Groundwater over-extraction drives land subsidence in CAMANAVA and the Bulacan coast.
2. Land subsidence increases the frequency and duration of flooding in coastal Metro Manila.
3. Fishpond conversion and coastal land-use change affect drainage and flood persistence.
4. River backflow and high tides in Manila Bay prolong flooding in Malabon and Navotas.
5. Urban expansion and impervious surfaces increase runoff.

Then write the JSON the frontend expects: an array of `{ "id", "title", "titleFil", "statement", "statementFil", "evidenceInApp", "references": [{ "citation", "url", "quote" }] }`. `evidenceInApp` names the Tanaw layer consistent with it, for example "Ground motion (N3)".

**Rules:** if you cannot verify a reference, leave it out. A hypothesis with no verified reference is dropped. Every item is labelled as a hypothesis, not a finding.

**Done when:** `docs/HYPOTHESES_SOURCES.md` contains the verified references and the final JSON block.

### T7: README truth pass (after T1–T5; around 13:00)

**Files you own:** `README.md` and `docs/DATA_MANIFEST.md`.

- Set each row of the challenge mapping table to its true status: done, done with synthetic data, partial, or cut.
- Put limitations first, using the real-run findings from T1, T2 and T5.
- Fill every row of the data manifest from the manifests under `backend/data/cache/*/`.
- Add a "Reproduce" section with the exact command sequence that produced the submitted products.

**Done when:** a stranger could reproduce the products, and nothing in the README claims more than the code and data show.

## 3. Order and timing (Manila time)

| Time | Laptop (needs Earthdata) | No laptop needed |
|---|---|---|
| 01:30–04:00 | T1 steps 1–3 (first file check) | T3 priority zones |
| 04:00–08:00 | T1 full run, then start the T2 download | T4 spot check and briefing |
| 08:00–11:00 | T2 chain run | T5 validation; T6 references |
| 11:00–13:00 | Re-run T3 on real data; check T4 on real data | T5 metrics on real data |
| 13:00–15:00 | — | T7 README truth pass |
| 15:00–17:00 | Bug fixes only | Bug fixes only |

If you can only do some of this, the priority is **T1 > T3 > T4 > T2 > T5 > T6 > T7**.

## 4. What to send back

At the end of each task, append to `docs/CODEX_STATUS.md`:
- task, status (done / partial / blocked) and commit hash;
- real numbers produced, with their source and caveats;
- anything that needs the coordinator (a `NEEDS-COORDINATOR:` line);
- anything you could not verify.
