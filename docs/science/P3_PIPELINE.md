# Kobe P3 backend

P3 adds seven offline processing modules and read-only APIs. Existing flood routes remain available. No frontend changes are included.

## Install and verify

From the repository root, create/activate a Python 3.12 virtual environment and install `backend/requirements-dev.txt`. With the repository's `.venv`, run:

```sh
cd backend
../.venv/bin/python -m unittest discover -s tests -v
../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `/docs` for request schemas. Heavy processing runs through scripts; HTTP requests never submit provider jobs. New read routes under `/api/v1` are `/ground-motion`, `/subsidence` (same LOS semantics), `/ground-motion/point`, `/vegetation`, `/scenario-inputs`, `/projection`, and `/briefing`. Supply `event` and optionally `runId`; projection also requires `scenarioId` and `year`. Projection briefings require a `year` when several years are published. Point requests use WGS84 `lon` and `lat`. The event list adds capabilities; its original `ready` flag still refers only to flood output.

## Processing order

Each script exposes `--help`; module docstrings describe its JSON inputs. Paths supplied to operator CLIs are local files. Never put provider credentials, raw products or production derived rasters into Git.

| Script | Input → output | Critical prerequisites |
|---|---|---|
| `10_ingest_nisar.py` | Explicit HDF5/ARIA source profile → `gunw` or `gcov` | File hashes, dataset paths, georeferencing, units, sensor/track/version metadata; GUNW sign/wavelength/correction state |
| `11_phase_to_los.py` | GUNW + reference config → `los-pair` | Coherent positive connected component; stable reference evidence for observations |
| `12_motion_series.py` | Compatible pair manifests → `ground-motion` | Shared source basis, reference geometry and correction state |
| `13_gcov_biomass.py` | GCOV + reference plots → calibration; calibration + GCOV → biomass; regional metrics → fusion | Independent spatial validation, declared timing and acceptance limits |
| `14_scenario_inputs.py` | Terrain + water levels + masks → `scenario-inputs` | Common vertical datum/reference epoch, reviewed projection baseline, coast seeds |
| `15_projection.py` | Motion + scenario config (+ prepared terrain) → `projection` | Reviewed horizon; exposure additionally needs supported vertical motion |
| `16_briefing.py` | Product manifest + optional registered region/exposure snapshot → `briefing` | Factual structured metrics; exact input run matching |
| `17_review_product.py` | Product manifest + review receipt → current pointer | Qualified human review of the exact run and upstream lineage |

The adapters are explicit layout readers. Fixture tests do not establish compatibility with every NISAR/ARIA release; a production profile must be substantiated by its pinned provider specification and an actual sample. Inspect the provider layout and correction state before declaring it supported. Historical events must keep their actual sensor identities.

Example command sequence from `backend` (replace paths with actual manifests/configs):

```sh
python scripts/10_ingest_nisar.py pilot --inputs /inputs/source.json
python scripts/11_phase_to_los.py pilot --inputs /runs/gunw/manifest.json --config /inputs/reference.json
python scripts/12_motion_series.py pilot --pair /runs/pair1/manifest.json --pair /runs/pair2/manifest.json
python scripts/14_scenario_inputs.py pilot --inputs /inputs/terrain-water.json
python scripts/15_projection.py pilot --motion-manifest /runs/motion/manifest.json --terrain-manifest /runs/terrain/manifest.json --config /inputs/scenario.json
python scripts/16_briefing.py pilot --manifest /runs/projection/manifest.json --year 2030
```

Repeat ingestion/conversion for every pair and include the full acquisition network in script 12. Two pairs can provide displacement, but cannot meet the six-epoch rate floor. The event must also be registered in `events.json` before its products can be served by the API. The tests create a disposable synthetic pilot rather than adding an unverified NISAR period to the real event registry.

The separate calibrated biomass path uses:

```sh
python scripts/13_gcov_biomass.py train --gcov /runs/gcov/manifest.json --plots /inputs/reference-plots.geojson --config /inputs/calibration.json
python scripts/13_gcov_biomass.py predict --gcov /runs/gcov/manifest.json --calibration /runs/calibration/manifest.json --regions /inputs/regions.geojson
python scripts/13_gcov_biomass.py fuse --event pilot --biomass-regions /runs/biomass/manifest.json --ground-motion-regions /inputs/motion-region-summaries.json
```

Motion regional records use `series.summarize_region(manifest, boolean_mask)` and a registered `regionId`, wrapped in a JSON object with `event`, `runId`, `dataKind`, lineage, native resolution and `regions`. Use the same region definitions as the biomass polygons. Fusion preserves the streams' separate observation periods; it does not manufacture temporal alignment or causal claims.

## Publication and scientific review

Immutable run files live in `data/output/<event>/p3/<product>/<runId>/`. Assets are SHA-256 bound to the manifest. Publication writes a staging directory and publishes the manifest with the run; failed writes preserve the prior current pointer. Current products require explicit review. A synthetic run may be selected for a demonstration, but stays synthetic and cannot be promoted to validated data. An explicit synthetic `runId` can be inspected without a current pointer.

For real observations/derived/scenario products, supply a review JSON to script 17:

```json
{
  "reviewer": "reviewer identity",
  "reviewedAt": "2026-10-29T00:00:00Z",
  "status": "validated",
  "manifestSha256": "SHA-256 of the exact immutable manifest.json",
  "sourceRunIds": ["exact values from manifest.sourceRunIds"],
  "evidence": ["review report or independently checked evidence reference"]
}
```

```sh
python scripts/17_review_product.py /path/to/manifest.json /path/to/review.json
```

The receipt records an operator's scientific review assertion. Software cannot certify the reviewer or independently inspect the linked evidence. Review must cover source identity, sign, corrections, reference stability, calibration and datum/scenario assumptions as applicable. Changing a manifest invalidates its receipt. Unreviewed real runs return `review_required`, never a ready map. Missing products return `data_unavailable`; invalid year/scenario/region and outside coverage have separate responses. Assets are served only through registered hash-checked manifests.

Implementation status and data status are separate. Run publication defaults implementation status to `pending`; automated fixture verification is recorded in test evidence, not silently converted into scientific validation. Missing values stay null/nodata and are distinct from a measured zero.

## Interpretation

- LOS displacement/rates are positive away from the satellite, in mm and mm/year. They are relative to a spatial reference and temporal reference epoch. `/subsidence` does not infer vertical movement.
- Rates require at least six connected epochs over 90 days. These are engineering floors. Fit residual/error diagnostics omit unmodeled atmospheric, orbital, reference and seasonal effects.
- GCOV power is not biomass. The supported calibrated model uses positive HHHH/HVHV converted to dB, standardized ridge regression (alpha 1, unpenalized intercept) on log1p biomass, with independent acceptance limits. Predictions outside training feature ranges are unavailable.
- Terrain can represent surface features. Datum, acquisition date, baseline epoch and supplied adjustments remain part of the scenario interpretation. Terrain and water sources explicitly declare `positiveDirection` (`up`/`down`); outputs use positive up. `uncertaintyMetres` stays in metres even if source heights use feet. Component water sums have exactly one absolute level and separately declared height anomalies; an absolute datum offset is applied once.
- Exposure is a static, coast-connected screening scenario using supplied water levels and reviewed vertical interpretation. It is not a hydrodynamic flood forecast. Absent asset/population snapshots cannot produce counts or damage claims.
- Briefings are deterministic templates. They describe supplied facts, coverage and limitations without an external LLM.

## Current data blockers

No genuine NISAR products, stable-reference evidence, biomass reference plots, compatible elevation/water-level packages or exposure snapshots are present. ASF/Earthdata destinations and credentials are unavailable in this managed environment. All numerical verification uses disposable synthetic fixtures. Real-data validation remains incomplete until those prerequisites are supplied and reviewed.

The ingestion adapter supports explicit window subsets, and network solving groups validity patterns within tiles. Some stages still materialize complete selected AOI arrays/series in memory. Bound the input AOI/window and size it to available RAM; this release is not an out-of-core continental processing service.

## Implementation verification

The integrated change passes 88 unittest checks, including the 17 existing coherence tests. The disposable end-to-end fixture exercises HDF5 → normalized phase → referenced pair differences → a six-epoch network recovering 12 mm/year → compatible terrain/water inputs → annual exposure polygons → year-specific briefing and API responses. Separate fixtures cover ARIA NetCDF, calibrated biomass/fusion, coast connectivity, missing support, review receipts, hash/path rejection, and staged-write failure recovery. A 64×64 network fixture gives consistent results across tile sizes. Compilation, all eight CLI help commands and dependency checks pass. These checks establish software behavior on fixtures; they do not complete scientific validation.
