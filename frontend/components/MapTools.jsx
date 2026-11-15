"use client";

import React, { useEffect, useRef } from "react";
import { useLang } from "../utils/LangContext";

export const DEFAULT_LAYERS = {
  bgy: true,
  labels: true,
  roads: false,
  rivers: true,
  study: true,
  buildings: false,
};

export const OVERLAY_FOR_MODE = {
  rhythm: "rhythm",
  season: "pass",
  motion: "motion",
  history: "rhythm",
  future: "scenario",
};

export const MODE_FOR_OVERLAY = {
  rhythm: "rhythm",
  pass: "season",
  motion: "motion",
  scenario: "future",
};

const OVERLAY_KEYS = ["rhythm", "pass", "rainResponse", "coherenceChange", "motion", "scenario"];
const LAYER_KEYS = ["bgy", "labels", "roads", "rivers", "study", "buildings"];
const MAP_MODES = ["streets", "minimal"];

export default function MapTools({
  open,
  onToggle,
  onClose,
  mapMode,
  onMapMode,
  overlay,
  onOverlay,
  showVeg,
  onShowVeg,
  opacity,
  onOpacity,
  layers,
  onToggleLayer,
  onReset,
  isDemoOverlay = false,
  compact = false,
}) {
  const { t } = useLang();
  const rootRef = useRef(null);
  const doneRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    const onDown = (e) => {
      if (rootRef.current && !rootRef.current.contains(e.target)) {
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("mousedown", onDown);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mousedown", onDown);
    };
  }, [open, onClose]);

  const activeLayerCount = Object.values(layers).filter(Boolean).length;
  const overlayShort = {
    rhythm: t("mode.rhythm"),
    pass: t("mode.season"),
    rainResponse: t("map.tools.overlay.rainResponse"),
    coherenceChange: t("map.tools.overlay.coherenceChange"),
    motion: t("mode.motion"),
    scenario: t("map.tools.overlay.scenario"),
  }[overlay] ?? t("mode.rhythm");
  const modeShort = t(`map.tools.mode.${mapMode}`);
  const summaryText = `${overlayShort}${isDemoOverlay ? ` (${t("demo.tag").toLowerCase()})` : ""} · ${modeShort} · ${t("map.tools.layersCount", { n: activeLayerCount })}`;

  return (
    <div ref={rootRef} className="relative">
      {compact ? (
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={open}
          aria-haspopup="dialog"
          aria-label={t("map.tools.open")}
          data-testid="map-tools-button"
          className="flex h-11 w-11 items-center justify-center rounded-xl border border-[#DCE3DB] bg-white text-[#16231B] shadow-[0_2px_8px_rgba(20,30,40,0.14)] hover:bg-[#F2F5F1]"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#1E5B3A" strokeWidth="2" strokeLinejoin="round" aria-hidden="true">
            <path d="M12 3l9 5-9 5-9-5 9-5z" />
            <path d="M3 13l9 5 9-5" />
          </svg>
        </button>
      ) : (
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={open}
          aria-haspopup="dialog"
          data-testid="map-tools-button"
          className="flex h-11 items-center gap-2 rounded-xl border border-[#DCE3DB] bg-white px-3 text-[13px] font-semibold text-[#16231B] shadow-[0_2px_8px_rgba(20,30,40,0.12)] hover:bg-[#F2F5F1]"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#1E5B3A" strokeWidth="2" strokeLinejoin="round" aria-hidden="true">
            <path d="M12 3l9 5-9 5-9-5 9-5z" />
            <path d="M3 13l9 5 9-5" />
          </svg>
          <span>{t("map.tools")}</span>
          <span className="max-w-[240px] truncate text-[11px] font-medium text-[#4A5850]">{summaryText}</span>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true" className={open ? "rotate-180" : ""}>
            <path d="M6 9l6 6 6-6" />
          </svg>
        </button>
      )}

      {open && (
        <div
          role="dialog"
          aria-label={t("map.tools")}
          data-testid="map-tools-dialog"
          className="absolute right-0 top-[52px] z-[1600] flex max-h-[min(78vh,620px)] w-[min(312px,calc(100vw-32px))] flex-col gap-3.5 overflow-y-auto rounded-[14px] border border-[#DCE3DB] bg-white p-3.5 text-[#16231B] shadow-[0_6px_24px_rgba(20,30,40,0.14)]"
        >
          {/* 1. Map mode (Streets / Minimal — Satellite hidden because no keyless free imagery meets terms) */}
          <div className="flex flex-col gap-2">
            <span className="text-[11px] font-bold uppercase tracking-[0.07em] text-[#4A5850]">{t("map.tools.mode")}</span>
            <div role="radiogroup" aria-label={t("map.tools.mode")} className="grid grid-cols-2 gap-1.5">
              {MAP_MODES.map((m) => {
                const active = mapMode === m;
                return (
                  <button
                    key={m}
                    type="button"
                    role="radio"
                    aria-checked={active}
                    onClick={() => onMapMode(m)}
                    data-testid={`map-mode-${m}`}
                    className={`flex h-9 items-center justify-center rounded-lg border px-2 text-[12px] ${
                      active
                        ? "border-2 border-[#1E5B3A] bg-[#E3EFE7] font-bold text-[#123B25]"
                        : "border-[#DCE3DB] bg-white font-medium text-[#16231B] hover:bg-[#F2F5F1]"
                    }`}
                  >
                    {t(`map.tools.mode.${m}`)}
                  </button>
                );
              })}
            </div>
          </div>

          {/* 2. Overlay (one at a time) + per-overlay options + opacity */}
          <div className="flex flex-col gap-1.5 border-t border-[#DCE3DB] pt-3">
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-[11px] font-bold uppercase tracking-[0.07em] text-[#4A5850]">{t("map.tools.overlay")}</span>
              <span className="text-[11px] text-[#4A5850]">{t("map.tools.overlay.one")}</span>
            </div>
            <div role="radiogroup" aria-label={t("map.tools.overlay")} className="flex flex-col gap-1.5">
              {OVERLAY_KEYS.map((k) => {
                const active = overlay === k;
                return (
                  <div key={k} className="flex flex-col gap-1.5">
                    <button
                      type="button"
                      role="radio"
                      aria-checked={active}
                      onClick={() => {
                        onOverlay(k);
                        onClose?.();
                      }}
                      data-testid={`overlay-opt-${k}`}
                      className={`flex h-9 items-center gap-2 rounded-lg border px-2.5 text-left text-[13px] ${
                        active
                          ? "border-2 border-[#1E5B3A] bg-[#E3EFE7] font-bold text-[#123B25]"
                          : "border-[#DCE3DB] bg-white font-medium text-[#16231B] hover:bg-[#F2F5F1]"
                      }`}
                    >
                      <span
                        aria-hidden="true"
                        className={`inline-block h-3.5 w-3.5 shrink-0 rounded-full border-2 ${
                          active ? "border-[#1E5B3A] bg-[#1E5B3A] shadow-[inset_0_0_0_2.5px_#E3EFE7]" : "border-[#94A39B] bg-white"
                        }`}
                      />
                      <span className="truncate">{t(`map.tools.overlay.${k}`)}</span>
                    </button>

                    {active && (
                      <div className="flex flex-col gap-2 pl-4">
                        {k === "pass" && (
                          <label className="flex cursor-pointer items-center gap-2 text-[12px] text-[#16231B]">
                            <input
                              type="checkbox"
                              checked={showVeg}
                              onChange={(e) => onShowVeg(e.target.checked)}
                              className="h-4 w-4 accent-[#1E5B3A]"
                            />
                            <span>{t("map.tools.showVeg")}</span>
                          </label>
                        )}
                        <label className="flex items-center justify-between gap-2 text-[12px] text-[#4A5850]">
                          <span>{t("map.opacity")}</span>
                          <input
                            type="range"
                            min={20}
                            max={100}
                            step={5}
                            value={Math.round(opacity * 100)}
                            onChange={(e) => onOpacity(Number(e.target.value) / 100)}
                            aria-label={t("map.opacity")}
                            className="w-[126px] accent-[#1E5B3A]"
                          />
                        </label>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* 3. Context Layers */}
          <div className="flex flex-col gap-1 border-t border-[#DCE3DB] pt-3">
            <span className="mb-0.5 text-[11px] font-bold uppercase tracking-[0.07em] text-[#4A5850]">{t("map.tools.layers")}</span>
            {LAYER_KEYS.map((k) => (
              <label key={k} className="flex h-7 cursor-pointer items-center gap-2 text-[13px] text-[#16231B]">
                <input
                  type="checkbox"
                  checked={Boolean(layers[k])}
                  onChange={() => onToggleLayer(k)}
                  className="h-4 w-4 accent-[#1E5B3A]"
                />
                <span>{t(`map.tools.layer.${k}`)}</span>
              </label>
            ))}
          </div>

          {/* Footer actions */}
          <div className="flex items-center justify-between border-t border-[#DCE3DB] pt-2.5">
            <button
              type="button"
              onClick={onReset}
              className="border-0 bg-transparent px-1 py-1 text-[13px] font-medium text-[#1E5B3A] hover:text-[#123B25]"
            >
              {t("map.tools.reset")}
            </button>
            <button
              ref={doneRef}
              type="button"
              onClick={onClose}
              className="h-9 rounded-lg bg-[#1E5B3A] px-3.5 text-[13px] font-semibold text-white hover:bg-[#123B25]"
            >
              {t("map.tools.done")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
