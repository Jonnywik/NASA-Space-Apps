// frontend/utils/changeFilter.js  -  small pure helpers for the Tier 2 change layer.
// No React in here, so they are easy to test.

// Default "strength of change" floor. The backend rule keeps pixels whose coherence loss is at least
// parameters.lossMin (0.3 by default), so every polygon already has meanLoss >= that value.
export const DEFAULT_LOSS_MIN = 0.3;
export const LOSS_SLIDER_MAX = 0.9;

export function lossFloor(coherence) {
  const v = coherence?.parameters?.lossMin;
  return typeof v === 'number' && Number.isFinite(v) ? v : DEFAULT_LOSS_MIN;
}

// Keep polygons whose mean coherence loss is at least minLoss.
// A polygon with no meanLoss is kept (we never hide something because a number is missing).
export function filterChangeFeatures(features, minLoss) {
  const list = Array.isArray(features) ? features : [];
  if (minLoss == null) return list;
  return list.filter((f) => {
    const loss = f?.properties?.meanLoss;
    return typeof loss !== 'number' || loss >= minLoss;
  });
}

export function featureLabel(feature) {
  const p = feature?.properties ?? {};
  const parts = [];
  if (typeof p.areaKm2 === 'number') parts.push(`${p.areaKm2.toFixed(2)} km²`);
  if (typeof p.meanLoss === 'number') parts.push(`coherence loss ${p.meanLoss.toFixed(2)}`);
  return parts.length ? parts.join(' · ') : 'Change area';
}

const fmt = (n) => n.toLocaleString(undefined, { maximumFractionDigits: 0 });

// Turn the backend's `exposure` block into text for the panel.
// Real answers: { available: false, reason } until an OSM snapshot is published, then
// { available: true, summary: { countStatus, mappedHazardOverlapCount, partialMappedHazardOverlapCount } }
export function describeExposure(exposure) {
  if (!exposure || exposure.available !== true) {
    return {
      value: '—',
      note: `Building counts not available${exposure?.reason ? ` (${exposure.reason})` : ''}.`,
    };
  }
  const s = exposure.summary ?? {};
  if (typeof s.mappedHazardOverlapCount === 'number') {
    return {
      value: fmt(s.mappedHazardOverlapCount),
      note: 'Mapped OpenStreetMap buildings touching a change area. This is not damage and not a count of people.',
    };
  }
  if (typeof s.partialMappedHazardOverlapCount === 'number') {
    return {
      value: `at least ${fmt(s.partialMappedHazardOverlapCount)}`,
      note: 'Partial count: OpenStreetMap coverage or hazard coverage is incomplete. Not damage and not a count of people.',
    };
  }
  return { value: '—', note: 'The building summary has no count yet.' };
}
