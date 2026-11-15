"use client";

import React from "react";
import { Area, Bar, CartesianGrid, Cell, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";
import { Caveats, DemoTag, HelpButton, PALETTE, SourceLine, Stat, StateNote, fmt } from "./ui";
import { useLang } from "../utils/LangContext";

const ym = (r) => `${r.year}-${String(r.month).padStart(2, "0")}`;

function PhaseBand({ months, startMonth }) {
  const { t } = useLang();
  const nOut = months.filter((m) => m.status === "outlook").length;
  const nScn = months.filter((m) => m.status === "scenario").length;
  const total = Math.max(1, months.length);
  return (
    <div className="mb-2" data-testid="phase-band" role="group" aria-label={t("future.phase.aria")}>
      <div className="flex text-[11px] font-semibold">
        <div className="flex w-20 shrink-0 items-center justify-center rounded-l-md border border-[#1E5B3A] bg-[#E3EFE7] px-1.5 py-1 text-[#123B25]">
          ● {t("future.phase.obs")}
        </div>
        <div
          className="flex items-center justify-center border border-dashed border-[#2171B5] bg-[#EEF5FA] px-1.5 py-1 text-[#0B4F79]"
          style={{ flex: nOut / total }}
        >
          ▲ {t("future.phase.outlook", { n: nOut })}
        </div>
        <div
          className="flex items-center justify-center rounded-r-md border border-dotted border-[#6B5A9E] bg-[#ECE8F4] px-1.5 py-1 text-[#4E3F80]"
          style={{ flex: nScn / total }}
        >
          ◇ {t("future.phase.scenario", { n: nScn })}
        </div>
      </div>
      <p className="mt-1 text-[11px] text-[#4A5850]">{t("future.phase.note", { month: startMonth ?? "" })}</p>
    </div>
  );
}

export { PhaseBand };

function OutlookChart({ d }) {
  const { t } = useLang();
  const rows = d.months.map((m) => ({
    label: `${ym(m)}${m.fullMonth === false ? "*" : ""}`,
    spread: m.memberMinMm != null && m.memberMaxMm != null ? [m.memberMinMm, m.memberMaxMm] : null,
    mean: m.meanMm,
    anomaly: m.anomalyVsModelClimatologyMm,
    partial: m.fullMonth === false ? `${m.coveredDays}/${m.monthDays}` : null,
  }));
  return (
    <div className="h-44 w-full" role="img" aria-label={t("future.outlook.aria", { n: rows.length })} data-testid="outlook-chart">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={rows} margin={{ top: 6, right: 4, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="#DCE3DB" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="label" tick={{ fill: "#4A5850", fontSize: 10 }} tickFormatter={(l) => l.slice(2)} stroke="#DCE3DB" />
          <YAxis tick={{ fill: "#4A5850", fontSize: 10 }} width={48} unit=" mm" stroke="#DCE3DB" />
          <Tooltip
            contentStyle={{ background: "#FFFFFF", border: "1px solid #DCE3DB", borderRadius: 10, fontSize: 12, color: "#16231B" }}
            labelStyle={{ color: "#16231B", fontWeight: 600 }}
            formatter={(v, name, p) =>
              name === "spread"
                ? [`${v[0]} … ${v[1]} mm`, t("future.outlook.spread")]
                : [`${v} mm${p?.payload?.partial ? ` (${t("future.outlook.partial", { days: p.payload.partial })})` : ""}${p?.payload?.anomaly != null ? ` · ${t("future.outlook.anom", { mm: p.payload.anomaly })}` : ""}`, t("future.outlook.mean")]
            }
          />
          <Bar dataKey="spread" name="spread" fill="#6BAED6" fillOpacity={0.35} stroke="#2171B5" strokeDasharray="4 3" isAnimationActive={false} />
          <Line dataKey="mean" name="mean" stroke="#0B4F6C" strokeWidth={0} dot={{ r: 4, fill: "#0B4F6C", stroke: "#FFFFFF", strokeWidth: 1.5 }} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

function ScenarioRainChart({ sc }) {
  const { t } = useLang();
  const rows = sc.months.map((m) => ({ label: ym(m), mm: m.rainfallMm, status: m.status, outlookMean: m.outlook?.meanMm ?? null }));
  const hasOutlook = rows.some((r) => r.outlookMean != null);
  const firstScn = rows.find((r) => r.status === "scenario");
  return (
    <div className="h-44 w-full" role="img" aria-label={t("future.scenario.aria", { label: sc.label })} data-testid="scenario-chart">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={rows} margin={{ top: 14, right: 4, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="#DCE3DB" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="label" tick={{ fill: "#4A5850", fontSize: 10 }} tickFormatter={(l) => l.slice(2)} stroke="#DCE3DB" />
          <YAxis tick={{ fill: "#4A5850", fontSize: 10 }} width={48} unit=" mm" stroke="#DCE3DB" />
          <Tooltip
            contentStyle={{ background: "#FFFFFF", border: "1px solid #DCE3DB", borderRadius: 10, fontSize: 12, color: "#16231B" }}
            labelStyle={{ color: "#16231B", fontWeight: 600 }}
            formatter={(v, name, p) =>
              name === "outlookMean" ? [`${v} mm`, t("future.outlook.mean")] : [`${v} mm`, p?.payload?.status === "outlook" ? t("future.status.outlook") : t("future.status.scenario")]
            }
          />
          {firstScn && <ReferenceLine x={firstScn.label} stroke="#6B5A9E" strokeWidth={1.5} strokeDasharray="3 3" label={{ value: t("future.boundary"), fill: "#4E3F80", fontSize: 10, position: "insideTopRight" }} />}
          <Bar dataKey="mm" isAnimationActive={false} radius={[3, 3, 0, 0]}>
            {rows.map((r) => (
              <Cell
                key={r.label}
                fill={r.status === "outlook" ? "#6BAED6" : "#6B5A9E"}
                fillOpacity={r.status === "outlook" ? 0.85 : 0.8}
                stroke={r.status === "outlook" ? "#2171B5" : "#4E3F80"}
                strokeWidth={1}
                strokeDasharray={r.status === "outlook" ? "4 2" : undefined}
              />
            ))}
          </Bar>
          {hasOutlook && <Line dataKey="outlookMean" name="outlookMean" strokeWidth={0} dot={{ r: 4, fill: "#123B25", stroke: "#FFFFFF", strokeWidth: 1.5 }} isAnimationActive={false} />}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

function FloodScenarioChart({ d }) {
  const { t } = useLang();
  const rows = d.months.map((m) => ({
    label: ym(m),
    band: m.expectedFloodedKm2 ? [m.expectedFloodedKm2.low, m.expectedFloodedKm2.high] : null,
    base: m.expectedFloodedKm2?.base ?? null,
    status: m.status,
  }));
  const firstScn = rows.find((r) => r.status === "scenario");
  return (
    <div className="h-44 w-full" role="img" aria-label={t("future.flood.aria")} data-testid="flood-scenario-chart">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={rows} margin={{ top: 14, right: 4, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="#DCE3DB" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="label" tick={{ fill: "#4A5850", fontSize: 10 }} tickFormatter={(l) => l.slice(2)} stroke="#DCE3DB" />
          <YAxis tick={{ fill: "#4A5850", fontSize: 10 }} width={48} unit=" km²" stroke="#DCE3DB" />
          <Tooltip
            contentStyle={{ background: "#FFFFFF", border: "1px solid #DCE3DB", borderRadius: 10, fontSize: 12, color: "#16231B" }}
            labelStyle={{ color: "#16231B", fontWeight: 600 }}
            formatter={(v, name) => (name === "band" ? [`${v?.[0]} … ${v?.[1]} km²`, t("future.flood.band")] : [`${v} km²`, t("future.flood.base")])}
          />
          {firstScn && <ReferenceLine x={firstScn.label} stroke="#6B5A9E" strokeWidth={1.5} strokeDasharray="3 3" />}
          <Area dataKey="band" name="band" stroke="#6B5A9E" strokeDasharray="4 3" fill="#6B5A9E" fillOpacity={0.22} isAnimationActive={false} />
          <Line dataKey="base" name="base" stroke="#4E3F80" strokeWidth={2} strokeDasharray="5 3" dot={{ r: 3, fill: "#FFFFFF", stroke: "#4E3F80", strokeWidth: 1.5 }} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

function RelationshipChart({ rel }) {
  const { t } = useLang();
  return (
    <div className="h-32 w-full" role="img" aria-label={t("future.rel.aria", { n: rel.n })}>
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 6, right: 8, bottom: 14, left: 0 }}>
          <CartesianGrid stroke="#DCE3DB" strokeDasharray="3 3" />
          <XAxis type="number" dataKey="prior7DayMm" tick={{ fill: "#4A5850", fontSize: 10 }} stroke="#DCE3DB" label={{ value: t("future.rel.x"), position: "insideBottom", offset: -8, fill: "#4A5850", fontSize: 10 }} />
          <YAxis type="number" dataKey="floodedKm2" tick={{ fill: "#4A5850", fontSize: 10 }} width={36} stroke="#DCE3DB" />
          <Tooltip contentStyle={{ background: "#FFFFFF", border: "1px solid #DCE3DB", borderRadius: 10, fontSize: 12, color: "#16231B" }} />
          <Scatter data={rel.points} fill={PALETTE.purple} isAnimationActive={false} />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function FuturePanel({ outlookTier, scenariosTier, scenarioId, onScenario, floodTier, projectionNode, onHelp, onSources, activeMonthIdx = null }) {
  const { t } = useLang();
  const o = outlookTier.data;
  const sd = scenariosTier.data;
  const chosen = sd?.scenarios?.find((s) => s.id === scenarioId) ?? sd?.scenarios?.[0];
  const f = floodTier.data;
  const isDemo = [o, sd, f].some((x) => x?.dataKind === "synthetic");

  const firstMonth = o?.months?.[0];
  const anomVal = firstMonth?.anomalyVsModelClimatologyMm;
  const activeFloodMonth =
    (activeMonthIdx != null && f?.months?.[activeMonthIdx]?.expectedFloodedKm2 ? f.months[activeMonthIdx] : null) ??
    f?.months?.find((m) => m.status === "scenario" && m.expectedFloodedKm2) ??
    f?.months?.find((m) => m.expectedFloodedKm2) ??
    null;

  return (
    <div className="flex flex-1 flex-col gap-4 text-[#16231B]" data-testid="future-panel">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] font-bold uppercase tracking-[0.08em] text-[#6B5A9E]">{t("future.v2.eyebrow")}</span>
        {onHelp && <HelpButton card="insar" onOpen={onHelp} />}
      </div>

      <div className="flex flex-col gap-1.5">
        <h1 className="m-0 font-serif text-[22px] font-semibold leading-[1.22] tracking-[-0.015em] text-[#16231B]">
          {t("future.v2.headline")}
        </h1>
        {isDemo && (
          <div className="flex">
            <DemoTag isNumber />
          </div>
        )}
      </div>

      <div className="grid grid-cols-3 gap-2">
        <Stat
          compact
          isDemo={o?.dataKind === "synthetic"}
          label={t("future.v2.stat.covers")}
          value={o ? `${o.horizonMonths ?? o.months?.length ?? "—"}` : null}
          unit={o ? t("future.months") : undefined}
          note={
            o
              ? t("future.v2.stat.members", {
                  n: o.ensembleMembers ?? o.months?.[0]?.members ?? "—",
                  res: o.nativeResolution ?? "—",
                })
              : undefined
          }
        />
        <Stat
          compact
          isDemo={o?.dataKind === "synthetic"}
          label={t("future.v2.stat.anom")}
          value={anomVal != null ? `${anomVal > 0 ? "+" : ""}${fmt(anomVal, 0)}` : firstMonth?.meanMm != null ? fmt(firstMonth.meanMm, 0) : null}
          unit={anomVal != null || firstMonth?.meanMm != null ? "mm" : undefined}
          note={
            o && (
              <>
                <span data-testid="outlook-model">{o.model ?? (o.modelRequested ? t("future.outlook.requested", { model: o.modelRequested }) : t("missing.notReported"))}</span>
                {" · "}
                <span data-testid="outlook-run">{o.runDate ?? t("missing.notReported")}</span>
              </>
            )
          }
        />
        <Stat
          compact
          isDemo={f?.dataKind === "synthetic"}
          label={t("future.v2.stat.flood", { month: activeFloodMonth ? ym(activeFloodMonth) : "—" })}
          value={activeFloodMonth?.expectedFloodedKm2?.base != null ? fmt(activeFloodMonth.expectedFloodedKm2.base) : t("future.v2.stat.exploratory")}
          unit={activeFloodMonth?.expectedFloodedKm2?.base != null ? "km²" : undefined}
          note={<span data-testid="exploratory">{t("future.exploratory")}</span>}
        />
      </div>

      <StateNote tier={scenariosTier} label={t("future.scenario.title")} />

      {sd && chosen && (
        <div className="flex flex-col gap-3 rounded-xl border border-[#DCE3DB] bg-white p-3.5">
          <div>
            <h2 className="m-0 font-serif text-[15px] font-semibold text-[#16231B]">{t("future.v2.pickLabel")}</h2>
            <p className="mt-0.5 text-[12px] text-[#4A5850]">{t("future.scenario.lead")}</p>
          </div>

          <div role="radiogroup" aria-label={t("future.scenario.pick")} className="grid grid-cols-1 gap-2 sm:grid-cols-2" data-testid="scenario-picker">
            {sd.scenarios.map((s) => {
              const active = s.id === chosen.id;
              return (
                <button
                  key={s.id}
                  type="button"
                  role="radio"
                  aria-checked={active}
                  onClick={() => onScenario(s.id)}
                  className={`flex items-start gap-2 rounded-[10px] border px-3 py-2 text-left text-[12px] transition-colors ${
                    active ? "border-2 border-[#6B5A9E] bg-[#ECE8F4] text-[#4E3F80]" : "border-[#DCE3DB] bg-white text-[#16231B] hover:bg-[#F2F5F1]"
                  }`}
                >
                  <span
                    className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border ${
                      active ? "border-[#6B5A9E] bg-[#6B5A9E]" : "border-[#C9D1C7]"
                    }`}
                    aria-hidden="true"
                  >
                    {active && <span className="h-1.5 w-1.5 rounded-full bg-white" />}
                  </span>
                  <span>
                    <span className="block font-semibold">{s.label}</span>
                    {s.basis && <span className="block text-[11px] text-[#4A5850]">{s.basis}</span>}
                  </span>
                </button>
              );
            })}
          </div>

          <ScenarioRainChart sc={chosen} />

          <div className="flex flex-wrap items-center gap-3 text-[11px] text-[#4A5850]">
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-sm border border-[#2171B5] bg-[#6BAED6]" aria-hidden="true" />
              {t("future.v2.outlookMonths")}
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-sm border border-[#4E3F80] bg-[#6B5A9E]" aria-hidden="true" />
              {t("future.v2.scenarioMonths")}
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-[#123B25]" aria-hidden="true" />
              {t("future.v2.outlookMean")}
            </span>
          </div>

          {chosen.isEnvelope && <p className="m-0 text-[11px] text-[#4A5850]">{t("future.scenario.envelope")}</p>}
        </div>
      )}

      {/* NASA POWER dry-season caveat always sits directly beneath the 12-month chart */}
      <p className="m-0 rounded-[10px] border border-dashed border-[#7A5B00]/50 bg-[#FFF6DE] px-3 py-2.5 text-[12px] leading-[1.5] text-[#5A4300]" data-testid="power-caveat">
        <span aria-hidden="true">⚠ </span>
        {t("future.scenario.powerCaveat")}
      </p>

      <details className="rounded-xl border border-[#DCE3DB] bg-white px-3.5 py-2.5">
        <summary className="cursor-pointer text-[13px] font-semibold text-[#1E5B3A]">
          {t("future.outlook.title")} · {t("future.flood.title")} · {t("future.motion.title")}
        </summary>
        <div className="mt-3 flex flex-col gap-4 border-t border-[#DCE3DB] pt-3">
          <div>
            <h3 className="mb-1.5 text-[13px] font-semibold text-[#16231B]">{t("future.outlook.title")}</h3>
            <StateNote tier={outlookTier} label={t("future.outlook.title")} />
            {o && (
              <>
                {chosen && <PhaseBand months={chosen.months} startMonth={sd?.startMonth} />}
                <OutlookChart d={o} />
                <dl className="mt-2 grid grid-cols-[auto,1fr] gap-x-3 gap-y-0.5 text-[11px]">
                  <dt className="text-[#4A5850]">{t("future.outlook.horizon")}</dt>
                  <dd className="text-[#16231B]">
                    {o.horizonMonths ?? o.months?.length} {t("future.months")}
                    {o.fullMonths != null ? ` (${t("future.outlook.full", { n: o.fullMonths })})` : ""}
                  </dd>
                  <dt className="text-[#4A5850]">{t("future.outlook.res")}</dt>
                  <dd className="text-[#16231B]">{o.nativeResolution ?? t("missing.notReported")}</dd>
                  <dt className="text-[#4A5850]">{t("future.outlook.members")}</dt>
                  <dd className="text-[#16231B]">{o.ensembleMembers ?? o.months?.[0]?.members ?? t("missing.notReported")}</dd>
                  {o.firstForecastDate && (
                    <>
                      <dt className="text-[#4A5850]">{t("future.outlook.days")}</dt>
                      <dd className="text-[#16231B]">
                        {o.firstForecastDate} … {o.lastForecastDate ?? "—"}
                      </dd>
                    </>
                  )}
                  {o.anomaly && (
                    <>
                      <dt className="text-[#4A5850]">{t("future.outlook.anomaly")}</dt>
                      <dd className="text-[#16231B]">{o.anomaly.available ? o.anomaly.basis : o.anomaly.reason ?? t("missing.notReported")}</dd>
                    </>
                  )}
                </dl>
                <p className="mt-1.5 text-[11px] text-[#4A5850]">
                  {t("future.outlook.note")}
                  {o.months?.some((m) => m.fullMonth === false) ? ` ${t("future.outlook.star")}` : ""}
                </p>
                <Caveats data={o} />
              </>
            )}
          </div>

          <div>
            <h3 className="mb-1.5 text-[13px] font-semibold text-[#16231B]">{t("future.flood.title")}</h3>
            <StateNote tier={floodTier} label={t("future.flood.title")} />
            {f && (
              <>
                <FloodScenarioChart d={f} />
                <p className="mt-1 text-[11px] text-[#4A5850]">{t("future.flood.legend")}</p>
                {(() => {
                  const gaps = f.months.filter((m) => !m.expectedFloodedKm2);
                  if (!gaps.length) return null;
                  return (
                    <p className="mt-1 rounded-md bg-[#FFF6DE] px-2 py-1 text-[11px] text-[#5A4300]" data-testid="flood-gaps">
                      {t("future.flood.gaps", { n: gaps.length, of: f.months.length })} {gaps[0].reason ?? ""}
                    </p>
                  );
                })()}
                {f.assumptions?.length > 0 && (
                  <ul className="mt-1.5 list-disc space-y-0.5 pl-4 text-[11px] text-[#4A5850]">
                    {f.assumptions.map((a) => (
                      <li key={a}>{a}</li>
                    ))}
                  </ul>
                )}
                {f.relationship && (
                  <div className="mt-2">
                    <div className="text-[11px] font-semibold text-[#16231B]">{t("future.rel.title", { n: f.relationship.n })}</div>
                    <p className="mt-0.5 text-[11px] text-[#4A5850]">{f.relationship.method}</p>
                    <RelationshipChart rel={f.relationship} />
                  </div>
                )}
                <Caveats data={f} />
              </>
            )}
          </div>

          <div>
            <h3 className="mb-1.5 text-[13px] font-semibold text-[#16231B]">{t("future.motion.title")}</h3>
            {projectionNode}
          </div>
        </div>
      </details>

      {(sd ?? o ?? f) && (
        <div className="mt-auto border-t border-[#DCE3DB] pt-3">
          <SourceLine data={sd ?? o ?? f} onSources={onSources} />
          <Caveats data={sd} />
        </div>
      )}
    </div>
  );
}
