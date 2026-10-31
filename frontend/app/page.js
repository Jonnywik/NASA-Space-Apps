'use client';

import { useEffect, useRef, useState } from 'react';
import StatsSidebar from '../components/StatsSidebar';
import { getEvents, getFloodExtent } from '../utils/api';

// The map can roam over Metro Manila AND the floodplains north of it
// (Pampanga, Bulacan). The old "Greater Manila only" box was too small:
// the flood events sit partly outside it.
const mapBounds = [
  [14.2, 120.3],
  [15.6, 121.4],
];

// Show only part of a map layer: everything left of the divider is "before",
// everything right of it is "after". This is the same trick the
// leaflet-side-by-side plugin uses, written out so you can read it.
function applyClip(map, fraction) {
  if (!map) return;
  const before = map.getPane('beforePane');
  const after = map.getPane('afterPane');
  if (!before || !after) return;

  const size = map.getSize();
  const nw = map.containerPointToLayerPoint([0, 0]);
  const se = map.containerPointToLayerPoint(size);
  const x = nw.x + size.x * fraction; // the divider, in layer coordinates

  // CSS clip: rect(top, right, bottom, left)
  before.style.clip = `rect(${nw.y}px, ${x}px, ${se.y}px, ${nw.x}px)`;
  after.style.clip = `rect(${nw.y}px, ${se.x}px, ${se.y}px, ${x}px)`;
}

