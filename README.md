# Tanaw

[![CI](https://github.com/Jonnywik/NASA-SA-Final/actions/workflows/ci.yml/badge.svg)](https://github.com/Jonnywik/NASA-SA-Final/actions/workflows/ci.yml)

Tanaw is a work-in-progress NASA Space Apps entry for exploring flood and land-motion data in CAMANAVA and the Bulacan coast.

## Limitations first

- **No real NISAR run yet.** Earthdata access is deferred. The catalogue contains real granule metadata, but no NISAR flood, motion or priority result has been verified from those files. Generated flood fixtures are explicitly synthetic and are not observations.
- **Validation remains incomplete.** No independent agreement or threshold-sensitivity result can be claimed without real NISAR outputs. See [validation](docs/VALIDATION.md).
- **Motion is line-of-sight**, not necessarily vertical motion. A short seasonal record is not a long-term rate. Exposure is not damage, and conditional scenarios are not predictions.
- NASA POWER, Open-Meteo and places caches contain retrieved data; their resolution, age and coverage limit interpretation. OSM building completeness is unknown. Sentinel-1 is separate context, never relabelled as NISAR.
- Filipino text awaits the user's review; the complete [review sheet](docs/FIL_REVIEW.md) includes UI strings, hypotheses and briefing templates. No personal stories are invented. Frontend integration builds, but visual and keyboard checks remain unverified because laptop browser control stopped; no public demo was deployed.

## Challenge mapping

Statuses describe software and available evidence, not a verified submission. Feature codes are in [the scope](docs/SUBMISSION_SCOPE.md).

| Challenge asks for | Tanaw | Status |
|---|---|---|
| NISAR surface change, flood extent and animation | Flood rhythm and pass views | Done with synthetic data; real processing blocked |
| Coastal deformation | GUNW processing and line-of-sight series | Partial; real motion unverified |
| Agricultural and vegetation change | Flooded vegetation and polarization processing | Done with synthetic data; real results unverified |
| Maps, time series and accessible summaries | Workspace, search, spot check and bilingual briefing | Software integrated and built; browser and Filipino review pending |
| Actionable information | Priority-mask and exposure software, briefing exports | Partial; no observed priority result |
| Supplemental GIS and rainfall | Places and climate caches and processing | Done with retrieved data; subject to source limitations |
| Independent validation | Comparison software and source research | Partial; no real NISAR comparison |
| Physical drivers and personal context | Referenced hypotheses and team stories | Four sourced hypotheses integrated; hypotheses are not findings; stories require team-authored text |
| Other sensors and future applications | Sentinel-1 context and future ideas | Partial; separate from NISAR |
| Open source and public access | MIT licence; public demo | Partial; demo not verified |

## Data sources

See [the data manifest](docs/DATA_MANIFEST.md) for sources, dates, hashes and gaps. The default NISAR catalogue selection is track 140 ascending, frame 009; catalogue coverage does not prove usable pixel coverage.

## Reproduce locally on Windows

From PowerShell at the repository root, install Python 3.12 and Node 20, then:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend/requirements-dev.txt
cd backend
..\.venv\Scripts\python -m uvicorn app.main:app --reload
```

In a second PowerShell window at the repository root:

```powershell
cd frontend
npm ci
npm run dev
```

Open http://localhost:3000; backend API documentation is at http://127.0.0.1:8000/docs. The frontend defaults to that API; NEXT_PUBLIC_USE_FIXTURES=1 enables synthetic frontend fixtures for development.

To generate **synthetic development flood output** from the cached catalogue dates, with the backend stopped, run from `backend/`:

```powershell
..\.venv\Scripts\python scripts/22_nisar_synthetic_demo.py
```

This creates synthetic pixels, not NISAR observations, and refuses to replace an observed product unless forced. Climate and places caches can be refreshed with scripts 30_fetch_climate.py and 40_fetch_places.py; refreshing may change data and requires network access. Their existing manifests record the retrieved versions. Real NISAR processing requires Earthdata access, first-file checks and calibration described in [the runbook](docs/NISAR_RUNBOOK.md); it has not been performed for this build. Thus there is no sequence yet that reproduces submitted real NISAR products.

## Tests

From the repository root:

```powershell
cd backend
..\.venv\Scripts\python -m unittest discover -s tests
cd ../frontend
npm run lint
npm run test:api
npm run build
```

CI is configured in .github/workflows/ci.yml; run results depend on the current checkout.

## Integration checks and recording

The spot-check card uses `/api/v1/spot-check` for its facts. It offers English and Filipino printable HTML briefings and a CSV download. The real cached boundary lookup places the test point `120.957, 14.665` in Niugan, City of Malabon. Exports were checked directly against those API facts; unavailable NISAR, motion and priority values remain missing with reasons. The Independent comparison card stays unavailable until a compatible observed comparison exists.

The pass legend now uses the backend renderer's shared colours. Data credits are reachable in the Limits drawer. Source findings and unresolved coverage checks are in [SOURCE_REVIEW.md](docs/SOURCE_REVIEW.md); the remaining laptop and recording checks are in [INTEGRATION_CHECK.md](docs/INTEGRATION_CHECK.md). These checks do not establish a working observed NISAR submission.

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
