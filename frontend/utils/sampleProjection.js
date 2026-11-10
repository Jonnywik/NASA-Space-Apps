// DEMO projection: an INVENTED blob that grows each year. It exists so the Future panel always has
// something to show; every screen that uses it says DEMO. Nothing here is a real prediction.
export const DEMO_YEARS = [2026, 2027, 2028, 2029, 2030, 2031, 2032, 2033, 2034, 2035];

function ring(year) {
  const cx = 120.8;
  const cy = 14.9;
  const rKm = 0.8 + 0.45 * (year - 2026);
  const kmPerLat = 111;
  const kmPerLon = 111 * Math.cos((cy * Math.PI) / 180);
  const coords = [];
  for (let i = 0; i <= 32; i += 1) {
    const a = (i / 32) * 2 * Math.PI;
    const wobble = 1 + 0.18 * Math.sin(3 * a);
    coords.push([cx + (rKm * wobble * Math.cos(a)) / kmPerLon, cy + (rKm * 0.7 * wobble * Math.sin(a)) / kmPerLat]);
  }
  let area = 0;
  for (let i = 0; i < coords.length - 1; i += 1) {
    const [x1, y1] = [coords[i][0] * kmPerLon, coords[i][1] * kmPerLat];
    const [x2, y2] = [coords[i + 1][0] * kmPerLon, coords[i + 1][1] * kmPerLat];
    area += x1 * y2 - x2 * y1;
  }
  return { coords, areaKm2: Math.abs(area) / 2 };
}

export function sampleProjection(year) {
  const { coords, areaKm2 } = ring(year);
  return {
    event: 'demo',
    product: 'projection',
    scenarioId: 'demo_scenario',
    dataKind: 'synthetic',
    dataStatus: 'synthetic',
    baselineEpoch: '2026-01-01',
    supportedYears: DEMO_YEARS,
    selectedYear: year,
    annualMetric: { year, annualDate: `${year}-01-01`, medianLosMm: Math.round(31.5 * (year - 2026)), exposedCellCount: Math.round(areaKm2 * 600) },
    assumptions: [
      'DEMO: invented numbers.',
      'Ground movement continues at a constant yearly rate (a simplification).',
      'Water level follows an invented rise.',
    ],
    uncertainty: { reason: 'DEMO data has no real uncertainty. Real projections report only the uncertainty terms the sources provide.' },
    geojson: {
      type: 'FeatureCollection',
      features: [{ type: 'Feature', properties: { year, areaKm2 }, geometry: { type: 'Polygon', coordinates: [coords] } }],
    },
  };
}
