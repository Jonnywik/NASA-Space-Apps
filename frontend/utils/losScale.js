// Colour scale for the NISAR line-of-sight layer. The orange/purple diverging pair stays readable with
// the common kinds of colour-blindness, and every class also has a printed range in the legend.
// Positive = away from the satellite (which includes sinking); negative = toward the satellite.
export const LOS_COLORS = ["#5e3c99", "#b2abd2", "#eeeeee", "#fdb863", "#e66101"];

export function pickLosProperty(geojson) {
  const f = geojson?.features?.find((x) => x?.properties);
  if (!f) return null;
  if (typeof f.properties.displacementMm === "number") return { prop: "displacementMm", unit: "mm", cumulative: true };
  if (typeof f.properties.rateMmPerYear === "number") return { prop: "rateMmPerYear", unit: "mm/yr", cumulative: false };
  return null;
}

export function makeLosScale(geojson) {
  const p = pickLosProperty(geojson);
  if (!p) return null;
  const vals = geojson.features.map((f) => f.properties?.[p.prop]).filter((v) => typeof v === "number");
  if (!vals.length) return null;
  const maxAbs = Math.max(1, Math.ceil(Math.max(...vals.map(Math.abs))));
  const edges = [-maxAbs, -0.6 * maxAbs, -0.2 * maxAbs, 0.2 * maxAbs, 0.6 * maxAbs, maxAbs];
  const bins = LOS_COLORS.map((color, i) => ({ lo: edges[i], hi: edges[i + 1], color }));
  const color = (v) => {
    if (typeof v !== "number") return "#94a3b8";
    const i = edges.findIndex((e, k) => k > 0 && v < e);
    return LOS_COLORS[i === -1 ? LOS_COLORS.length - 1 : i - 1];
  };
  return { ...p, bins, color, maxAbs };
}
