# NISAR runbook (Agent B)

How to produce the real NISAR flood rhythm (N1, N2, N4, N5) and ground motion (N3) on a laptop. The cloud workspace has no Earthdata credential, so **no real NISAR pixel has been read yet**. What is in `backend/data/output/camanava_2026/nisar/` right now is a synthetic demo (`dataKind: "synthetic"`).

All commands run from `backend/` with the virtual environment active (`source ../.venv/bin/activate`).

## 0. Decide the track first (important)

The contract default is track 133 descending, frame 81. The real catalogue footprints (script 19, 14 Nov 2026) say that stack covers only about **35 % of the study bbox**: the Manila Bay side, west of roughly 120.91–120.95° E. Most of CAMANAVA's land is outside it. Its 4005 granules are also partial frames.

| Stack | GCOV dates | GUNW pairs | Share of bbox in footprint | GCOV size each |
|---|---|---|---|---|
| 133 D, frame 81, mode 4005 (contract default) | 11 (23 Jun–2 Nov) | 9 | 35–36 % | ~3.6 GB |
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
python scripts/19_nisar_search.py --track 32 --direction D --frame 81     # or: --track 140 --direction A --frame 9
MANIFEST=data/cache/nisar/nisar_manifest_t032_D_f081_m4005.json
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
bash data/raw/nisar/gunw_chain/t032_D_f081/run_gunw_chain.sh      # runs 10 and 11 per pair, then 12
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
