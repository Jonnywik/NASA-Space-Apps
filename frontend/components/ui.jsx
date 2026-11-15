"use client";

import React from "react";
import { useLang } from "../utils/LangContext";

// Shared Mangrove UI primitives for the CAMANAVA workspace.
export const PALETTE = {
  blue: "#2171B5",
  sky: "#6BAED6",
  orange: "#E69F00",
  vermillion: "#7B3294",
  green: "#1E5B3A",
  yellow: "#FFF6DE",
  purple: "#6B5A9E",
};

const SENSORS = {
  nisar_l: { label: "L-band · NISAR", cls: "border-[#DCE3DB] bg-[#F2F5F1] text-[#16231B]" },
  s1_c: { label: "C-band · Sentinel-1", cls: "border-[#DCE3DB] bg-[#F2F5F1] text-[#16231B]" },
  insar: { label: "InSAR LOS · NISAR", cls: "border-[#C2A5CF] bg-[#F6F1F9] text-[#5B2370]" },
  power: { label: "NASA POWER", cls: "border-[#DCE3DB] bg-[#E3EFE7] text-[#123B25]" },
  imerg: { label: "NASA GPM IMERG", cls: "border-[#2171B5]/40 bg-[#EEF5FA] text-[#0B4F79]" },
  outlook: { label: "Outlook model", cls: "border-[#2171B5]/40 bg-[#EEF5FA] text-[#0B4F79]" },
  places: { label: "Places · gazetteer", cls: "border-[#DCE3DB] bg-[#F2F5F1] text-[#16231B]" },
};

