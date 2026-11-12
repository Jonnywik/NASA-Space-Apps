// frontend/utils/sampleData.js
// SAMPLE data shaped like the real backend answers (checked against backend/app/coherence_api.py,
// p3_api.py, series.sample_point and briefing.build_briefing).
// Everything here is INVENTED. The UI must always show it with the SAMPLE badge.

export const SAMPLE_NOTE =
  "SAMPLE DATA: invented for layout testing, not a radar result.";

function box(
  id,
  west,
  south,
  east,
  north,
  areaKm2,
  meanLoss,
  category = "unknown",
  extra = {},
) {
  return {
    type: "Feature",
    properties: { id, areaKm2, meanLoss, category, ...extra },
    geometry: {
      type: "Polygon",
      coordinates: [
        [
          [west, south],
          [east, south],
          [east, north],
          [west, north],
          [west, south],
        ],
      ],
    },
  };
}

export const sampleEvents = [
  {
    id: "karding_2022",
    name: "Typhoon Karding (Noru), Sept 2022 [DEMO]",
    aoi: "Pampanga-Bulacan floodplain",
    beforeDate: "2022-09-19",
    afterDate: "2022-10-01",
    ready: true,
  },
  {
    id: "carina_2024",
    name: "Typhoon Carina (Gaemi) + habagat, July 2024 [DEMO]",
    aoi: "Manila Bay north coast (Bulacan-Pampanga-NCR)",
    beforeDate: "2024-07-10",
    afterDate: "2024-07-30",
    ready: true,
  },
];

export const sampleFloodExtent = {
  event: "karding_2022",
  aoi: "Pampanga-Bulacan floodplain (SAMPLE)",
  beforeDate: "2022-09-19",
  afterDate: "2022-10-01",
  dataKind: "synthetic",
  dataStatus: "synthetic",
  stats: {
    km2Flooded: 142.8,
    peopleExposed: 84500,
    householdsExposed: 21125,
    waterBeforeKm2: 38.4,
    waterAfterKm2: 181.2,
  },
  bbox: [120.72, 14.88, 120.86, 14.96],
  overlays: null,
  floodGeojson: {
    type: "FeatureCollection",
    features: [
      box("f1", 120.75, 14.9, 120.785, 14.945, 12.4, null, "flood"),
      box("f2", 120.795, 14.89, 120.83, 14.925, 9.8, null, "flood"),
      box("f3", 120.73, 14.93, 120.748, 14.952, 4.1, null, "flood"),
    ],
  },
};

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
  stats: {
    km2Changed: 2.4,
    changedPixelCount: 1500,
    byCategory: {
      vegetation: 0.9,
      construction: 0.6,
      damage: 0.5,
      unknown: 0.4,
    },
  },
  coverage: { commonValidPixelCount: 90000, eligiblePixelCount: 61000 },
  warnings: [SAMPLE_NOTE],
  interpretation:
    "Coherence decrease; not confirmed damage or causal attribution",
  assets: {},
  changeGeojson: {
    type: "FeatureCollection",
    features: [
      box("c1", 120.76, 14.9, 120.775, 14.912, 0.9, 0.42, "vegetation"),
      box("c2", 120.8, 14.93, 120.81, 14.94, 0.6, 0.55, "construction"),
      box("c3", 120.84, 14.88, 120.85, 14.89, 0.5, 0.74, "damage"),
      box("c4", 120.78, 14.95, 120.785, 14.956, 0.4, 0.33, "unknown"),
    ],
  },
  exposure: {
    available: true,
    dataKind: "synthetic",
    dataStatus: "synthetic",
    snapshotDate: "2026-11-05",
    snapshotCoverage: { completeness: "partial" },
    scope: "whole-event",
    summary: {
      countStatus: "partial",
      mappedHazardOverlapCount: null,
      partialMappedHazardOverlapCount: 412,
    },
  },
};

export const sampleGroundMotion = {
  event: "karding_2022",
  product: "ground-motion",
  runId: "sample-motion-run",
  dataKind: "synthetic",
  dataStatus: "synthetic",
  referenceEpoch: "2026-06-17",
  epochs: [
    "2026-06-17",
    "2026-06-29",
    "2026-07-11",
    "2026-07-23",
    "2026-08-04",
    "2026-08-16",
    "2026-08-28",
    "2026-09-09",
    "2026-09-21",
  ],
  regionalSummary: {
    medianRateMmPerYear: 28.4,
    validRateCellCount: 4200,
    selectedCellCount: 5000,
    medianValidEpochCount: 9,
  },
  // Sample spatial heatmap grid cells (mm/yr positive away from satellite)
  heatmapGeojson: {
    type: "FeatureCollection",
    features: [
      box("m1", 120.755, 14.905, 120.785, 14.935, 3.2, null, "motion", {
        rateMmPerYear: 36.2,
      }),
      box("m2", 120.785, 14.905, 120.815, 14.935, 3.2, null, "motion", {
        rateMmPerYear: 22.8,
      }),
      box("m3", 120.815, 14.905, 120.84, 14.935, 2.6, null, "motion", {
        rateMmPerYear: 9.5,
      }),
      box("m4", 120.755, 14.935, 120.795, 14.955, 2.8, null, "motion", {
        rateMmPerYear: -1.8,
      }),
    ],
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
      "2026-06-17",
      "2026-06-29",
      "2026-07-11",
      "2026-07-23",
      "2026-08-04",
      "2026-08-16",
      "2026-08-28",
      "2026-09-09",
      "2026-09-21",
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
    "the satellite of about 31.5 mm per year across 9 dates (96 days). This text is invented to test the briefing card layout.",
  facts: { rateMmPerYear: 31.5, validEpochCount: 9, spanDays: 96 },
  provenance: { note: "sample" },
  templateVersion: "sample-v1",
  dataKind: "synthetic",
  selectedYear: null,
  sourceRunIds: ["sample-run"],
};
