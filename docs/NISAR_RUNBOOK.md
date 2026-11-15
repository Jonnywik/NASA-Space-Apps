# NISAR runbook (Agent B)

How to produce the real NISAR flood rhythm (N1, N2, N4, N5) and ground motion (N3) on a laptop. The cloud workspace has no Earthdata credential, so **no real NISAR pixel has been read yet**. What is in `backend/data/output/camanava_2026/nisar/` right now is a synthetic demo (`dataKind: "synthetic"`).

All commands run from `backend/` with the virtual environment active (`source ../.venv/bin/activate`).

## 0. Decide the track first (important)

The contract default is track 133 descending, frame 81. The real catalogue footprints (script 19, 14 Nov 2026) say that stack covers only about **35 % of the study bbox**: the Manila Bay side, west of roughly 120.91–120.95° E. Most of CAMANAVA's land is outside it. Its 4005 granules are also partial frames.

| Stack | GCOV dates | GUNW pairs | Share of bbox in footprint | GCOV size each |
|---|---|---|---|---|
| 133 D, frame 81, mode 4005 (former default) | 11 (23 Jun–2 Nov) | 9 | 35–36 % | ~3.6 GB |
| **032 D, frame 81, mode 4005** | 10 (28 Jun–26 Oct) | 8 | 100 % | ~5.5 GB |
| **140 A, frame 9, mode 4005** | 11 (23 Jun–2 Nov) | 9 | 100 % | ~5.4 GB |
| 039 A, frame 9 | 10 | 8 | 0 % | — |

The footprint share comes from the catalogue polygon, not from pixels. Confirm it on the first file (`validFraction` printed by script 20). If it holds, use 032 D or 140 A; 140 A + 032 D is also the pair to use for the N3+ vertical-motion stretch. The coordinator decides, then updates the contract constants. The commands below use a `MANIFEST` variable so either choice works.

All stacks have one 24-day step (no pass around 29 Jul–3 Aug). Each mixes Provisional and V1 processing for the last one or two dates.

## 1. Earthdata token

1. Create a free account at <https://urs.earthdata.nasa.gov> and sign in.
2. Open the profile menu → **Generate Token** → copy the token (valid 60 days).
3. In the shell that will run the scripts:
   ```sh
   export EARTHDATA_TOKEN='paste-the-token-here'
   ```
   Do not put it in a file in the repo, a commit, or a screenshot. The code reads only this variable, sends it only to NASA/ASF hosts, and never prints it.
4. If the first read returns `HTTP 401/403`, sign in to <https://search.asf.alaska.edu> once and accept the data-use terms, then retry.

## 2. Search (no login)

```sh
python scripts/19_nisar_search.py --track 140 --direction A --frame 9     # alternative with full coverage: --track 32 --direction D --frame 81
MANIFEST=data/cache/nisar/nisar_manifest_t140_A_f009_m4005.json
```
This rewrites the manifest and prints every stack with its coverage. Manifests for 133 D, 032 D and 140 A from 14 Nov are already committed.

## 3. First real file: two-date trial

```sh
python scripts/20_nisar_flood_rhythm.py --manifest $MANIFEST --dry-run          # lists files and sizes, reads nothing
python scripts/20_nisar_flood_rhythm.py --manifest $MANIFEST --max-dates 2 --calibrate --min-valid-passes 1 \
    --out-dir /tmp/nisar_trial
```
The reader uses HTTP range requests and fetches only the chunks that hold the study window. Expect tens to a few hundred MB per date and about 1–5 minutes per date on a home connection; this is an estimate, not a measurement. If the range read fails, add `--allow-download`: the whole file (3.6–5.5 GB per date, 40–59 GB for a full stack) goes to `data/raw/nisar/` with size and MD5 checked against the catalogue. Windows are cached in `data/raw/nisar_windows/`, so a re-run does not fetch again.

### What to check on the first real file

Nothing below has been verified against a real product. Open one file (after `--allow-download`, or with `h5ls -r file.h5 | head -80`) and check:

