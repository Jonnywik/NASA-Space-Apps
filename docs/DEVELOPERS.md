# For developers

The [README](../README.md) is written for judges and first-time users. This page holds the details for working on the code.

## Repository layout

```
.
├── backend/              FastAPI service and data processing (Python)
│   ├── app/              API routers (/api/v1); interactive docs at http://127.0.0.1:8000/docs
│   ├── processing/       NISAR, climate, places and validation code
│   ├── scripts/          numbered pipeline steps (19–63), run from backend/
│   ├── tests/            unit tests
│   └── data/cache/       small committed inputs and results (the NISAR product is in the data package)
├── frontend/             Next.js app (components/, utils/, app/, public/, tests/)
├── deploy/               optional hosting: one-process server and a tested Docker image (HOSTING.md)
├── docs/                 documentation (index: docs/README.md)
├── AGENTS.md             instructions for the AI coding agents
└── LICENSE
```

## Running

Follow the README's "Try it yourself" steps. Notes:
- **Production build:** `npm run build` then `npm start` in `frontend/`. The build downloads two web fonts from Google Fonts; if it stops with an error in `next/font`, check the connection and run it again.
- **Synthetic fixtures:** `NEXT_PUBLIC_USE_FIXTURES=1` answers every endpoint with synthetic development data (no backend needed). These are clearly labelled and are not observations.
- **The data package** creates only `backend/data/output/camanava_2026/`. Size 392,437,688 bytes; SHA-256 `3290a66b2fc115bd666c1f199c17c7e5d0c6f978132264eb28335219110a2cfa`. Details and the clean-checkout test records: [data/DATA_PACKAGE.md](data/DATA_PACKAGE.md).
- **Product binding:** the validation, robustness, cross-track and timelapse results are bound to the product's content (`backend/app/product_binding.py`). If you reprocess and the numbers change, those panels report "unavailable" until you rerun scripts 61, 62, 63 and 28.

## Tests

```bash
cd backend && ../.venv/bin/python -m unittest discover -s tests     # Windows: ..\.venv\Scripts\python
cd ../frontend && npm run lint && npm run test:api && npm run build
```

## Downloads and season animation

`GET /api/v1/downloads?area=camanava_2026` lists the real-data exports with attribution and licence; follow an entry's `url` to download it. Raster entries need the local NISAR product; missing files are omitted, never replaced by samples. The season animation is at `/api/v1/nisar/timelapse.gif?area=camanava_2026` and is rebuilt with `scripts/28_nisar_timelapse.py` (from `backend/`).

## Reprocess the data from raw NISAR files (advanced)

Only needed to rebuild the product from the satellite files; to run the app, use the data package.

You need an Earthdata account with access to ASF and NASA GES DISC (and PO.DAAC for OPERA). Set `EARTHDATA_TOKEN` privately in the same terminal session; never save or print it in the repository. Range reads need network access. Script 20 replaces the existing local NISAR output. Fresh catalogue queries can select newly released products, so keep the committed manifest to reproduce the recorded selection.

From the repository root (Windows shown; on macOS/Linux use `.venv/bin/python`):

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend/requirements-dev.txt
cd backend
..\.venv\Scripts\python scripts/19_nisar_search.py --track 140 --direction A --frame 9 --out data/cache/nisar/nisar_manifest_refresh.json
..\.venv\Scripts\python scripts/23_worldcover_water_mask.py --dilate-px 1
..\.venv\Scripts\python scripts/20_nisar_flood_rhythm.py --manifest data/cache/nisar/nisar_manifest_t140_A_f009_m4005.json --rule-file data/cache/nisar/water_rule_t140_A_f009.json --permanent-mask data/cache/places/worldcover_water_mask.tif --landcover data/cache/places/esa_worldcover_2021_clip.tif
..\.venv\Scripts\python scripts/61_opera_comparison.py
..\.venv\Scripts\python scripts/25_nisar_soil_moisture.py --track 140 --direction A --frame 9
..\.venv\Scripts\python scripts/31_fetch_imerg_passes.py --hours 48 --workers 12
..\.venv\Scripts\python scripts/26_nisar_extras.py
..\.venv\Scripts\python scripts/28_nisar_timelapse.py
..\.venv\Scripts\python scripts/62_robustness.py
```

Scripts 25 and 31 refresh their caches and may pick up newer upstream data. The second-orbit check (script 63) also needs the track 32 descending product; its commands are in the [runbook](NISAR_RUNBOOK.md) section "Independent replication on a second NISAR track". The runbook also covers the first-file checks and how to interpret each result.

## Hosting

The app can run as one Docker container on any host with about 1 GB of memory: see [HOSTING.md](HOSTING.md).

## More documentation

- [API contract](API_CONTRACT.md): endpoints, response shapes and shared constants
- [Submission scope](SUBMISSION_SCOPE.md): the plan and the findings as they evolved
- [Documentation index](README.md)
