"use client";

import React from "react";
import SeasonChart from "./SeasonChart";
import { Caveats, Section, SourceLine, Stat, StateNote, fmt } from "./ui";
import { useLang } from "../utils/LangContext";

export const DEFAULT_PASS_LEGEND = [
  { id: "water", label: "Open water on this pass", color: "#0072B2", shape: "square" },
  { id: "vegetation", label: "Possible flooded vegetation (L-band)", color: "#E69F00", shape: "diamond" },
];

function utcTime(iso) {
  if (!iso) return null;
  return String(iso).replace("T", " ").replace(/\.\d+/, "").replace("Z", " UTC");
}

export default function SeasonPanel({ passesTier, rainTier, polTier, idx, onIdx, playing, onPlaying, polView, onPolView, compare, opacity, onOpacity, onHelp }) {
  const { t } = useLang();
  const d = passesTier.data;
  const passes = d?.passes ?? [];
  const cur = passes[idx];

  function onKey(e) {
    if (["INPUT", "SELECT", "TEXTAREA"].includes(e.target.tagName)) return;
    if (e.key === "ArrowLeft") {
      e.preventDefault();
      onIdx(Math.max(0, idx - 1));
    } else if (e.key === "ArrowRight") {
      e.preventDefault();
      onIdx(Math.min(passes.length - 1, idx + 1));
    } else if (e.key === "Home") {
      e.preventDefault();
      onIdx(0);
    } else if (e.key === "End") {
      e.preventDefault();
      onIdx(passes.length - 1);
    } else if ((e.key === " " || e.key === "Enter") && e.target === e.currentTarget) {
      e.preventDefault();
      onPlaying(!playing);
    }
  }

  const legend = d?.legend ?? DEFAULT_PASS_LEGEND;
  const btn = "rounded-md border border-slate-500 bg-slate-800 px-2.5 py-1.5 text-sm font-semibold text-slate-100 hover:bg-slate-700 disabled:opacity-40";

  return (
    <>
      <Section title={t("season.title")} sensor="nisar_l" kind={d?.dataKind} helpCard="water" onHelp={onHelp} testId="season-panel">
        <p className="mb-2 text-xs text-slate-300">{t("season.lead")}</p>
        <StateNote tier={passesTier} label={t("season.title")} />
        {d && (
          <>
            <div
              tabIndex={0}
              role="group"
              aria-label={t("season.player.aria")}
              onKeyDown={onKey}
              className="rounded-lg border border-slate-600 bg-slate-800/70 p-2.5"
              data-testid="season-player"
            >
              <div className="flex items-center justify-between gap-2">
                <div>
                  <div className="text-base font-bold text-slate-100" data-testid="pass-date">
                    {cur?.date ?? "—"}
                  </div>
                  <div className="text-[11px] text-slate-400">
                    {t("season.acquired")}: {utcTime(cur?.acquisitionTime) ?? t("missing.noTime")} · {cur?.maturity ?? "—"}
                  </div>
                  {cur?.acquisitionTimeManila && (
                    <div className="text-[11px] text-slate-400">
                      {t("season.manila")}: {String(cur.acquisitionTimeManila).replace("T", " ").slice(0, 16)}
                    </div>
                  )}
                  <div className="text-[11px] text-slate-400">
                    {t("season.passOf", { i: idx + 1, n: passes.length })}
                  </div>
                </div>
                <div className="flex gap-1.5">
                  <button type="button" className={btn} onClick={() => onIdx(Math.max(0, idx - 1))} disabled={idx <= 0} aria-label={t("season.prev")}>
                    ◀
                  </button>
                  <button type="button" className={btn} onClick={() => onPlaying(!playing)} aria-pressed={playing} aria-label={playing ? t("season.pause") : t("season.play")} data-testid="play">
                    {playing ? "❚❚" : "▶"}
                  </button>
                  <button type="button" className={btn} onClick={() => onIdx(Math.min(passes.length - 1, idx + 1))} disabled={idx >= passes.length - 1} aria-label={t("season.next")}>
                    ▶|
                  </button>
                </div>
              </div>
              <p className="mt-1.5 text-[11px] text-slate-400">{t("season.keys")}</p>
            </div>

            <div className="mt-2 grid grid-cols-3 gap-1.5">
              <Stat label={t("season.flooded")} value={fmt(cur?.floodedKm2)} unit="km²" />
              <Stat label={t("season.vegetation")} value={fmt(cur?.floodedVegetationKm2)} unit="km²" note={t("season.vegetation.note")} />
              <Stat label={t("season.valid")} value={cur?.validFraction != null ? `${Math.round(cur.validFraction * 100)}%` : null} note={t("season.valid.note")} />
            </div>
            {cur?.floodedKm2 == null && cur?.missingReason && <p className="mt-1 text-[11px] text-amber-200">{cur.missingReason}</p>}
            {cur?.permanentWaterKm2 != null && <p className="mt-1 text-[11px] text-slate-400">{t("season.permanent", { km2: fmt(cur.permanentWaterKm2) })}</p>}
          </>
        )}
      </Section>

      {d && (
        <>
          <Section title={t("season.layers")} sensor="nisar_l">
            <div role="radiogroup" aria-label={t("season.layers")} className="grid grid-cols-3 gap-1.5 text-xs">
              {[
                ["flood", t("season.layer.flood")],
                ["hh", t("season.layer.hh")],
                ["rgb", t("season.layer.rgb")],
              ].map(([k, label]) => (
                <button
                  key={k}
                  type="button"
                  role="radio"
                  aria-checked={polView === k}
                  disabled={k === "rgb" && compare.on}
                  onClick={() => onPolView(k)}
                  className={`rounded-md border px-2 py-1.5 text-left ${polView === k ? "border-sky-300 bg-sky-600/30 text-white" : "border-slate-600 bg-slate-800 text-slate-300 hover:bg-slate-700"} disabled:opacity-40`}
                >
                  {polView === k ? "● " : "○ "}
                  {label}
                </button>
              ))}
            </div>
            {polView === "flood" && (
              <ul className="mt-2 space-y-0.5 text-[11px] text-slate-300" aria-label={t("season.legend")}>
                {legend.map((l) => (
                  <li key={l.id ?? l.label} className="flex items-center gap-2">
                    <span aria-hidden="true" className={`inline-block h-3 w-3 border border-white/60 ${(l.shape === "diamond" || String(l.id).includes("veg")) ? "rotate-45" : ""}`} style={{ background: l.color }} />
                    {l.label}
                  </li>
                ))}
                <li className="text-slate-400">{t("season.legend.rest")}</li>
              </ul>
            )}
            {polView === "hh" && <p className="mt-2 text-[11px] text-slate-300">{t("season.hh.note")}</p>}
            {polView === "rgb" && (
              <div className="mt-2" data-testid="pol-explainer">
                <StateNote tier={polTier} label={t("season.layer.rgb")} />
                {polTier.state === "ready" && (
                  <>
                    <p className="text-[11px] text-slate-200">
                      <b>R</b> = {polTier.data.channels?.r} · <b>G</b> = {polTier.data.channels?.g} · <b>B</b> = {polTier.data.channels?.b}
                    </p>
                    <ol className="mt-1 list-decimal space-y-1 pl-4 text-[11px] text-slate-200">
                      {(polTier.data.explanation ?? []).slice(0, 3).map((x) => (
                        <li key={x}>{x}</li>
                      ))}
                    </ol>
                    <SourceLine data={polTier.data} className="mt-1" />
                  </>
                )}
              </div>
            )}
            <label className="mt-2 flex items-center gap-2 text-[11px] text-slate-300">
              {t("map.opacity")}
              <input type="range" min={0.2} max={1} step={0.05} value={opacity} onChange={(e) => onOpacity(Number(e.target.value))} className="flex-1 accent-sky-400" />
            </label>
          </Section>

          <Section title={t("swipe.title")} sensor="nisar_l">
            <label className="flex items-center gap-2 text-xs text-slate-200">
              <input type="checkbox" checked={compare.on} onChange={(e) => compare.onToggle(e.target.checked)} className="h-4 w-4 accent-sky-400" data-testid="compare-toggle" />
              {t("swipe.enable")}
            </label>
            {compare.on && (
              <div className="mt-2 space-y-1.5 text-xs">
                <div className="grid grid-cols-2 gap-2">
                  <label className="text-slate-300">
                    {t("swipe.before")}
                    <select value={compare.before} onChange={(e) => compare.onBefore(Number(e.target.value))} className="mt-0.5 w-full rounded border border-slate-600 bg-slate-800 px-1.5 py-1 text-slate-100">
                      {passes.map((p, i) => (
                        <option key={p.id} value={i}>
                          {p.date}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="text-slate-300">
                    {t("swipe.after")}
                    <select value={compare.after} onChange={(e) => compare.onAfter(Number(e.target.value))} className="mt-0.5 w-full rounded border border-slate-600 bg-slate-800 px-1.5 py-1 text-slate-100">
                      {passes.map((p, i) => (
                        <option key={p.id} value={i}>
                          {p.date}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <label className="block text-slate-300">
                  {t("swipe.position")}
                  <input
                    type="range"
                    min={2}
                    max={98}
                    value={Math.round(compare.split * 100)}
                    onChange={(e) => compare.onSplit(Number(e.target.value) / 100)}
                    className="w-full accent-sky-400"
                    aria-valuetext={`${Math.round(compare.split * 100)}%`}
                    data-testid="swipe-range"
                  />
                </label>
                <p className="text-[11px] text-slate-400">{t("swipe.keys")}</p>
              </div>
            )}
          </Section>

          <Section title={t("season.chart.title")} sensor="nisar_l">
            {rainTier.state !== "ready" && <StateNote tier={rainTier} label={t("season.rain")} />}
            <SeasonChart passes={passes} days={rainTier.data?.days} selectedDate={cur?.date} onSelectDate={(date) => onIdx(Math.max(0, passes.findIndex((p) => p.date === date)))} />
            <SourceLine data={rainTier.data} className="mt-1" />
            <Caveats data={rainTier.data} />
            <details className="mt-2 text-[11px] text-slate-300">
              <summary className="cursor-pointer">{t("season.table")}</summary>
              <table className="mt-1 w-full border-collapse text-left">
                <thead>
                  <tr className="text-slate-400">
                    <th className="py-0.5 pr-2 font-medium">{t("col.date")}</th>
                    <th className="pr-2 font-medium">km²</th>
                    <th className="pr-2 font-medium">{t("season.valid")}</th>
                    <th className="font-medium">{t("season.maturity")}</th>
                  </tr>
                </thead>
                <tbody>
                  {passes.map((p, i) => (
                    <tr key={p.id} className={i === idx ? "bg-slate-700/60" : ""}>
                      <td className="py-0.5 pr-2">{p.date}</td>
                      <td className="pr-2">{fmt(p.floodedKm2) ?? "—"}</td>
                      <td className="pr-2">{p.validFraction != null ? `${Math.round(p.validFraction * 100)}%` : "—"}</td>
                      <td>{p.maturity ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>
          </Section>

          {d.rule && (
            <details className="mb-4 text-[11px] text-slate-300">
              <summary className="cursor-pointer font-semibold">{t("season.rule")}</summary>
              <p className="mt-1">{d.rule.description}</p>
              <p className="mt-1">
                HH {d.rule.hhThresholdDb ?? "—"} dB · HV {d.rule.hvThresholdDb ?? "—"} dB
              </p>
              {d.rule.calibration && (
                <p className="mt-1">
                  {typeof d.rule.calibration === "string"
                    ? d.rule.calibration
                    : [d.rule.calibration.status && `${t("season.calibration")}: ${d.rule.calibration.status}`, d.rule.calibration.method, d.rule.calibration.knownWater]
                        .filter(Boolean)
                        .join(" · ")}
                </p>
              )}
              {d.permanentWater?.fraction != null && (
                <p className="mt-1">{t("season.permRule", { pct: Math.round(d.permanentWater.fraction * 100), n: d.permanentWater.minValidPasses ?? "—" })}</p>
              )}
              {d.possibleFloodedVegetation?.marginDb != null && (
                <p className="mt-1">{t("season.vegRule", { db: d.possibleFloodedVegetation.marginDb })}</p>
              )}
              {d.verification?.layout && <p className="mt-1 text-slate-400">{t("season.layout", { v: d.verification.layout })}</p>}
              <p className="mt-1 text-slate-400">
                {d.sensor ? `${d.sensor} · ` : ""}
                {d.product} · track {d.track} {d.direction} · frame {d.frame}
                {d.mode ? ` · mode ${d.mode}` : ""} · {(d.polarizations ?? []).join("+")}
              </p>
            </details>
          )}
          <SourceLine data={d} />
          <Caveats data={d} />
        </>
      )}
    </>
  );
}