1. **Dataset paths.** Expected: `/science/LSAR/GCOV/grids/frequencyA/{HHHH,HVHV,xCoordinates,yCoordinates,projection}`. If script 20 says `HDF5 path ... is not in this file`, pass the right names with `--layout-base`, `--layout-hh`, `--layout-hv`.
2. **Units and radiometry.** `HHHH` should be real-valued linear power, not dB and not complex (the reader refuses both). Check its `units`/`description` attributes and whether it is gamma0 or sigma0. Open-water HH in the trial printout should sit around −20 to −30 dB; values near 0 or positive mean the scaling is wrong.
3. **Projection.** The `projection` dataset should carry an `epsg_code` (expected 32651, UTM 51N). If it does not, pass `--crs-fallback EPSG:32651` only after confirming the CRS another way.
4. **Coordinates are pixel centres** and y decreases down the array (north-up). If they are edges, use `--coordinates-are edge`. Check by overlaying `hh_<date>.png` on a basemap: the Navotas/Manila Bay shoreline must line up.
5. **Nodata.** Outside the swath the file should hold NaN (or the `_FillValue`). If a `mask` layer exists and is needed, pass `--layout-mask mask`.
6. **Coverage.** `valid NN% of the study area` in the printout confirms or refutes the footprint table in section 0.
7. **Calibration box.** `--calibrate` takes Manila Bay pixels in `[120.885, 14.62, 120.897, 14.70]`. That box was chosen from map knowledge. Confirm on the HH image that it is all open water, with no ships, fish pens or land. The record (pixel count, percentiles, thresholds) is saved in `water_rule.json` and in the manifest.

When these pass, record it so the product stops carrying the "unverified layout" warning: add `--layout-verified "checked by <name> on <date>: paths, units, EPSG, shoreline alignment"` to the full run.

## 4. Full flood-rhythm run

```sh
python scripts/20_nisar_flood_rhythm.py --manifest $MANIFEST --calibrate \
    --layout-verified "checked by <name> on <date>: ..."
```
Optional inputs: `--landcover worldcover.tif` (restricts possible flooded vegetation to WorldCover classes 40, 90, 95), `--permanent-mask water.tif`, `--rule-file data/output/camanava_2026/nisar/water_rule.json` (re-use the calibrated thresholds unchanged in later runs instead of `--calibrate`).

Output replaces `data/output/camanava_2026/nisar/`:

| File | Use |
|---|---|
| `manifest.json` | everything the API serves; top-level `dataKind`, `passCount`, `passes[{date, floodedKm2, ...}]`, SHA-256 of every asset |
| `pass_<date>.png`, `hh_<date>.png`, `veg_<date>.png`, `pol_<date>.png`, `rhythm.png`, `rhythm_legend.png` | map overlays (Web Mercator, bounds in the manifest) |
| `rhythm.tif` | band 1 = passes flooded, −1 = nodata (read by the exposure endpoint) |
| `rhythm_half.tif` | 1 = flooded on half or more of the pixel's own valid passes |
| `tif/state_<date>.tif`, `tif/db_<date>.tif`, `tif/rhythm_counts.tif`, `tif/permanent_water.tif`, `tif/hh_dry_reference.tif` | downloads and point lookups |
| `water_rule.json` | the fixed rule and its calibration record |

## 5. Switch the API from the synthetic demo to the real run

There is nothing to configure. The API serves whatever product is in `data/output/camanava_2026/nisar/`, and step 4 replaces the synthetic one. Then check:
```sh
curl -s 'http://127.0.0.1:8000/api/v1/nisar/passes?area=camanava_2026' | python -m json.tool | grep -m1 dataKind
```
It must say `"observed"`. If it says `"synthetic"`, the real run did not finish. Script 22 refuses to overwrite a real product unless `--force` is given. That folder is git-ignored, so copy it to the deployment host or the static demo by hand.

