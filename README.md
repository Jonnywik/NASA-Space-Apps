# Tanaw

NISAR sees CAMANAVA and the Bulacan coast through clouds and rain. Tanaw explores what its L-band radar can show about water and wetness, and what it cannot yet see. Eleven track 140 ascending passes from 23 June to 2 November 2026 capture open water outside the usual water mask, mainly at the urban fringe, wetlands and coast. In the regenerated v6 product, 0.3721 km² (about 0.37 km²) is classified as open water on at least half of valid passes, and 0.9919 km² at least once. These are rule-dependent measurements and do not map flooded city streets. See the [real-run notes](docs/NISAR_RUNBOOK.md#real-run-results-15-nov-2026-coordinator-first-real-nisar-read).

## Limitations first

- **Urban street flooding is not visible in this open-water layer.** Water between buildings can brighten radar returns, while narrow streets, shadow and layover complicate detection. A missing signal does not mean the city did not flood.
- Passes were around **05:30 Manila time**, roughly every 12 days; floods between passes or after the morning acquisition can be missed. IMERG gives coarse rainfall timing, not street-level rain.
- **Ground motion and priority zones are unavailable.** The short GUNW record is dominated by ionospheric noise and the phase sign and correction state need further work; no motion measurement is presented. Exposure is not damage.
- Most selected GCOV products and all selected SME2 products are provisional and may change. Water thresholds and the 2021 WorldCover mask affect the result. Three OPERA comparisons are more than 48 hours apart from the NISAR passes, compare total water including coast and permanent water, and are not flood accuracy. See [validation](docs/VALIDATION.md).
- Soil moisture is a provisional 200 m product with recommended retrievals on only about 5–7% of study cells; it is not served as a flood layer. NASA POWER can overestimate dry-season rain, WorldPop is a 2020 model, and OSM building completeness is unknown. Conditional scenarios are not predictions.
- Filipino wording, independent user testing, public deployment and the recording require confirmation; none is claimed here. Sentinel-1 is separate context, never NISAR.

## Challenge mapping

Statuses describe the evidence and implementation; they do not imply a verified deployment. See the [scope](docs/SUBMISSION_SCOPE.md) and [API contract](docs/API_CONTRACT.md).

| Challenge asks for | Tanaw | Status |
|---|---|---|
| NISAR surface water and time series | GCOV open water outside usual water over 11 passes | real-but-limited |
| Agricultural and vegetation change | Possible flooded vegetation and polarizations | real-but-limited |
| Coastal deformation | GUNW examined; no defensible motion result | unavailable |
| Maps, search and summaries | Workspace, places, spot check and briefing | real-but-limited |
| Actionable information | Place exposure and briefing; priority zones require motion | real-but-limited |
| Rainfall and GIS context | IMERG, POWER, WorldCover, WorldPop, boundaries and OSM | real-but-limited |
| Independent validation | Three near-date OPERA total-water comparisons | real-but-limited |
| Physical drivers | Sourced hypotheses, not established causes | real-but-limited |
| Personal context | Team-authored stories | unavailable |
| Other sensors | Sentinel-1 historical context | real-but-limited |
| Vertical motion | Requires compatible multi-geometry evidence | cut |
| Open source and public access | MIT licence; deployed demo not verified | real-but-limited |

## Data sources

The [data manifest](docs/DATA_MANIFEST.md) records granules, versions, retrieval dates and source limitations. The derived NISAR product is large and gitignored; the cached catalogue and rule do not themselves contain its pixels.

For NISAR passes on 15 September, 9 October and 2 November, agreement with OPERA was 0.8712, 0.8499 and 0.8750; F1 was 0.7291, 0.6662 and 0.7386; IoU was 0.5737, 0.4994 and 0.5855. Each reference was acquired about 48 hours 15 minutes later. The comparison includes coastal and permanent water; OPERA may also include inundated vegetation. These scores are not ground-truth flood accuracy.

Changing both thresholds by -1, 0 and +1 dB yields half-or-more areas of 0.0230, 0.3721 and 0.3588 km². Permanent water is recalculated for each threshold, so the results are not necessarily monotonic and are not a confidence interval.

## Reproduce locally on Windows

Use Python 3.12 and Node 20. An Earthdata account and access to ASF and NASA GES DISC are needed for remote reads. Set `EARTHDATA_TOKEN` privately in the **same PowerShell session** used for processing; never save or print it in the repository. Range reads require network access. Script 20 replaces the existing local NISAR output. Fresh catalogue queries can select newly released products, so retain the committed manifest to reproduce the recorded selection; compare it with the refreshed manifest before using new results.

From the repository root:

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
..\.venv\Scripts\python -m uvicorn app.main:app --reload
```

Scripts 25 and 31 refresh their caches and may reflect newer upstream data. Check [the runbook](docs/NISAR_RUNBOOK.md) for the first-file checks and scientific interpretation. In a second PowerShell window at the repository root:

```powershell
cd frontend
npm ci
npm run dev
```

Open http://localhost:3000; the API documentation is at http://127.0.0.1:8000/docs. The frontend defaults to this API. `NEXT_PUBLIC_USE_FIXTURES=1` enables synthetic development fixtures; they are not observations.

## Downloads and season animation

`GET /api/v1/downloads?area=camanava_2026` lists the available real-data exports with attribution and licence information. Follow an entry's `url` to download it. Raster entries require the local NISAR product; absent files are omitted rather than replaced by samples.

From `backend/`, build the animation with `..\.venv\Scripts\python scripts/28_nisar_timelapse.py`. It uses the existing real product and IMERG cache without regenerating the radar results. View it at `/api/v1/nisar/timelapse.gif?area=camanava_2026`. A changed input requires rebuilding the animation.

## Tests

```powershell
cd backend
..\.venv\Scripts\python -m unittest discover -s tests
cd ../frontend
npm run lint
npm run test:api
npm run build
```

## Further documentation

- [Data manifest](docs/DATA_MANIFEST.md), [validation](docs/VALIDATION.md), [source review](docs/SOURCE_REVIEW.md), and [integration checks](docs/INTEGRATION_CHECK.md)
- [NISAR runbook](docs/NISAR_RUNBOOK.md), [API contract](docs/API_CONTRACT.md), and [submission scope](docs/SUBMISSION_SCOPE.md)
- [Coherence pipeline](backend/COHERENCE_PIPELINE.md), [P2 pipeline](backend/DREI_P2_PIPELINE.md), and [P3 pipeline](backend/P3_PIPELINE.md)

## AI assistance and licence

AI coding assistants were used in development. Record the full disclosure on the submission page. [MIT licence](LICENSE), copyright 2026 Tanaw contributors.
