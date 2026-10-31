// frontend/utils/sampleData.js
// SAMPLE data shaped like the real backend answers (checked against backend/app/coherence_api.py,
// p3_api.py, series.sample_point and briefing.build_briefing on Oct 31, 2026).
// Everything here is INVENTED. The UI must always show it with the SAMPLE badge.
// Open the app with ?sample=1 to use it. Delete or replace when real products exist.

export const SAMPLE_NOTE = "SAMPLE DATA: invented for layout testing, not a radar result.";

// A few small boxes near Calumpit, Bulacan, drawn as GeoJSON (lon, lat order).
function box(id, west, south, east, north, areaKm2, meanLoss) {
  return {
    type: "Feature",
    properties: { id, areaKm2, meanLoss }, // real property names to be confirmed from change.geojson
    geometry: {
      type: "Polygon",
      coordinates: [[[west, south], [east, south], [east, north], [west, north], [west, south]]],
    },
  };
}

export const sampleCoherenceLoss = {
  event: "karding_2022",
  product: "coherence-change",
  productView: "change",
  runId: "sample-run",
  dataKind: "synthetic",
  dataStatus: "synthetic",
  prePair: ["2022-09-07", "2022-09-19"],
  coPair: ["2022-09-19", "2022-10-01"],
  parameters: { preMin: 0.5, lossMin: 0.3, minPixels: 10 },
  stats: { km2Changed: 2.4, changedPixelCount: 1500 },
  coverage: { commonValidPixelCount: 90000, eligiblePixelCount: 61000 },
  warnings: [SAMPLE_NOTE],
  interpretation: "Coherence decrease; not confirmed damage or causal attribution",
  assets: {},
  changeGeojson: {
    type: "FeatureCollection",
    features: [
      box("c1", 120.76, 14.9, 120.775, 14.912, 0.9, 0.42),
      box("c2", 120.8, 14.93, 120.81, 14.94, 0.6, 0.37),
      box("c3", 120.84, 14.88, 120.85, 14.89, 0.5, 0.45),
      box("c4", 120.78, 14.95, 120.785, 14.956, 0.4, 0.33),
    ],
  },
  // Real answers: exposure.available is false (with a reason) until a snapshot exists.
  exposure: {
    available: true,
    dataKind: "synthetic",
    dataStatus: "synthetic",
    snapshotDate: "2026-11-05",
    snapshotCoverage: { completeness: "partial" },
    scope: "whole-event",
    summary: { countStatus: "partial", mappedHazardOverlapCount: null, partialMappedHazardOverlapCount: 412 },
  },
};

export const sampleGroundMotionPoint = {
  event: "karding_2022",
  runId: "sample-run",
  dataKind: "synthetic",
  dataStatus: "synthetic",
  point: {
    status: "ok",
    reason: null,
    longitude: 120.8,
    latitude: 14.93,
    epochs: [
      "2026-06-17", "2026-06-29", "2026-07-11", "2026-07-23", "2026-08-04",
      "2026-08-16", "2026-08-28", "2026-09-09", "2026-09-21",
    ],
    // mm, positive = away from the satellite (relative to the first epoch)
    displacementMm: [0, 1.1, 2.3, 2.9, 4.2, 5.0, 6.4, 7.1, 8.3],
    validEpochCount: 9,
    spanDays: 96,
    rateMmPerYear: 31.5,
    rateStandardErrorMmPerYear: 2.1,
    fitResidualMm: 0.4,
  },
};

export const sampleBriefing = {
  text:
    "SAMPLE briefing. In the selected area the sample ground-motion product shows relative movement away from " +
    "the satellite of about 31 mm per year. This text is invented to test the briefing card layout.",
  facts: { rateMmPerYear: 31.5, validEpochCount: 9, spanDays: 96 },
  provenance: { note: "sample" },
  templateVersion: "sample",
  dataKind: "synthetic",
  selectedYear: null,
  sourceRunIds: ["sample-run"],
};
