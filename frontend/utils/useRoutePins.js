'use client';

import { useCallback, useEffect, useState } from 'react';

const pinHtml = (letter, color) =>
  `<div style="width:28px;height:28px;border-radius:9999px;background:${color};color:#fff;border:2px solid #fff;` +
  `display:flex;align-items:center;justify-content:center;font:700 13px system-ui;box-shadow:0 2px 6px rgba(0,0,0,.5)">${letter}</div>`;

// Start (A) and end (B) pins for the route tool.
//   active    listens to map clicks only while the route tool is on
//   resetKey  a new event clears the pins
// Click the map to place A, then B. After that, drag the pins. `mode` says which pin the next click sets.
export default function useRoutePins({ mapRef, leafletRef, mapReady, active, resetKey }) {
  const [from, setFrom] = useState(null);
  const [to, setTo] = useState(null);
  const [mode, setMode] = useState('from');

  useEffect(() => {
    setFrom(null);
    setTo(null);
    setMode('from');
  }, [resetKey]);

  useEffect(() => {
    const map = mapRef.current;
    if (!mapReady || !map || !active) return undefined;
    const el = map.getContainer();
    const previous = el.style.cursor;
    el.style.cursor = 'crosshair';
    const onClick = (e) => {
      const p = { lng: e.latlng.lng, lat: e.latlng.lat };
      if (mode === 'from') {
        setFrom(p);
        setMode('to');
      } else {
        setTo(p);
      }
    };
    map.on('click', onClick);
    return () => {
      map.off('click', onClick);
      el.style.cursor = previous;
    };
  }, [mapRef, mapReady, active, mode]);

  useEffect(() => {
    const map = mapRef.current;
    const L = leafletRef.current;
    if (!mapReady || !map || !L || !active) return undefined;
    const markers = [];
    const add = (p, letter, color, setter) => {
      if (!p) return;
      const m = L.marker([p.lat, p.lng], {
        draggable: true,
        keyboard: true,
        title: letter === 'A' ? 'Start (drag to move)' : 'End (drag to move)',
        icon: L.divIcon({ html: pinHtml(letter, color), className: '', iconSize: [28, 28], iconAnchor: [14, 14] }),
        zIndexOffset: 1000,
      }).addTo(map);
      m.on('dragend', () => {
        const ll = m.getLatLng();
        setter({ lng: ll.lng, lat: ll.lat });
      });
      markers.push(m);
    };
    add(from, 'A', '#2563eb', setFrom);
    add(to, 'B', '#dc2626', setTo);
    return () => markers.forEach((m) => map.removeLayer(m));
  }, [mapRef, leafletRef, mapReady, active, from, to]);

  const clear = useCallback(() => {
    setFrom(null);
    setTo(null);
    setMode('from');
  }, []);
  const setBoth = useCallback((a, b) => {
    setFrom(a);
    setTo(b);
    setMode('to');
  }, []);

  return { from, to, mode, setMode, clear, setBoth };
}
