// frontend/app/page.js
"use client";

import { useEffect, useRef, useState } from "react";
import StatsSidebar from "../components/StatsSidebar";
import LayerToggle from "../components/LayerToggle";
import BriefingCard from "../components/BriefingCard";
import Tier3Panel, { motionRateColor } from "../components/Tier3Panel";
import TierBar from "../components/TierBar";
import Tier2Panel from "../components/Tier2Panel";
import ProjectionPanel from "../components/ProjectionPanel";
import RoutePanel from "../components/RoutePanel";
import {
  getCoherenceLoss,
  getEvents,
  getFloodExtent,
  getGroundMotion,
  getRoute,
} from "../utils/api";
import { LOSS_SLIDER_MAX, lossFloor } from "../utils/changeFilter";
import {
  sampleCoherenceLoss,
  sampleEvents,
  sampleFloodExtent,
  sampleGroundMotion,
} from "../utils/sampleData";
import useChangeLayer from "../utils/useChangeLayer";
import { fitOptions } from "../utils/mapPadding";
import useGeoLayer from "../utils/useGeoLayer";
import useMapPick from "../utils/useMapPick";
import useProjection from "../utils/useProjection";
import useRouteLayers from "../utils/useRouteLayers";
import useRoutePins from "../utils/useRoutePins";
import {
  DEMO_BOUNDS,
  demoHazardGeojson,
  demoRoute,
} from "../utils/routeEngine";
import { useSampleMode, useTier } from "../utils/useTier";

const mapBounds = [
  [14.2, 120.3],
  [15.6, 121.4],
];

const INITIAL_CATEGORIES = {
  vegetation: true,
  construction: true,
  damage: true,
  unknown: true,
};

function applyClip(map, fraction) {
  if (!map) return;
  const before = map.getPane("beforePane");
  const after = map.getPane("afterPane");
  if (!before || !after) return;

  const size = map.getSize();
  const nw = map.containerPointToLayerPoint([0, 0]);
  const se = map.containerPointToLayerPoint(size);
  const x = nw.x + size.x * fraction;

  before.style.clip = `rect(${nw.y}px, ${x}px, ${se.y}px, ${nw.x}px)`;
  after.style.clip = `rect(${nw.y}px, ${se.x}px, ${se.y}px, ${x}px)`;
}

