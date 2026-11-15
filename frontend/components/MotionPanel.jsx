"use client";

import React from "react";
import ExposureTable from "./ExposureTable";
import { Caveats, DemoTag, HelpButton, SourceLine, Stat, StateNote, fmt } from "./ui";
import { useLang } from "../utils/LangContext";

function span(epochs) {
  if (!Array.isArray(epochs) || epochs.length < 2) return null;
  return Math.round((Date.parse(epochs[epochs.length - 1]) - Date.parse(epochs[0])) / 86400000);
}

function monthRange(epochs, lang = "en") {
  if (!Array.isArray(epochs) || !epochs.length) return "—";
  const fmtMonth = (iso) => new Date(`${iso}T00:00:00Z`).toLocaleDateString(lang === "fil" ? "fil-PH" : "en-GB", { month: "short", timeZone: "UTC" });
  return `${fmtMonth(epochs[0])} – ${fmtMonth(epochs[epochs.length - 1])}`;
}

export default function MotionPanel({ tier, scale, rhythmUnder, onRhythmUnder, priorityTier, onHelp, onPlace, onSources }) {
  const { t, lang } = useLang();
  const d = tier.data;
  const none = t("missing.notReported");
  const days = span(d?.epochs);
  const corrections = Array.isArray(d?.correctionsApplied) ? d.correctionsApplied : null;
  const med = d?.regionalSummary?.medianDisplacementMm;
  const isDemo = d?.dataKind === "synthetic";
  const isPrioDemo = priorityTier.data?.dataKind === "synthetic";
  const pairsCount = d?.pairCount ?? (Array.isArray(d?.epochs) && d.epochs.length > 1 ? d.epochs.length - 1 : null);
  const overlapKm2 = priorityTier.data?.totals?.areaKm2;

  return (
    <div className="flex flex-1 flex-col gap-4 text-[#16231B]" data-testid="motion-panel">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] font-bold uppercase tracking-[0.08em] text-[#7B3294]">{t("motion.v2.eyebrow")}</span>
        {onHelp && <HelpButton card="insar" onOpen={onHelp} />}
      </div>

      <div className="flex flex-col gap-1.5">
        <h1 className="m-0 font-serif text-[22px] font-semibold leading-[1.22] text-[#16231B]">
          {t("motion.title")}
        </h1>
      </div>

      {tier.state === "loading" ? (
        <StateNote tier={tier} label={t("motion.title")} />
      ) : !d ? (
        <div
          className="flex flex-col gap-2 rounded-xl border border-[#DCE3DB] bg-[#F2F5F1] p-3.5 text-[13px] leading-[1.55] text-[#16231B]"
          role="status"
          data-testid="motion-unavailable"
        >
          <p className="m-0 font-semibold text-[#16231B]">{t("state.unavailable.title")}</p>
          <p className="m-0 text-[#4A5850]">{t("motion.v2.unavailableIono")}</p>
          {tier.error?.detail?.message && (
            <p className="m-0 text-[11px] text-[#4A5850]">{tier.error.detail.message}</p>
          )}
        </div>
      ) : null}

      {!d && tier.state !== "loading" && (
        <div
          className="flex flex-col gap-1.5 rounded-xl border border-[#DCE3DB] bg-white p-3 text-[12px]"
          data-testid="priority-zones"
        >
          <div className="font-semibold text-[#16231B]">{t("priority.title")}</div>
          <p className="m-0 text-[#4A5850]" data-testid="priority-unavailable">
            {t("priority.v2.unavailable")}
          </p>
        </div>
      )}

      {d && (
        <>
          <div className="flex flex-col gap-1.5">
            <h1 className="m-0 font-serif text-[24px] font-semibold leading-[1.22] text-[#16231B]">
              {t("motion.v2.headline")}
            </h1>
            {isDemo && (
              <div className="flex">
                <DemoTag />
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 gap-2.5">
            <Stat
              compact
              isDemo={isDemo}
              label={t("motion.v2.stat.pairs")}
              value={pairsCount}
              note="consecutive L-band passes"
            />
            <Stat
              compact
              label={t("motion.v2.stat.period")}
              value={monthRange(d.epochs, lang)}
              note={days != null ? t("motion.span", { days }) : undefined}
            />
            <Stat
              compact
              isDemo={isDemo}
              label={scale?.cumulative === false ? t("motion.median.rate") : t("motion.median.cum")}
              value={fmt(scale?.cumulative === false ? d.regionalSummary?.medianRateMmPerYear : med)}
              unit={scale?.cumulative === false ? "mm/yr" : "mm"}
              note={t("motion.positive")}
            />
            <Stat
              compact
              isDemo={isPrioDemo}
              label={t("motion.v2.stat.overlap")}
              value={fmt(overlapKm2, 2)}
              unit={overlapKm2 != null ? "km²" : undefined}
              note={t("motion.v2.stat.overlapSub")}
            />
          </div>

          <div className="flex flex-col gap-1.5 border-t border-[#DCE3DB] pt-3.5">
            <h2 className="m-0 font-serif text-[16px] font-semibold text-[#16231B]">{t("rhythm.v2.plainTitle")}</h2>
            <p className="m-0 text-[13px] leading-[1.6] text-[#16231B]">{t("motion.v2.plainBody")}</p>
            <label className="mt-1.5 flex cursor-pointer items-center gap-2 text-[12px] font-medium text-[#16231B]">
              <input type="checkbox" checked={rhythmUnder} onChange={(e) => onRhythmUnder(e.target.checked)} className="h-4 w-4 accent-[#7B3294]" />
              {t("motion.rhythmUnder")}
            </label>
          </div>

          <details className="rounded-xl border border-[#DCE3DB] bg-white p-3" data-testid="priority-zones">
            <summary className="cursor-pointer text-[13px] font-semibold text-[#16231B]">
              {t("priority.title")} &amp; {t("motion.ref.area")}
            </summary>
            <div className="mt-2 space-y-3">
              <dl className="grid grid-cols-[auto,1fr] gap-x-3 gap-y-1 rounded-lg bg-[#F2F5F1] p-2.5 text-[11px]" data-testid="motion-meta">
                <dt className="text-[#4A5850]">{t("motion.ref.area")}</dt>
                <dd className="font-medium text-[#16231B]">{d.spatialReferenceId ?? none}</dd>
                <dt className="text-[#4A5850]">{t("motion.ref.epoch")}</dt>
                <dd className="font-medium text-[#16231B]">{d.referenceEpoch ?? none}</dd>
                <dt className="text-[#4A5850]">{t("motion.epochs.list")}</dt>
                <dd className="font-medium text-[#16231B]">{Array.isArray(d.epochs) ? `${d.epochs[0]} … ${d.epochs[d.epochs.length - 1]} (${d.epochs.length})` : none}</dd>
                <dt className="text-[#4A5850]">{t("motion.corrections")}</dt>
                <dd className="font-medium text-[#16231B]">
                  {d.correctionState ?? none}
                  {corrections ? (corrections.length ? `: ${corrections.join(", ")}` : ` (${t("motion.corrections.none")})`) : ""}
                </dd>
                <dt className="text-[#4A5850]">{t("motion.geometry")}</dt>
                <dd className="font-medium text-[#16231B]">
                  {[d.track != null && `track ${d.track}`, d.flightDirection, d.frame != null && `frame ${d.frame}`, d.frequency, d.maturity].filter(Boolean).join(" · ") || none}
                </dd>
              </dl>
              <p className="text-[11px] text-[#4A5850]">{t("priority.lead")}</p>
              <ExposureTable tier={priorityTier} onPlace={onPlace} label={t("priority.title")} />
              <Caveats data={d} />
            </div>
          </details>

          <SourceLine data={d} className="mt-auto pt-2" onSources={onSources} />
        </>
      )}
    </div>
  );
}