export default function Home() {
  const mapElement = useRef(null);
  const mapRef = useRef(null); // the Leaflet map
  const leafletRef = useRef(null); // the Leaflet library (L)
  const layersRef = useRef([]); // layers of the current event, so we can remove them
  const splitRef = useRef(0.5); // divider position: 0 = far left, 1 = far right
  const dragging = useRef(false);

  const [events, setEvents] = useState([]); // events that have results
  const [eventId, setEventId] = useState(null); // the selected event
  const [data, setData] = useState(null); // the selected event's data from the API
  const [error, setError] = useState(null);
  const [mapReady, setMapReady] = useState(false);
  const [split, setSplit] = useState(0.5);

  // 1. Ask the API which events exist
  useEffect(() => {
    getEvents()
      .then((list) => {
        const ready = list.filter((e) => e.ready);
        setEvents(ready);
        if (ready.length > 0) setEventId(ready[0].id);
        else setError('No flood results yet. Run the backend scripts first.');
      })
      .catch(() =>
        setError('Cannot reach the backend. Is uvicorn running on port 8000?')
      );
  }, []);

  // 2. Create the map (once)
  useEffect(() => {
    let cancelled = false;

    async function initializeMap() {
      const leaflet = await import('leaflet');
      if (cancelled || !mapElement.current) return;

      const L = leaflet.default;
      leafletRef.current = L;

      const map = L.map(mapElement.current, {
        center: [14.9, 120.85],
        zoom: 9,
        minZoom: 8,
        maxZoom: 17,
        maxBounds: mapBounds,
        maxBoundsViscosity: 0.85,
        zoomControl: false,
      });

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
      }).addTo(map);

      L.control.zoom({ position: 'bottomright' }).addTo(map);

      // Two extra layers ("panes") on top of the map:
      // beforePane = left of the divider, afterPane = right of the divider
      map.createPane('beforePane').style.zIndex = 410;
      map.createPane('afterPane').style.zIndex = 420;

      const update = () => applyClip(map, splitRef.current);
      map.on('move zoom resize', update);

      mapRef.current = map;
      setMapReady(true);
    }

    initializeMap();

    return () => {
      cancelled = true;
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  // 3. Load the selected event from the API
  useEffect(() => {
    if (!eventId) return;
    let cancelled = false;
    setData(null);
    setError(null);
    getFloodExtent(eventId)
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [eventId]);

  // 4. Draw the event on the map
  useEffect(() => {
    const map = mapRef.current;
    const L = leafletRef.current;
    if (!mapReady || !map || !L || !data) return;

    const added = [];
    const { overlays, floodGeojson } = data;

    if (overlays) {
      // blue water picture: before (left side) and after (right side)
      added.push(
        L.imageOverlay(overlays.beforeUrl, overlays.bounds, {
          pane: 'beforePane',
          opacity: 0.85,
        })
      );
      added.push(
        L.imageOverlay(overlays.afterUrl, overlays.bounds, {
          pane: 'afterPane',
          opacity: 0.85,
        })
      );
    }

    if (floodGeojson?.features?.length) {
      // red flood shapes, on the "after" side
      added.push(
        L.geoJSON(floodGeojson, {
          pane: 'afterPane',
          style: {
            color: '#ef4444',
            weight: 1,
            fillColor: '#ef4444',
            fillOpacity: 0.55,
          },
        })
      );
    }

    added.forEach((layer) => layer.addTo(map));
    layersRef.current = added;

    // zoom to the event
    const bounds =
      overlays?.bounds ??
      (data.bbox && [
        [data.bbox[1], data.bbox[0]],
        [data.bbox[3], data.bbox[2]],
      ]);
    if (bounds) map.fitBounds(bounds, { padding: [20, 20] });
    applyClip(map, splitRef.current);

    return () => {
      added.forEach((layer) => map.removeLayer(layer));
    };
  }, [data, mapReady]);

  // Dragging the divider
  function moveDivider(clientX) {
    const rect = mapElement.current.getBoundingClientRect();
    const fraction = Math.min(0.98, Math.max(0.02, (clientX - rect.left) / rect.width));
    splitRef.current = fraction;
    setSplit(fraction);
    applyClip(mapRef.current, fraction);
  }

  const hasSlider = Boolean(data?.overlays);

  return (
    <main className="relative h-screen w-screen overflow-hidden bg-slate-950">
      <div
        ref={mapElement}
        className="absolute inset-0"
        role="application"
        aria-label="Interactive before and after flood map"
      />

      {/* Title, event picker and legend */}
      <div className="absolute left-4 top-4 z-[1000] rounded-xl border border-slate-700 bg-slate-900/90 px-4 py-3 text-white shadow-xl backdrop-blur-md">
        <div className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-300">
          Tanaw
        </div>
        <label htmlFor="event" className="mt-2 block text-xs text-slate-400">
          Flood event
        </label>
        <select
          id="event"
          value={eventId ?? ''}
          onChange={(e) => setEventId(e.target.value)}
          className="mt-1 w-64 rounded-md border border-slate-600 bg-slate-800 px-2 py-1.5 text-sm text-white"
        >
          {events.map((e) => (
            <option key={e.id} value={e.id}>
              {e.name}
            </option>
          ))}
        </select>
        <div className="mt-3 flex items-center gap-4 text-xs text-slate-300">
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-3 w-3 rounded-sm bg-blue-500" /> Water
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-3 w-3 rounded-sm bg-red-500" /> New flood
          </span>
        </div>
      </div>

      {/* The before / after divider */}
      {hasSlider && (
        <>
          <div
            className="absolute inset-y-0 z-[900] w-12 -translate-x-1/2 cursor-ew-resize"
            style={{ left: `${split * 100}%`, touchAction: 'none' }}
            onPointerDown={(e) => {
              dragging.current = true;
              e.currentTarget.setPointerCapture(e.pointerId);
            }}
            onPointerMove={(e) => {
              if (dragging.current) moveDivider(e.clientX);
            }}
            onPointerUp={() => {
              dragging.current = false;
            }}
            role="slider"
            aria-label="Before and after divider"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(split * 100)}
            data-testid="divider"
          >
            <div className="absolute inset-y-0 left-1/2 w-0.5 -translate-x-1/2 bg-white shadow" />
            <div className="absolute left-1/2 top-1/2 flex h-9 w-9 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border-2 border-white bg-slate-900 text-xs text-white shadow-lg">
              ◀▶
            </div>
          </div>

          <div className="pointer-events-none absolute bottom-6 left-4 z-[1000] rounded-full border border-slate-700 bg-slate-900/90 px-3 py-1 text-xs text-white">
            Before · {data.beforeDate}
          </div>
          <div className="pointer-events-none absolute bottom-6 right-16 z-[1000] rounded-full border border-slate-700 bg-slate-900/90 px-3 py-1 text-xs text-white">
            After · {data.afterDate}
          </div>
        </>
      )}

      {error && (
        <div className="absolute bottom-16 left-1/2 z-[1000] -translate-x-1/2 rounded-lg border border-red-500/40 bg-red-950/90 px-4 py-2 text-sm text-red-200">
          {error}
        </div>
      )}

      <StatsSidebar data={data} />
    </main>
  );
}
