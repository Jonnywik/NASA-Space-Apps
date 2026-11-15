"use client";

import React from "react";
import SeasonChart from "./SeasonChart";
import { Caveats, DemoTag, HelpButton, SourceLine, Stat, StateNote, fmt } from "./ui";
import { useLang } from "../utils/LangContext";

export const DEFAULT_PASS_LEGEND = [
  { id: "water", label: "Open water on this pass", color: "#2171B5", shape: "square" },
  { id: "vegetation", label: "Possible flooded vegetation (L-band)", color: "#E69F00", shape: "diamond" },
];

function shortDate(iso) {
  if (!iso) return "—";
  const d = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}

function shortMonthDay(iso) {
  if (!iso) return "—";
  const d = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
}

function passClockLine(cur) {
  const utcRaw = cur?.acquisitionTime;
  const manilaRaw = cur?.acquisitionTimeManila;
  if (!utcRaw) return null;
  const ms = Date.parse(utcRaw);
  const utcHHMM = String(utcRaw).includes("T") ? String(utcRaw).split("T")[1].slice(0, 5) : null;
  let manilaHHMM = manilaRaw && String(manilaRaw).includes("T") ? String(manilaRaw).split("T")[1].slice(0, 5) : null;
  if (!manilaHHMM && Number.isFinite(ms)) {
    const mDate = new Date(ms + 8 * 3600000);
    manilaHHMM = `${String(mDate.getUTCHours()).padStart(2, "0")}:${String(mDate.getUTCMinutes()).padStart(2, "0")}`;
  }
  return { utcHHMM, manilaHHMM };
}

function rainWindow7d(days, targetIso) {
  if (!Array.isArray(days) || !targetIso) return null;
  const endMs = Date.parse(`${targetIso}T00:00:00Z`);
  if (!Number.isFinite(endMs)) return null;
  const startMs = endMs - 6 * 86400000;
  const inWin = days.filter((r) => {
    const t = Date.parse(`${r.date}T00:00:00Z`);
    return t >= startMs && t <= endMs;
  });
  if (!inWin.length || inWin.some((r) => r.mm == null)) return null;
  const sum = inWin.reduce((acc, r) => acc + r.mm, 0);
  const startIso = new Date(startMs).toISOString().slice(0, 10);
  return { sum, from: shortMonthDay(startIso), to: shortMonthDay(targetIso) };
}

