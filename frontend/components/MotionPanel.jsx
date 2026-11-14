"use client";

import React from "react";
import ExposureTable from "./ExposureTable";
import { Caveats, Section, SourceLine, Stat, StateNote, fmt } from "./ui";
import { useLang } from "../utils/LangContext";

function span(epochs) {
  if (!Array.isArray(epochs) || epochs.length < 2) return null;
  return Math.round((Date.parse(epochs[epochs.length - 1]) - Date.parse(epochs[0])) / 86400000);
}

// N3 ground motion on camanava_2026, line of sight. Reference area, epochs and correction state come
// from the API; anything it does not report says so.
export default function MotionPanel({ tier, scale, rhythmUnder, onRhythmUnder, priorityTier, onHelp, onPlace }) {
  const { t } = useLang();
  const d = tier.data;
  const none = t("missing.notReported");
  const days = span(d?.epochs);
  const corrections = Array.isArray(d?.correctionsApplied) ? d.correctionsApplied : null;
  const med = d?.regionalSummary?.medianDisplacementMm;
  return (
    <>
      <Section title={t("motion.title")} sensor="insar" kind={d?.dataKind} helpCard="insar" onHelp={onHelp} testId="motion-panel">
        <p className="mb-2 rounded border border-orange-300/40 bg-orange-500/10 p-2 text-xs text-orange-100">{t("motion.los")}</p>
        <StateNote tier={tier} label={t("motion.title")} />
        {d && (
          <>
            <div className="grid grid-cols-2 gap-1.5">
              <Stat
                label={scale?.cumulative === false ? t("motion.median.rate") : t("motion.median.cum")}
                value={fmt(scale?.cumulative === false ? d.regionalSummary?.medianRateMmPerYear : med)}
                unit={scale?.cumulative === false ? "mm/yr" : "mm"}
                note={t("motion.positive")}
              />
              <Stat label={t("motion.epochs")} value={Array.isArray(d.epochs) ? d.epochs.length : null} note={days != null ? t("motion.span", { days }) : null} />
            </div>
            {days != null && <p className="mt-1.5 text-[11px] text-slate-300">{t("motion.cumulative", { days })}</p>}
            <p className="mt-1 text-[11px] text-slate-400">{t("motion.extrapolation")}</p>

            {scale && (
              <>
                <h4 className="mb-1 mt-3 text-xs font-semibold text-slate-200">
                  {scale.cumulative ? t("motion.legend.cum") : t("motion.legend.rate")} ({scale.unit})
                </h4>
                <ul className="space-y-0.5" data-testid="motion-legend">
                  {[...scale.bins].reverse().map((b, i) => (
                    <li key={b.color} className="flex items-center gap-2 text-[11px] text-slate-200">
                      <span aria-hidden="true" className="inline-block h-3.5 w-5 border border-white/60" style={{ background: b.color }} />
                      {i === 0 ? `≥ ${fmt(b.lo)}` : i === scale.bins.length - 1 ? `≤ ${fmt(b.hi)}` : `${fmt(b.lo)} … ${fmt(b.hi)}`} {scale.unit}
                      <span className="text-slate-400">{i < 2 ? t("motion.away") : i > 2 ? t("motion.toward") : t("motion.near0")}</span>
                    </li>
                  ))}
                </ul>
              </>
            )}

            <dl className="mt-3 grid grid-cols-[auto,1fr] gap-x-3 gap-y-1 text-[11px]" data-testid="motion-meta">
              <dt className="text-slate-400">{t("motion.ref.area")}</dt>
              <dd className="text-slate-100">{d.spatialReferenceId ?? none}</dd>
              <dt className="text-slate-400">{t("motion.ref.epoch")}</dt>
              <dd className="text-slate-100">{d.referenceEpoch ?? none}</dd>
              <dt className="text-slate-400">{t("motion.epochs.list")}</dt>
              <dd className="text-slate-100">{Array.isArray(d.epochs) ? `${d.epochs[0]} … ${d.epochs[d.epochs.length - 1]} (${d.epochs.length})` : none}</dd>
              <dt className="text-slate-400">{t("motion.corrections")}</dt>
              <dd className="text-slate-100">
                {d.correctionState ?? none}
                {corrections ? (corrections.length ? `: ${corrections.join(", ")}` : ` (${t("motion.corrections.none")})`) : ""}
              </dd>
              <dt className="text-slate-400">{t("motion.geometry")}</dt>
              <dd className="text-slate-100">
                {[d.track != null && `track ${d.track}`, d.flightDirection, d.frame != null && `frame ${d.frame}`, d.frequency, d.maturity].filter(Boolean).join(" · ") || none}
              </dd>
            </dl>

            <label className="mt-3 flex items-center gap-2 text-xs text-slate-200">
              <input type="checkbox" checked={rhythmUnder} onChange={(e) => onRhythmUnder(e.target.checked)} className="h-4 w-4 accent-sky-400" />
              {t("motion.rhythmUnder")}
            </label>
            <p className="mt-2 text-[11px] text-slate-300">{t("motion.click")}</p>
            <SourceLine data={d} className="mt-1" />
            <Caveats data={d} />
          </>
        )}
      </Section>

      <Section title={t("priority.title")} sensor="places" kind={priorityTier.data?.dataKind} testId="priority-zones">
        <p className="mb-1.5 text-[11px] text-slate-300">{t("priority.lead")}</p>
        <ExposureTable tier={priorityTier} onPlace={onPlace} label={t("priority.title")} />
      </Section>
    </>
  );
}
