# Data package: tanaw-data-camanava_2026-v1

The repository's `.gitignore` excludes `backend/data/output/camanava_2026/`, so a fresh clone does not contain the derived NISAR product that the app reads. This package supplies that folder, unchanged. It matches repository commit `ce42105` (main of Jonnywik/NASA-SA-Final).

Download: `<PACKAGE_URL>` (to be added by the owner; anonymous access not yet verified).

## Files

| File | Size (bytes) | SHA-256 |
|---|---:|---|
| `tanaw-data-camanava_2026-v1.zip` | 392,437,688 (374.3 MiB) | `3290a66b2fc115bd666c1f199c17c7e5d0c6f978132264eb28335219110a2cfa` |
| `tanaw-data-camanava_2026-v1.zip.part00` | 99,614,720 | `5efeb8afbd4536ed9baf7c1f870b172235ea5ef1be90e1051d240ce90e7f5dd0` |
| `tanaw-data-camanava_2026-v1.zip.part01` | 99,614,720 | `84b9ef2daa13dd9900c3299b7c47749113425e6b8da6fb330e2f707b04ea5468` |
| `tanaw-data-camanava_2026-v1.zip.part02` | 99,614,720 | `a1d9c3a0262d06df8719a264ec41f835ef305a3d7732ff47c1d72cf94bd255b8` |
| `tanaw-data-camanava_2026-v1.zip.part03` | 93,593,528 | `e316c6feaba08afb6537c67346f3ab14a242eaa3b50e7583255dbcbf7884c7b1` |

The zip is over 100 MB, so it is also split into four parts of at most 95 MiB for hosts with a 100 MB file limit. Publish either the single zip or all four parts. The parts are plain byte slices; join them in order and check the result against the zip hash above:

```bash
cat tanaw-data-camanava_2026-v1.zip.part0{0,1,2,3} > tanaw-data-camanava_2026-v1.zip
sha256sum tanaw-data-camanava_2026-v1.zip
```

```powershell
cmd /c copy /b tanaw-data-camanava_2026-v1.zip.part00+tanaw-data-camanava_2026-v1.zip.part01+tanaw-data-camanava_2026-v1.zip.part02+tanaw-data-camanava_2026-v1.zip.part03 tanaw-data-camanava_2026-v1.zip
Get-FileHash -Algorithm SHA256 tanaw-data-camanava_2026-v1.zip
```

The DEFLATE compression saves little because the GeoTIFFs and PNGs are already compressed.

## Inventory

Paths inside the zip are relative to the repository root. Unzip it at the root.

```
backend/data/output/camanava_2026/DATA_README.txt     source, caveats and licence
backend/data/output/camanava_2026/nisar/              75 files, 393,575,234 bytes (376 MB)
```

The `nisar/` folder is a byte-for-byte copy of the product used for the submission. All 75 files were compared with `diff -r` after extraction. `manifest.json` has SHA-256 `49c00d050b9414f113b7c5311ee8fe2b32696a6623a073871400dfedf4fc990c`, the value recorded by the committed validation, robustness and cross-track results. Every one of its 73 assets matched its recorded SHA-256 before packaging.

| Files | Read by | Used for |
|---|---|---|
| `manifest.json` | `nisar_api`, `downloads_api`, `validation_api`, `climate_api`, `places_api` | Product metadata, asset registry with SHA-256, and the binding for validation, robustness, cross-track and timelapse (`product_binding.py`) |
| `pass_*.png` (11) | `/nisar/overlay` | Per-pass open water outside usual water |
| `hh_*.png`, `pol_*.png`, `veg_*.png` (11 each) | `/nisar/overlay`, `/nisar/polarization` | HH backscatter, HH/HV composite and possible flooded vegetation overlays |
| `rhythm.png`, `rhythm_legend.png` | `/nisar/overlay` | Open-water rhythm map overlay |
| `rhythm.tif`, `rhythm_half.tif` | `/downloads`, `/places/exposure` | GeoTIFF downloads; place exposure for "half or more passes" |
| `tif/state_*.tif`, `tif/db_*.tif` (11 each) | `/nisar/point`, `/spot-check` | Per-pass state and dB at a clicked point |
| `tif/rhythm_counts.tif`, `tif/permanent_water.tif`, `tif/hh_dry_reference.tif` | registered in manifest | Rhythm count, usual-water mask and dry-season HH reference |
| `water_rule.json` | not read by the API | Calibrated thresholds; kept with the product for provenance |

Everything else the app reads is committed already: `backend/data/cache/` (validation, robustness, cross-track, timelapse GIF and sidecar, IMERG, soil moisture, places) and the three Sentinel-1 context events in `backend/data/output/{carina_2024,habagat_2025,karding_2022}/`.

## Excluded

