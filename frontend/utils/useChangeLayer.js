'use client';

import { useEffect, useState } from 'react';
import { featureLabel, filterChangeFeatures } from './changeFilter';

// Draws the Tier 2 "coherence loss" polygons on the Leaflet map.
// It lives on its own pane ("changePane") ABOVE the before/after panes and is not clipped by the
// divider, because Tier 2 is not a before/after picture.
//   geojson   FeatureCollection from /coherence-loss (changeGeojson), or null
//   visible   layer toggle
//   minLoss   hide polygons whose mean loss is below this (null = show all)
// Returns { total, shown } so the panel can say "showing 3 of 4 areas".
export default function useChangeLayer({ mapRef, leafletRef, mapReady, geojson, visible, minLoss }) {
  const [counts, setCounts] = useState({ total: 0, shown: 0 });

  useEffect(() => {
    const map = mapRef.current;
    const L = leafletRef.current;
    if (!mapReady || !map || !L) return undefined;

    const all = geojson?.features ?? [];
    const kept = filterChangeFeatures(all, minLoss);
    setCounts({ total: all.length, shown: kept.length });

    if (!visible || kept.length === 0) return undefined;
    if (!map.getPane('changePane')) map.createPane('changePane').style.zIndex = 430;

    const layer = L.geoJSON(
      { type: 'FeatureCollection', features: kept },
      {
        pane: 'changePane',
        style: { color: '#f59e0b', weight: 1.5, fillColor: '#f59e0b', fillOpacity: 0.45 },
        onEachFeature: (feature, l) => l.bindTooltip(featureLabel(feature), { sticky: true }),
      }
    ).addTo(map);

    return () => {
      map.removeLayer(layer);
    };
  }, [mapRef, leafletRef, mapReady, geojson, visible, minLoss]);

  return counts;
}