export default function SeasonPanel({ passesTier, rainTier, polTier, idx, onIdx, polView, onPolView, compare, onHelp, onSources }) {
  const { t } = useLang();
  const d = passesTier.data;
  const passes = d?.passes ?? [];
  const cur = passes[idx];
  const prev = idx > 0 ? passes[idx - 1] : null;
  const isDemo = d?.dataKind === "synthetic";
  const clock = passClockLine(cur);
  const rain7 = rainWindow7d(rainTier.data?.days, cur?.date);

  const deltaKm2 =
    cur?.floodedKm2 != null && prev?.floodedKm2 != null ? cur.floodedKm2 - prev.floodedKm2 : null;
  const deltaStr =
    deltaKm2 == null ? (idx === 0 ? "First pass" : "—") : `${deltaKm2 >= 0 ? "+" : "−"}${fmt(Math.abs(deltaKm2))}`;

  return (
    <div className="flex flex-1 flex-col gap-4 text-[#16231B]" data-testid="season-panel">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] font-bold uppercase tracking-[0.08em] text-[#1E5B3A]">{t("season.v2.eyebrow")}</span>
        {onHelp && <HelpButton card="water" onOpen={onHelp} />}
      </div>

      <StateNote tier={passesTier} label={t("season.title")} />

      {d && cur && (
        <>
          <div className="flex flex-col gap-1">
            <div className="flex flex-wrap items-baseline gap-2">
              <h1 className="m-0 font-serif text-[25px] font-semibold leading-[1.2] text-[#16231B]" data-testid="pass-date">
                {shortDate(cur.date)}
              </h1>
              {isDemo && <DemoTag />}
            </div>
            <span className="text-[12px] text-[#4A5850]">
              {clock
                ? t("season.v2.manilaLine", { utc: clock.utcHHMM, manila: clock.manilaHHMM })
                : `${t("missing.noTime")} · L-band HH/HV`}
              {d.track != null ? ` · Track ${d.track}` : ""}
              {d.direction ? `, ${d.direction}` : ""}
              {` · ${t("season.passOf", { i: idx + 1, n: passes.length })}`}
            </span>
            <p className="mt-1 font-serif text-[19px] font-medium leading-[1.28] text-[#16231B]">
              {cur.floodedKm2 != null
                ? t("season.v2.headline", { km2: fmt(cur.floodedKm2) })
                : t("season.v2.headlineMissing", { date: cur.date })}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-2.5">
            <Stat
              compact
              isDemo={isDemo}
              label={prev ? t("season.v2.changeSince", { date: shortMonthDay(prev.date) }) : t("season.passOf", { i: 1, n: passes.length })}
              value={deltaStr}
              unit={deltaKm2 != null ? "km²" : undefined}
              note={prev && cur.floodedKm2 != null && prev.floodedKm2 != null ? `${fmt(prev.floodedKm2)} → ${fmt(cur.floodedKm2)} km²` : cur?.missingReason ?? undefined}
            />
            <Stat
              compact
              label={rain7 ? t("season.v2.rainWindow", { window: `${rain7.from} – ${rain7.to}` }) : t("season.rain")}
              value={rain7 ? fmt(rain7.sum, 0) : null}
              unit={rain7 ? "mm" : undefined}
              note="NASA POWER grid cell"
            />
            <Stat
              compact
              isDemo={isDemo}
              label={t("season.v2.vegLabel")}
              value={fmt(cur.floodedVegetationKm2)}
              unit="km²"
              note={t("season.v2.vegSub")}
            />
            <Stat
              compact
              label={t("season.v2.validLabel")}
              value={cur.validFraction != null ? `${Math.round(cur.validFraction * 100)}%` : null}
              note={t("season.v2.validSub")}
            />
          </div>

          <div className="flex flex-col gap-1.5 border-t border-[#DCE3DB] pt-3">
            <h2 className="m-0 font-serif text-[16px] font-semibold text-[#16231B]">{t("rhythm.v2.plainTitle")}</h2>
            <p className="m-0 text-[13px] leading-[1.6] text-[#16231B]">
              {cur.floodedKm2 != null && rain7
                ? t("season.v2.plainBody", { rain: fmt(rain7.sum, 0), km2: fmt(cur.floodedKm2), date: shortDate(cur.date) })
                : t("season.v2.plainNoRain", { date: shortDate(cur.date), km2: fmt(cur.floodedKm2) ?? "—" })}
            </p>
          </div>

          {/* Radar layer toggle + Before/After Swipe */}
          <div className="flex flex-col gap-2 rounded-xl border border-[#DCE3DB] bg-[#F2F5F1] p-3">
            <div className="flex items-center justify-between gap-2">
              <span className="text-[12px] font-semibold text-[#16231B]">{t("season.v2.layerLabel")}</span>
              <span className="text-[11px] text-[#4A5850]">{cur?.maturity ?? "—"}</span>
            </div>
            <div role="radiogroup" aria-label={t("season.layers")} className="grid grid-cols-3 gap-1.5 text-xs">
              {[
                ["flood", t("season.layer.flood")],
                ["hh", t("season.layer.hh")],
                ["rgb", t("season.layer.rgb")],
              ].map(([k, label]) => {
                const active = polView === k;
                return (
                  <button
                    key={k}
                    type="button"
                    role="radio"
                    aria-checked={active}
                    disabled={k === "rgb" && compare.on}
                    onClick={() => onPolView(k)}
                    className={`rounded-lg border px-2 py-1.5 text-left text-[11px] disabled:opacity-40 ${
                      active
                        ? "border-2 border-[#1E5B3A] bg-[#E3EFE7] font-bold text-[#123B25]"
                        : "border-[#DCE3DB] bg-white font-medium text-[#16231B] hover:bg-[#F2F5F1]"
                    }`}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
            {polView === "hh" && <p className="m-0 text-[11px] text-[#4A5850]">{t("season.hh.note")}</p>}
            {polView === "rgb" && (
              <div className="mt-1" data-testid="pol-explainer">
                <StateNote tier={polTier} label={t("season.layer.rgb")} />
                {polTier.state === "ready" && (
                  <div className="text-[11px] text-[#16231B]">
                    <p className="m-0">
                      <b>R</b> = {polTier.data.channels?.r} · <b>G</b> = {polTier.data.channels?.g} · <b>B</b> = {polTier.data.channels?.b}
                    </p>
                    <ol className="mt-1 list-decimal space-y-0.5 pl-4 text-[#4A5850]">
                      {(polTier.data.explanation ?? []).slice(0, 3).map((x) => (
                        <li key={x}>{x}</li>
                      ))}
                    </ol>
                  </div>
                )}
              </div>
            )}

            <label className="mt-1 flex cursor-pointer items-center gap-2 text-[12px] font-medium text-[#16231B]">
              <input
                type="checkbox"
                checked={compare.on}
                onChange={(e) => compare.onToggle(e.target.checked)}
                className="h-4 w-4 accent-[#1E5B3A]"
                data-testid="compare-toggle"
              />
              {t("season.v2.compareToggle")}
            </label>
            {compare.on && (
              <div className="grid grid-cols-2 gap-2 pt-1 text-xs">
                <label className="text-[#4A5850]">
                  {t("swipe.before")}
                  <select
                    value={compare.before}
                    onChange={(e) => compare.onBefore(Number(e.target.value))}
                    className="mt-0.5 w-full rounded-lg border border-[#DCE3DB] bg-white px-2 py-1 text-[#16231B]"
                  >
                    {passes.map((p, i) => (
                      <option key={p.id} value={i}>
                        {p.date}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-[#4A5850]">
                  {t("swipe.after")}
                  <select
                    value={compare.after}
                    onChange={(e) => compare.onAfter(Number(e.target.value))}
                    className="mt-0.5 w-full rounded-lg border border-[#DCE3DB] bg-white px-2 py-1 text-[#16231B]"
                  >
                    {passes.map((p, i) => (
                      <option key={p.id} value={i}>
                        {p.date}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="col-span-2 block text-[#4A5850]">
                  {t("swipe.position")}
                  <input
                    type="range"
                    min={2}
                    max={98}
                    value={Math.round(compare.split * 100)}
                    onChange={(e) => compare.onSplit(Number(e.target.value) / 100)}
                    className="w-full accent-[#1E5B3A]"
                    aria-valuetext={`${Math.round(compare.split * 100)}%`}
                    data-testid="swipe-range"
                  />
                </label>
              </div>
            )}
          </div>

          <details className="rounded-xl border border-[#DCE3DB] bg-white p-3">
            <summary className="cursor-pointer text-[13px] font-semibold text-[#16231B]">{t("season.chart.title")} &amp; {t("season.table")}</summary>
            <div className="mt-2 space-y-2">
              {rainTier.state !== "ready" && <StateNote tier={rainTier} label={t("season.rain")} />}
              <SeasonChart passes={passes} days={rainTier.data?.days} selectedDate={cur?.date} onSelectDate={(date) => onIdx(Math.max(0, passes.findIndex((p) => p.date === date)))} />
              <table className="w-full border-collapse text-left text-[11px]">
                <thead>
                  <tr className="border-b border-[#DCE3DB] text-[#4A5850]">
                    <th className="py-1 pr-2 font-medium">{t("col.date")}</th>
                    <th className="pr-2 font-medium">km²</th>
                    <th className="pr-2 font-medium">{t("season.valid")}</th>
                    <th className="font-medium">{t("season.maturity")}</th>
                  </tr>
                </thead>
                <tbody>
                  {passes.map((p, i) => (
                    <tr key={p.id} className={`border-b border-[#DCE3DB]/50 ${i === idx ? "bg-[#E3EFE7] font-semibold" : ""}`}>
                      <td className="py-1 pr-2">{p.date}</td>
                      <td className="pr-2 tabular-nums">{fmt(p.floodedKm2) ?? "—"}</td>
                      <td className="pr-2 tabular-nums">{p.validFraction != null ? `${Math.round(p.validFraction * 100)}%` : "—"}</td>
                      <td>{p.maturity ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {d.rule && (
                <div className="border-t border-[#DCE3DB] pt-2 text-[11px] text-[#4A5850]">
                  <div className="font-semibold text-[#16231B]">{t("season.rule")}</div>
                  <p className="mt-0.5">{d.rule.description}</p>
                  <p className="mt-0.5">HH {d.rule.hhThresholdDb ?? "—"} dB · HV {d.rule.hvThresholdDb ?? "—"} dB</p>
                </div>
              )}
              <Caveats data={d} />
            </div>
          </details>

          <SourceLine data={d} className="mt-auto pt-2" onSources={onSources} />
        </>
      )}
    </div>
  );
}