The router has to be registered once in `backend/app/main.py` (coordinator):
```python
from app.nisar_api import make_router as make_nisar_router
app.include_router(make_nisar_router(OUTPUT, read_public_events))
```

## 6. Ground motion: script 21, then 10 → 11 → 12

```sh
python scripts/21_nisar_gunw_chain.py --manifest $MANIFEST --download --max-pairs 1     # ~2.3 GB, first-file check
python scripts/21_nisar_gunw_chain.py --manifest $MANIFEST --download                    # all pairs: about 18–21 GB
python scripts/21_nisar_gunw_chain.py --manifest $MANIFEST --fill-hashes \
    --phase-sign <+1 or -1> --reference-bbox <W S E N>
bash data/raw/nisar/gunw_chain/t140_A_f009/run_gunw_chain.sh      # runs 10 and 11 per pair, then 12
```
(or add `--execute` to the third command to run 10 → 11 → 12 in-process).

Script 21 writes one script-10 source manifest per pair, one script-11 reference config and the shell script. It will not guess two things, and scripts 10/11 stop until they are set:

- **`--phase-sign`**: whether positive unwrapped phase means motion away from (+1) or toward (−1) the satellite. Take it from the GUNW product specification, not from a guess.
- **`--reference-bbox`**: a stable, coherent reference area chosen by a person after looking at coherence. The built-in candidate is a placeholder.

Check on the first GUNW file: paths `/science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram/{xCoordinates,yCoordinates,projection}` and `.../HH/{unwrappedPhase,coherenceMagnitude,connectedComponents,ionospherePhaseScreen}` (override with `--gunw-base`, `--gunw-pol`); phase in radians; the centre frequency in the metadata against the 0.2384 m wavelength used; which corrections are already applied (`--corrections-applied`); and whether to register the ionosphere screen (`--ionosphere-sign`). L-band ionosphere matters here, so state the correction state next to any result.

The ground-motion product is published as `needs-review`. The existing P3 routes (`/ground-motion?event=camanava_2026`) serve real data only after `scripts/17_review_product.py <manifest> <review.json>`.

## 7. Synthetic demo (development only)

```sh
python scripts/22_nisar_synthetic_demo.py
```
Generates fake GCOV-like HDF5 files in `data/raw/nisar_synthetic/`, runs the same chain, and writes a product labelled `dataKind: "synthetic"` in the manifest, every API response and the legend image. Its date slots are copied from the real catalogue so charts line up; product IDs read `SYNTHETIC-FIXTURE-<date>`. Never ship it in the public build.

## 8. Method notes and limits

- One fixed rule for every date: water where HH < threshold **and** HV < threshold. Calibrated once on Manila Bay (95th percentile of bay dB plus 1 dB), recorded, then frozen.
- Urban double-bounce hides street flooding: flooded area over dense built-up land is a lower bound.
- Permanent water = water on ≥ 90 % of a pixel's valid passes (at least 3). It is masked out, so the bay is never "flooded".
- A pixel with no valid HH/HV on a pass is nodata. It leaves the denominator and is never counted as dry. Pixels with fewer than 3 valid passes are not counted at all.
- Areas use a per-pixel equal-area calculation and cover only pixels inside the study bbox.
- Possible flooded vegetation = HH at least 3 dB above the pixel's own season median. It is a separate class and never adds to open water.
- Dates are UTC. Descending passes are about 18:30 Manila time the same day; ascending passes (140 A) are about 05:30 Manila time the next day.

## 9. Tests

```sh
../.venv/bin/python -m unittest discover -s tests
```

## Real run results (15 Nov 2026, coordinator; first real NISAR read)

Run from the cloud session with the proxy-held Earthdata token, track 140 A / frame 9, all 11 GCOV passes
(23 Jun – 2 Nov 2026), read by HTTP range requests (about 70–90 MB per date, 4 minutes for all 11).
**These results were written to a scratch folder; the app still serves the synthetic demo product until the owner approves publishing.**

