"use client";

import React, { useEffect, useRef, useState } from "react";
import { useLang } from "../utils/LangContext";

export const RADAR_CARDS = ["water", "vegetation", "limits", "insar", "bands"];

// U5 "How radar sees": four short cards. Opened from a "?" on a panel, which selects the matching card.
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
    <div
      className="fixed inset-0 z-[3000] flex items-center justify-center bg-black/35 p-3 backdrop-blur-[1px]"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
      data-testid="radar-cards"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="radar-title"
        className="max-h-[90vh] w-full max-w-2xl overflow-auto rounded-2xl border border-[#DCE3DB] bg-white p-5 text-[#16231B] shadow-2xl"
      >
        <div className="flex items-center justify-between gap-2 border-b border-[#DCE3DB] pb-3">
          <h2 id="radar-title" className="font-serif text-[20px] font-semibold text-[#16231B]">
            {t("radar.title")}
          </h2>
          <button
            type="button"
            ref={closeRef}
            onClick={onClose}
            className="h-9 rounded-lg border border-[#DCE3DB] bg-[#F2F5F1] px-3 text-[13px] font-medium text-[#16231B] hover:bg-[#E3EFE7]"
          >
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
              className={`rounded-lg border px-3 py-1.5 text-[12px] font-medium transition-colors ${
                card === c ? "border-[#1E5B3A] bg-[#E3EFE7] font-semibold text-[#123B25]" : "border-[#DCE3DB] bg-white text-[#4A5850] hover:bg-[#F2F5F1]"
              }`}
            >
              {t(`radar.${c}.title`)}
            </button>
          ))}
        </div>
        <article role="tabpanel" className="mt-4" data-testid={`radar-card-${card}`}>
          <h3 className="font-serif text-[17px] font-semibold text-[#16231B]">{t(`radar.${card}.title`)}</h3>
          <p className="mt-2 text-[14px] leading-relaxed text-[#16231B]">{t(`radar.${card}.p1`)}</p>
          <p className="mt-2 text-[14px] leading-relaxed text-[#16231B]">{t(`radar.${card}.p2`)}</p>
          <p className="mt-2 text-[14px] leading-relaxed text-[#16231B]">{t(`radar.${card}.p3`)}</p>
          <p className="mt-3 rounded-xl border border-[#DCE3DB] bg-[#E3EFE7] p-3 text-[13px] leading-relaxed text-[#123B25]">
            <b>{t("radar.remember")}</b> {t(`radar.${card}.tip`)}
          </p>
        </article>
      </div>
    </div>
  );
}
