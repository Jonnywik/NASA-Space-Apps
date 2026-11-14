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
      className="absolute bottom-3 left-3 z-[1100] w-[min(360px,calc(100%-1.5rem))] rounded-xl border border-yellow-300/70 bg-slate-900/95 p-3.5 text-white shadow-2xl backdrop-blur"
      data-testid="story"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-yellow-200">
          {t("story.label")} · {t("story.step", { i: step + 1, n: STORY_STEPS.length })}
        </span>
        <button type="button" onClick={onClose} className="rounded border border-slate-500 px-2 py-0.5 text-xs text-slate-100 hover:bg-slate-700" data-testid="story-skip">
          {step === last ? t("story.close") : t("story.skip")}
        </button>
      </div>
      <h2 id="story-title" className="mt-1.5 text-base font-bold">
        {t(`story.${step + 1}.title`)}
      </h2>
      <p id="story-body" className="mt-1 text-sm leading-snug text-slate-200">
        {t(`story.${step + 1}.body`)}
      </p>
      {factText && <p className="mt-1.5 rounded bg-slate-800 px-2 py-1 text-xs text-sky-100">{factText}</p>}
      {cur.focusSearch && (
        <button type="button" onClick={onTry} className="mt-2 rounded-md border border-yellow-300 bg-yellow-300/20 px-2.5 py-1 text-xs font-semibold text-yellow-100 hover:bg-yellow-300/30">
          {t("story.try")}
        </button>
      )}
      <div className="mt-3 flex items-center justify-between">
        <div className="flex gap-1.5" aria-hidden="true">
          {STORY_STEPS.map((s, i) => (
            <span key={s.id} className={`h-2 w-2 rounded-full ${i === step ? "bg-yellow-300" : i < step ? "bg-slate-300" : "bg-slate-600"}`} />
          ))}
        </div>
        <div className="flex gap-1.5">
          <button type="button" disabled={step === 0} onClick={() => onStep(step - 1)} className="rounded-md border border-slate-500 bg-slate-800 px-3 py-1 text-xs font-semibold hover:bg-slate-700 disabled:opacity-40">
            {t("story.back")}
          </button>
          <button
            type="button"
            ref={nextRef}
            onClick={() => (step < last ? onStep(step + 1) : onClose())}
            className="rounded-md border border-sky-300 bg-sky-600 px-3 py-1 text-xs font-semibold hover:bg-sky-500"
            data-testid="story-next"
          >
            {step < last ? t("story.next") : t("story.done")}
          </button>
        </div>
      </div>
      <p className="mt-2 text-[11px] text-slate-400">{t("story.keys")}</p>
    </div>
  );
}