### First-file checks (runbook section 3)
1. **Layout.** The real file matches the expected paths: `science/LSAR/GCOV/grids/frequencyA/{HHHH,HVHV,xCoordinates,yCoordinates,projection,mask,numberOfLooks}`, float32, 33120 × 33840 samples. No layout override was needed. (Frequency B, a narrow second band, is also present and unused.)
2. **Coverage.** The study window reads as **valid for 100 % of the study area on all 11 passes**, so track 140 A covers CAMANAVA fully (track 133 D covers about 35 %).
3. **Window size.** 1752 × 2457 samples on a 10 m UTM 51N (EPSG:32651) grid.
4. **Coastline.** The HH image lines up with the shoreline: Manila Bay is dark, the Bulacan fishponds are dark rectangles, the Navotas–Manila port area and reclaimed land are bright and sharp, and ships appear as bright dots. Checked by eye by the coordinator.
5. **Radiometry.** Manila Bay (calibration box `[120.885, 14.62, 120.897, 14.70]`, 1.26 million pixels over 11 passes): HH median about −15.8 dB, 95th percentile about −13.6 dB; HV median about −25.5 dB. The bay is brighter than a calm sea because of wind roughening, and it brightens toward the coast.
6. **Calibrated rule (one rule for all passes):** HH < −12.5 dB and HV < −22.5 dB.

### What the real data shows
- **Open water outside permanent water is tiny on every pass: 0.13–0.57 km² of a 419 km² study window** (flood rhythm: 0.37 km² flooded on half or more of the valid passes). Possible flooded vegetation (L-band HH brightening in cropland and wetland) is 0.11–0.77 km² per pass.
- **Where the flagged pixels are:** small clusters in the far north-west wetlands and fishponds, and a strip along the reclaimed Navotas coast. **None are in the dense urban streets of Malabon, Navotas or Caloocan.**
- **Why:** street flooding is not visible as dark water to L-band radar. Flooded streets between buildings look bright (double-bounce), and the 21:30 UTC passes are at 05:30 Manila time, so flooding that peaks in the afternoon and recedes by morning is not captured. Both are known limits and are in the manifest limitations. **This run does not show that CAMANAVA did not flood; it shows that these 11 pre-dawn passes, read as open water, do not map it.**
- **Without masking, the bay's nearshore strip looks like flooding.** A two-date trial with no external mask flagged 8–11 km² of "flood", almost all of it nearshore bay water that crosses the threshold on some passes. The mask used for the full run is WorldCover 2021 class 80 (water bodies, grown by one 10 m pixel): `scripts/23_worldcover_water_mask.py`, passed with `--permanent-mask`. The mask also removes fishponds, which is intended.
- **Backscatter tracks rain.** Compared with each pixel's median over the 11 passes, mean HH change over built-up land (WorldCover class 50) correlates with the 7-day rain before each pass (NASA POWER): Spearman ρ = 0.80 (n = 11, p ≈ 0.003). Non-built land shows the same pattern, so this is general wetness (soil and vegetation), not a distinct urban flood signal. It is an exploratory result, not a flood map.

### Open
- The rule was calibrated on the bay with a margin chosen for wind roughening. A stricter or looser margin changes the totals only slightly because most permanent water is masked, but it has not been tested against an independent flood map (OPERA DSWx-S1 matches 10 of 11 passes in the catalogue, not yet downloaded).
- Ground motion (T2) has not been run.

## Ground motion (T2): first real look, 15 Nov 2026 (coordinator)

**Status: stopped at the planned approval point. No ground-motion product was produced, and none is served.** The two decisions script 21 refuses to guess (phase sign, stable reference area) could not be settled from the evidence below.

