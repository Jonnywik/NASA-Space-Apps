"use client";

import React, { useState } from "react";
import ExposureTable from "./ExposureTable";
import { Caveats, DemoTag, HelpButton, SourceLine, Stat, StateNote, fmt } from "./ui";
import { useLang } from "../utils/LangContext";

function shortMonthDay(iso, lang = "en") {
  if (!iso) return "—";
  const d = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(lang === "fil" ? "fil-PH" : "en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
}

function RainWaterScatter({ passes, imergPasses }) {
  const { t, lang } = useLang();
  const [showTable, setShowTable] = useState(false);
  const [activeDate, setActiveDate] = useState(null);

  const imergMap = new Map((imergPasses ?? []).map((p) => [p.date, p.last48hMm]));
  const pts = (passes ?? [])
    .map((p) => ({ date: p.date, rain48h: imergMap.get(p.date), waterKm2: p.floodedKm2 }))
    .filter((p) => typeof p.rain48h === "number" && Number.isFinite(p.rain48h) && typeof p.waterKm2 === "number" && Number.isFinite(p.waterKm2));

  if (!pts.length) return null;

  const rains = pts.map((p) => p.rain48h);
  const waters = pts.map((p) => p.waterKm2);
  const minRain = Math.min(...rains);
  const maxRain = Math.max(...rains);
  const minWater = Math.min(...waters);
  const maxWater = Math.max(...waters);
  const maxX = Math.max(20, Math.ceil(maxRain / 20) * 20);
  const maxY = maxWater <= 1 ? Math.max(0.2, Math.ceil(maxWater * 10) / 10) : Math.ceil(maxWater * 1.1);
  const yDigits = maxY <= 2 ? 2 : 1;

  const W = 360;
  const H = 190;
  const padL = 42;
  const padR = 16;
  const padT = 20;
  const padB = 34;
  const plotW = W - padL - padR;
  const plotH = H - padT - padB;
  const xPos = (x) => padL + (x / maxX) * plotW;
  const yPos = (y) => padT + plotH - (y / maxY) * plotH;

  const yTicks = [0, maxY / 2, maxY];
  const xTicks = [0, maxX / 2, maxX];
  const activePt = pts.find((p) => p.date === activeDate) ?? pts[0];
  const aria = t("rhythm.v2.scatter.aria", {
    n: pts.length,
    minRain: fmt(minRain, 1),
    maxRain: fmt(maxRain, 1),
    minWater: fmt(minWater, 2),
    maxWater: fmt(maxWater, 2),
  });

  return (
    <div className="flex flex-col gap-2 rounded-xl border border-[#DCE3DB] bg-white p-3" data-testid="rhythm-rain-scatter">
      <div className="flex items-center justify-between gap-2">
        <h3 className="m-0 font-serif text-[15px] font-semibold text-[#16231B]">{t("rhythm.v2.scatter.title")}</h3>
        <button
          type="button"
          onClick={() => setShowTable((s) => !s)}
          aria-expanded={showTable}
          className="rounded-lg border border-[#DCE3DB] bg-[#F2F5F1] px-2.5 py-1 text-[11px] font-semibold text-[#1E5B3A] hover:bg-[#E3EFE7]"
          data-testid="rhythm-scatter-table-toggle"
        >
          {showTable ? t("rhythm.v2.scatter.hideTable") : t("rhythm.v2.scatter.showTable")}
        </button>
      </div>

      {activePt && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-[#F2F5F1] px-2.5 py-1 text-[11px] text-[#16231B]" data-testid="rhythm-scatter-readout">
          <span className="font-semibold text-[#1E5B3A]">{activePt.date}</span>
          <span className="tabular-nums">
            {fmt(activePt.rain48h, 1)} mm · {fmt(activePt.waterKm2, 2)} km²
          </span>
        </div>
      )}

      {!showTable ? (
        <svg viewBox={`0 0 ${W} ${H}`} className="h-[190px] w-full overflow-visible" role="img" aria-label={aria} data-testid="rhythm-scatter-svg">
          <text x={padL} y={12} fontSize="10" fill="#4A5850">
            {t("rhythm.v2.scatter.yAxis")}
          </text>
          {yTicks.map((v) => {
            const y = yPos(v);
            return (
              <g key={`y-${v}`}>
                <line x1={padL} x2={W - padR} y1={y} y2={y} stroke="#DCE3DB" strokeDasharray={v > 0 ? "3 3" : undefined} />
                <text x={padL - 5} y={y + 3} textAnchor="end" fontSize="10" fill="#4A5850">
                  {fmt(v, yDigits)}
                </text>
              </g>
            );
          })}
          {xTicks.map((v) => {
            const x = xPos(v);
            return (
              <g key={`x-${v}`}>
                <line x1={x} x2={x} y1={padT} y2={padT + plotH} stroke="#DCE3DB" strokeDasharray={v > 0 ? "3 3" : undefined} />
                <text x={x} y={padT + plotH + 13} textAnchor="middle" fontSize="10" fill="#4A5850">
                  {fmt(v, 0)}
                </text>
              </g>
            );
          })}
          <text x={padL + plotW / 2} y={H - 4} textAnchor="middle" fontSize="10" fill="#4A5850">
            {t("rhythm.v2.scatter.xAxis")}
          </text>
          {pts.map((pt) => {
            const cx = xPos(pt.rain48h);
            const cy = yPos(pt.waterKm2);
            const isActive = activePt?.date === pt.date;
            return (
              <g
                key={pt.date}
                tabIndex={0}
                onMouseEnter={() => setActiveDate(pt.date)}
                onFocus={() => setActiveDate(pt.date)}
                onClick={() => setActiveDate(pt.date)}
                className="cursor-pointer outline-none"
                aria-label={`${pt.date}: ${fmt(pt.rain48h, 1)} mm, ${fmt(pt.waterKm2, 2)} km²`}
                data-testid={`scatter-dot-${pt.date}`}
              >
                <title>{`${pt.date}: ${fmt(pt.rain48h, 1)} mm · ${fmt(pt.waterKm2, 2)} km²`}</title>
                <circle
                  cx={cx}
                  cy={cy}
                  r={isActive ? 6 : 4.5}
                  fill={isActive ? "#1E5B3A" : "#2171B5"}
                  stroke="#FFFFFF"
                  strokeWidth={1.5}
                />
                {isActive && (
                  <text
                    x={cx > padL + plotW - 44 ? cx - 8 : cx + 8}
                    y={Math.max(padT + 10, cy - 6)}
                    textAnchor={cx > padL + plotW - 44 ? "end" : "start"}
                    fontSize="10"
                    fontWeight="600"
                    fill="#16231B"
                  >
                    {shortMonthDay(pt.date, lang)}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      ) : (
        <div className="max-h-52 overflow-y-auto rounded-lg border border-[#DCE3DB]">
          <table className="w-full text-left text-[11px] text-[#16231B]" data-testid="rhythm-scatter-table">
            <thead className="bg-[#F2F5F1] text-[#4A5850]">
              <tr>
                <th className="px-2.5 py-1.5 font-semibold">{t("rhythm.v2.scatter.colDate")}</th>
                <th className="px-2.5 py-1.5 text-right font-semibold">{t("rhythm.v2.scatter.colRain")}</th>
                <th className="px-2.5 py-1.5 text-right font-semibold">{t("rhythm.v2.scatter.colWater")}</th>
              </tr>
            </thead>
            <tbody>
              {pts.map((pt) => (
                <tr key={pt.date} className="border-t border-[#DCE3DB]">
                  <td className="px-2.5 py-1 font-medium">{pt.date}</td>
                  <td className="px-2.5 py-1 text-right tabular-nums">{fmt(pt.rain48h, 1)}</td>
                  <td className="px-2.5 py-1 text-right tabular-nums">{fmt(pt.waterKm2, 2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="m-0 text-[11px] leading-relaxed text-[#4A5850]">{t("rhythm.v2.scatter.caption")}</p>
      <p className="m-0 text-[11px] font-medium text-[#4A5850]">{t("rhythm.v2.scatter.sources")}</p>
    </div>
  );
}

// N1 flood rhythm: "flooded on k of n passes".
export default function RhythmPanel({ tier, exposureTier, passes = [], imergTier, onHelp, onPlace, onSources }) {
  const { t, lang } = useLang();
  const [more, setMore] = useState(false);
  const d = tier.data;
  const n = d?.passCount ?? passes.length ?? null;
  const max = d ? Math.max(0.0001, ...((d.km2ByCount ?? []).map((r) => r.km2 ?? 0))) : 1;
  const firstDate = passes[0]?.date;
  const lastDate = passes[passes.length - 1]?.date;
  const fromLabel = shortMonthDay(firstDate, lang);
  const toLabel = shortMonthDay(lastDate, lang);
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

          <RainWaterScatter passes={passes} imergPasses={imergTier?.data?.passes} />

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
