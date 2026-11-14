"use client";

import React from "react";
import { datasetAt } from "./HistoryPanel";
import { useLang } from "../utils/LangContext";

const btn = "rounded-md border border-slate-500 bg-slate-800 px-2 py-1 text-sm font-semibold text-slate-100 hover:bg-slate-700 disabled:opacity-40";

// The bottom time bar. It changes with the mode: NISAR passes (season, rhythm, ground motion),
// a 2000-to-now slider with dataset availability (history), or the outlook / scenario months (future).
export default function TimeBar({ mode, passes, idx, onIdx, playing, onPlaying, hist, future }) {
  const { t } = useLang();

  if (mode === "history") {
    return (
      <div className="border-t border-slate-700 bg-slate-900 px-3 py-2" data-testid="timebar-history">
        <label className="flex items-center gap-3 text-xs text-slate-200">
          <span className="shrink-0 font-semibold">{t("time.history")}</span>
          <input
            type="range"
            min={0}
            max={hist.max}
            value={hist.value}
            onChange={(e) => hist.onChange(Number(e.target.value))}
            className="flex-1 accent-yellow-300"
            aria-valuetext={hist.date}
            data-testid="history-slider"
          />
          <span className="w-20 shrink-0 text-right text-sm font-bold text-yellow-100">{hist.date.slice(0, 7)}</span>
        </label>
        <ul className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 text-[11px]" aria-label={t("time.history.avail")}>
          {(hist.datasets ?? []).map((ds) => {
            const at = datasetAt(ds, hist.date);
            return (
              <li key={ds.id} className={at.ok ? "text-emerald-200" : "text-slate-400 line-through decoration-slate-500"} title={at.ok ? "" : t(`hist.atDate.${at.why}`, { when: at.when })}>
                {at.ok ? "✓" : "✗"} {ds.label.split(" (")[0]}
                {ds.status === "catalogue_only" ? ` (${t("hist.catalogueOnly")})` : ""}
              </li>
            );
          })}
        </ul>
      </div>
    );
  }

  if (mode === "future") {
    const months = future?.months ?? [];
    return (
      <div className="border-t border-slate-700 bg-slate-900 px-3 py-2" data-testid="timebar-future">
        <div className="mb-1 text-[11px] text-slate-300">{t("time.future")}</div>
        <ol className="flex gap-0.5 overflow-x-auto" aria-label={t("time.future")}>
          <li className="shrink-0 rounded-l border-2 border-solid border-sky-300 bg-sky-500/20 px-2 py-1 text-[11px] font-semibold text-sky-100">● {t("future.phase.obs")}</li>
          {months.map((m) => (
            <li
              key={`${m.year}-${m.month}`}
              className={`shrink-0 px-1.5 py-1 text-center text-[11px] font-semibold ${m.status === "outlook" ? "border-2 border-dashed border-amber-300 bg-amber-500/15 text-amber-100" : "border-2 border-dotted border-fuchsia-300 bg-fuchsia-500/15 text-fuchsia-100"}`}
              title={m.status === "outlook" ? t("future.status.outlook") : t("future.status.scenario")}
            >
              {m.status === "outlook" ? "▲" : "◇"} {String(m.year).slice(2)}-{String(m.month).padStart(2, "0")}
            </li>
          ))}
        </ol>
      </div>
    );
  }

  const n = passes?.length ?? 0;
  const showPlayer = mode === "season";
  return (
    <div className="border-t border-slate-700 bg-slate-900 px-3 py-2" data-testid="timebar-passes">
      <div className="flex items-center gap-2">
        {showPlayer && (
          <div className="flex shrink-0 gap-1">
            <button type="button" className={btn} onClick={() => onIdx(Math.max(0, idx - 1))} disabled={!n || idx <= 0} aria-label={t("season.prev")}>
              ◀
            </button>
            <button type="button" className={btn} onClick={() => onPlaying(!playing)} disabled={!n} aria-pressed={playing} aria-label={playing ? t("season.pause") : t("season.play")}>
              {playing ? "❚❚" : "▶"}
            </button>
            <button type="button" className={btn} onClick={() => onIdx(Math.min(n - 1, idx + 1))} disabled={!n || idx >= n - 1} aria-label={t("season.next")}>
              ▶|
            </button>
          </div>
        )}
        <ol className="flex flex-1 items-end gap-1 overflow-x-auto" aria-label={t("time.passes")}>
          {(passes ?? []).map((p, i) => (
            <li key={p.id} className="flex-1">
              <button
                type="button"
                onClick={() => onIdx(i)}
                aria-current={i === idx ? "true" : undefined}
                aria-label={`${t("time.pass")} ${p.date}`}
                className={`w-full min-w-[44px] rounded border px-1 py-1 text-center text-[11px] leading-tight ${i === idx ? "border-yellow-300 bg-yellow-300/20 font-bold text-white" : "border-slate-600 bg-slate-800 text-slate-300 hover:bg-slate-700"}`}
              >
                <span aria-hidden="true">{i === idx ? "◆" : "◇"}</span>
                <br />
                {p.date.slice(5)}
              </button>
            </li>
          ))}
          {n === 0 && <li className="px-2 text-xs text-slate-400">{t("time.nopasses")}</li>}
        </ol>
      </div>
      {!showPlayer && <p className="mt-1 text-[11px] text-slate-400">{t("time.selected.note")}</p>}
    </div>
  );
}
