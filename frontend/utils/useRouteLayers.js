'use client';

import { useEffect } from 'react';
import { fitOptions } from './mapPadding';

// Draw the two routes: grey dashed = shortest, green = hazard-aware. Zoom to them when a new result arrives.
export default function useRouteLayers({ mapRef, leafletRef, mapReady, route, visible }) {
  useEffect(() => {
    const map = mapRef.current;
    const L = leafletRef.current;
    if (!mapReady || !map || !L || !visible || !route) return undefined;
    if (!map.getPane('routePane')) map.createPane('routePane').style.zIndex = 450;
    const swap = (coords) => coords.map(([lng, lat]) => [lat, lng]);
    const layers = [];
    if (route.shortest?.geometry) {
      layers.push(
        L.polyline(swap(route.shortest.geometry.coordinates), {
          pane: 'routePane',
          color: '#94a3b8',
          weight: 6,
          opacity: 0.95,
          dashArray: '10 8',
        }).bindTooltip('Shortest route (ignores hazards)', { sticky: true })
      );
    }
    if (route.safe?.geometry) {
      layers.push(
        L.polyline(swap(route.safe.geometry.coordinates), {
          pane: 'routePane',
          color: '#22c55e',
          weight: 5,
          opacity: 0.95,
        }).bindTooltip('Hazard-aware route', { sticky: true })
      );
    }
    layers.forEach((l) => l.addTo(map));
    const group = L.featureGroup(layers);
    if (layers.length) map.fitBounds(group.getBounds(), fitOptions({ maxZoom: 15 }));
    return () => layers.forEach((l) => map.removeLayer(l));
  }, [mapRef, leafletRef, mapReady, route, visible]);
}