### What was done
- `scripts/24_nisar_gunw_subset.py` (new) saved only the study window of all 9 real GUNW pairs on track 140 A / frame 9, 23 Jun → 21 Oct 2026. That is 339 × 251 pixels at 80 m, about 0.9 MB per pair instead of 2.3 GB, with the same internal paths, so scripts 21 and 10–12 can read them. The files are in `data/raw/nisar/gunw/` (gitignored). Each records its source URL, the full granule's MD5 and the window.
- **Layout verified on the real file:** `science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram/{xCoordinates,yCoordinates,projection}` and `.../HH/{unwrappedPhase,coherenceMagnitude,connectedComponents,ionospherePhaseScreen}`, phase in radians, posting 80 m.
- **Wavelength:** the file's `centerFrequency` is 1.239 GHz, so **λ = 0.2420 m**. `gunw_chain.py` hard-codes 0.2384 m (1.2575 GHz nominal), which must be changed before any run.
- **Corrections:** the processing metadata says ionospheric and tropospheric corrections were applied **to geolocation only**. The ionosphere phase screen is a separate layer, **not applied to the unwrapped phase**.
- **Sign convention:** the GUNW product specification (JPL D-102272 Rev E, Nov 2024; downloaded from the NISAR sample-docs folder) describes the unwrapped phase in radians but **does not state whether positive phase means motion toward or away from the satellite.** The ASF GUNW user-guide page doesn't state it either.

### Evidence gathered (window statistics, 9 pairs)
- **Coherence:** mean 0.38–0.46 per pair; 54–65 % of the window has coherence ≥ 0.3. Urban inland areas are high (Valenzuela about 0.67; east Caloocan about 0.70); the Navotas/Malabon coast is about 0.33; the Obando/Bulacan fishpond coast is about 0.19, too low for reliable unwrapping.
- **Ionosphere:** within this 25 km window, the difference between "raw" and "ionosphere-subtracted" relative phase is 2–3 radians (about 40–60 mm) in every test region over the chain. L-band ionosphere dominates the signal here.
- **Sign check against known subsidence:** summed phase over the chain relative to a north-east reference box (121.00–121.04 E, 14.76–14.82 N), converted at 19.25 mm/rad:

| Region | Raw | Ionosphere-subtracted |
|---|---|---|
| Navotas/Malabon coast | −47 mm | +5 mm |
| Obando/Bulacan coast | −30 mm | −1 mm |
| Valenzuela inland | −35 mm | +30 mm |
| East Caloocan | −44 mm | +15 mm |

  Per-pair signs alternate in every region. Published InSAR studies place the fastest subsidence on the coast, but here the inland region moves more than the coast after ionosphere subtraction. That points to residual ionospheric or tropospheric noise, not deformation. **The empirical check doesn't establish the sign, and the 4-month signal is not separable from noise with this approach.**

### What a defensible result would need
1. The phase sign from an authoritative source: the NISAR RIFG/RUNW product spec or ATBD, or ISCE3's interferogram convention confirmed against a documented example.
2. The ionosphere screen's sign relative to the phase (`--ionosphere-sign`), confirmed the same way, then applied.
3. Tropospheric correction (wet season), redundancy (NISAR provides only 12-day nearest-neighbour GUNW pairs, so no redundant network), and a longer record than 4 months. A real reference area should be chosen on ground with independent evidence of stability.

Until then, Ground motion shows "not available yet", and priority zones (which need motion) stay unavailable.

## Soil moisture (NISAR L3 SME2): real data, 15 Nov 2026 (coordinator)

- `scripts/25_nisar_soil_moisture.py` reads the study window of `NISAR_L3_SME2_PROVISIONAL_V1` for track 140 A / frame 9: **9 passes, 23 Jun → 9 Oct 2026**, about 5 seconds each by range request. It writes `data/cache/nisar/soil_moisture/manifest.json` and one PNG per pass (120 kB in total, committed). The layer is the top-level `soilMoisture` (m³/m³, 200 m EASE-Grid 2.0), recommended retrievals only (quality-flag bit 0 = 0), with cells more than half water excluded. Tests: `tests/test_nisar_soil_moisture.py`.
- **Coverage is low:** only about 22 % of the study cells have any retrieval, and **5–7 % have recommended retrievals**, scattered and concentrated in the northern Bulacan farmland. The dense urban core gets no recommended soil moisture, which is expected for an L-band soil-moisture algorithm.
- **Values:** study-area median of the recommended cells 0.23–0.34 m³/m³ per pass.
- **No rain signal:** compared with the 7-day prior NASA POWER rain, Spearman ρ = −0.33 (p = 0.38, n = 9). For example, 10 Aug, after about 230 mm in 7 days, has a median of 0.27 m³/m³, lower than June. With a few hundred scattered cells and a provisional product, this does not confirm the wetness signal seen in the GCOV backscatter (ρ = 0.80).
- **Not yet served by the API or shown in the app.**

