"use client";

import React, { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Caveats, PALETTE, Section, SourceLine, Stat, StateNote, fmt } from "./ui";
import { useLang } from "../utils/LangContext";

export const HISTORY_START = "2000-01-01";
const KIND_LABEL = { climate: "kind.climate", optical: "kind.optical", sar_c: "kind.sar_c", sar_l: "kind.sar_l", insar: "kind.insar" };
const NOW_ISO = () => new Date().toISOString().slice(0, 10);

export function datasetAt(ds, date) {
  const end = ds.end ?? NOW_ISO();
  if (date < ds.start) return { ok: false, why: "starts", when: ds.start };
  if (date > end) return { ok: false, why: "ended", when: end };
  return { ok: true };
}

function pct(date, t0, t1) {
  return Math.min(100, Math.max(0, ((Date.parse(date) - t0) / (t1 - t0)) * 100));
}

// F1: which dataset exists when, back to 2000. Catalogue-only datasets are hatched and say so.
export function AvailabilityStrip({ tier, date }) {
  const { t } = useLang();
  const d = tier.data;
  if (!d) return <StateNote tier={tier} label={t("hist.avail.title")} />;
  const t0 = Date.parse(HISTORY_START);
  const t1 = Date.parse(NOW_ISO());
  const years = [2000, 2005, 2010, 2015, 2020, 2025];
  return (
    <div data-testid="availability">
      <div className="relative ml-0 h-4 text-[10px] text-slate-400" aria-hidden="true">
        {years.map((y) => (
          <span key={y} className="absolute -translate-x-1/2" style={{ left: `${pct(`${y}-01-01`, t0, t1)}%` }}>
            {y}
          </span>
        ))}
      </div>
      <ul className="space-y-2">
        {d.datasets.map((ds) => {
          const left = pct(ds.start, t0, t1);
          const right = pct(ds.end ?? NOW_ISO(), t0, t1);
          const cat = ds.status === "catalogue_only";
          const at = date ? datasetAt(ds, date) : null;
          return (
            <li key={ds.id}>
              <div className="flex items-baseline justify-between gap-2 text-[11px]">
                <span className="font-semibold text-slate-100">{ds.label}</span>
                <span className="shrink-0 text-slate-400">
                  {t(KIND_LABEL[ds.kind] ?? "kind.other")} · {ds.start.slice(0, 4)}–{ds.end ? ds.end.slice(0, 4) : t("hist.now")}
                </span>
              </div>
              <div className="relative h-4 rounded bg-slate-800" role="img" aria-label={`${ds.label}: ${ds.start} to ${ds.end ?? t("hist.now")}, ${cat ? t("hist.catalogueOnly") : t("hist.integrated")}`}>
                <div
                  className={`absolute inset-y-0.5 rounded-sm border ${cat ? "border-dashed border-slate-300" : "border-solid border-sky-200 bg-sky-500"}`}
                  style={{
                    left: `${left}%`,
                    width: `${Math.max(1.5, right - left)}%`,
                    backgroundImage: cat ? "repeating-linear-gradient(45deg, rgba(203,213,225,.55) 0 3px, transparent 3px 6px)" : undefined,
                  }}
                />
                {date && <div className="absolute inset-y-[-2px] w-0.5 bg-yellow-300" style={{ left: `${pct(date, t0, t1)}%` }} />}
              </div>
              <div className="flex flex-wrap justify-between gap-x-2 text-[11px] text-slate-400">
                <span>
                  {cat ? "▨ " : "■ "}
                  {cat ? t("hist.catalogueOnly") : t("hist.integrated")} · {ds.cadence}
                  {ds.note ? ` · ${ds.note}` : ""}
                </span>
                {at && <span className={at.ok ? "text-emerald-200" : "text-amber-200"}>{at.ok ? `✓ ${t("hist.atDate.yes")}` : `✗ ${t(`hist.atDate.${at.why}`, { when: at.when })}`}</span>}
              </div>
            </li>
          );
        })}
      </ul>
      <p className="mt-2 text-[11px] text-slate-300">{t("hist.nosplice")}</p>
      <SourceLine data={d} className="mt-1" />
      <Caveats data={d} />
    </div>
  );
}

