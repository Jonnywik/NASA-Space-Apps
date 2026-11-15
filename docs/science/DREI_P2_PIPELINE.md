# Drei P2: frequency, building overlap and coherence API

This adds three offline capabilities to the paired coherence pipeline. It does not acquire provider products or start background jobs. Existing flood endpoints remain compatible.

## Operator sequence

From `backend`, using the repository virtual environment:

```sh
../.venv/bin/python scripts/05_coherence_extract.py EVENT --inputs /inputs/pairs.json
../.venv/bin/python scripts/06_change_map.py EVENT
../.venv/bin/python scripts/09_publish_change.py EVENT --metadata data/output/EVENT/change_extent.json
```

Repeat for each unique, compatible dated comparison, preserving each output in its own directory with `--output-dir`. Use the returned immutable manifests as inputs to script 07. Script 08 consumes a published hazard run plus a dated, hash-bound local OSM snapshot. Both scripts expose their JSON contracts and options through module documentation and `--help`.

```sh
../.venv/bin/python scripts/07_change_frequency.py EVENT --comparison /runs/comparison1/manifest.json --comparison /runs/comparison2/manifest.json
../.venv/bin/python scripts/08_building_exposure.py EVENT --hazard-manifest /runs/change/manifest.json --snapshot-config /inputs/osm-snapshot.json
# For frequency exposure, choose and record the threshold explicitly:
../.venv/bin/python scripts/08_building_exposure.py EVENT --hazard-manifest /runs/frequency/manifest.json --snapshot-config /inputs/osm-snapshot.json --frequency-threshold 0.5
```

Snapshot JSON declares `schemaVersion: "1.0"`, `dataKind`, `sourceDate`, source/provenance, `geojsonPath`, the footprint file's `sha256`, and `coverage` with a polygon `geometry`, `crs`, and `completeness: "complete"|"partial"|"unknown"`. Complete is an explicit operator assertion, not an automatic inference from file existence. Footprint properties contain `osmType` and positive numeric `osmId`. Supply footprint CRS in the GeoJSON or `geojsonCrs`. Optional region GeoJSON uses unique `properties.regionId` polygon features. Inputs are local, dated snapshots; no live OSM query is required.

The normalized change assets are `changeMask` (0/1 with nodata) and `changeGeometry` (WGS84 GeoJSON), plus the QA image. Imports verify original output hashes and retain dates, thresholds, source identities and synthetic labeling. Importing a run does not validate its science.

## Interpretation

Frequency is detection count divided by valid comparison count at each pixel. Its default minimum support is two comparisons. Counts remain available below the minimum; frequency is nodata there. Different coverage contributes different denominators. Shared acquisitions/overlapping periods are disclosed; frequency is not an independent probability, confirmed damage or evidence of storm causation. Duplicate logical comparisons must not inflate support.

All comparison grids use the same normalized CRS before frequency processing. Resolution and extent may differ. The legacy detector's finite zero cells include supported baseline-threshold non-detections; frequency does not reconstruct an unavailable eligibility mask or claim that every zero had stable baseline coherence.

Building exposure means mapped building footprint overlap with positive area. OSM way and relation identifiers occupy separate namespaces. Duplicate identities are counted once; combined selected regions are unioned before totals. Building counts do not establish damage, occupancy or population. Missing/incomplete snapshots and missing hazard support remain explicitly unavailable or partial. A measured zero requires supported coverage.

## API and publication

`GET /api/v1/coherence-loss` accepts `event`, optional `product=change|frequency`, optional `runId`, optional `exposureRunId`, and registered `regionId` where supported. The API reads published outputs only. Building summaries must reference the selected hazard run; stale exposure cannot silently attach to a different result.

Products are `coherence-change`, `change-frequency` and `building-exposure`. They reuse the existing immutable catalog beneath `data/output/<event>/p3/<product>/<runId>/`; `p3` is the historical storage directory name, not a claim about the task's phase. Assets are served through registered hash-checked URLs. Event capabilities report availability independently of the original flood `ready` field.

Synthetic runs can be inspected by explicit run ID and remain visibly synthetic. Real runs require a review receipt and promotion with `17_review_product.py`, as documented in `P3_PIPELINE.md`. Publication failures preserve prior selected runs; analytical adjustments create separate versions. Large inputs/outputs stay outside Git.

## Verification and data blockers

Run `../.venv/bin/python -m unittest discover -s tests -v` from `backend`. New tests cover frequency denominators/compatibility, building deduplication/coverage, API contracts and actual mapper-to-frequency/exposure integration, alongside existing regressions.

Integrated verification: 112 tests pass (88 existing and 24 added), compilation passes, and all three new CLI help commands run. An application smoke check confirms the route is registered and returns `data_unavailable` for an event without a published real result. This is software verification on fixtures.

Real completion requires multiple reviewed compatible HyP3 comparisons and dated OSM footprints with declared coverage. These inputs are absent for Carina, Karding and Habagat. Automated fixture checks do not establish real-event accuracy. Selected AOI arrays are processed in memory; limit AOI size to available RAM.