## Rain timing before each pass: NASA GPM IMERG (15 Nov 2026, coordinator)

`scripts/31_fetch_imerg_passes.py` fetched IMERG Late Run V07 half-hourly rain (`GPM_3IMERGHHL`, 0.1°) for the 48 hours before each of the 11 NISAR passes: 1,067 files, none missing, over 0.1° cells overlapping the study bbox. Only half-hours ending at or before the pass are counted; an early version included the half-hour containing the pass, which was fixed and the summaries recomputed. Output: `data/cache/climate/imerg_passes.json`, served at `GET /api/v1/climate/imerg/passes`.

| Pass (UTC date; 05:30 Manila the next morning) | Rain 24 h before (mm) | Rain 48 h before (mm) | Peak (mm/hr, area mean) | Hours since last ≥ 1 mm/hr | NISAR open water outside permanent water (km²) |
|---|---|---|---|---|---|
| 23 Jun | 1.8 | 5.2 | 2.1 | 0.0 | 0.53 |
| 5 Jul | 5.7 | 7.1 | 1.1 | 15.5 | 0.50 |
| 17 Jul | 0.1 | 0.3 | 0.1 | none | 0.41 |
| 10 Aug | 31.4 | 96.6 | 11.9 (9 Aug 07:00 Manila) | 7.5 | 0.19 |
| 22 Aug | 10.1 | 10.2 | 2.7 | 12.0 | 0.13 |
| 3 Sep | 23.9 | 29.1 | 10.5 | 0.0 (raining at the pass) | 0.19 |
| 15 Sep | 16.0 | 19.1 | 5.3 | 14.0 | 0.38 |
| 27 Sep | 4.8 | 6.6 | 3.0 | 0.5 | 0.47 |
| 9 Oct | 1.8 | 8.0 | 2.2 | 38.5 | 0.34 |
| 21 Oct | 3.2 | 3.2 | 1.4 | 8.0 | 0.58 |
| 2 Nov | 1.2 | 5.4 | 1.4 | 0.0 | 0.50 |

**Finding: the NISAR open-water area goes down after rain.** Spearman ρ = −0.77 (p = 0.01) against 48-hour rain, and −0.61 (p = 0.05) against 24-hour rain, n = 11.
- The passes after the heaviest rain (10 Aug, 3 Sep, 22 Aug) have the smallest areas.
- This is consistent with L-band physics: wet soil and vegetation, and rain- or wind-roughened water, scatter more energy back, so fewer pixels fall below the "dark = water" threshold. The same rain response shows as general brightening (ρ = +0.80 with 7-day POWER rain).
- **So the "flood rhythm" layer is not a map of rain-driven flooding.** It maps open water outside permanent water, mostly wetland and fishpond margins, and it shrinks when it rains. It must be labelled that way.
- Rain-driven urban flooding is not visible in these 05:30 passes: flooded streets look bright (double-bounce), and on 10 Aug the main storm peaked about 46 hours before the pass.

Exploratory: n = 11, one study area, provisional NISAR products, and IMERG is a satellite estimate at about 11 km.

## Two exploratory layers from cached real data (15 Nov 2026, about 15:00, coordinator)

