'use client';

import { useEffect, useState } from 'react';
import { getGeojson, getProjection } from './api';
import { sampleProjection } from './sampleProjection';
import { useTier } from './useTier';

// Scenario id: the backend only serves a projection when it is asked for the scenario it holds.
// Set NEXT_PUBLIC_SCENARIO_ID in frontend/.env.local if the reviewed scenario is named differently.
export const SCENARIO_ID = process.env.NEXT_PUBLIC_SCENARIO_ID || 'reviewed_scenario';

// Loads the projection for one year (real or DEMO) and the polygons for that year.
export default function useProjection({ eventId, year, demo, active }) {
  const load = !active
    ? null
    : demo
      ? () => Promise.resolve(sampleProjection(year))
      : eventId
        ? () => getProjection(eventId, SCENARIO_ID, year)
        : null;
  const tier = useTier(load, [eventId, year, demo, active]);
  const [fetched, setFetched] = useState(null);

  useEffect(() => {
    setFetched(null);
    if (demo || tier.state !== 'ready') return undefined;
    const url = tier.data?.assets?.[`geometry${year}`]?.url;
    if (!url) return undefined;
    let cancelled = false;
    getGeojson(url)
      .then((g) => {
        if (!cancelled) setFetched(g);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [demo, tier.state, tier.data, year]);

  const geojson = demo ? tier.data?.geojson ?? null : fetched;
  const areaKm2 = geojson?.features ? geojson.features.reduce((s, f) => s + (f.properties?.areaKm2 ?? 0), 0) : null;
  return { tier, geojson, areaKm2 };
}
