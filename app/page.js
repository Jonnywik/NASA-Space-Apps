'use client';

import { useEffect, useRef } from 'react';
import StatsSidebar from './StatsSidebar';
import { mockFloodData } from './mockData';

const greaterManilaBounds = [
  [14.15, 120.72],
  [15.02, 121.34],
];

export default function Home() {
  const mapElement = useRef(null);

  useEffect(() => {
    let map;
    let cancelled = false;

    async function initializeMap() {
      const leaflet = await import('leaflet');
      if (cancelled || !mapElement.current) return;

      const L = leaflet.default;
      map = L.map(mapElement.current, {
        center: [14.5995, 120.9842],
        zoom: 11,
        minZoom: 10,
        maxZoom: 18,
        maxBounds: greaterManilaBounds,
        maxBoundsViscosity: 0.85,
        zoomControl: false,
      });

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
      }).addTo(map);

      L.control.zoom({ position: 'bottomright' }).addTo(map);

      L.circleMarker([14.5995, 120.9842], {
        radius: 6,
        color: '#bfdbfe',
        weight: 2,
        fillColor: '#3b82f6',
        fillOpacity: 1,
      })
        .bindTooltip('Manila', { direction: 'top', offset: [0, -8] })
        .addTo(map);
    }

    initializeMap();

    return () => {
      cancelled = true;
      map?.remove();
    };
  }, []);

  return (
    <main className="relative h-screen w-screen overflow-hidden bg-slate-950">
      <div
        ref={mapElement}
        className="absolute inset-0"
        role="application"
        aria-label="Interactive map of Greater Manila"
      />

      <div className="pointer-events-none absolute left-4 top-4 z-[1000] rounded-xl border border-slate-700 bg-slate-900/90 px-4 py-3 text-white shadow-xl backdrop-blur-md">
        <div className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-300">
          Tanaw
        </div>
        <h1 className="mt-1 text-lg font-bold">Greater Manila</h1>
        <p className="text-xs text-slate-400">Pan and zoom to explore the region</p>
      </div>

      <StatsSidebar data={mockFloodData} />
    </main>
  );
}