`scripts/26_nisar_extras.py` builds both layers in seconds from data already cached by scripts 20, 24 and 31, with no download. It writes small files to `data/cache/nisar/extra/` (committed), served by `GET /api/v1/nisar/rain-response`, `GET /api/v1/nisar/coherence-change` and `GET /api/v1/nisar/extra/{name}.png`. Tests: `tests/test_nisar_extras.py`.

- **Rain response:** per 50 m cell, Spearman ρ between NISAR HH backscatter and the 48-hour IMERG rain before each of the 11 passes, with WorldCover water excluded. **Median ρ = 0.65; 70 % of land cells have ρ > 0.5.** The response is similar across built-up (0.65), tree cover (0.68), grassland (0.70) and cropland (0.59): the whole area "wets up" to the radar after storms. With n = 11, |ρ| above about 0.6 stands out from chance. **Not a flood map.**
- **Storm coherence loss:** NISAR GUNW HH coherence at 80 m, calculated as the median of the 8 calm 12-day pairs minus the pair 17 Jul → 10 Aug, which spans the 8–9 Aug storm. **Median loss 0.06; 4.8 km² of land lost more than 0.3.** Loss is largest in vegetated classes (cropland 0.12, trees 0.11, mangroves 0.11) and smallest in built-up areas (0.055). Caveat: the storm pair spans 24 days and the calm pairs 12, so part of the loss is expected anyway. Loss can come from water, vegetation change, construction or noise; **never call it flooding.**
- **NISAR soil moisture** is now served at `GET /api/v1/nisar/soil-moisture`, with per-pass overlays.

### Correction: the backscatter-vs-rain check
The cached GCOV windows (`data/raw/nisar_windows/*.npz`, written by script 20) store **HH in dB**, not linear power. The first quick check of "backscatter tracks rain" took the logarithm of those dB values. It was recomputed correctly: change from each pixel's median dB, averaged over WorldCover classes.
- Against 7-day NASA POWER rain, Spearman **ρ = +0.80 for built-up land (p = 0.003)**, the same value as stated before, and +0.84 for other land.
- Against 48-hour IMERG rain, **ρ = +0.93 (built-up) and +0.95 (other land)**, both p < 0.001.
- After the 8 Aug storm (10 Aug pass), built-up land averaged **+0.63 dB** above its seasonal median.

The published statement (ρ = 0.80) stands. No other result used the flawed calculation.

## Science and validation hardening (15 Nov 2026, about 16:00, coordinator)

### Robustness of the headline findings (`scripts/62_robustness.py` → `data/cache/validation/robustness.json`, `GET /api/v1/validation/robustness`)
No download needed. It is bound to the product manifest SHA-256 like `/validation`, so rerun it after any product regeneration.

| Finding (track 140 A, n = 11) | ρ | permutation p | 95 % bootstrap | leave-one-pass-out |
|---|---|---|---|---|
| Open water outside permanent water vs 48 h IMERG | −0.77 | 0.008 | −0.98 to −0.34 | −0.88 to −0.72 (always negative) |
| Mean HH change, built-up land, vs 48 h IMERG | +0.93 | 0.0002 | 0.67 to 0.99 | 0.90 to 0.95 |
| Mean HH change, other land, vs 48 h IMERG | +0.94 | < 0.0001 | 0.70 to 1.00 | 0.92 to 0.95 |

- **The rain-response map is not chance.** The rain dates were shuffled 2,000 times and the whole map recomputed each time. With shuffled rain, at most 26 % of land cells (95th percentile; 6 % on average) reach ρ > 0.5; the real map has **70 %** (field p < 0.001). Shuffling keeps the radar's spatial pattern, so this test allows for neighbouring cells being alike.
- **Correction: the storm coherence loss does not survive the interval control.** With Markov decorrelation, a 24-day pair keeps about (12-day coherence)². Allowing for that leaves **0.04–0.09 km²** with loss over 0.3 (naive: 3.2 km² on classified land, 4.8 km² including unclassified cells). The storm pair loses more than any calm pair (calm pairs: 0.2–1.5 km² on the same naive measure), but the storm and the longer interval cannot be separated with this data. The layer stays in the app as exploratory and its card now says so (`km2DropOver03IntervalCorrected`).

