// frontend/utils/changeFilter.js  -  small pure helpers for the Tier 2 change layer.
// No React in here, so they are easy to test.

export const DEFAULT_LOSS_MIN = 0.3;
export const LOSS_SLIDER_MAX = 0.9;

// Strength bands (colour = how strong the coherence loss is, NOT what kind of change it is).
export const LOSS_BANDS = [
  { min: 0.7, color: "#dc2626", label: "Very strong (≥ 0.7)" },
  { min: 0.5, color: "#f97316", label: "Strong (0.5 – 0.7)" },
  { min: 0, color: "#facc15", label: "Moderate (< 0.5)" },
];

// Land-cover context categories (used when polygons carry properties.category).
export const CHANGE_CATEGORIES = [
  { key: "vegetation", label: "Likely vegetation loss", color: "#22c55e" },
  { key: "construction", label: "Likely new construction", color: "#f59e0b" },
  { key: "damage", label: "Likely flood-overlap change", color: "#ec4899" },
  { key: "unknown", label: "Other / unclassified", color: "#94a3b8" },
];

export function hasCategoryData(features) {
  return (
    Array.isArray(features) &&
    features.some((f) => Boolean(f?.properties?.category))
  );
}

export function categoryColor(cat) {
  return (CHANGE_CATEGORIES.find((c) => c.key === cat) ?? CHANGE_CATEGORIES[3])
    .color;
}

export function lossColor(loss) {
  if (typeof loss !== "number") return "#f59e0b";
  return (
    LOSS_BANDS.find((b) => loss >= b.min) ?? LOSS_BANDS[LOSS_BANDS.length - 1]
  ).color;
}

export function lossFloor(coherence) {
  const v = coherence?.parameters?.lossMin;
  return typeof v === "number" && Number.isFinite(v) ? v : DEFAULT_LOSS_MIN;
}

// Keep polygons whose mean coherence loss is at least minLoss, area >= minAreaKm2,
// and (if category data exists and activeCategories is provided) matching category.
export function filterChangeFeatures(
  features,
  minLoss,
  minAreaKm2 = 0,
  activeCategories = null,
) {
  const list = Array.isArray(features) ? features : [];
  return list.filter((f) => {
    const loss = f?.properties?.meanLoss;
    const area = f?.properties?.areaKm2;
    const cat = f?.properties?.category;
    if (minLoss != null && typeof loss === "number" && loss < minLoss)
      return false;
    if (minAreaKm2 > 0 && typeof area === "number" && area < minAreaKm2)
      return false;
    if (activeCategories && cat && !activeCategories[cat]) return false;
    return true;
  });
}

export const AREA_SLIDER_MAX = 0.2;

export function featureLabel(feature) {
  const p = feature?.properties ?? {};
  const parts = [];
  if (p.category) {
    const found = CHANGE_CATEGORIES.find((c) => c.key === p.category);
    parts.push(found ? found.label : `Likely ${p.category}`);
  }
  if (typeof p.areaKm2 === "number") parts.push(`${p.areaKm2.toFixed(2)} km²`);
  if (typeof p.meanLoss === "number")
    parts.push(`coherence loss ${p.meanLoss.toFixed(2)}`);
  return parts.length ? parts.join(" · ") : "Change area";
}

const fmt = (n) => n.toLocaleString(undefined, { maximumFractionDigits: 0 });

export function describeExposure(exposure) {
  if (!exposure || exposure.available !== true) {
    return {
      value: "—",
      note: `Building counts not available${exposure?.reason ? ` (${exposure.reason})` : ""}.`,
    };
  }
  const s = exposure.summary ?? {};
  if (typeof s.mappedHazardOverlapCount === "number") {
    return {
      value: fmt(s.mappedHazardOverlapCount),
      note: "Mapped OpenStreetMap buildings touching a change area. This is not damage and not a count of people.",
    };
  }
  if (typeof s.partialMappedHazardOverlapCount === "number") {
    return {
      value: `at least ${fmt(s.partialMappedHazardOverlapCount)}`,
      note: "Partial count: OpenStreetMap coverage or hazard coverage is incomplete. Not damage and not a count of people.",
    };
  }
  return { value: "—", note: "The building summary has no count yet." };
}
