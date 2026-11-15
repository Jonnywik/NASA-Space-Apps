"use client";

import React, { useState } from "react";
import ExposureTable from "./ExposureTable";
import { Caveats, DemoTag, HelpButton, SourceLine, Stat, StateNote, fmt } from "./ui";
import { useLang } from "../utils/LangContext";

function shortMonthDay(iso) {
  if (!iso) return "—";
  const d = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
}

// N1 flood rhythm: "flooded on k of n passes".
export default function RhythmPanel({ tier, exposureTier, passes = [], onHelp, onPlace, onSources }) {
  const { t } = useLang();
  const [more, setMore] = useState(false);
  const d = tier.data;
  const n = d?.passCount ?? passes.length ?? null;
  const max = d ? Math.max(0.0001, ...((d.km2ByCount ?? []).map((r) => r.km2 ?? 0))) : 1;
  const firstDate = passes[0]?.date;
  const lastDate = passes[passes.length - 1]?.date;
  const fromLabel = shortMonthDay(firstDate);
  const toLabel = shortMonthDay(lastDate);
  const isDemo = d?.dataKind === "synthetic";
  const isExpDemo = exposureTier.data?.dataKind === "synthetic";
  const halfKm2 = fmt(d?.halfOrMoreKm2);
  const popVal = fmt(exposureTier.data?.totals?.population, 0);

  return (
    <div className="flex flex-1 flex-col gap-4 text-[#16231B]" data-testid="rhythm-panel">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] font-bold uppercase tracking-[0.08em] text-[#1E5B3A]">{t("rhythm.v2.eyebrow")}</span>
        {onHelp && <HelpButton card="water" onOpen={onHelp} />}
      </div>

      <StateNote tier={tier} label={t("rhythm.title")} />

      {d && (
        <>
          <div className="flex flex-col gap-1.5">
            <h1 className="m-0 font-serif text-[24px] font-semibold leading-[1.22] text-[#16231B]">
              {halfKm2 != null ? t("rhythm.v2.headline", { km2: halfKm2 }) : t("rhythm.v2.headlineMissing")}
            </h1>
            {isDemo && (
              <div className="flex">
                <DemoTag isNumber />
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 gap-2.5">
            <Stat
              label={t("rhythm.v2.stat.passes")}
              value={n}
              note={firstDate && lastDate ? t("rhythm.v2.stat.period", { from: fromLabel, to: toLabel }) : undefined}
              isDemo={isDemo}
            />
            <Stat
              label={t("rhythm.v2.stat.people")}
              value={popVal}
              note={
                exposureTier.data?.populationUnavailableReason
                  ? exposureTier.data.populationUnavailableReason
                  : t("rhythm.v2.stat.buildingsNote")
              }
              isDemo={isExpDemo}
            />
          </div>

          <div className="flex flex-col gap-1.5 border-t border-[#DCE3DB] pt-3.5">
            <h2 className="m-0 font-serif text-[16px] font-semibold text-[#16231B]">{t("rhythm.v2.plainTitle")}</h2>
            <p className="m-0 text-[13px] leading-[1.6] text-[#16231B]">
              {t("rhythm.v2.plainBody", { n: n ?? "—", from: fromLabel, to: toLabel })}{" "}
              <button
                type="button"
                onClick={() => setMore((m) => !m)}
                className="inline border-0 bg-transparent p-0 font-semibold text-[#1E5B3A] underline hover:text-[#123B25]"
              >
                {more ? t("rhythm.v2.readLess") : t("rhythm.v2.readMore")}
              </button>
            </p>
            {onHelp && (
              <div className="mt-1 flex flex-col items-start gap-1.5 rounded-xl border border-[#DCE3DB] bg-[#F2F5F1] p-3 text-[12px] leading-relaxed text-[#4A5850]">
                <p className="m-0">{t("rhythm.v2.limitsCallout")}</p>
                <button
                  type="button"
                  onClick={() => onHelp("limits")}
                  data-testid="open-nisar-limits"
                  className="rounded-lg border border-[#1E5B3A] bg-white px-2.5 py-1 text-[12px] font-semibold text-[#1E5B3A] hover:bg-[#E3EFE7]"
                >
                  {t("rhythm.v2.limitsBtn")}
                </button>
              </div>
            )}
          </div>

          {more && (
            <div className="flex flex-col gap-3 rounded-xl border border-[#DCE3DB] bg-[#F2F5F1] p-3">
              <div className="grid grid-cols-2 gap-2">
                {d.floodedAtLeastOnceKm2 != null && (
                  <Stat compact isDemo={isDemo} label={t("rhythm.once")} value={fmt(d.floodedAtLeastOnceKm2)} unit="km²" />
                )}
                {d.countableKm2 != null && (
                  <Stat
                    compact
                    isDemo={isDemo}
                    label={t("rhythm.countable")}
                    value={fmt(d.countableKm2)}
                    unit="km²"
                    note={d.minValidPasses != null ? t("rhythm.countable.note", { n: d.minValidPasses }) : null}
                  />
                )}
              </div>
              <h4 className="m-0 text-xs font-semibold text-[#16231B]">{t("rhythm.legend")}</h4>
              <ul className="m-0 list-none space-y-1 p-0" data-testid="rhythm-legend">
                {(d.legend ?? []).map((l) => {
                  const row = (d.km2ByCount ?? []).find((r) => r.count === l.count);
                  const km2 = row?.km2;
                  return (
                    <li key={l.count} className="flex items-center gap-2 text-[11px] text-[#16231B]">
                      <span aria-hidden="true" className="inline-block h-3.5 w-5 shrink-0 rounded-[2px] border border-[#C9D1C7]" style={{ background: l.color }} />
                      <span className="w-28 shrink-0">{t("rhythm.k_of_n", { k: l.count, n })}</span>
                      <span className="relative h-2 flex-1 rounded bg-[#DCE3DB]">
                        <span className="absolute inset-y-0 left-0 rounded bg-[#2171B5]" style={{ width: `${km2 != null ? Math.max(2, (km2 / max) * 100) : 0}%` }} />
                      </span>
                      <span className="w-16 shrink-0 text-right tabular-nums">{km2 != null ? `${fmt(km2)} km²` : "—"}</span>
                    </li>
                  );
                })}
              </ul>
              {Array.isArray(d.byValidPasses) && d.byValidPasses.length > 1 && (
                <p className="m-0 text-[11px] text-[#4A5850]">
                  {t("rhythm.byValid")} {d.byValidPasses.map((b) => `${b.validPasses}: ${fmt(b.km2)} km²`).join(" · ")}
                </p>
              )}
              {d.permanentWaterMasked && <p className="m-0 text-[11px] text-[#4A5850]">{t("rhythm.permanent")}</p>}
              {d.method && <p className="m-0 text-[11px] text-[#4A5850]">{d.method}</p>}
              <Caveats data={d} />
            </div>
          )}

          <details className="rounded-xl border border-[#DCE3DB] bg-white p-3">
            <summary className="cursor-pointer text-[13px] font-semibold text-[#16231B]">
              {t("exposure.title")}
              {exposureTier.data?.zones?.length ? ` (${exposureTier.data.zones.length})` : ""}
            </summary>
            <div className="mt-2">
              <p className="mb-1.5 text-[11px] text-[#4A5850]">{t("exposure.lead.rhythm")}</p>
              <ExposureTable tier={exposureTier} onPlace={onPlace} label={t("exposure.title")} />
            </div>
          </details>

          <SourceLine data={d} className="mt-auto pt-2" onSources={onSources} />
        </>
      )}
    </div>
  );
}