export default function Home() {
  const mapElement = useRef(null);
  const mapRef = useRef(null);
  const leafletRef = useRef(null);
  const layersRef = useRef([]);
  const splitRef = useRef(0.5);
  const dragging = useRef(false);

  const [events, setEvents] = useState([]);
  const [eventId, setEventId] = useState(null);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [mapReady, setMapReady] = useState(false);
  const [split, setSplit] = useState(0.5);

  const [layers, setLayers] = useState({
    flood: true,
    change: true,
    motion: false,
    route: false,
    scenario: false,
  });
  const [minArea, setMinArea] = useState(0);
  const [activeCategories, setActiveCategories] = useState(INITIAL_CATEGORIES);
  const [controlsOpen, setControlsOpen] = useState(true);
  const [year, setYear] = useState(2026);

  const urlSample = useSampleMode();
  const [appDemo, setAppDemo] = useState(false);
  const [routeDemo, setRouteDemo] = useState(false);
  const [scenarioDemo, setScenarioDemo] = useState(false);

  const isGlobalDemo = urlSample || appDemo;
  const routeIsDemo = isGlobalDemo || routeDemo;
  const scenarioIsDemo = isGlobalDemo || scenarioDemo;
  const [lossFilter, setLossFilter] = useState(null);

  // Tier 2: coherence change
  const tier2 = useTier(
    eventId
      ? isGlobalDemo
        ? () => Promise.resolve(sampleCoherenceLoss)
        : () => getCoherenceLoss(eventId)
      : null,
    [eventId, isGlobalDemo],
    { sampleData: sampleCoherenceLoss },
  );
  const tier2Ready = tier2.state === "ready";
  const minLoss = lossFilter ?? lossFloor(tier2.data);
  const changeOn = layers.change && tier2Ready;

  // Tier 3: regional ground motion + click-a-pixel
  const motionTier = useTier(
    layers.motion && eventId
      ? isGlobalDemo
        ? () => Promise.resolve(sampleGroundMotion)
        : () => getGroundMotion(eventId)
      : null,
    [eventId, layers.motion, isGlobalDemo],
    { sampleData: sampleGroundMotion },
  );

  useGeoLayer({
    mapRef,
    leafletRef,
    mapReady,
    geojson:
      motionTier.state === "ready"
        ? (motionTier.data?.heatmapGeojson ?? null)
        : null,
    visible: layers.motion && motionTier.state === "ready",
    pane: "motionPane",
    zIndex: 425,
    style: (f) => {
      const c = motionRateColor(f?.properties?.rateMmPerYear);
      return { color: c, weight: 1.5, fillColor: c, fillOpacity: 0.45 };
    },
    tooltip: (f) =>
      `LOS rate: ${(f?.properties?.rateMmPerYear ?? 0).toFixed(1)} mm/yr (positive = away from satellite)`,
  });

  const pick = useMapPick({
    mapRef,
    leafletRef,
    mapReady,
    active: layers.motion && !layers.route,
    resetKey: eventId,
  });

  // Tier 4A: routes between two pins
  const pins = useRoutePins({
    mapRef,
    leafletRef,
    mapReady,
    active: layers.route,
    resetKey: eventId,
  });
  const haveTrip = layers.route && pins.from && pins.to;
  const routeLoad = !haveTrip
    ? null
    : routeIsDemo
      ? () => Promise.resolve().then(() => demoRoute(pins.from, pins.to))
      : eventId
        ? () => getRoute(eventId, pins.from, pins.to)
        : null;
  const routeTier = useTier(routeLoad, [
    eventId,
    routeIsDemo,
    layers.route,
    pins.from?.lng,
    pins.from?.lat,
    pins.to?.lng,
    pins.to?.lat,
  ]);
  useRouteLayers({
    mapRef,
    leafletRef,
    mapReady,
    route: routeTier.state === "ready" ? routeTier.data : null,
    visible: layers.route,
  });

  const demoHazards = routeIsDemo ? demoHazardGeojson() : null;
  const demoStyle = (f) =>
    f.properties.kind === "area"
      ? { color: "#f59e0b", weight: 2, dashArray: "6 6", fill: false }
      : f.properties.kind === "flood"
        ? {
            color: "#ef4444",
            weight: 1,
            fillColor: "#ef4444",
            fillOpacity: 0.45,
          }
        : {
            color: "#f97316",
            weight: 1,
            fillColor: "#f97316",
            fillOpacity: 0.4,
          };
  useGeoLayer({
    mapRef,
    leafletRef,
    mapReady,
    geojson: demoHazards,
    visible: layers.route && routeIsDemo,
    pane: "demoHazardPane",
    zIndex: 440,
    style: demoStyle,
    tooltip: (f) =>
      `DEMO ${f.properties.kind === "area" ? "area" : f.properties.kind + " (invented)"}`,
  });

  useGeoLayer({
    mapRef,
    leafletRef,
    mapReady,
    geojson: data?.floodGeojson ?? null,
    visible: layers.route && !routeIsDemo,
    pane: "hazardPane",
    zIndex: 440,
    style: {
      color: "#ef4444",
      weight: 1,
      fillColor: "#ef4444",
      fillOpacity: 0.4,
    },
  });

  useEffect(() => {
    const map = mapRef.current;
    if (mapReady && map && layers.route && routeIsDemo)
      map.fitBounds(DEMO_BOUNDS, fitOptions());
  }, [mapReady, layers.route, routeIsDemo]);

  // Tier 4B: projection for the chosen year
  const proj = useProjection({
    eventId,
    year,
    demo: scenarioIsDemo,
    active: layers.scenario,
  });
  useGeoLayer({
    mapRef,
    leafletRef,
    mapReady,
    geojson: proj.geojson,
    visible: layers.scenario,
    pane: "projectionPane",
    zIndex: 435,
    style: {
      color: "#a78bfa",
      weight: 2,
      dashArray: "4 4",
      fillColor: "#8b5cf6",
      fillOpacity: 0.35,
    },
    tooltip: (f) =>
      `PROJECTION ${f.properties?.year ?? ""}: ${(f.properties?.areaKm2 ?? 0).toFixed(1)} km²`,
  });

  useEffect(() => {
    const map = mapRef.current;
    if (mapReady && map && layers.scenario && scenarioIsDemo) {
      map.fitBounds(
        [
          [14.86, 120.76],
          [14.94, 120.84],
        ],
        fitOptions(),
      );
    }
  }, [mapReady, layers.scenario, scenarioIsDemo]);

  const changeCounts = useChangeLayer({
    mapRef,
    leafletRef,
    mapReady,
    geojson: tier2Ready ? tier2.data.changeGeojson : null,
    visible: changeOn,
    minLoss: lossFilter,
    minArea,
    activeCategories,
  });

  useEffect(() => {
    setControlsOpen(window.innerWidth >= 768);
  }, []);

  // 1. Ask the API which events exist (or load sampleEvents when in DEMO mode)
  useEffect(() => {
    if (isGlobalDemo) {
      setEvents(sampleEvents);
      setEventId((prev) => prev ?? sampleEvents[0].id);
      setError(null);
      return;
    }
    getEvents()
      .then((list) => {
        const ready = list.filter((e) => e.ready);
        setEvents(ready);
        if (ready.length > 0) setEventId(ready[0].id);
        else setError("No flood results yet. Run the backend scripts first.");
      })
      .catch(() =>
        setError("Cannot reach the backend. Is uvicorn running on port 8000?"),
      );
  }, [isGlobalDemo]);

  // 2. Create the map (once)
  useEffect(() => {
    let cancelled = false;

    async function initializeMap() {
      const leaflet = await import("leaflet");
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

      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
      }).addTo(map);

      L.control.zoom({ position: "bottomright" }).addTo(map);

      map.createPane("beforePane").style.zIndex = 410;
      map.createPane("afterPane").style.zIndex = 420;

      const update = () => applyClip(map, splitRef.current);
      map.on("move zoom resize", update);

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

  // 3. Load the selected event from the API (or sampleFloodExtent in DEMO mode)
  useEffect(() => {
    if (!eventId) return;
    if (isGlobalDemo) {
      const chosen =
        sampleEvents.find((e) => e.id === eventId) ?? sampleEvents[0];
      setData({
        ...sampleFloodExtent,
        event: chosen.id,
        aoi: `${chosen.aoi} (SAMPLE)`,
        beforeDate: chosen.beforeDate,
        afterDate: chosen.afterDate,
      });
      setError(null);
      return undefined;
    }
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
  }, [eventId, isGlobalDemo]);

  // 4. Draw the event on the map
  useEffect(() => {
    const map = mapRef.current;
    const L = leafletRef.current;
    if (!mapReady || !map || !L || !data) return;

    const added = [];
    const { overlays, floodGeojson } = data;

    if (overlays) {
      added.push(
        L.imageOverlay(overlays.beforeUrl, overlays.bounds, {
          pane: "beforePane",
          opacity: 0.85,
        }),
      );
      added.push(
        L.imageOverlay(overlays.afterUrl, overlays.bounds, {
          pane: "afterPane",
          opacity: 0.85,
        }),
      );
    }

    if (floodGeojson?.features?.length) {
      added.push(
        L.geoJSON(floodGeojson, {
          pane: overlays ? "afterPane" : "overlayPane",
          style: {
            color: "#ef4444",
            weight: 1,
            fillColor: "#ef4444",
            fillOpacity: 0.55,
          },
        }),
      );
    }

    added.forEach((layer) => layer.addTo(map));
    layersRef.current = added;

    const bounds =
      overlays?.bounds ??
      (data.bbox && [
        [data.bbox[1], data.bbox[0]],
        [data.bbox[3], data.bbox[2]],
      ]);
    if (bounds) map.fitBounds(bounds, fitOptions());

    applyClip(map, splitRef.current);

    return () => {
      added.forEach((layer) => map.removeLayer(layer));
    };
  }, [data, mapReady]);

  useEffect(() => {
    setLossFilter(null);
    setMinArea(0);
    setActiveCategories(INITIAL_CATEGORIES);
  }, [eventId]);

  useEffect(() => {
    const map = mapRef.current;
    if (!mapReady || !map) return;
    ["beforePane", "afterPane"].forEach((name) => {
      const pane = map.getPane(name);
      if (pane) pane.style.display = layers.flood ? "" : "none";
    });
  }, [layers.flood, mapReady]);

  function moveDivider(clientX) {
    const rect = mapElement.current.getBoundingClientRect();
    const fraction = Math.min(
      0.98,
      Math.max(0.02, (clientX - rect.left) / rect.width),
    );
    splitRef.current = fraction;
    setSplit(fraction);
    applyClip(mapRef.current, fraction);
  }

  const hasSlider = Boolean(data?.overlays) && layers.flood;

  return (
    <main className="relative h-screen w-screen overflow-hidden bg-slate-950">
      <div
        ref={mapElement}
        className="absolute inset-0"
        role="application"
        aria-label="Interactive before and after flood map"
      />

      {/* Title, event picker and legend */}
      <div className="absolute left-2 top-2 z-[1000] max-h-[55vh] max-w-[calc(100vw-1rem)] overflow-y-auto rounded-xl border border-slate-700 bg-slate-900/90 px-4 py-3 text-white shadow-xl backdrop-blur-md md:left-4 md:top-4 md:max-h-[calc(100vh-2rem)]">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-300">
              Tanaw
            </span>
            {isGlobalDemo && (
              <span className="rounded-full border border-amber-500/50 bg-amber-500/20 px-2 py-0.5 text-[10px] font-bold text-amber-300">
                SAMPLE MODE
              </span>
            )}
          </div>
          <button
            type="button"
            onClick={() => setControlsOpen((o) => !o)}
            aria-expanded={controlsOpen}
            className="rounded px-1.5 text-xs text-slate-300 hover:bg-slate-700"
          >
            {controlsOpen ? "Hide ▲" : "Controls ▼"}
          </button>
        </div>
        <div className={controlsOpen ? "" : "hidden"}>
          <label htmlFor="event" className="mt-2 block text-xs text-slate-400">
            Flood event
          </label>
          <select
            id="event"
            value={eventId ?? ""}
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
              <span className="inline-block h-3 w-3 rounded-sm bg-blue-500" />{" "}
              Water
            </span>
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-3 w-3 rounded-sm bg-red-500" />{" "}
              New flood
            </span>
          </div>

          <TierBar
            layers={layers}
            onToggle={(key) =>
              setLayers((prev) => ({ ...prev, [key]: !prev[key] }))
            }
            disabled={{}}
          />

          <LayerToggle
            visible={changeOn}
            strength={{
              value: minLoss,
              min: lossFloor(tier2.data),
              max: LOSS_SLIDER_MAX,
              onChange: setLossFilter,
            }}
            counts={changeCounts}
            minArea={minArea}
            onMinArea={setMinArea}
            activeCategories={activeCategories}
            onToggleCategory={(cat) =>
              setActiveCategories((prev) => ({ ...prev, [cat]: !prev[cat] }))
            }
          />
        </div>
      </div>

      {/* The before / after divider */}
      {hasSlider && (
        <>
          <div
            className="absolute inset-y-0 z-[900] w-12 -translate-x-1/2 cursor-ew-resize"
            style={{ left: `${split * 100}%`, touchAction: "none" }}
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
              ↔
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
          {error}{" "}
          <button
            type="button"
            onClick={() => setAppDemo(true)}
            className="ml-1 font-semibold underline hover:text-white"
          >
            Open DEMO data
          </button>
        </div>
      )}

      <StatsSidebar data={data}>
        {layers.change && <Tier2Panel tier2={tier2} counts={changeCounts} />}
        {layers.motion && (
          <Tier3Panel
            eventId={eventId}
            motionTier={motionTier}
            point={pick.point}
            onClear={pick.clear}
          />
        )}
        {layers.motion && <BriefingCard eventId={eventId} />}
        {layers.route && (
          <RoutePanel
            pins={pins}
            routeTier={routeTier}
            demo={routeIsDemo}
            onDemo={() => setRouteDemo(true)}
            hasEvent={Boolean(eventId)}
          />
        )}
        {layers.scenario && (
          <ProjectionPanel
            proj={proj}
            year={year}
            setYear={setYear}
            demo={scenarioIsDemo}
            onDemo={() => setScenarioDemo(true)}
          />
        )}
      </StatsSidebar>
    </main>
  );
}
