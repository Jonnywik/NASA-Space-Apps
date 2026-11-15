"use client";

import React, { useEffect, useRef, useState } from "react";
import { DemoTag } from "./ui";
import { applyClip } from "../utils/mapClip";
import { useLang } from "../utils/LangContext";

const AREA_BOUNDS = [
  [14.6, 120.88],
  [14.82, 121.04],
];
const POWER_CELL_BOUNDS = [
  [14.48, 120.72],
  [14.95, 121.18],
];
const PANES = { rhythmPane: 405, beforePane: 410, afterPane: 420, motionPane: 425, projectionPane: 435 };

function tileConfig(mapMode, showLabels) {
  if (mapMode === "minimal") {
    const url = showLabels
      ? "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
      : "https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png";
    return {
      url,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; CARTO · NISAR: NASA/ISRO via ASF',
    };
  }
  return {
    url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors · NISAR: NASA/ISRO via ASF',
  };
}

const EXTRA_LEGEND_TITLES = {
  rainResponse: "rainResp.legendTitle",
  coherenceChange: "cohChange.legendTitle",
  soilMoisture: "sm.legendTitle",
};

function MapLegend({ mode, passCount, showVeg, losScale, hasPoint, isDemo, extraOverlayKind, extraLegend }) {
  const { t } = useLang();

  const extraTitleKey = EXTRA_LEGEND_TITLES[extraOverlayKind];
  if (extraTitleKey && Array.isArray(extraLegend) && extraLegend.length > 0) {
    const title = t(extraTitleKey);
    const fullTitle = extraOverlayKind === "soilMoisture" && !title.includes("m³/m³") ? `${title} (m³/m³)` : title;
    return (
      <div
        className={`pointer-events-auto absolute z-[950] flex max-w-[300px] flex-col gap-1.5 rounded-xl border border-[#DCE3DB] bg-white px-3 py-2.5 text-[11px] text-[#16231B] shadow-[0_1px_4px_rgba(20,30,40,0.10)] ${
          hasPoint ? "hidden md:flex md:right-4 md:bottom-7" : "left-3 bottom-3 md:left-4 md:bottom-4"
        }`}
        data-testid="map-legend"
      >
        <div className="flex items-center justify-between gap-2">
          <span className="text-[12px] font-semibold leading-snug">{fullTitle}</span>
          {isDemo && <DemoTag compact />}
        </div>
        <div className="flex items-start gap-1">
          {extraLegend.map((item, idx) => (
            <div key={`${item.value}-${idx}`} className="flex flex-1 flex-col items-center gap-1">
              <span
                aria-hidden="true"
                className="h-2.5 w-full rounded-[2px] border border-[#DCE3DB]/80"
                style={{ background: item.color }}
              />
              <span className="tabular-nums text-[10px] text-[#4A5850]">{item.value}</span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (mode === "history") {
    return (
      <div
        className={`pointer-events-auto flex max-w-[330px] flex-col gap-1 rounded-xl border border-[#DCE3DB] bg-white px-3.5 py-2.5 text-[12px] leading-snug text-[#16231B] shadow-[0_1px_4px_rgba(20,30,40,0.10)] ${
          hasPoint ? "hidden md:flex md:right-4 md:bottom-7" : "left-3 bottom-3 md:left-4 md:bottom-4"
        } absolute z-[950]`}
        data-testid="map-legend"
      >
        <span className="flex items-center gap-2 font-semibold">
          <span aria-hidden="true" className="inline-block w-4 border-t-[2.5px] border-dashed border-[#1E5B3A]" />
          {t("hist.v2.mapCellTitle")}
        </span>
        <span className="text-[#4A5850]">{t("hist.v2.mapCellSub")}</span>
        <span className="flex items-center gap-2 text-[#16231B]">
          <span aria-hidden="true" className="inline-block w-4 border-t-[2px] border-dashed border-[#1B2430]" />
          {t("hist.v2.mapStudy")}
        </span>
      </div>
    );
  }

  if (mode === "future") {
    return (
      <div
        className={`pointer-events-auto flex max-w-[320px] flex-col gap-1 rounded-xl border border-[#DCE3DB] bg-white px-3.5 py-2.5 text-[12px] leading-snug text-[#16231B] shadow-[0_1px_4px_rgba(20,30,40,0.10)] ${
          hasPoint ? "hidden md:flex md:right-4 md:bottom-7" : "left-3 bottom-3 md:left-4 md:bottom-4"
        } absolute z-[950]`}
        data-testid="map-legend"
      >
        <span className="flex items-center gap-2 font-semibold">
          <span
            aria-hidden="true"
            className="inline-block h-3.5 w-3.5 rounded-[3px]"
            style={{ background: "repeating-linear-gradient(45deg, #6B5A9E 0 2px, #E7E3F1 2px 5px)" }}
          />
          {t("future.v2.mapLegendTitle")}
          {isDemo && <DemoTag compact />}
        </span>
        <span className="text-[#4A5850]">{t("future.v2.mapLegendSub")}</span>
      </div>
    );
  }

  if (mode === "motion") {
    // Scale numbers come from the loaded LOS layer only; with no data they are shown as "—", never as a made-up range.
    const minVal = losScale ? `−${Math.round(losScale.maxAbs)}` : "—";
    const maxVal = losScale ? `+${Math.round(losScale.maxAbs)}` : "—";
    const unit = losScale?.unit ?? "mm";
    return (
      <div
        className="pointer-events-auto absolute bottom-6 right-3 z-[950] flex max-w-[260px] flex-col gap-1.5 rounded-xl border border-[#DCE3DB] bg-white px-3 py-2.5 text-[11px] text-[#16231B] shadow-[0_1px_4px_rgba(20,30,40,0.10)] md:bottom-7 md:right-4"
        data-testid="map-legend"
      >
        <div className="flex items-center justify-between gap-2">
          <span className="text-[12px] font-semibold">{t("motion.v2.legendTitle")}</span>
          {isDemo && <DemoTag compact />}
        </div>
        <span className="text-[#4A5850]">{t("motion.v2.legendSub")}</span>
        <div className="grid grid-cols-6 gap-0.5" aria-hidden="true">
          {["#7B3294", "#9970AB", "#C2A5CF", "#F2F0F2", "#A6DBA0", "#1B7837"].map((c) => (
            <span key={c} className="h-2.5 rounded-[2px]" style={{ background: c }} />
          ))}
        </div>
        <div className="flex justify-between text-[#4A5850]">
          <span>{`${t("motion.v2.legendAway")} ${maxVal}`}</span>
          <span>{t("motion.v2.legendStable")}</span>
          <span>{losScale ? `${minVal} ${unit}` : minVal}</span>
        </div>
        <div className="mt-0.5 flex items-center gap-1.5 border-t border-[#DCE3DB] pt-1.5 text-[#16231B]">
          <span aria-hidden="true" className="inline-block h-3 w-3 rounded-[2px] border-[1.5px] border-[#16231B] bg-white" />
          <span>{t("motion.v2.refArea")}</span>
        </div>
      </div>
    );
  }

  if (mode === "season") {
    return (
      <div
        className="pointer-events-auto absolute bottom-6 right-3 z-[950] flex max-w-[240px] flex-col gap-1.5 rounded-xl border border-[#DCE3DB] bg-white px-3 py-2.5 text-[11px] text-[#16231B] shadow-[0_1px_4px_rgba(20,30,40,0.10)] md:bottom-7 md:right-4"
        data-testid="map-legend"
      >
        <div className="flex items-center justify-between gap-2">
          <span className="text-[12px] font-semibold">{t("season.legend")}</span>
          {isDemo && <DemoTag compact />}
        </div>
        <div className="flex items-center gap-2">
          <span aria-hidden="true" className="inline-block h-3 w-3 shrink-0 rounded-[3px] bg-[#2171B5]" />
          <span>{t("spot.card.standingWater")}</span>
        </div>
        {showVeg && (
          <div className="flex items-center gap-2">
            <span aria-hidden="true" className="inline-block h-2.5 w-2.5 shrink-0 rotate-45 bg-[#E69F00]" />
            <span>{t("spot.card.veg")}</span>
          </div>
        )}
        <div className="flex items-center gap-2 text-[#4A5850]">
          <span aria-hidden="true" className="inline-block h-3 w-3 shrink-0 rounded-[3px] border border-[#9DB6C4] bg-[#D3E2EA]" />
          <span>{t("rhythm.v2.legendPerm")}</span>
        </div>
      </div>
    );
  }

  // Flood rhythm (default)
  // passCount is 0 until the NISAR pass list loads; show a dash rather than a made-up pass count.
  const maxPasses = passCount > 0 ? passCount : "—";
  return (
    <div
      className="pointer-events-auto absolute bottom-6 right-3 z-[950] flex flex-col gap-1.5 rounded-xl border border-[#DCE3DB] bg-white px-3 py-2.5 text-[11px] text-[#16231B] shadow-[0_1px_4px_rgba(20,30,40,0.10)] md:bottom-7 md:right-4"
      data-testid="map-legend"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-[12px] font-semibold">{t("rhythm.v2.legendTitle")}</span>
        {isDemo && <DemoTag compact />}
      </div>
      <div className="grid grid-cols-4 gap-0.5" aria-hidden="true">
        {["#C6DBEF", "#6BAED6", "#2171B5", "#08306B"].map((c) => (
          <span key={c} className="h-2.5 w-9 rounded-[2px]" style={{ background: c }} />
        ))}
      </div>
      <div className="flex justify-between text-[#4A5850]">
        <span>{t("rhythm.v2.legendMin")}</span>
        <span>{t("rhythm.v2.legendMax", { n: maxPasses })}</span>
      </div>
      <div className="flex items-center gap-2 text-[#4A5850]">
        <span aria-hidden="true" className="inline-block h-2.5 w-2.5 shrink-0 rounded-[2px] border border-[#9DB6C4] bg-[#D3E2EA]" />
        <span>{t("rhythm.v2.legendPerm")}</span>
      </div>
    </div>
  );
}

export default function NisarMap({
  overlays,
  geojsons,
  pins,
  point,
  compare,
  view,
  onPick,
  onPin,
  ariaLabel,
  mapMode = "streets",
  layers = {},
  boundariesGeojson = null,
  mode = "rhythm",
  passCount = 0,
  showVeg = true,
  losScale = null,
  isDemoOverlay = false,
  extraOverlayKind = null,
  extraLegend = null,
  topRightTools = null,
  topLeftSearch = null,
  bottomLeftSpot = null,
}) {
  const { t } = useLang();
  const wrap = useRef(null);
  const el = useRef(null);
  const mapRef = useRef(null);
  const leafletRef = useRef(null);
  const tileRef = useRef(null);
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
      const cfg = tileConfig("streets", true);
      tileRef.current = L.tileLayer(cfg.url, {
        attribution: cfg.attribution,
        maxZoom: 19,
      }).addTo(map);
      Object.entries(PANES).forEach(([name, z]) => {
        map.createPane(name).style.zIndex = z;
      });
      map.fitBounds(AREA_BOUNDS, { padding: [24, 24] });
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

  // keep base tiles in sync with mapMode and labels layer
  useEffect(() => {
    const map = mapRef.current;
    const L = leafletRef.current;
    if (!ready || !map || !L) return;
    if (tileRef.current) {
      map.removeLayer(tileRef.current);
    }
    const cfg = tileConfig(mapMode, layers.labels !== false);
    tileRef.current = L.tileLayer(cfg.url, {
      attribution: cfg.attribution,
      maxZoom: 19,
    }).addTo(map);
  }, [ready, mapMode, layers.labels]);

  // keep Leaflet sized when the layout changes
  useEffect(() => {
    if (!wrap.current) return undefined;
    const ro = new ResizeObserver(() => mapRef.current?.invalidateSize());
    ro.observe(wrap.current);
    return () => ro.disconnect();
  }, []);

  // study area outline & optional NASA POWER cell (in History mode)
  useEffect(() => {
    const map = mapRef.current;
    const L = leafletRef.current;
    if (!ready || !map || !L) return undefined;
    const added = [];
    if (layers.study !== false) {
      added.push(
        L.rectangle(AREA_BOUNDS, {
          color: "#1B2430",
          weight: 1.8,
          dashArray: "8 6",
          fill: false,
          interactive: false,
        }).addTo(map),
      );
    }
    if (mode === "history") {
      added.push(
        L.rectangle(POWER_CELL_BOUNDS, {
          color: "#1E5B3A",
          weight: 2.2,
          dashArray: "12 8",
          fillColor: "#1E5B3A",
          fillOpacity: 0.06,
          interactive: false,
        }).addTo(map),
      );
    }
    return () => added.forEach((l) => map.removeLayer(l));
  }, [ready, layers.study, mode]);

  // barangay boundaries layer
  useEffect(() => {
    const map = mapRef.current;
    const L = leafletRef.current;
    if (!ready || !map || !L || layers.bgy === false || !boundariesGeojson?.features?.length) return undefined;
    const layer = L.geoJSON(boundariesGeojson, {
      style: { color: "#1E5B3A", weight: 1, opacity: 0.45, fill: false },
      interactive: false,
    }).addTo(map);
    return () => map.removeLayer(layer);
  }, [ready, layers.bgy, boundariesGeojson]);

  // 2. raster overlays
  const overlayKey = JSON.stringify((overlays ?? []).map((o) => [o.key, o.url, o.pane, o.opacity, o.bounds]));
  useEffect(() => {
    const map = mapRef.current;
    const L = leafletRef.current;
    if (!ready || !map || !L) return undefined;
    const layersAdded = (overlays ?? []).filter((o) => o.url).map((o) =>
      L.imageOverlay(o.url, o.bounds ?? AREA_BOUNDS, { pane: o.pane ?? "afterPane", opacity: o.opacity ?? 0.8, alt: o.alt ?? "", interactive: false }).addTo(map),
    );
    applyClip(map, clipRef.current);
    return () => layersAdded.forEach((l) => map.removeLayer(l));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, overlayKey]);

  // 3. vector layers
  useEffect(() => {
    const map = mapRef.current;
    const L = leafletRef.current;
    if (!ready || !map || !L) return undefined;
    const layersAdded = (geojsons ?? []).filter((g) => g.data?.features?.length).map((g) =>
      L.geoJSON(g.data, {
        pane: g.pane ?? "motionPane",
        style: g.style,
        onEachFeature: g.tooltip ? (f, l) => l.bindTooltip(g.tooltip(f), { sticky: true }) : undefined,
        interactive: Boolean(g.tooltip),
        bubblingMouseEvents: true,
      }).addTo(map),
    );
    return () => layersAdded.forEach((l) => map.removeLayer(l));
  }, [ready, geojsons]);

  // 4. story pins
  useEffect(() => {
    const map = mapRef.current;
    const L = leafletRef.current;
    if (!ready || !map || !L || !pins?.length) return undefined;
    const markers = pins.map((p) => {
      const icon = L.divIcon({
        className: "",
        html: `<span style="display:block;width:22px;height:22px;border-radius:50% 50% 50% 0;transform:rotate(-45deg);background:#1E5B3A;border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,0.35)"></span>`,
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

  // 5. spot-check marker
  useEffect(() => {
    const map = mapRef.current;
    const L = leafletRef.current;
    if (!ready || !map || !L || !point) return undefined;
    const outer = L.circleMarker([point.lat, point.lon], {
      radius: 9,
      color: "#FFFFFF",
      weight: 3,
      fillColor: "#1E5B3A",
      fillOpacity: 1,
      interactive: false,
    }).addTo(map);
    return () => map.removeLayer(outer);
  }, [ready, point?.lon, point?.lat]); // eslint-disable-line react-hooks/exhaustive-deps

  // 6. fly to requested view
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
    <div ref={wrap} className="relative h-full w-full overflow-hidden bg-[#E8EBE3]">
      <div ref={el} className="absolute inset-0" role="application" aria-label={ariaLabel} data-testid="map" />

      {/* Top-left floating Search box */}
      {topLeftSearch && (
        <div className="pointer-events-auto absolute left-3 right-[68px] top-3 z-[1050] md:left-4 md:right-auto md:top-4 md:w-[min(360px,calc(100%-220px))]">
          {topLeftSearch}
        </div>
      )}

      {/* Top-right Map tools + zoom stack */}
      <div className="pointer-events-auto absolute right-3 top-[70px] z-[1050] flex flex-col items-end gap-2 md:right-4 md:top-4">
        {topRightTools}
        <div className="hidden overflow-hidden rounded-[10px] border border-[#DCE3DB] bg-white shadow-[0_2px_8px_rgba(20,30,40,0.12)] md:flex md:flex-col">
          <button
            type="button"
            onClick={() => mapRef.current?.zoomIn()}
            aria-label={t("map.zoomIn")}
            className="flex h-[38px] w-[38px] items-center justify-center border-b border-[#DCE3DB] bg-white text-[18px] text-[#16231B] hover:bg-[#F2F5F1]"
          >
            +
          </button>
          <button
            type="button"
            onClick={() => mapRef.current?.zoomOut()}
            aria-label={t("map.zoomOut")}
            className="flex h-[38px] w-[38px] items-center justify-center bg-white text-[18px] text-[#16231B] hover:bg-[#F2F5F1]"
          >
            −
          </button>
        </div>
      </div>

      {/* Swipe compare divider */}
      {compare?.on && (
        <>
          <div
            className="group absolute inset-y-0 z-[900] w-12 -translate-x-1/2 cursor-ew-resize focus:outline-none focus-visible:outline-none"
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
            <div className="absolute inset-y-0 left-1/2 w-[3px] -translate-x-1/2 bg-[#1E5B3A] shadow" />
            <div
              className="absolute left-1/2 top-1/2 flex h-11 w-11 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border-2 border-[#1E5B3A] bg-white text-[14px] font-bold text-[#1E5B3A] shadow-[0_2px_10px_rgba(20,30,40,0.22)] group-focus-visible:ring-2 group-focus-visible:ring-[#1E5B3A] group-focus-visible:ring-offset-2"
              title={t("map.swipe.handle")}
            >
              ◂▸
            </div>
          </div>
          <div className="pointer-events-none absolute left-3 top-[72px] z-[960] rounded-lg border border-[#DCE3DB] bg-white px-2.5 py-1 text-[12px] font-semibold text-[#16231B] shadow-[0_2px_6px_rgba(20,30,40,0.12)] md:left-4">
            {t("swipe.before")} · {compare.beforeLabel}
          </div>
          <div className="pointer-events-none absolute right-3 top-[120px] z-[960] rounded-lg border border-[#DCE3DB] bg-white px-2.5 py-1 text-[12px] font-semibold text-[#1E5B3A] shadow-[0_2px_6px_rgba(20,30,40,0.12)] md:right-[70px] md:top-[76px]">
            {t("swipe.after")} · {compare.afterLabel}
          </div>
        </>
      )}

      {/* Bottom-left SpotCard (desktop, or when selected) */}
      {bottomLeftSpot && (
        <div className="pointer-events-auto absolute bottom-3 left-3 z-[1020] md:bottom-4 md:left-4">
          {bottomLeftSpot}
        </div>
      )}

      {/* Mode legend card */}
      <MapLegend
        mode={mode}
        passCount={passCount}
        showVeg={showVeg}
        losScale={losScale}
        hasPoint={Boolean(bottomLeftSpot)}
        isDemo={isDemoOverlay}
        extraOverlayKind={extraOverlayKind}
        extraLegend={extraLegend}
      />
    </div>
  );
}
