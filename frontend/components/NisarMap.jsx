"use client";

import React, { useEffect, useRef, useState } from "react";
import { applyClip } from "../utils/mapClip";
import { useLang } from "../utils/LangContext";

// The Leaflet map of the CAMANAVA workspace. It is controlled from outside:
//   overlays   [{key, url, bounds, pane, opacity, alt}]   raster PNGs (pane: beforePane | afterPane | rhythmPane)
//   geojsons   [{key, data, style, tooltip, pane}]        vector layers (motion heat map, projection)
//   pins       [{id, lat, lon, label}]                    "Our stories" pins
//   point      {lon, lat} | null                          the spot-check marker
//   compare    {on, split, onSplit, beforeLabel, afterLabel}
//   view       {nonce, bounds?, center?, zoom?}           a new nonce flies the map
const AREA_BOUNDS = [
  [14.6, 120.88],
  [14.82, 121.04],
];
const PANES = { rhythmPane: 405, beforePane: 410, afterPane: 420, motionPane: 425, projectionPane: 435 };

export default function NisarMap({ overlays, geojsons, pins, point, compare, view, onPick, onPin, ariaLabel }) {
  const { t } = useLang();
  const wrap = useRef(null);
  const el = useRef(null);
  const mapRef = useRef(null);
  const leafletRef = useRef(null);
  const clipRef = useRef(null);
  const pickRef = useRef(onPick);
  const pinRef = useRef(onPin);
  const dragging = useRef(false);
  const [ready, setReady] = useState(false);
  pickRef.current = onPick;
  pinRef.current = onPin;

  // 1. create the map once
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const leaflet = await import("leaflet");
      if (cancelled || !el.current) return;
      const L = leaflet.default;
      leafletRef.current = L;
      const map = L.map(el.current, {
        center: [14.71, 120.96],
        zoom: 12,
        minZoom: 9,
        maxZoom: 18,
        maxBounds: [
          [14.2, 120.5],
          [15.2, 121.4],
        ],
        maxBoundsViscosity: 0.8,
        zoomControl: false,
      });
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
      }).addTo(map);
      L.control.zoom({ position: "topleft" }).addTo(map);
      Object.entries(PANES).forEach(([name, z]) => {
        map.createPane(name).style.zIndex = z;
      });
      // the study area outline, always visible, so the map is never empty
      L.rectangle(AREA_BOUNDS, { color: "#F0E442", weight: 2, dashArray: "6 6", fill: false, interactive: false }).addTo(map);
      map.fitBounds(AREA_BOUNDS, { padding: [20, 20] });
      map.on("move zoom resize", () => applyClip(map, clipRef.current));
      map.on("click", (e) => pickRef.current?.(e.latlng.lng, e.latlng.lat));
      mapRef.current = map;
      setReady(true);
    })();
    return () => {
      cancelled = true;
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  // keep Leaflet sized when the layout changes (panel open or closed, phone rotation)
  useEffect(() => {
    if (!wrap.current) return undefined;
    const ro = new ResizeObserver(() => mapRef.current?.invalidateSize());
    ro.observe(wrap.current);
    return () => ro.disconnect();
  }, []);

  // 2. raster overlays
  const overlayKey = JSON.stringify((overlays ?? []).map((o) => [o.key, o.url, o.pane, o.opacity]));
  useEffect(() => {
    const map = mapRef.current;
    const L = leafletRef.current;
    if (!ready || !map || !L) return undefined;
    const layers = (overlays ?? []).filter((o) => o.url).map((o) =>
      L.imageOverlay(o.url, o.bounds ?? AREA_BOUNDS, { pane: o.pane ?? "afterPane", opacity: o.opacity ?? 0.8, alt: o.alt ?? "", interactive: false }).addTo(map),
    );
    applyClip(map, clipRef.current);
    return () => layers.forEach((l) => map.removeLayer(l));
    // overlays is described by overlayKey
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, overlayKey]);

  // 3. vector layers
  useEffect(() => {
    const map = mapRef.current;
    const L = leafletRef.current;
    if (!ready || !map || !L) return undefined;
    const layers = (geojsons ?? []).filter((g) => g.data?.features?.length).map((g) =>
      L.geoJSON(g.data, {
        pane: g.pane ?? "motionPane",
        style: g.style,
        onEachFeature: g.tooltip ? (f, l) => l.bindTooltip(g.tooltip(f), { sticky: true }) : undefined,
        interactive: Boolean(g.tooltip),
        bubblingMouseEvents: true,
      }).addTo(map),
    );
    return () => layers.forEach((l) => map.removeLayer(l));
  }, [ready, geojsons]);

  // 4. story pins
  useEffect(() => {
    const map = mapRef.current;
    const L = leafletRef.current;
    if (!ready || !map || !L || !pins?.length) return undefined;
    const markers = pins.map((p) => {
      const icon = L.divIcon({
        className: "",
        html: `<span style="display:block;width:22px;height:22px;border-radius:50% 50% 50% 0;transform:rotate(-45deg);background:#CC79A7;border:2px solid #fff;box-shadow:0 1px 4px #000"></span>`,
        iconSize: [22, 22],
        iconAnchor: [11, 22],
      });
      const m = L.marker([p.lat, p.lon], { icon, title: p.label, alt: p.label, keyboard: true }).addTo(map);
      m.on("click", (e) => {
        L.DomEvent.stopPropagation(e);
        pinRef.current?.(p.id);
      });
      return m;
    });
    return () => markers.forEach((m) => map.removeLayer(m));
  }, [ready, pins]);

  // 5. the spot-check marker
  useEffect(() => {
    const map = mapRef.current;
    const L = leafletRef.current;
    if (!ready || !map || !L || !point) return undefined;
    const ring = L.circleMarker([point.lat, point.lon], { radius: 9, color: "#ffffff", weight: 3, fillColor: "#D55E00", fillOpacity: 0.9, interactive: false }).addTo(map);
    return () => map.removeLayer(ring);
  }, [ready, point?.lon, point?.lat]); // eslint-disable-line react-hooks/exhaustive-deps

  // 6. fly to a requested view
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map || !view) return;
    if (view.bounds) map.flyToBounds(view.bounds, { padding: [24, 24], duration: 0.8, maxZoom: view.maxZoom ?? 16 });
    else if (view.center) map.flyTo(view.center, view.zoom ?? 14, { duration: 0.8 });
  }, [ready, view?.nonce]); // eslint-disable-line react-hooks/exhaustive-deps

  // 7. swipe clip
  useEffect(() => {
    clipRef.current = compare?.on ? compare.split : null;
    applyClip(mapRef.current, clipRef.current);
  }, [ready, compare?.on, compare?.split]);

  function moveDivider(clientX) {
    const rect = el.current.getBoundingClientRect();
    compare.onSplit(Math.min(0.98, Math.max(0.02, (clientX - rect.left) / rect.width)));
  }
  function onDividerKey(e) {
    const step = e.shiftKey ? 0.2 : 0.05;
    let next = null;
    if (e.key === "ArrowLeft" || e.key === "ArrowDown") next = compare.split - step;
    else if (e.key === "ArrowRight" || e.key === "ArrowUp") next = compare.split + step;
    else if (e.key === "Home") next = 0.02;
    else if (e.key === "End") next = 0.98;
    if (next == null) return;
    e.preventDefault();
    compare.onSplit(Math.min(0.98, Math.max(0.02, next)));
  }

  return (
    <div ref={wrap} className="relative h-full w-full">
      <div ref={el} className="absolute inset-0" role="application" aria-label={ariaLabel} data-testid="map" />
      {compare?.on && (
        <>
          <div
            className="absolute inset-y-0 z-[900] w-12 -translate-x-1/2 cursor-ew-resize"
            style={{ left: `${compare.split * 100}%`, touchAction: "none" }}
            onPointerDown={(e) => {
              dragging.current = true;
              e.currentTarget.setPointerCapture(e.pointerId);
            }}
            onPointerMove={(e) => dragging.current && moveDivider(e.clientX)}
            onPointerUp={() => {
              dragging.current = false;
            }}
            onKeyDown={onDividerKey}
            tabIndex={0}
            role="slider"
            aria-label={t("swipe.divider")}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(compare.split * 100)}
            aria-valuetext={t("swipe.valuetext", { before: compare.beforeLabel, pct: Math.round(compare.split * 100), after: compare.afterLabel })}
            data-testid="divider"
          >
            <div className="absolute inset-y-0 left-1/2 w-0.5 -translate-x-1/2 bg-white shadow" />
            <div className="absolute left-1/2 top-1/2 flex h-9 w-9 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border-2 border-white bg-slate-900 text-xs text-white shadow-lg">
              ↔
            </div>
          </div>
          <div className="pointer-events-none absolute left-3 top-3 z-[1000] rounded-full border border-slate-600 bg-slate-900/90 px-3 py-1 text-xs text-white md:left-14">
            {t("swipe.before")} · {compare.beforeLabel}
          </div>
          <div className="pointer-events-none absolute right-3 top-3 z-[1000] rounded-full border border-slate-600 bg-slate-900/90 px-3 py-1 text-xs text-white">
            {t("swipe.after")} · {compare.afterLabel}
          </div>
        </>
      )}
    </div>
  );
}
