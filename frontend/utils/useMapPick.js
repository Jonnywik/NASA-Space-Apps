'use client';

import { useCallback, useEffect, useState } from 'react';

// Lets the user click the Leaflet map to pick a point (used by Tier 3, click-a-pixel).
//   active   only listens (and shows a crosshair cursor) while true
//   resetKey when this changes (e.g. a new event) the picked point is forgotten
// Returns { point: {lng, lat} | null, clear }
export default function useMapPick({ mapRef, leafletRef, mapReady, active, resetKey }) {
  const [point, setPoint] = useState(null);

  useEffect(() => {
    setPoint(null);
  }, [resetKey]);

  useEffect(() => {
    const map = mapRef.current;
    if (!mapReady || !map || !active) return undefined;
    const el = map.getContainer();
    const previous = el.style.cursor;
    el.style.cursor = 'crosshair';
    const onClick = (e) => setPoint({ lng: e.latlng.lng, lat: e.latlng.lat });
    map.on('click', onClick);
    return () => {
      map.off('click', onClick);
      el.style.cursor = previous;
    };
  }, [mapRef, mapReady, active]);

  // a small ring on the picked point
  useEffect(() => {
    const map = mapRef.current;
    const L = leafletRef.current;
    if (!mapReady || !map || !L || !active || !point) return undefined;
    const marker = L.circleMarker([point.lat, point.lng], {
      radius: 7,
      color: '#ffffff',
      weight: 2,
      fillColor: '#06b6d4',
      fillOpacity: 0.9,
    }).addTo(map);
    return () => {
      map.removeLayer(marker);
    };
  }, [mapRef, leafletRef, mapReady, active, point]);

  const clear = useCallback(() => setPoint(null), []);
  return { point, clear };
}
