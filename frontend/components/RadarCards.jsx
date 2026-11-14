"use client";

import React, { useEffect, useRef, useState } from "react";
import { useLang } from "../utils/LangContext";

export const RADAR_CARDS = ["water", "vegetation", "insar", "bands"];

// U5 "How radar sees": four short cards. Opened from a "?" on a layer, which selects the matching card.
export default function RadarCards({ open, initial, onClose }) {
  const { t } = useLang();
  const [card, setCard] = useState(initial ?? "water");
  const closeRef = useRef(null);

  useEffect(() => {
    if (open) setCard(RADAR_CARDS.includes(initial) ? initial : "water");
  }, [open, initial]);

  useEffect(() => {
    if (!open) return undefined;
    closeRef.current?.focus();
    const onKey = (e) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[3000] flex items-center justify-center bg-black/70 p-3" onMouseDown={(e) => e.target === e.currentTarget && onClose()} data-testid="radar-cards">
      <div role="dialog" aria-modal="true" aria-labelledby="radar-title" className="max-h-[90vh] w-full max-w-2xl overflow-auto rounded-xl border border-slate-500 bg-slate-900 p-4 text-white shadow-2xl">
        <div className="flex items-center justify-between gap-2">
          <h2 id="radar-title" className="text-lg font-bold">
            {t("radar.title")}
          </h2>
          <button type="button" ref={closeRef} onClick={onClose} className="rounded-md border border-slate-400 px-2.5 py-1 text-sm hover:bg-slate-700">
            {t("radar.close")}
          </button>
        </div>
        <div role="tablist" aria-label={t("radar.title")} className="mt-3 flex flex-wrap gap-1.5">
          {RADAR_CARDS.map((c) => (
            <button
              key={c}
              role="tab"
              type="button"
              aria-selected={card === c}
              onClick={() => setCard(c)}
              className={`rounded-md border px-2.5 py-1 text-xs ${card === c ? "border-yellow-300 bg-yellow-300/20 text-white" : "border-slate-600 bg-slate-800 text-slate-300 hover:bg-slate-700"}`}
            >
              {t(`radar.${c}.title`)}
            </button>
          ))}
        </div>
        <article role="tabpanel" className="mt-3" data-testid={`radar-card-${card}`}>
          <h3 className="text-base font-bold text-yellow-100">{t(`radar.${card}.title`)}</h3>
          <p className="mt-2 text-sm leading-relaxed text-slate-100">{t(`radar.${card}.p1`)}</p>
          <p className="mt-2 text-sm leading-relaxed text-slate-100">{t(`radar.${card}.p2`)}</p>
          <p className="mt-2 text-sm leading-relaxed text-slate-100">{t(`radar.${card}.p3`)}</p>
          <p className="mt-3 rounded-md border border-sky-300/40 bg-sky-500/10 p-2 text-sm text-sky-100">
            <b>{t("radar.remember")}</b> {t(`radar.${card}.tip`)}
          </p>
        </article>
      </div>
    </div>
  );
}
