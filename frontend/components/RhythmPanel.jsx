"use client";

import React from "react";
import ExposureTable from "./ExposureTable";
import { Caveats, Section, SourceLine, Stat, StateNote, fmt } from "./ui";
import { useLang } from "../utils/LangContext";

// N1 flood rhythm: "flooded on k of n passes".
export default function RhythmPanel({ tier, exposureTier, onHelp, onPlace }) {
  const { t } = useLang();
  const d = tier.data;
  const n = d?.passCount;
  const max = d ? Math.max(0.0001, ...((d.km2ByCount ?? []).map((r) => r.km2 ?? 0))) : 1;
  return (
    <>
      <Section title={t("rhythm.title")} sensor="nisar_l" kind={d?.dataKind} helpCard="water" onHelp={onHelp} testId="rhythm-panel">
        <p className="mb-2 text-xs text-slate-300">{t("rhythm.lead")}</p>
        <StateNote tier={tier} label={t("rhythm.title")} />
        {d && (
          <>
            <div className="grid grid-cols-2 gap-1.5">
              <Stat label={t("rhythm.passes")} value={n} />
              <Stat label={t("rhythm.half")} value={fmt(d.halfOrMoreKm2)} unit="km²" note={t("rhythm.half.note")} />
              {d.floodedAtLeastOnceKm2 != null && <Stat label={t("rhythm.once")} value={fmt(d.floodedAtLeastOnceKm2)} unit="km²" />}
              {d.countableKm2 != null && <Stat label={t("rhythm.countable")} value={fmt(d.countableKm2)} unit="km²" note={d.minValidPasses != null ? t("rhythm.countable.note", { n: d.minValidPasses }) : null} />}
            </div>
            <h4 className="mb-1 mt-3 text-xs font-semibold text-slate-200">{t("rhythm.legend")}</h4>
            <ul className="space-y-1" data-testid="rhythm-legend">
              {(d.legend ?? []).map((l) => {
                const row = (d.km2ByCount ?? []).find((r) => r.count === l.count);
                const km2 = row?.km2;
                return (
                  <li key={l.count} className="flex items-center gap-2 text-[11px] text-slate-200">
                    <span aria-hidden="true" className="inline-block h-3.5 w-5 shrink-0 border border-white/60" style={{ background: l.color }} />
                    <span className="w-28 shrink-0">{t("rhythm.k_of_n", { k: l.count, n })}</span>
                    <span className="relative h-2 flex-1 rounded bg-slate-700">
                      <span className="absolute inset-y-0 left-0 rounded bg-slate-300" style={{ width: `${km2 != null ? Math.max(2, (km2 / max) * 100) : 0}%` }} />
                    </span>
                    <span className="w-16 shrink-0 text-right">{km2 != null ? `${fmt(km2)} km²` : "—"}</span>
                  </li>
                );
              })}
              {d.permanentWaterMasked && (
                <li className="flex items-center gap-2 text-[11px] text-slate-300">
                  <span aria-hidden="true" className="inline-block h-3.5 w-5 shrink-0 border border-white/60" style={{ background: "#999999", opacity: 0.6, backgroundImage: "repeating-linear-gradient(45deg, rgba(0,0,0,.35) 0 2px, transparent 2px 5px)" }} />
                  {t("rhythm.permanent.legend")}
                </li>
              )}
            </ul>
            {Array.isArray(d.byValidPasses) && d.byValidPasses.length > 1 && (
              <p className="mt-2 text-[11px] text-slate-400">
                {t("rhythm.byValid")}{" "}
                {d.byValidPasses.map((b) => `${b.validPasses}: ${fmt(b.km2)} km²`).join(" · ")}
              </p>
            )}
            {d.permanentWaterMasked && <p className="mt-2 text-[11px] text-slate-300">{t("rhythm.permanent")}</p>}
            <p className="mt-1 text-[11px] text-slate-400">{d.method}</p>
            <SourceLine data={d} className="mt-1" />
            <Caveats data={d} />
          </>
        )}
      </Section>
      <Section title={t("exposure.title")} sensor="places" kind={exposureTier.data?.dataKind}>
        <p className="mb-1.5 text-[11px] text-slate-400">{t("exposure.lead.rhythm")}</p>
        <ExposureTable tier={exposureTier} onPlace={onPlace} label={t("exposure.title")} />
      </Section>
    </>
  );
}