| Item | Reason |
|---|---|
| `backend/data/output/camanava_2026/nisar_t032D/` (343 MB) | Research product for the second track. The app does not read it; its results are in the committed `backend/data/cache/validation/cross_track.json`. |
| `backend/data/raw/` | Raw NISAR granules and source downloads; only processing scripts read them. Granule IDs are listed in the manifest. |
| `*.pre-r2-preserved-*` | Superseded output; none were found next to the product. |
| Ground-motion and priority-zone outputs | No reviewed product exists. Their endpoints say "unavailable". |
| Credentials, `.netrc`, tokens, signed URLs | None are included. The manifest holds only public ASF granule URLs without signatures. |

`manifest.json` records the processing machine's local working paths in its `provenance.options` block. These paths are inert. They were left unchanged because editing the manifest would change its hash and unbind the validation results.

## Attribution and licence

- NASA-ISRO NISAR L2 GCOV (`NISAR_L2_GCOV_PROVISIONAL_V1` and `NISAR_L2_GCOV_V1`), distributed by ASF DAAC. Nine of the eleven passes are provisional products.
- NASA GPM IMERG via NASA GES DISC (rainfall context; committed cache).
- ESA WorldCover 2021 v200, CC BY 4.0 (usual-water mask and land cover used to derive the product).
- WorldPop Philippines 2020 constrained, CC BY 4.0; OpenStreetMap buildings, © OpenStreetMap contributors, ODbL 1.0; HDX COD-AB Philippines boundaries, CC BY-IGO (committed caches).
- The derived files in the package: CC BY 4.0, Tanaw contributors, subject to the source terms. Application code: MIT.

Caveats, as stated in `DATA_README.txt`: open water outside usual water is not a flood map, and flooded city streets are under-detected. Possible flooded vegetation is not a confirmed flood. Ground motion is unavailable, so priority zones are also unavailable.

## Clean-checkout verification (15 Nov 2026)

Method:

1. `git clone` of main at `ce42105` into a fresh directory, with no ignored data.
2. Python dependencies came from the existing project virtualenv (Python 3.13). `frontend/node_modules` was symlinked from the working copy. A judge installs both by following the README.
3. Backend: `uvicorn app.main:app --port 8103`. Frontend: `NEXT_PUBLIC_API_URL=http://127.0.0.1:8103 npx next dev -p 3103`.
4. `EARTHDATA_TOKEN` was not set.
5. Checks ran first without the package. The four split parts were then joined, the joined zip matched the zip hash, `unzip` ran at the repository root, and the backend was restarted. After extraction, `git status` showed no tracked or untracked changes, because the folder is ignored.

All requests use `area=camanava_2026`.

| Endpoint | Without package | With package |
|---|---|---|
| `GET /api/v1/nisar/flood-rhythm` | 404 `data_unavailable` | 200 |
| `GET /api/v1/nisar/passes` | 404 | 200 (11 passes) |
| `GET /api/v1/validation` | 404 | 200 (status `partial`; 15 Sep F1 0.729, IoU 0.574) |
| `GET /api/v1/validation/robustness` | 404 | 200 |
| `GET /api/v1/validation/cross-track` | 404 | 200 |
| `GET /api/v1/nisar/timelapse.gif` | 404 | 200 `image/gif`, 3,794,164 bytes |
| `GET /api/v1/downloads` | 200 with 2 ids (`imerg-passes`, `soil-moisture-passes`) | 200 with 7 ids (`rhythm`, `rhythm-half`, `open-water-passes`, `imerg-passes`, `soil-moisture-passes`, `validation`, `timelapse`). Each `/downloads/{id}` returned 200. |
| `GET /api/v1/downloads/rhythm` | 404 | 200 `image/tiff`, 118,140 bytes |
| `GET /api/v1/nisar/point?lon=120.957&lat=14.665` | 404 | 200 (11 valid passes, flood count 0, per-pass values) |
| `GET /api/v1/spot-check?lon=120.957&lat=14.665` | 200; `nisar` stream unavailable | 200; place, nisar, rainfall and IMERG streams have values; motion, priority and exposure stay unavailable |
| `GET /api/v1/nisar/overlay/camanava_2026/rhythm.png` | 404 | 200 `image/png` |
| `GET /api/v1/nisar/overlay/camanava_2026/{pass,hh,pol,veg}_20261102.png` | 404 | 200 |
| `GET /api/v1/nisar/polarization?date=2026-11-02` | 404 | 200 |
| `GET /api/v1/places/exposure?mask=rhythm_half&level=barangay` | 404 | 200 |

Browser checks used Playwright with Chromium at 1440×1000:

- `/?mode=rhythm` without the package showed no map overlay. The validation panel read "Not available yet".
- `/?mode=rhythm` with the package loaded the `rhythm.png` overlay (`naturalWidth > 0`). The validation panel showed jointly valid pixels 466,248, IoU 0.574, F1 0.729 and agreement 0.871, plus the cross-track block.
- `/?mode=season&pass=20261102` loaded the `pass_20261102.png` and `veg_20261102.png` overlays.
- There were no page errors.
- Basemap tiles did not load in the offline sandbox. They need internet access.

Not tested: `npm run build` followed by `npm start`, Windows, the PowerShell extraction steps, and anonymous download from the final host.
