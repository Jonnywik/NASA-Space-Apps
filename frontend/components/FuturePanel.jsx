"use client";

import React from "react";
import { Area, Bar, CartesianGrid, Cell, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";
import { Caveats, PALETTE, Section, SourceLine, StateNote, fmt } from "./ui";
import { useLang } from "../utils/LangContext";

const ym = (r) => `${r.year}-${String(r.month).padStart(2, "0")}`;

// A labelled band that shows where observations end, where the outlook runs and where conditional
// scenarios begin. The three segments differ in pattern as well as colour.
export function PhaseBand({ months, startMonth }) {
  const { t } = useLang();
  const nOut = months.filter((m) => m.status === "outlook").length;
  const nScn = months.filter((m) => m.status === "scenario").length;
  const total = Math.max(1, months.length);
  return (
    <div className="mb-2" data-testid="phase-band" role="group" aria-label={t("future.phase.aria")}>
      <div className="flex text-[11px] font-semibold">
        <div className="flex w-20 shrink-0 items-center justify-center rounded-l border-2 border-solid border-sky-300 bg-sky-500/20 px-1 text-sky-100">
          ● {t("future.phase.obs")}
        </div>
        <div
          className="flex items-center justify-center border-2 border-dashed border-amber-300 bg-amber-500/15 px-1 text-amber-100"
          style={{ flex: nOut / total }}
        >
          ▲ {t("future.phase.outlook", { n: nOut })}
        </div>
        <div
          className="flex items-center justify-center rounded-r border-2 border-dotted border-fuchsia-300 bg-fuchsia-500/15 px-1 text-fuchsia-100"
          style={{ flex: nScn / total, backgroundImage: "repeating-linear-gradient(45deg, rgba(240,171,252,.18) 0 4px, transparent 4px 8px)" }}
        >
          ◇ {t("future.phase.scenario", { n: nScn })}
        </div>
      </div>
      <p className="mt-0.5 text-[11px] text-slate-400">{t("future.phase.note", { month: startMonth ?? "" })}</p>
    </div>
  );
}

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
          <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
          <XAxis dataKey="label" tick={{ fill: "#cbd5e1", fontSize: 10 }} tickFormatter={(l) => l.slice(2)} />
          <YAxis tick={{ fill: "#cbd5e1", fontSize: 10 }} width={42} unit=" mm" />
          <Tooltip
            contentStyle={{ background: "#0f172a", border: "1px solid #475569", fontSize: 12 }}
            labelStyle={{ color: "#e2e8f0" }}
            formatter={(v, name, p) =>
              name === "spread"
                ? [`${v[0]} … ${v[1]} mm`, t("future.outlook.spread")]
                : [`${v} mm${p?.payload?.partial ? ` (${t("future.outlook.partial", { days: p.payload.partial })})` : ""}${p?.payload?.anomaly != null ? ` · ${t("future.outlook.anom", { mm: p.payload.anomaly })}` : ""}`, t("future.outlook.mean")]
            }
          />
          <Bar dataKey="spread" name="spread" fill="#fbbf24" fillOpacity={0.3} stroke="#fcd34d" strokeDasharray="4 3" isAnimationActive={false} />
          <Line dataKey="mean" name="mean" stroke="#fde68a" strokeWidth={0} dot={{ r: 5, fill: "#fde68a", stroke: "#0f172a", strokeWidth: 1 }} isAnimationActive={false} />
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
          <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
          <XAxis dataKey="label" tick={{ fill: "#cbd5e1", fontSize: 10 }} tickFormatter={(l) => l.slice(2)} />
          <YAxis tick={{ fill: "#cbd5e1", fontSize: 10 }} width={42} unit=" mm" />
          <Tooltip
            contentStyle={{ background: "#0f172a", border: "1px solid #475569", fontSize: 12 }}
            labelStyle={{ color: "#e2e8f0" }}
            formatter={(v, name, p) =>
              name === "outlookMean" ? [`${v} mm`, t("future.outlook.mean")] : [`${v} mm`, p?.payload?.status === "outlook" ? t("future.status.outlook") : t("future.status.scenario")]
            }
          />
          {firstScn && <ReferenceLine x={firstScn.label} stroke="#f0abfc" strokeWidth={2} strokeDasharray="2 3" label={{ value: t("future.boundary"), fill: "#f0abfc", fontSize: 10, position: "insideTopRight" }} />}
          <Bar dataKey="mm" isAnimationActive={false}>
            {rows.map((r) => (
              <Cell
                key={r.label}
                fill={r.status === "outlook" ? "#fbbf24" : "#e879f9"}
                fillOpacity={r.status === "outlook" ? 0.4 : 0.55}
                stroke={r.status === "outlook" ? "#fcd34d" : "#f0abfc"}
                strokeWidth={2}
                strokeDasharray={r.status === "outlook" ? "5 3" : "1 3"}
              />
            ))}
          </Bar>
          {hasOutlook && <Line dataKey="outlookMean" name="outlookMean" strokeWidth={0} dot={{ r: 4, fill: "#fde68a", stroke: "#0f172a", strokeWidth: 1 }} isAnimationActive={false} />}
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
          <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
          <XAxis dataKey="label" tick={{ fill: "#cbd5e1", fontSize: 10 }} tickFormatter={(l) => l.slice(2)} />
          <YAxis tick={{ fill: "#cbd5e1", fontSize: 10 }} width={42} unit=" km²" />
          <Tooltip
            contentStyle={{ background: "#0f172a", border: "1px solid #475569", fontSize: 12 }}
            labelStyle={{ color: "#e2e8f0" }}
            formatter={(v, name) => (name === "band" ? [`${v?.[0]} … ${v?.[1]} km²`, t("future.flood.band")] : [`${v} km²`, t("future.flood.base")])}
          />
          {firstScn && <ReferenceLine x={firstScn.label} stroke="#f0abfc" strokeWidth={2} strokeDasharray="2 3" />}
          <Area dataKey="band" name="band" stroke="#c4b5fd" strokeDasharray="4 3" fill="#a78bfa" fillOpacity={0.3} isAnimationActive={false} />
          <Line dataKey="base" name="base" stroke="#f5f3ff" strokeWidth={2} strokeDasharray="6 3" dot={{ r: 3, fill: "#0f172a", stroke: "#f5f3ff" }} isAnimationActive={false} />
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
          <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
          <XAxis type="number" dataKey="prior7DayMm" tick={{ fill: "#cbd5e1", fontSize: 10 }} label={{ value: t("future.rel.x"), position: "insideBottom", offset: -8, fill: "#cbd5e1", fontSize: 10 }} />
          <YAxis type="number" dataKey="floodedKm2" tick={{ fill: "#cbd5e1", fontSize: 10 }} width={36} />
          <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #475569", fontSize: 12 }} />
          <Scatter data={rel.points} fill={PALETTE.vermillion} isAnimationActive={false} />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

const kindOf = (d, fallback) => (d?.dataKind === "synthetic" ? "synthetic" : fallback);

export default function FuturePanel({ outlookTier, scenariosTier, scenarioId, onScenario, floodTier, projectionNode, onHelp }) {
  const { t } = useLang();
  const o = outlookTier.data;
  const sd = scenariosTier.data;
  const chosen = sd?.scenarios?.find((s) => s.id === scenarioId) ?? sd?.scenarios?.[0];
  const f = floodTier.data;
  return (
    <>
      <Section title={t("future.outlook.title")} sensor="outlook" kind={kindOf(o, "outlook")} testId="future-panel">
        <p className="mb-2 text-xs text-slate-300">{t("future.outlook.lead")}</p>
        <StateNote tier={outlookTier} label={t("future.outlook.title")} />
        {o && (
          <>
            <OutlookChart d={o} />
            <dl className="mt-1 grid grid-cols-[auto,1fr] gap-x-3 text-[11px]">
              <dt className="text-slate-400">{t("future.outlook.model")}</dt>
              <dd className="text-slate-100" data-testid="outlook-model">
                {o.model ?? (o.modelRequested ? t("future.outlook.requested", { model: o.modelRequested }) : t("missing.notReported"))}
                {!o.model && o.modelNote && <span className="block text-slate-400">{o.modelNote}</span>}
              </dd>
              <dt className="text-slate-400">{t("future.outlook.run")}</dt>
              <dd className="text-slate-100" data-testid="outlook-run">
                {o.runDate ?? t("missing.notReported")}
                {!o.runDate && o.runDateReason && <span className="block text-slate-400">{o.runDateReason}</span>}
              </dd>
              {o.firstForecastDate && (
                <>
                  <dt className="text-slate-400">{t("future.outlook.days")}</dt>
                  <dd className="text-slate-100">
                    {o.firstForecastDate} … {o.lastForecastDate ?? "—"}
                  </dd>
                </>
              )}
              <dt className="text-slate-400">{t("future.outlook.horizon")}</dt>
              <dd className="text-slate-100">
                {o.horizonMonths ?? o.months?.length} {t("future.months")}
                {o.fullMonths != null ? ` (${t("future.outlook.full", { n: o.fullMonths })})` : ""}
              </dd>
              <dt className="text-slate-400">{t("future.outlook.res")}</dt>
              <dd className="text-slate-100">{o.nativeResolution ?? t("missing.notReported")}</dd>
              <dt className="text-slate-400">{t("future.outlook.members")}</dt>
              <dd className="text-slate-100">{o.ensembleMembers ?? o.months?.[0]?.members ?? t("missing.notReported")}</dd>
              {o.anomaly && (
                <>
                  <dt className="text-slate-400">{t("future.outlook.anomaly")}</dt>
                  <dd className="text-slate-100">{o.anomaly.available ? o.anomaly.basis : o.anomaly.reason ?? t("missing.notReported")}</dd>
                </>
              )}
            </dl>
            <p className="mt-1 text-[11px] text-slate-300">
              {t("future.outlook.note")}
              {o.months?.some((m) => m.fullMonth === false) ? ` ${t("future.outlook.star")}` : ""}
            </p>
            <SourceLine data={o} className="mt-1" />
            <Caveats data={o} />
          </>
        )}
      </Section>

      <Section title={t("future.scenario.title")} sensor="power" kind={kindOf(sd, "scenario")}>
        <p className="mb-2 text-xs font-semibold text-fuchsia-100">{t("future.scenario.lead")}</p>
        <StateNote tier={scenariosTier} label={t("future.scenario.title")} />
        {sd && chosen && (
          <>
            <div role="radiogroup" aria-label={t("future.scenario.pick")} className="mb-2 grid gap-1" data-testid="scenario-picker">
              {sd.scenarios.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  role="radio"
                  aria-checked={s.id === chosen.id}
                  onClick={() => onScenario(s.id)}
                  className={`rounded-md border px-2 py-1.5 text-left text-xs ${s.id === chosen.id ? "border-fuchsia-300 bg-fuchsia-600/25 text-white" : "border-slate-600 bg-slate-800 text-slate-300 hover:bg-slate-700"}`}
                >
                  {s.id === chosen.id ? "● " : "○ "}
                  {s.label}
                  {s.basis && <span className="block text-[11px] text-slate-400">{s.basis}</span>}
                </button>
              ))}
            </div>
            <PhaseBand months={chosen.months} startMonth={sd.startMonth} />
            <ScenarioRainChart sc={chosen} />
            <p className="text-[11px] text-slate-300">{t("future.scenario.bars")}</p>
            {chosen.isEnvelope && <p className="text-[11px] text-amber-200">{t("future.scenario.envelope")}</p>}
            <SourceLine data={sd} className="mt-1" />
            <Caveats data={sd} />
          </>
        )}
      </Section>

      <Section title={t("future.flood.title")} sensor="nisar_l" kind={kindOf(f, "scenario")}>
        <p className="mb-1 inline-block rounded border-2 border-dashed border-violet-300 bg-violet-500/20 px-2 py-0.5 text-xs font-black uppercase tracking-wider text-violet-100" data-testid="exploratory">
          {t("future.exploratory")}
        </p>
        <StateNote tier={floodTier} label={t("future.flood.title")} />
        {f && (
          <>
            <FloodScenarioChart d={f} />
            <p className="text-[11px] text-slate-300">{t("future.flood.legend")}</p>
            {(() => {
              const gaps = f.months.filter((m) => !m.expectedFloodedKm2);
              if (!gaps.length) return null;
              return (
                <p className="mt-1 text-[11px] text-amber-200" data-testid="flood-gaps">
                  {t("future.flood.gaps", { n: gaps.length, of: f.months.length })} {gaps[0].reason ?? ""}
                </p>
              );
            })()}
            {f.assumptions?.length > 0 && (
              <ul className="mt-1 list-disc pl-4 text-[11px] text-slate-400">
                {f.assumptions.map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ul>
            )}
            {f.relationship && (
              <details className="mt-2 text-[11px] text-slate-300">
                <summary className="cursor-pointer">{t("future.rel.title", { n: f.relationship.n })}</summary>
                <p className="mt-1 text-slate-400">{f.relationship.method}</p>
                <RelationshipChart rel={f.relationship} />
              </details>
            )}
            <SourceLine data={f} className="mt-1" />
            <Caveats data={f} />
          </>
        )}
      </Section>

      <Section title={t("future.motion.title")} sensor="insar" kind="scenario" helpCard="insar" onHelp={onHelp}>
        {projectionNode}
      </Section>
    </>
  );
}