export function SensorBadge({ sensor }) {
  const s = SENSORS[sensor];
  if (!s) return null;
  return (
    <span
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded-md border px-2 py-0.5 text-[11px] font-medium ${s.cls}`}
      data-testid={`sensor-${sensor}`}
    >
      {s.label}
    </span>
  );
}

const KINDS = {
  observed: { glyph: "●", cls: "border-[#2171B5]/50 bg-[#EEF5FA] text-[#0B4F79]" },
  derived: { glyph: "◆", cls: "border-[#1E5B3A]/40 bg-[#E3EFE7] text-[#123B25]" },
  outlook: { glyph: "▲", cls: "border-dashed border-[#2171B5] bg-[#EEF5FA] text-[#0B4F79]" },
  scenario: { glyph: "◇", cls: "border-dotted border-[#6B5A9E] bg-[#ECE8F4] text-[#4E3F80]" },
  synthetic: {
    glyph: "▨",
    cls: "border-dashed border-[#7A5B00] bg-[#FFF6DE] text-[#7A5B00] font-semibold",
  },
};

export function DemoTag({ isNumber = false, compact = false, className = "" }) {
  const { t } = useLang();
  return (
    <span
      className={`inline-flex items-center whitespace-nowrap rounded border border-dashed border-[#7A5B00] bg-[#FFF6DE] text-[11px] font-semibold leading-tight text-[#7A5B00] ${compact ? "px-1.5 py-0" : "px-1.5 py-0.5"} ${className}`}
      data-testid="kind-synthetic"
      title={t("demo.title")}
      aria-label={t("demo.title")}
    >
      {isNumber ? t("demo.number") : t("demo.tag")}
    </span>
  );
}

// kind = dataKind from the API. "synthetic" renders the quiet dashed amber DemoTag.
export function KindBadge({ kind, label, isNumber = false }) {
  const { t } = useLang();
  const k = KINDS[kind] ? kind : null;
  if (!k) return null;
  if (k === "synthetic" && !label) return <DemoTag isNumber={isNumber} />;
  return (
    <span
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded border px-1.5 py-0.5 text-[11px] font-semibold ${KINDS[k].cls}`}
      data-testid={`kind-${k}`}
      title={t(`kind.${k}.hint`)}
    >
      <span aria-hidden="true">{KINDS[k].glyph}</span>
      {label ?? t(`kind.${k}`)}
    </span>
  );
}

export function HelpButton({ card, onOpen, label }) {
  const { t } = useLang();
  return (
    <button
      type="button"
      onClick={() => onOpen(card)}
      aria-label={label ?? t("help.open")}
      title={label ?? t("help.open")}
      className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-[#DCE3DB] bg-[#F2F5F1] text-xs font-bold text-[#1E5B3A] hover:bg-[#E3EFE7]"
    >
      ?
    </button>
  );
}

export function Section({ title, sensor, kind, helpCard, onHelp, children, testId, className = "" }) {
  return (
    <section className={`mb-4 ${className}`} aria-label={title} data-testid={testId}>
      <div className="mb-2 flex flex-wrap items-center gap-1.5">
        <h3 className="mr-auto font-serif text-[16px] font-semibold leading-snug text-[#16231B]">{title}</h3>
        {sensor && <SensorBadge sensor={sensor} />}
        {kind && <KindBadge kind={kind} />}
        {helpCard && onHelp && <HelpButton card={helpCard} onOpen={onHelp} />}
      </div>
      {children}
    </section>
  );
}

export function Stat({ label, value, unit, note, tone = "text-[#16231B]", isDemo = false, compact = false }) {
  return (
    <div className={`flex flex-col gap-0.5 rounded-xl border border-[#DCE3DB] bg-[#F2F5F1] ${compact ? "p-2.5" : "p-3"}`}>
      <div className="flex items-start justify-between gap-1 text-[12px] leading-snug text-[#4A5850]">
        <span>{label}</span>
        {isDemo && <DemoTag compact />}
      </div>
      <div className={`font-bold leading-tight tabular-nums ${compact ? "text-[20px]" : "text-[22px]"} ${tone}`}>
        {value ?? "—"}
        {unit && value != null && <span className="ml-1 text-[12px] font-medium text-[#4A5850]">{unit}</span>}
      </div>
      {note && <div className="text-[11px] leading-snug text-[#4A5850]">{note}</div>}
    </div>
  );
}

export function fmt(n, d = 1) {
  return typeof n === "number" && Number.isFinite(n) ? n.toLocaleString(undefined, { maximumFractionDigits: d }) : null;
}

// Fraction (0..1) as a percentage string; null when the value is missing, so a gap never reads as 0%.
export function fmtPct(v, d = 0) {
  return typeof v === "number" && Number.isFinite(v) ? `${(v * 100).toFixed(d)}%` : null;
}

export function formatResolution(r) {
  if (r == null) return null;
  if (typeof r === "string" || typeof r === "number") return String(r);
  if (typeof r === "object" && (r.x != null || r.y != null)) return `${r.x ?? "?"} × ${r.y ?? "?"} ${r.units ?? ""}`.trim();
  return null;
}

export function SourceLine({ data, className = "", onSources }) {
  const { t } = useLang();
  if (!data) return null;
  const src = data.source;
  const when = data.retrievedAt ?? data.generatedAt;
  const name = typeof src === "string" ? src : src?.name;
  const url = typeof src === "object" ? src?.url : null;
  const version = typeof src === "object" ? src?.version : null;
  return (
    <p className={`text-[11px] leading-relaxed text-[#4A5850] ${className}`} data-testid="source-line">
      <span>{t("src.label")}: </span>
      {url ? (
        <a href={url} target="_blank" rel="noreferrer" className="font-medium text-[#1E5B3A] underline">
          {name ?? url}
        </a>
      ) : (
        <span>{name ?? t("src.none")}</span>
      )}
      {version ? ` (${version})` : ""}
      {when ? ` · ${String(when).slice(0, 10)}` : ""}
      {formatResolution(data.nativeResolution) ? ` · ${t("src.resolution")} ${formatResolution(data.nativeResolution)}` : ""}
      {onSources && (
        <>
          {" · "}
          <button type="button" onClick={onSources} className="font-semibold text-[#1E5B3A] underline hover:text-[#123B25]">
            {t("header.sources")}
          </button>
        </>
      )}
    </p>
  );
}

export function Caveats({ data }) {
  const { t } = useLang();
  const w = Array.isArray(data?.warnings) ? data.warnings : [];
  const l = Array.isArray(data?.limitations) ? data.limitations : [];
  if (!w.length && !l.length) return null;
  return (
    <div className="mt-2 text-[11px] text-[#4A5850]">
      {w.map((x) => (
        <p key={x} className="mb-1 rounded-lg border border-dashed border-[#7A5B00]/50 bg-[#FFF6DE] px-2.5 py-1.5 text-[#5A4300]">
          {x}
        </p>
      ))}
      {l.length > 0 && (
        <details className="rounded-lg border border-[#DCE3DB] bg-[#F2F5F1]/60 px-2.5 py-1.5">
          <summary className="cursor-pointer font-medium text-[#16231B]">{t("limits.inline", { n: l.length })}</summary>
          <ul className="mt-1 list-disc space-y-0.5 pl-4 text-[#4A5850]">
            {l.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

export function StateNote({ tier, label }) {
  const { t } = useLang();
  const { state, error } = tier;
  if (state === "ready" || state === "idle" || !state) return null;
  const detail = error?.detail && typeof error.detail === "object" ? error.detail : null;
  const msg = detail?.message;
  const isWarn = state !== "loading" && state !== "outside" && state !== "unavailable";
  return (
    <div
      className={`rounded-xl border p-3 text-xs ${isWarn ? "border-dashed border-[#7A5B00]/60 bg-[#FFF6DE] text-[#5A4300]" : "border-[#DCE3DB] bg-[#F2F5F1] text-[#16231B]"}`}
      role={state === "loading" ? "status" : "alert"}
      data-testid={`state-${state}`}
    >
      <div className="font-semibold">
        {label ? `${label}: ` : ""}
        {t(`state.${state}.title`)}
      </div>
      <p className="mt-0.5 text-[#4A5850]">{t(`state.${state}.body`)}</p>
      {msg && state !== "loading" && <p className="mt-0.5 text-[#4A5850]">{msg}</p>}
      {state === "upstream" && detail?.cachedAt && <p className="mt-0.5 text-[#4A5850]">{t("state.cachedAt", { when: detail.cachedAt })}</p>}
    </div>
  );
}

export function reasonFor(tier, t) {
  if (!tier || tier.state === "ready") return null;
  if (tier.state === "loading" || tier.state === "idle") return t("state.loading.title");
  return t(`state.${tier.state}.title`);
}
