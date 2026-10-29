# Coherence change pipeline

This pipeline prepares two matched coherence rasters and maps places where coherence decreased during an event. A detected decrease is a change indicator. It does not establish damage or storm causation.

The implementation is verified with synthetic fixtures. Real-data validation is blocked until Kobe supplies provider products and confirms their pair metadata. Do not treat the example below as an observation or a scientific result.

## Input manifest

Place `pairs.json` and its source products under `data/raw/<event>/insar/`. Source paths are relative to the manifest. A ZIP must contain exactly one `*_corr.tif`; point directly to a GeoTIFF when a provider archive contains multiple candidate coherence layers. Each pair must describe the same orbit, flight direction, polarization, and processing version. The two ordered pairs must share scene B and its acquisition date, with A < B < C. Both baseline dates must precede the event window, and C must follow it.

The following is a complete synthetic placeholder manifest. The dates, identifiers, paths, and provider labels are illustrative only; they are not real acquisitions. Replace every placeholder using provider records before processing an event.

```json
{
  "event": "test_event",
  "eventWindow": {
    "start": "2024-07-22",
    "end": "2024-07-25"
  },
  "dataKind": "synthetic",
  "pre": {
    "source": "synthetic_pre_product.zip",
    "productId": "SYNTH-PRE-PLACEHOLDER",
    "sceneIds": ["SYNTH-A-PLACEHOLDER", "SYNTH-B-PLACEHOLDER"],
    "acquisitionDates": ["2024-07-05", "2024-07-17"],
    "relativeOrbit": 123,
    "flightDirection": "ASCENDING",
    "polarization": "VV",
    "processingVersion": "synthetic-fixture-1"
  },
  "co": {
    "source": "synthetic_co_product.zip",
    "productId": "SYNTH-CO-PLACEHOLDER",
    "sceneIds": ["SYNTH-B-PLACEHOLDER", "SYNTH-C-PLACEHOLDER"],
    "acquisitionDates": ["2024-07-17", "2024-07-29"],
    "relativeOrbit": 123,
    "flightDirection": "ASCENDING",
    "polarization": "VV",
    "processingVersion": "synthetic-fixture-1"
  }
}
```

The pair durations in that example are equal by construction. Real product durations can differ; the extractor records a comparability warning so the pair choice can be reviewed. It rejects incompatible track metadata, a missing shared scene, unconfirmed chronology, different processing versions, duplicate products, unknown event IDs, and declarations that conflict with embedded product metadata. Supply missing metadata from provider records; do not infer it from filenames.

Input rasters must be georeferenced, single-band coherence values in `[0, 1]`. The extractor honors raster masks and declared nodata while preserving a legitimate zero. It does not convert coherence to dB and does not apply a water mask. Current regional outputs use EPSG:32651; the default square metre resolution is based on the coarser native product resolution. Explicit resolution cannot be finer than that default.

## Run

Run commands from `backend/` with the project environment:

```bash
source ../.venv/bin/activate
python scripts/05_coherence_extract.py test_event \
  --inputs data/raw/test_event/insar/pairs.json
python scripts/06_change_map.py test_event \
  --pre-min 0.5 --loss-min 0.3 --min-pixels 10 --simplify 15
python -m unittest discover -s tests -v
```

For real use, replace `test_event` and the synthetic placeholders with the registered event ID and confirmed input manifest. Both commands default to `data/output/<event>/`. Use `--output-dir` to retain a separate parameter run. Existing outputs require `--overwrite` before replacement.

If extraction and change products use separate directories, pass the extraction directory to the mapper:

```bash
python scripts/05_coherence_extract.py carina_2024 \
  --inputs data/raw/carina_2024/insar/pairs.json \
  --output-dir /tmp/carina-coherence
python scripts/06_change_map.py carina_2024 \
  --input-dir /tmp/carina-coherence \
  --output-dir /tmp/carina-change \
  --pre-min 0.5 --loss-min 0.3 --min-pixels 10 --simplify 15
```

The extractor aligns both sources to the same EPSG:32651 AOI grid, reprojects coherence with bilinear resampling, and carries source validity separately with nearest-neighbor resampling. It writes:

- `coh_pre.tif` and `coh_co.tif`: float32 values with NaN nodata and matching dimensions, affine transform, and CRS.
- `coherence_info.json`: event and pair dates, scene and source identifiers, source and prepared-raster SHA-256 hashes, native and output grids, valid-pixel coverage, parameters, warnings, timestamp, and code version. Each TIFF is tagged with the extraction ID, event ID, and data kind.

The change step verifies those hashes, tags, units, and grid alignment. It does not silently repair a mismatched prepared pair. For each raster it uses the same common-valid 3×3 neighborhood, requires a valid center and at least five valid neighbors, then calculates signed loss as smoothed pre-event coherence minus smoothed event-pair coherence. Positive values indicate a coherence decrease. The default rule requires pre-event coherence of at least `0.5` and loss of at least `0.3`; both boundaries are inclusive with a `1e-6` numerical tolerance. Eight-connected components smaller than ten pixels are removed by default.

The change step writes:

- `change_mask.tif`: `1` for retained detections, `0` for observed pixels without a retained detection (including pixels below the baseline threshold), and `255` where observations lack valid common support.
- `change.geojson`: one feature per retained component, with a stable component ID, measured `areaKm2`, and `meanLoss`. Features are simplified for display in metres and transformed to longitude/latitude. Zero detections produce an empty FeatureCollection.
- `change_extent.json`: event and pair provenance, run and extraction IDs, data kind, event bounds, parameters, warnings, output hashes, pixel/area coverage, raw and retained counts, polygon count, and authoritative `stats.km2Changed`.
- `06_change_check.png`: pre-event coherence, event-pair coherence, signed loss, and retained detections for visual review. Synthetic runs are marked as synthetic.

Area totals use retained pixel counts and affine pixel area in verified metre units. They are not calculated from simplified display polygons. `valid` coverage describes common observations; `eligible` coverage describes common pixels that also meet the baseline-coherence threshold. Low baseline coherence is excluded from change eligibility and is not evidence of stability. Partial coverage is reported as partial and must not be presented as a whole-event estimate.

## Interpretation and validation

Inspect the source rasters, valid-data edges, pair dates, coverage, warnings, histograms, and QA image before accepting an output. Unequal acquisition intervals affect coherence comparability even when rasters share a grid. Keep alternative parameter runs separate and document why the selected thresholds changed.

Synthetic fixtures check input validation, nodata behavior, grid matching, thresholds, neighborhood support, connected components, area, empty results, hashes, and output writing. They do not establish real-data accuracy. Until real HyP3/InSAR products arrive and are reviewed for Carina, Karding, and Habagat, report the pipeline as implementation-verified on synthetic fixtures with real-data validation blocked. Do not claim a frequency from one before/after comparison, populate downstream damage categories from this mask, or describe detections as confirmed damage.