### Independent replication on a second NISAR track (`scripts/63_cross_track.py` → `data/cache/validation/cross_track.json`, `GET /api/v1/validation/cross-track`)
Script 19 lists **track 32 descending, frame 81: 100 % coverage, 10 passes, 28 Jun – 26 Oct 2026, at 10:24 UTC = 18:24 Manila the same day** (track 140 A passes at 05:30). It was processed separately into `data/output/camanava_2026/nisar_t032D/` (gitignored). The canonical ascending product and its validation hash were not touched.

```
cd backend
python scripts/19_nisar_search.py --track 32 --direction D --frame 81
python scripts/20_nisar_flood_rhythm.py --manifest data/cache/nisar/nisar_manifest_t032_D_f081_m4005.json --out-dir data/output/camanava_2026/nisar_t032D --calibrate --permanent-mask data/cache/places/worldcover_water_mask.tif --landcover data/cache/places/esa_worldcover_2021_clip.tif
python scripts/31_fetch_imerg_passes.py --manifest data/cache/nisar/nisar_manifest_t032_D_f081_m4005.json --out data/cache/climate/imerg_passes_t032D.json
python scripts/63_cross_track.py      # needs EARTHDATA_TOKEN for PO.DAAC (OPERA)
```
Pitfall: three 120 m trial windows from an old test run (28 Jun, 10 Jul, 22 Jul) were in `data/raw/nisar_windows/` and gave 32–58 km² of fake "open water". They were removed and reread at 10 m. If you see a pass with tens of km², check the cached window's grid (`transform[0]` must be 10).

- **Its own Manila Bay calibration gives HH < −13.0 dB, HV < −22.5 dB** (track 140 A: −12.5 / −22.5).
- **Open water outside permanent water: 0.10–0.86 km² per pass; 0.43 km² on half or more of passes** (track 140 A: 0.13–0.57 and 0.37).
- **Same places:** **99 %** of the ascending track's recurring open water lies within 30 m of the descending track's recurring open water (76 % the other way). A randomly shifted map gives 0.04 % on average. Exact pixel overlap is 0.19 km², all of it on cropland (0.12), grassland, wetland and tree cover, with **0 km² on built-up land**: fishponds, paddies and wetland margins, not streets.
- **OPERA DSWx-S1 (Sentinel-1C, 10:06 UTC), 24.3 h before each descending pass, 10 matches** (the ascending validation had 3 matches, each more than 48 h apart). Median **F1 0.74, IoU 0.58, agreement 0.87; precision 0.97, recall 0.60** (range F1 0.68–0.82). NISAR's water rule is conservative: what it calls water, Sentinel-1 almost always calls water. It misses some water OPERA includes, mostly inundated vegetation and shallow coastal edges. Total water, not flood-only accuracy; two satellites, not ground truth.
- **The rain link is NOT reproduced on the 18:24 track.** IMERG (48 h before each 18:24 pass; `imerg_passes_t032D.json`) shows the afternoon thunderstorms, peaking about 14:00–15:30 Manila, and several passes 0.4–1.4 h after rain. But open water vs 48 h rain gives ρ = −0.15 (p = 0.68), and brightening over built-up and other land gives ρ = +0.35 (p = 0.33), n = 10. The 24 h and 6 h windows and 7-day POWER rain are also weak (|ρ| ≤ 0.5, not significant). So **"less open water and brighter land after rain" is a 05:30-track result only**: keep it exploratory and say it was not reproduced. Possible reasons (not tested): different incidence and look direction, evening drying, or provisional calibration differences between passes. The location of recurring water, by contrast, replicates strongly.
- Also visible: on the 18:24 track, built-up land is about 0.5 dB darker than its median on the three June–July passes and on 26 Oct (the only V1 pass). This may be a processing or calibration difference between product versions; it is unexplained.
