"use client";

import React, { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Caveats, DemoTag, HelpButton, PALETTE, SourceLine, Stat, StateNote, fmt } from "./ui";
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

// Which dataset exists when back to 2000. Catalogue-only datasets use diagonal hatching.
export function AvailabilityStrip({ tier, date }) {
  const { t } = useLang();
  const d = tier.data;
  if (!d) return <StateNote tier={tier} label={t("hist.avail.title")} />;
  const t0 = Date.parse(HISTORY_START);
  const t1 = Date.parse(NOW_ISO());
  const years = [2000, 2005, 2010, 2015, 2020, 2025];
  return (
    <div data-testid="availability">
      <div className="relative mb-1 h-4 text-[10px] font-medium text-[#4A5850] tabular-nums" aria-hidden="true">
        {years.map((y) => (
          <span key={y} className="absolute -translate-x-1/2" style={{ left: `${pct(`${y}-01-01`, t0, t1)}%` }}>
            {y}
          </span>
        ))}
      </div>
      <ul className="space-y-2.5">
        {d.datasets.map((ds) => {
          const left = pct(ds.start, t0, t1);
          const right = pct(ds.end ?? NOW_ISO(), t0, t1);
          const cat = ds.status === "catalogue_only";
          const at = date ? datasetAt(ds, date) : null;
          return (
            <li key={ds.id}>
              <div className="flex items-baseline justify-between gap-2 text-[12px]">
                <span className="font-semibold text-[#16231B]">{ds.label}</span>
                <span className="shrink-0 text-[11px] text-[#4A5850] tabular-nums">
                  {t(KIND_LABEL[ds.kind] ?? "kind.other")} · {ds.start ? ds.start.slice(0, 4) : "—"}–{ds.end ? ds.end.slice(0, 4) : t("hist.now")}
                </span>
              </div>
              <div
                className="relative mt-0.5 h-4 rounded-md border border-[#DCE3DB] bg-[#EEF2EC]"
                role="img"
                aria-label={`${ds.label}: ${ds.start} to ${ds.end ?? t("hist.now")}, ${cat ? t("hist.catalogueOnly") : t("hist.integrated")}`}
              >
                <div
                  className={`absolute inset-y-0.5 rounded-sm border ${cat ? "border-dashed border-[#6B5A9E]" : "border-solid border-[#1E5B3A] bg-[#1E5B3A]"}`}
                  style={{
                    left: `${left}%`,
                    width: `${Math.max(1.5, right - left)}%`,
                    backgroundImage: cat ? "repeating-linear-gradient(45deg, rgba(107,90,158,.32) 0 3px, transparent 3px 6px)" : undefined,
                  }}
                />
                {date && <div className="absolute inset-y-[-2px] w-0.5 bg-[#16231B]" style={{ left: `${pct(date, t0, t1)}%` }} />}
              </div>
              <div className="mt-0.5 flex flex-wrap justify-between gap-x-2 text-[11px] text-[#4A5850]">
                <span>
                  {cat ? "▨ " : "■ "}
                  {cat ? t("hist.catalogueOnly") : t("hist.integrated")} · {ds.cadence}
                  {ds.note ? ` · ${ds.note}` : ""}
                </span>
                {at && (
                  <span className={at.ok ? "font-medium text-[#1E5B3A]" : "font-medium text-[#7A5B00]"}>
                    {at.ok ? `✓ ${t("hist.atDate.yes")}` : `✗ ${t(`hist.atDate.${at.why}`, { when: at.when })}`}
                  </span>
                )}
              </div>
            </li>
          );
        })}
      </ul>
      <p className="mt-2 text-[11px] leading-relaxed text-[#4A5850]">{t("hist.nosplice")}</p>
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
          <CartesianGrid stroke="#DCE3DB" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="label" tick={{ fill: "#4A5850", fontSize: 10 }} tickFormatter={(l) => l.slice(0, 4)} interval={59} stroke="#DCE3DB" />
          <YAxis tick={{ fill: "#4A5850", fontSize: 10 }} width={60} unit=" mm" stroke="#DCE3DB" />
          <Tooltip
            contentStyle={{ background: "#FFFFFF", border: "1px solid #DCE3DB", borderRadius: 10, fontSize: 12, color: "#16231B" }}
            labelStyle={{ color: "#16231B", fontWeight: 600 }}
            formatter={(v, _n, p) => [v == null ? t("chart.missing") : `${v} mm${p?.payload?.missing ? ` (${t("hist.missingDays", { n: p.payload.missing })})` : ""}`, t("hist.anomaly")]}
          />
          <ReferenceLine y={0} stroke="#4A5850" />
          <Bar dataKey="anomaly" isAnimationActive={false}>
            {rows.map((r) => (
              <Cell key={r.label} fill={r.anomaly >= 0 ? PALETTE.blue : PALETTE.orange} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function RankChart({ d, peakYear }) {
  const { t } = useLang();
  const toDate = d.rankBasis === "to_date_same_window";
  const rows = (d.seasons ?? []).map((s) => ({ ...s, value: toDate ? s.toDateMm : s.totalMm }));
  return (
    <div className="h-40 w-full" role="img" aria-label={t("hist.rank.aria", { year: d.year, rank: d.rank, of: d.of })} data-testid="rank-chart">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 6, right: 4, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="#DCE3DB" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="year" tick={{ fill: "#4A5850", fontSize: 10 }} interval={4} stroke="#DCE3DB" />
          <YAxis tick={{ fill: "#4A5850", fontSize: 10 }} width={60} unit=" mm" stroke="#DCE3DB" />
          <Tooltip
            contentStyle={{ background: "#FFFFFF", border: "1px solid #DCE3DB", borderRadius: 10, fontSize: 12, color: "#16231B" }}
            labelStyle={{ color: "#16231B", fontWeight: 600 }}
            formatter={(v) => [`${v} mm`, toDate ? t("hist.rank.todate") : t("hist.rank.total")]}
          />
          <Bar dataKey="value" isAnimationActive={false} radius={[3, 3, 0, 0]}>
            {rows.map((r) => {
              const isCur = r.year === d.year;
              const isPeak = r.year === peakYear && !isCur;
              return (
                <Cell
                  key={r.year}
                  fill={isCur ? "#1E5B3A" : isPeak ? "#0B4F6C" : "#6BAED6"}
                  stroke={isCur ? "#123B25" : "none"}
                  strokeDasharray={isCur && !d.complete ? "3 2" : undefined}
                  strokeWidth={isCur ? 1.5 : 0}
                />
              );
            })}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function HistoryPanel({ availabilityTier, monthlyTier, rankTier, trendTier, date, onHelp, onSources }) {
  const { t } = useLang();
  const m = monthlyTier.data;
  const r = rankTier.data;
  const tr = trendTier.data;
  const isDemo = [availabilityTier.data, m, r, tr].some((x) => x?.dataKind === "synthetic");

  const toDate = r?.rankBasis === "to_date_same_window";
  const wettest = useMemo(() => {
    if (!r?.seasons?.length) return null;
    return r.seasons.reduce((best, s) => {
      const v = (toDate ? s.toDateMm : s.totalMm) ?? -Infinity;
      const bv = (toDate ? best.toDateMm : best.totalMm) ?? -Infinity;
      return v > bv ? s : best;
    }, r.seasons[0]);
  }, [r, toDate]);

  const sofarMm = r ? (toDate ? r.toDateMm : r.totalMm) : null;
  const peakMm = wettest ? (toDate ? wettest.toDateMm : wettest.totalMm) : null;
  const srcObj = r ?? m ?? tr ?? availabilityTier.data;

  return (
    <div className="flex flex-1 flex-col gap-4 text-[#16231B]" data-testid="history-panel">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] font-bold uppercase tracking-[0.08em] text-[#1E5B3A]">{t("hist.v2.eyebrow")}</span>
        {onHelp && <HelpButton card="bands" onOpen={onHelp} />}
      </div>

      <div className="flex flex-col gap-1.5">
        <h1 className="m-0 font-serif text-[22px] font-semibold leading-[1.22] tracking-[-0.015em] text-[#16231B]">
          {r ? t("hist.v2.headlineRank", { year: r.year, rank: r.rank, of: r.of }) : t("hist.v2.headline")}
        </h1>
        {isDemo && (
          <div className="flex">
            <DemoTag isNumber />
          </div>
        )}
      </div>

      <StateNote tier={rankTier} label={t("hist.rank.title")} />

      <div className="grid grid-cols-3 gap-2">
        <Stat
          compact
          isDemo={r?.dataKind === "synthetic"}
          label={t("hist.v2.stat.sofar", { year: r?.year ?? 2026 })}
          value={sofarMm != null ? fmt(sofarMm, 0) : null}
          unit="mm"
          note={toDate && r?.observedThrough ? r.observedThrough : r?.season}
        />
        <Stat
          compact
          isDemo={r?.dataKind === "synthetic"}
          label={t("hist.v2.stat.peak")}
          value={wettest ? String(wettest.year) : null}
          note={peakMm != null ? `${fmt(peakMm, 0)} mm` : undefined}
        />
        <Stat
          compact
          isDemo={tr?.dataKind === "synthetic"}
          label={t("hist.v2.stat.trend")}
          value={tr?.slopeMmPerDecade != null ? `${tr.slopeMmPerDecade > 0 ? "+" : ""}${fmt(tr.slopeMmPerDecade, 0)}` : null}
          unit={tr?.slopeMmPerDecade != null ? "mm/10y" : undefined}
          note={
            tr ? (
              <span data-testid="trend-significance">{tr.significant ? t("hist.trend.sig") : t("hist.trend.notsig")}</span>
            ) : undefined
          }
        />
      </div>

      {r && (
        <div className="flex flex-col gap-2.5 rounded-xl border border-[#DCE3DB] bg-white p-3.5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="m-0 font-serif text-[15px] font-semibold text-[#16231B]">{t("hist.v2.chartTitle", { year: r.year })}</h2>
            <span className="text-[11px] font-medium text-[#4A5850]">
              {r.rank} / {r.of} · {r.complete ? t("hist.rank.complete") : t("hist.rank.incomplete")}
            </span>
          </div>
          <RankChart d={r} peakYear={wettest?.year} />
          <div className="flex flex-wrap items-center gap-3 text-[11px] text-[#4A5850]">
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-sm bg-[#6BAED6]" aria-hidden="true" />
              {t("hist.v2.fullSeason")}
            </span>
            {wettest && (
              <span className="inline-flex items-center gap-1.5 font-medium text-[#0B4F6C]">
                <span className="h-2.5 w-2.5 rounded-sm bg-[#0B4F6C]" aria-hidden="true" />
                {t("hist.v2.wettestLegend", { year: wettest.year, mm: fmt(peakMm, 0) ?? "—" })}
              </span>
            )}
            <span className="inline-flex items-center gap-1.5 font-medium text-[#1E5B3A]">
              <span className="h-2.5 w-2.5 rounded-sm bg-[#1E5B3A]" aria-hidden="true" />
              {toDate && r.observedThrough ? t("hist.v2.incompleteLegend", { year: r.year, date: r.observedThrough }) : r.year}
            </span>
          </div>
          <p className="m-0 text-[11px] leading-relaxed text-[#4A5850]">
            {t("hist.rank.meaning", { year: r.year, rank: r.rank, of: r.of })}
            {toDate && r.observedThrough ? ` ${t("hist.rank.partial", { date: r.observedThrough })}` : ""}
          </p>
        </div>
      )}

      <div className="rounded-xl border border-[#DCE3DB] bg-[#F2F5F1] p-3.5">
        <h2 className="m-0 font-serif text-[15px] font-semibold text-[#16231B]">{t("rhythm.v2.plainTitle")}</h2>
        <p className="mt-1 text-[13px] leading-[1.6] text-[#16231B]">{t("hist.v2.plainBody")}</p>
      </div>

      <details className="rounded-xl border border-[#DCE3DB] bg-white px-3.5 py-2.5">
        <summary className="cursor-pointer text-[13px] font-semibold text-[#1E5B3A]">
          {t("hist.monthly.title")} · {t("hist.avail.title")} · {t("hist.trend.title")}
        </summary>
        <div className="mt-3 flex flex-col gap-4 border-t border-[#DCE3DB] pt-3">
          <div>
            <h3 className="mb-1 text-[13px] font-semibold text-[#16231B]">{t("hist.monthly.title")}</h3>
            <StateNote tier={monthlyTier} label={t("hist.monthly.title")} />
            {m && (
              <>
                <p className="mb-1.5 text-[11px] text-[#4A5850]">{t("hist.monthly.lead", { period: m.baseline?.period ?? "1991-2020" })}</p>
                <AnomalyChart series={m.series ?? []} />
                <p className="mt-1 text-[11px] text-[#4A5850]">{t("hist.monthly.missing")}</p>
                <Caveats data={m} />
              </>
            )}
          </div>

          <div>
            <h3 className="mb-1 text-[13px] font-semibold text-[#16231B]">{t("hist.avail.title")}</h3>
            <p className="mb-2 text-[12px] text-[#4A5850]">{t("hist.avail.lead")}</p>
            <AvailabilityStrip tier={availabilityTier} date={date} />
          </div>

          <div>
            <h3 className="mb-1 text-[13px] font-semibold text-[#16231B]">{t("hist.trend.title")}</h3>
            <StateNote tier={trendTier} label={t("hist.trend.title")} />
            {tr && (
              <div className="space-y-1.5 text-[12px] text-[#4A5850]">
                <div className="grid grid-cols-2 gap-2">
                  <Stat
                    compact
                    isDemo={tr.dataKind === "synthetic"}
                    label={t("hist.trend.slope")}
                    value={fmt(tr.slopeMmPerDecade)}
                    unit="mm/10 yr"
                    note={tr.ci95 ? `95% CI ${fmt(tr.ci95[0])} … ${fmt(tr.ci95[1])}` : null}
                  />
                  <Stat compact isDemo={tr.dataKind === "synthetic"} label={t("hist.trend.n")} value={tr.n} note={tr.period} />
                </div>
                <p className="m-0 text-[11px]">{tr.method}</p>
                {(tr.effectiveN != null || tr.lag1Autocorrelation != null) && (
                  <p className="m-0 text-[11px]">
                    {t("hist.trend.auto", { eff: fmt(tr.effectiveN, 0) ?? "—", r: fmt(tr.lag1Autocorrelation, 2) ?? "—" })}
                  </p>
                )}
                <p className="m-0 text-[11px] font-medium text-[#16231B]">{t("hist.trend.nocause")}</p>
                <Caveats data={tr} />
              </div>
            )}
          </div>
        </div>
      </details>

      {srcObj && (
        <div className="mt-auto border-t border-[#DCE3DB] pt-3">
          <SourceLine data={srcObj} onSources={onSources} />
          <Caveats data={r} />
        </div>
      )}
    </div>
  );
}
