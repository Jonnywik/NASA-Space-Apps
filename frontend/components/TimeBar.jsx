"use client";

import React, { useMemo } from "react";
import { datasetAt, HISTORY_START } from "./HistoryPanel";
import { useLang } from "../utils/LangContext";

function formatShortDate(iso) {
  if (!iso) return "—";
  const d = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
}

function formatMonthLabel(ymStr) {
  if (!ymStr) return "—";
  const [y, m] = ymStr.split("-").map(Number);
  if (!y || !m) return ymStr;
  const d = new Date(Date.UTC(y, m - 1, 1));
  return d.toLocaleDateString("en-US", { month: "short", year: "numeric", timeZone: "UTC" });
}

// Bottom footer bar: adapts cleanly across Flood rhythm, Season, Ground motion, History, and Future.
export default function TimeBar({ mode, passes, idx, onIdx, playing, onPlaying, hist, future, rainDays = [], motionEpochs = [] }) {
  const { t } = useLang();

  const passWindowStart = passes?.[0]?.date;
  const passWindowEnd = passes?.[passes.length - 1]?.date;

  const rainRange = useMemo(() => {
    const startIso = rainDays[0]?.date ?? passWindowStart ?? "2026-06-01";
    const endIso = rainDays[rainDays.length - 1]?.date ?? passWindowEnd ?? "2026-11-30";
    const t0 = Date.parse(`${startIso}T00:00:00Z`);
    const t1 = Math.max(t0 + 86400000, Date.parse(`${endIso}T00:00:00Z`));
    return { t0, t1 };
  }, [rainDays, passWindowStart, passWindowEnd]);

  if (mode === "history") {
    const dsList = hist.datasets ?? [];
    const t0 = Date.parse(HISTORY_START);
    const t1 = Date.parse(new Date().toISOString().slice(0, 10));
    const pctAt = (d) => Math.min(100, Math.max(0, ((Date.parse(d) - t0) / Math.max(1, t1 - t0)) * 100));
    return (
      <div className="border-t border-[#DCE3DB] bg-white px-4 py-2.5 text-[#16231B]" data-testid="timebar-history">
        <div className="flex flex-wrap items-center gap-4">
          <div className="min-w-[170px] shrink-0">
            <div className="flex items-center gap-2">
              <span className="text-[12px] font-semibold text-[#16231B]">{t("hist.v2.footerTitle")}</span>
              <span className="rounded-md bg-[#E3EFE7] px-2 py-0.5 text-[12px] font-bold text-[#123B25] tabular-nums">
                {hist.date.slice(0, 7)}
              </span>
            </div>
            <div className="text-[11px] text-[#4A5850]">{t("hist.v2.footerSub")}</div>
          </div>

          <div className="min-w-[200px] flex-1">
            {dsList.length > 0 && (
              <div className="mb-1 space-y-0.5" aria-hidden="true">
                {dsList.slice(0, 4).map((ds) => {
                  const l = pctAt(ds.start);
                  const r = pctAt(ds.end ?? new Date().toISOString().slice(0, 10));
                  const ok = datasetAt(ds, hist.date).ok;
                  return (
                    <div key={ds.id} className="relative h-1.5 w-full overflow-hidden rounded-full bg-[#F2F5F1]">
                      <div
                        className={`absolute inset-y-0 rounded-full ${ok ? "bg-[#1E5B3A]" : "bg-[#6BAED6]/60"}`}
                        style={{ left: `${l}%`, width: `${Math.max(2, r - l)}%` }}
                      />
                    </div>
                  );
                })}
              </div>
            )}
            <label className="flex items-center gap-2 text-[11px] text-[#4A5850]">
              <span className="sr-only">{t("time.history")}</span>
              <span>2000</span>
              <input
                type="range"
                min={0}
                max={hist.max}
                value={hist.value}
                onChange={(e) => hist.onChange(Number(e.target.value))}
                className="flex-1 accent-[#1E5B3A]"
                aria-valuetext={hist.date}
                data-testid="history-slider"
              />
              <span>2026</span>
            </label>
          </div>

          <ul className="hidden flex-wrap gap-x-3 gap-y-0.5 text-[11px] lg:flex" aria-label={t("time.history.avail")}>
            {dsList.map((ds) => {
              const at = datasetAt(ds, hist.date);
              return (
                <li
                  key={ds.id}
                  className={at.ok ? "font-medium text-[#1E5B3A]" : "text-[#7A847D] line-through"}
                  title={at.ok ? "" : t(`hist.atDate.${at.why}`, { when: at.when })}
                >
                  {at.ok ? "✓" : "✗"} {String(ds.label ?? ds.id ?? "").split(" (")[0]}
                </li>
              );
            })}
          </ul>
        </div>
      </div>
    );
  }

  if (mode === "future") {
    const months = future?.months ?? [];
    const activeIdx = Math.min(Math.max(0, future?.activeIdx ?? 0), Math.max(0, months.length - 1));
    const cur = months[activeIdx];
    const curLabel = cur ? formatMonthLabel(`${cur.year}-${String(cur.month).padStart(2, "0")}`) : t("time.future");
    const outlookList = months.map((m, i) => ({ m, i })).filter((x) => x.m.status === "outlook");
    const scnList = months.map((m, i) => ({ m, i })).filter((x) => x.m.status !== "outlook");

    return (
      <div className="border-t border-[#DCE3DB] bg-white px-4 py-2.5 text-[#16231B]" data-testid="timebar-future">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex shrink-0 items-center gap-1.5">
            <button
              type="button"
              onClick={() => future?.onSelectMonth?.(Math.max(0, activeIdx - 1))}
              disabled={!months.length || activeIdx <= 0}
              aria-label={t("time.v2.prevMonth")}
              className="flex h-8 w-8 items-center justify-center rounded-lg border border-[#DCE3DB] bg-white text-sm font-semibold text-[#16231B] hover:bg-[#F2F5F1] disabled:opacity-40"
            >
              ‹
            </button>
            <span className="min-w-[84px] text-center text-[13px] font-semibold text-[#16231B] tabular-nums">{curLabel}</span>
            <button
              type="button"
              onClick={() => future?.onSelectMonth?.(Math.min(months.length - 1, activeIdx + 1))}
              disabled={!months.length || activeIdx >= months.length - 1}
              aria-label={t("time.v2.nextMonth")}
              className="flex h-8 w-8 items-center justify-center rounded-lg border border-[#DCE3DB] bg-white text-sm font-semibold text-[#16231B] hover:bg-[#F2F5F1] disabled:opacity-40"
            >
              ›
            </button>
          </div>

          <ol className="flex flex-1 items-stretch gap-1 overflow-x-auto text-[11px]" aria-label={t("time.future")}>
            <li className="flex shrink-0 items-center rounded-l-lg border border-[#1E5B3A]/40 bg-[#E3EFE7] px-2.5 py-1.5 font-semibold text-[#123B25]">
              ● {t("future.phase.obs")}
            </li>
            {outlookList.map(({ m, i }) => {
              const active = i === activeIdx;
              const code = `${String(m.year).slice(2)}-${String(m.month).padStart(2, "0")}`;
              return (
                <li key={code} className="flex-1">
                  <button
                    type="button"
                    onClick={() => future?.onSelectMonth?.(i)}
                    className={`h-full w-full min-w-[44px] border border-dashed px-1.5 py-1.5 font-semibold transition-colors ${
                      active
                        ? "border-[#2171B5] bg-[#2171B5] text-white"
                        : "border-[#2171B5]/60 bg-[#EEF5FA] text-[#0B4F79] hover:bg-[#DDECF6]"
                    }`}
                  >
                    ▲ {code}
                  </button>
                </li>
              );
            })}
            {scnList.map(({ m, i }) => {
              const active = i === activeIdx;
              const code = `${String(m.year).slice(2)}-${String(m.month).padStart(2, "0")}`;
              return (
                <li key={code} className="flex-1">
                  <button
                    type="button"
                    onClick={() => future?.onSelectMonth?.(i)}
                    className={`h-full w-full min-w-[44px] border border-dotted px-1.5 py-1.5 font-semibold transition-colors last:rounded-r-lg ${
                      active
                        ? "border-[#4E3F80] bg-[#6B5A9E] text-white"
                        : "border-[#6B5A9E]/60 bg-[#ECE8F4] text-[#4E3F80] hover:bg-[#DFD7EE]"
                    }`}
                  >
                    ◇ {code}
                  </button>
                </li>
              );
            })}
          </ol>
        </div>
      </div>
    );
  }

  if (mode === "motion") {
    const first = motionEpochs[0]?.date ?? passWindowStart;
    const last = motionEpochs[motionEpochs.length - 1]?.date ?? passWindowEnd;
    const count = motionEpochs.length || passes?.length || 0;
    return (
      <div className="border-t border-[#DCE3DB] bg-white px-4 py-2.5 text-[#16231B]" data-testid="timebar-passes">
        <div className="flex flex-wrap items-center gap-4">
          <div className="shrink-0">
            <div className="text-[13px] font-semibold text-[#16231B]">
              {first && last ? `${formatShortDate(first)} → ${formatShortDate(last)}` : t("mode.motion")}
            </div>
            <div className="text-[11px] text-[#4A5850]">
              {t("motion.passCounts", { n: count, m: Math.max(0, count - 1) })}
            </div>
          </div>

          <div className="flex flex-1 items-center gap-2 rounded-lg border border-[#C2A5CF] bg-[#F6F1F9] px-3 py-2">
            <span className="h-2.5 w-2.5 shrink-0 rounded-full bg-[#7B3294]" aria-hidden="true" />
            <div className="relative h-1.5 flex-1 rounded-full bg-[#C2A5CF]">
              <div className="absolute inset-0 rounded-full bg-[#7B3294]" />
            </div>
            <span className="text-[11px] font-semibold text-[#5B2370]">{t("motion.title")}</span>
            <span className="h-2.5 w-2.5 shrink-0 rounded-full bg-[#7B3294]" aria-hidden="true" />
          </div>

          <p className="hidden text-[11px] text-[#4A5850] xl:block">{t("time.selected.note")}</p>
        </div>
      </div>
    );
  }

  // Season & Flood rhythm footer
  const n = passes?.length ?? 0;
  const activePass = passes?.[idx];
  const isSeason = mode === "season";
  const maxRain = Math.max(1, ...rainDays.map((d) => Number(d.rainfallMm ?? d.mm ?? 0)));
  const activeEndMs = activePass ? Date.parse(`${activePass.date}T00:00:00Z`) : null;
  const activeStartMs = activeEndMs != null ? activeEndMs - 7 * 86400000 : null;

  return (
    <div className="border-t border-[#DCE3DB] bg-white px-3 py-2 text-[#16231B] md:px-4 md:py-2.5" data-testid="timebar-passes">
      <div className="flex items-center gap-3">
        {isSeason ? (
          <div className="flex shrink-0 items-center gap-1.5">
            <button
              type="button"
              onClick={() => onIdx(Math.max(0, idx - 1))}
              disabled={!n || idx <= 0}
              aria-label={t("season.prev")}
              className="flex h-8 w-8 items-center justify-center rounded-lg border border-[#DCE3DB] bg-white text-base font-semibold text-[#16231B] hover:bg-[#F2F5F1] disabled:opacity-40"
            >
              ‹
            </button>
            <button
              type="button"
              onClick={() => onPlaying(!playing)}
              disabled={!n}
              aria-label={playing ? t("season.pause") : t("season.play")}
              className="flex h-9 w-9 items-center justify-center rounded-full bg-[#1E5B3A] text-xs font-bold text-white shadow-sm hover:bg-[#123B25] disabled:opacity-40"
            >
              {playing ? "❚❚" : "▶"}
            </button>
            <button
              type="button"
              onClick={() => onIdx(Math.min(n - 1, idx + 1))}
              disabled={!n || idx >= n - 1}
              aria-label={t("season.next")}
              className="flex h-8 w-8 items-center justify-center rounded-lg border border-[#DCE3DB] bg-white text-base font-semibold text-[#16231B] hover:bg-[#F2F5F1] disabled:opacity-40"
            >
              ›
            </button>
            <span className="hidden min-w-[92px] pl-1 text-[12px] font-semibold text-[#16231B] tabular-nums sm:inline">
              {formatShortDate(activePass?.date)}
            </span>
          </div>
        ) : (
          <div className="hidden shrink-0 sm:block">
            <div className="text-[12px] font-semibold text-[#16231B]">
              {n} {t("rhythm.v2.stat.passes")}
            </div>
            <div className="text-[11px] text-[#4A5850]">
              {passWindowStart && passWindowEnd ? `${passWindowStart.slice(5)} → ${passWindowEnd.slice(5)}` : "2026"}
            </div>
            <div className="mt-0.5 hidden items-center gap-2 text-[10px] text-[#4A5850] lg:flex 2xl:hidden" aria-hidden="true">
              <span className="flex items-center gap-1">
                <span className="h-2 w-1.5 rounded-sm bg-[#6BAED6]" />
                {t("time.v2.rainShort")}
              </span>
              <span className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-[#1E5B3A]" />
                {t("time.v2.passShort")}
              </span>
            </div>
          </div>
        )}

        <div className="min-w-0 flex-1">
          {rainDays.length > 0 && (
            <div className="mb-1 flex h-8 items-end gap-px rounded-t-md bg-[#F2F5F1] px-1 pt-1" aria-hidden="true">
              {rainDays.map((d) => {
                const val = Number(d.rainfallMm ?? d.mm ?? 0);
                const h = val > 0 ? Math.max(3, Math.round(Math.sqrt(val / maxRain) * 26)) : 1;
                const ms = Date.parse(`${d.date}T00:00:00Z`);
                const inWin = isSeason && activeStartMs != null && ms >= activeStartMs && ms <= activeEndMs;
                return (
                  <span
                    key={d.date}
                    title={`${d.date}: ${val} mm`}
                    className={`min-w-[2px] flex-1 rounded-t-[1px] ${inWin ? "bg-[#2171B5]" : "bg-[#6BAED6]"}`}
                    style={{ height: `${h}px` }}
                  />
                );
              })}
            </div>
          )}

          <ol className="flex items-center gap-1 overflow-x-auto" aria-label={t("time.passes")}>
            {(passes ?? []).map((p, i) => {
              const active = i === idx;
              const pctPos = ((Date.parse(`${p.date}T00:00:00Z`) - rainRange.t0) / (rainRange.t1 - rainRange.t0)) * 100;
              return (
                <li key={p.id} className="min-w-[46px] flex-1" data-pos={Math.round(pctPos)}>
                  <button
                    type="button"
                    onClick={() => onIdx(i)}
                    aria-current={active ? "true" : undefined}
                    aria-label={`${t("time.pass")} ${p.date}`}
                    className={`flex w-full items-center justify-center gap-1 whitespace-nowrap rounded-md border px-1 py-1 text-[11px] font-medium tabular-nums transition-colors ${
                      active && isSeason
                        ? "border-[#1E5B3A] bg-[#E3EFE7] font-bold text-[#123B25]"
                        : "border-[#DCE3DB] bg-white text-[#4A5850] hover:bg-[#F2F5F1]"
                    }`}
                  >
                    <span
                      className={`h-2 w-2 rounded-full ${active && isSeason ? "bg-[#1E5B3A]" : "bg-[#0B4F6C]"}`}
                      aria-hidden="true"
                    />
                    {p.date.slice(5)}
                  </button>
                </li>
              );
            })}
            {n === 0 && <li className="px-2 text-xs text-[#4A5850]">{t("time.nopasses")}</li>}
          </ol>
        </div>

        <div className="hidden shrink-0 flex-col gap-0.5 text-[11px] text-[#4A5850] 2xl:flex" aria-hidden="true">
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2 rounded-sm bg-[#6BAED6]" />
            {t("time.v2.dailyRain")}
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-[#1E5B3A]" />
            {t("time.v2.nisarPass")}
          </span>
        </div>
      </div>
    </div>
  );
}