function AnomalyChart({ series }) {
  const { t } = useLang();
  const rows = useMemo(
    () => series.map((r) => ({ label: `${r.year}-${String(r.month).padStart(2, "0")}`, anomaly: r.anomalyMm, missing: r.missingDays })),
    [series],
  );
  return (
    <div className="h-44 w-full" role="img" aria-label={t("hist.anomaly.aria", { from: rows[0]?.label, to: rows[rows.length - 1]?.label })} data-testid="anomaly-chart">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 6, right: 4, bottom: 0, left: 0 }} barCategoryGap={0}>
          <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
          <XAxis dataKey="label" tick={{ fill: "#cbd5e1", fontSize: 10 }} tickFormatter={(l) => l.slice(0, 4)} interval={59} />
          <YAxis tick={{ fill: "#cbd5e1", fontSize: 10 }} width={42} unit=" mm" />
          <Tooltip
            contentStyle={{ background: "#0f172a", border: "1px solid #475569", fontSize: 12 }}
            labelStyle={{ color: "#e2e8f0" }}
            formatter={(v, _n, p) => [v == null ? t("chart.missing") : `${v} mm${p?.payload?.missing ? ` (${t("hist.missingDays", { n: p.payload.missing })})` : ""}`, t("hist.anomaly")]}
          />
          <ReferenceLine y={0} stroke="#e2e8f0" />
          <Bar dataKey="anomaly" isAnimationActive={false}>
            {rows.map((r) => (
              <Cell key={r.label} fill={r.anomaly >= 0 ? PALETTE.sky : PALETTE.orange} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function RankChart({ d }) {
  const { t } = useLang();
  const toDate = d.rankBasis === "to_date_same_window";
  const rows = (d.seasons ?? []).map((s) => ({ ...s, value: toDate ? s.toDateMm : s.totalMm }));
  return (
    <div className="h-40 w-full" role="img" aria-label={t("hist.rank.aria", { year: d.year, rank: d.rank, of: d.of })} data-testid="rank-chart">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 6, right: 4, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
          <XAxis dataKey="year" tick={{ fill: "#cbd5e1", fontSize: 10 }} interval={4} />
          <YAxis tick={{ fill: "#cbd5e1", fontSize: 10 }} width={42} unit=" mm" />
          <Tooltip
            contentStyle={{ background: "#0f172a", border: "1px solid #475569", fontSize: 12 }}
            labelStyle={{ color: "#e2e8f0" }}
            formatter={(v) => [`${v} mm`, toDate ? t("hist.rank.todate") : t("hist.rank.total")]}
          />
          <Bar dataKey="value" isAnimationActive={false}>
            {rows.map((r) => (
              <Cell
                key={r.year}
                fill={r.year === d.year ? PALETTE.vermillion : PALETTE.sky}
                fillOpacity={0.95}
                stroke={r.year === d.year ? "#fff" : "none"}
                strokeWidth={r.year === d.year ? 2 : 0}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function HistoryPanel({ availabilityTier, monthlyTier, rankTier, trendTier, date, onHelp }) {
  const { t } = useLang();
  const m = monthlyTier.data;
  const r = rankTier.data;
  const tr = trendTier.data;
  return (
    <>
      <Section title={t("hist.avail.title")} kind={availabilityTier.data?.dataKind} testId="history-panel">
        <p className="mb-2 text-xs text-slate-300">{t("hist.avail.lead")}</p>
        <AvailabilityStrip tier={availabilityTier} date={date} />
      </Section>

      <Section title={t("hist.monthly.title")} sensor="power" kind={m?.dataKind}>
        <StateNote tier={monthlyTier} label={t("hist.monthly.title")} />
        {m && (
          <>
            <p className="mb-1 text-[11px] text-slate-300">{t("hist.monthly.lead", { period: m.baseline?.period ?? "1991-2020" })}</p>
            <AnomalyChart series={m.series ?? []} />
            <p className="text-[11px] text-slate-400">{t("hist.monthly.missing")}</p>
            <SourceLine data={m} className="mt-1" />
            <Caveats data={m} />
          </>
        )}
      </Section>

      <Section title={t("hist.rank.title")} sensor="power" kind={r?.dataKind}>
        <StateNote tier={rankTier} label={t("hist.rank.title")} />
        {r && (
          <>
            <div className="mb-2 grid grid-cols-2 gap-1.5">
              <Stat label={t("hist.rank.year", { year: r.year })} value={`${r.rank} / ${r.of}`} note={r.complete ? t("hist.rank.complete") : t("hist.rank.incomplete")} />
              <Stat
                label={r.rankBasis === "to_date_same_window" ? t("hist.rank.todate") : t("hist.rank.total")}
                value={fmt(r.rankBasis === "to_date_same_window" ? r.toDateMm : r.totalMm, 0)}
                unit="mm"
                note={r.rankBasis === "to_date_same_window" && r.observedThrough ? t("hist.rank.window", { date: r.observedThrough }) : r.season}
              />
            </div>
            <p className="mb-1 text-[11px] text-slate-300">
              {t("hist.rank.meaning", { year: r.year, rank: r.rank, of: r.of })}
              {r.rankBasis === "to_date_same_window" && r.observedThrough ? ` ${t("hist.rank.partial", { date: r.observedThrough })}` : ""}
            </p>
            <RankChart d={r} />
            <p className="text-[11px] text-slate-400">■ {t("hist.rank.highlight", { year: r.year })}</p>
            <SourceLine data={r} className="mt-1" />
            <Caveats data={r} />
          </>
        )}
      </Section>

      <Section title={t("hist.trend.title")} sensor="power" kind={tr?.dataKind}>
        <StateNote tier={trendTier} label={t("hist.trend.title")} />
        {tr && (
          <>
            <div className="grid grid-cols-2 gap-1.5">
              <Stat label={t("hist.trend.slope")} value={fmt(tr.slopeMmPerDecade)} unit="mm/10 yr" note={tr.ci95 ? `95% CI ${fmt(tr.ci95[0])} … ${fmt(tr.ci95[1])}` : null} />
              <Stat label={t("hist.trend.n")} value={tr.n} note={tr.period} />
            </div>
            <p className="mt-1.5 text-xs font-semibold text-slate-100" data-testid="trend-significance">
              {tr.significant ? t("hist.trend.sig") : t("hist.trend.notsig")}
            </p>
            <p className="mt-1 text-[11px] text-slate-400">{tr.method}</p>
            {(tr.effectiveN != null || tr.lag1Autocorrelation != null) && (
              <p className="mt-1 text-[11px] text-slate-400">
                {t("hist.trend.auto", { eff: fmt(tr.effectiveN, 0) ?? "—", r: fmt(tr.lag1Autocorrelation, 2) ?? "—" })}
              </p>
            )}
            <p className="mt-1 text-[11px] text-slate-300">{t("hist.trend.nocause")}</p>
            <SourceLine data={tr} className="mt-1" />
            <Caveats data={tr} />
          </>
        )}
      </Section>
    </>
  );
}
