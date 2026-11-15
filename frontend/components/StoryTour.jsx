"use client";

import React, { useEffect, useRef } from "react";
import { STORY_STEPS } from "../utils/storySteps";
import { useLang } from "../utils/LangContext";

// U3: the guided tour. Arrow keys move, Esc closes, the card never blocks the map.
export default function StoryTour({ step, onStep, onClose, fact, onTry }) {
  const { t } = useLang();
  const nextRef = useRef(null);
  const last = STORY_STEPS.length - 1;
  const cur = STORY_STEPS[step];

  useEffect(() => {
    nextRef.current?.focus();
    // focus the card once when the tour opens
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    function onKey(e) {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }
      if (["INPUT", "TEXTAREA", "SELECT"].includes(e.target?.tagName)) return;
      if (e.target?.closest?.(".leaflet-container, [role=slider]")) return;
      if (e.key === "ArrowRight") {
        e.preventDefault();
        step < last ? onStep(step + 1) : onClose();
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        if (step > 0) onStep(step - 1);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [step, last, onStep, onClose]);

  const factText = fact?.(step);
  return (
    <div
      role="dialog"
      aria-modal="false"
      aria-labelledby="story-title"
      aria-describedby="story-body"
      className="absolute bottom-3 left-3 z-[1100] w-[min(360px,calc(100%-1.5rem))] rounded-xl border border-[#DCE3DB] bg-white p-4 text-[#16231B] shadow-[0_4px_16px_rgba(20,30,40,0.16)]"
      data-testid="story"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] font-bold uppercase tracking-[0.08em] text-[#1E5B3A]">
          {t("story.label")} · {t("story.step", { i: step + 1, n: STORY_STEPS.length })}
        </span>
        <button
          type="button"
          onClick={onClose}
          className="rounded-lg border border-[#DCE3DB] bg-[#F2F5F1] px-2.5 py-1 text-[12px] font-medium text-[#16231B] hover:bg-[#E3EFE7]"
          data-testid="story-skip"
        >
          {step === last ? t("story.close") : t("story.skip")}
        </button>
      </div>
      <h2 id="story-title" className="mt-2 font-serif text-[18px] font-semibold leading-snug text-[#16231B]">
        {t(`story.${step + 1}.title`)}
      </h2>
      <p id="story-body" className="mt-1.5 text-[13px] leading-[1.55] text-[#4A5850]">
        {t(`story.${step + 1}.body`)}
      </p>
      {factText && (
        <p className="mt-2 rounded-lg border border-[#DCE3DB] bg-[#E3EFE7] px-2.5 py-1.5 text-[12px] font-medium text-[#123B25]">
          {factText}
        </p>
      )}
      {cur.focusSearch && (
        <button
          type="button"
          onClick={onTry}
          className="mt-2 rounded-lg border border-[#1E5B3A] bg-[#E3EFE7] px-3 py-1.5 text-[12px] font-semibold text-[#123B25] hover:bg-[#D5E6DB]"
        >
          {t("story.try")}
        </button>
      )}
      <div className="mt-3 flex items-center justify-between">
        <div className="flex gap-1.5" aria-hidden="true">
          {STORY_STEPS.map((s, i) => (
            <span key={s.id} className={`h-2 w-2 rounded-full ${i === step ? "bg-[#1E5B3A]" : i < step ? "bg-[#6BAED6]" : "bg-[#DCE3DB]"}`} />
          ))}
        </div>
        <div className="flex gap-1.5">
          <button
            type="button"
            disabled={step === 0}
            onClick={() => onStep(step - 1)}
            className="h-8 rounded-lg border border-[#DCE3DB] bg-white px-3 text-[12px] font-medium text-[#16231B] hover:bg-[#F2F5F1] disabled:opacity-40"
          >
            {t("story.back")}
          </button>
          <button
            type="button"
            ref={nextRef}
            onClick={() => (step < last ? onStep(step + 1) : onClose())}
            className="h-8 rounded-lg bg-[#1E5B3A] px-3 text-[12px] font-semibold text-white hover:bg-[#123B25]"
            data-testid="story-next"
          >
            {step < last ? t("story.next") : t("story.done")}
          </button>
        </div>
      </div>
      <p className="mt-2 text-[11px] text-[#7A847D]">{t("story.keys")}</p>
    </div>
  );
}
