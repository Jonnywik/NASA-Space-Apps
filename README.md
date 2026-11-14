# Tanaw

[![CI](https://github.com/Jonnywik/NASA-Space-Apps/actions/workflows/ci.yml/badge.svg)](https://github.com/Jonnywik/NASA-Space-Apps/actions/workflows/ci.yml)

> Replace `Jonnywik/NASA-Space-Apps` in the badge above with the real repository path.

**Tanaw** is an entry to NASA Space Apps "Dancing with the SARs". We grew up wading through the floods of CAMANAVA (Caloocan, Malabon, Navotas, Valenzuela) and the Bulacan coast north of it, one of the most flood-prone and fastest-sinking urban coasts in the Philippines. NASA-ISRO's NISAR satellite revisits the area about every 12 days. Tanaw is an interactive map that uses those L-band radar passes to show how often each place flooded during the 2026 wet season and how the ground moved, then turns that into plain-language briefings for the people who live there.

The project is mid-build. Everything below describes what Tanaw is planned to do for the submission, not what is finished.

## Limitations first

- **Work in progress.** Features are planned for the submission. None is marked complete in this README yet.
- **Real data only.** No silent sample data, no Sentinel-1 relabelled as NISAR, and no number without a source.
- **NISAR files are not yet read.** The catalogue (NASA CMR) lists the 2026 GCOV and GUNW products over the study area, but the actual files are still to be read and processed. See [docs/DATA_MANIFEST.md](docs/DATA_MANIFEST.md).
- **Provisional data.** Most NISAR products in the season are labelled Provisional by the provider.
- **Short record.** The NISAR season is only a few months and about 11 passes on one track. Flood counts are not a long-term flood frequency.
- **Line-of-sight motion.** Ground motion from InSAR is along the satellite's line of sight, not true vertical, unless ascending and descending tracks are combined.
- **Exposure, not damage.** Priority zones show who and what is in flood-prone, sinking places. They are not damage or risk estimates.
- **Rain-to-flood and scenarios are exploratory.** With about 11 passes no model is fitted, and scenarios are not forecasts.
- **Different sensors are never merged.** Sentinel-1 (C-band) and Landsat are shown as context and are not combined numerically with NISAR (L-band).
- **Hypotheses only.** Explanations for flooding and sinking are labelled hypotheses, not causes.

## Challenge mapping

Feature codes refer to [docs/SUBMISSION_SCOPE.md](docs/SUBMISSION_SCOPE.md).

| Challenge asks for | Tanaw | Status |
|---|---|---|
| Interactive app using **NISAR** to track and visualize surface change | N1 Flood rhythm, N2 animation, N3 ground motion: all NISAR | in progress |
| Floodplains extending and retracting | N1 and N2: flood extent on every pass, June–November 2026 | in progress |
| Coastal subsidence and land deformation | N3: GUNW InSAR over the Manila Bay coast | in progress |
| Agricultural lands and crop changes | N4: L-band flooded vegetation in the Bulacan fields and fishponds | in progress |
| Change maps, time-series animations, dashboards | N2 animation, U1 swipe, U2 spot check, U3 story mode | in progress |
| Accessible to a broad audience | U3 story mode, U5 "How radar sees", U6 briefings in English and Filipino, U4 barangay search | in progress |
| Open-source and actionable | MIT licence, public demo, priority zones, briefing export, downloads | in progress |
| Study area such as a hometown or flooded neighbourhood | The team's own CAMANAVA, with P2 personal stories | in progress |
| Free NISAR data | ASF NISAR GCOV and GUNW (Provisional/V1), recorded in a manifest | in progress |
| Supplemental optical and GIS layers | WorldCover, WorldPop, OSM buildings, municipal boundaries, NASA POWER rainfall, Sentinel-1 history | in progress |
| Hypothesize physical drivers | N6: labelled hypotheses, each with a checked reference | in progress |
| Which polarizations show the change | N5: HH vs HV vs ratio, explained | in progress |
| Other frequencies from other sensors | C2: Sentinel-1 C-band context | in progress |
| Time series plus ancillary population and vegetation data | N1–N3 with WorldPop and WorldCover | in progress |
| Human drivers | N6 (groundwater pumping, reclamation, fishponds), C1 exposure | in progress |
| Personal context and stories | P2 and U7 "Our stories" pins | in progress |
| Interactive summary | U1 swipe, U3 story mode, the public web map | in progress |
| Future NISAR applications | P3 | in progress |

## Features (planned for the submission)

- **Flood rhythm (N1, N2):** how many of the season's NISAR passes saw water at each place, with a pass-by-pass animation and a chart against NASA POWER rainfall.
- **Ground motion (N3):** cumulative line-of-sight displacement from chained 12-day GUNW pairs, with a time series per point.
- **Flooded vegetation, polarizations, hypotheses (N4–N6):** HH/HV/ratio views and labelled hypotheses for why this is happening.
- **Priority zones and context (C1–C5):** places that flood often and are sinking, with population, buildings and barangay; Sentinel-1 then-and-now; rain-to-flood response; validation against independent sources.
- **History and future conditions (F1–F5):** timeline from 2000, rainfall history, optical then-and-now, seasonal outlook and conditional scenarios.
- **Experience (U1–U10):** swipe and spot check, guided Story Mode, find-my-barangay search, "How radar sees" cards, briefings in English and Filipino, "Our stories" pins, a public static demo and downloads.

## Data sources

Provenance, licences and retrieval dates are tracked in [docs/DATA_MANIFEST.md](docs/DATA_MANIFEST.md).

- NISAR L2 GCOV and GUNW via the [Alaska Satellite Facility (ASF) DAAC](https://asf.alaska.edu/) (collections found through [NASA CMR](https://cmr.earthdata.nasa.gov/))
- [NASA POWER](https://power.larc.nasa.gov/) daily rainfall
- [Open-Meteo](https://open-meteo.com/) seasonal forecast and historical APIs
- [WorldPop](https://www.worldpop.org/) population
- [OpenStreetMap](https://www.openstreetmap.org/) buildings and places
- [ESA WorldCover](https://esa-worldcover.org/) land cover
- [Sentinel-1](https://sentinels.copernicus.eu/web/sentinel/missions/sentinel-1) for regional context only

## Quick start

Backend (Python 3.12), from the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements-dev.txt
cd backend
uvicorn app.main:app --reload
```

Frontend (Node 20), in a second terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). API documentation is served at `/docs` on the backend.

Downloading NISAR files needs a free NASA Earthdata login. Set the token as an environment variable and never commit it:

```bash
export EARTHDATA_TOKEN=...
```

## Tests

```bash
cd backend
python -m unittest discover -s tests
cd ../frontend
npm run lint
npm run build
```

The same checks run in GitHub Actions (`.github/workflows/ci.yml`).

## Repository layout

| Path | Contents |
|---|---|
| `backend/app/` | FastAPI application |
| `backend/scripts/` | Numbered offline processing scripts |
| `backend/processing/` | Processing modules |
| `backend/tests/` | Backend unit tests |
| `backend/data/` | Local data and outputs (large raw products are not committed) |
| `frontend/` | Next.js web app |
| `docs/` | Scope, API contract and data manifest |

## Pipeline documentation

- [backend/COHERENCE_PIPELINE.md](backend/COHERENCE_PIPELINE.md): paired HyP3 coherence extraction, change mapping, input manifests and verification commands.
- [backend/DREI_P2_PIPELINE.md](backend/DREI_P2_PIPELINE.md)
- [backend/P3_PIPELINE.md](backend/P3_PIPELINE.md): NISAR ground-motion, vegetation, scenario and briefing modules.
- [docs/API_CONTRACT.md](docs/API_CONTRACT.md) and [docs/SUBMISSION_SCOPE.md](docs/SUBMISSION_SCOPE.md)

## Future of NISAR

Future work, not part of the current build: near-real-time flood alerts for local government units, nationwide subsidence monitoring, and crop-loss warning. Flood watch and evacuation planning are the first roadmap items.

## AI assistance

AI coding assistants were used in development; see the submission page for the full disclosure.

## Licence

[MIT](LICENSE). Copyright 2026 Tanaw contributors.
