'use client';

import { useEffect } from 'react';

// Draw any GeoJSON on its own Leaflet pane. Used by Tier 4 (projection, route hazards, demo shapes).
//   pane / zIndex  name and stacking of the pane (created when missing)
//   style          Leaflet path style object or function(feature)
//   tooltip        optional function(feature) -> string
export default function useGeoLayer({ mapRef, leafletRef, mapReady, geojson, visible, pane, zIndex, style, tooltip }) {
  useEffect(() => {
    const map = mapRef.current;
    const L = leafletRef.current;
    if (!mapReady || !map || !L || !visible || !geojson?.features?.length) return undefined;
    if (!map.getPane(pane)) map.createPane(pane).style.zIndex = zIndex;
    const layer = L.geoJSON(geojson, {
      pane,
      style,
      onEachFeature: tooltip ? (f, l) => l.bindTooltip(tooltip(f), { sticky: true }) : undefined,
    }).addTo(map);
    return () => {
      map.removeLayer(layer);
    };
    // style and tooltip are constants in the callers
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mapRef, leafletRef, mapReady, geojson, visible, pane, zIndex]);
}
