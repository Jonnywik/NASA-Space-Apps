"use client";

import React from "react";
import { useLang } from "../utils/LangContext";

// Shared bits of the CAMANAVA workspace. Colours follow the Okabe-Ito colour-blind-safe palette and
// no status is shown by colour alone: every badge has a text label, a glyph and a border style.

export const PALETTE = {
  blue: "#0072B2",
  sky: "#56B4E9",
  orange: "#E69F00",
  vermillion: "#D55E00",
  green: "#009E73",
  yellow: "#F0E442",
  purple: "#CC79A7",
};

const SENSORS = {
  nisar_l: { label: "L-band · NISAR", cls: "border-sky-400/50 text-sky-200" },
  s1_c: { label: "C-band · Sentinel-1", cls: "border-slate-400/60 text-slate-200" },
  insar: { label: "InSAR LOS · NISAR", cls: "border-orange-300/60 text-orange-200" },
  power: { label: "NASA POWER", cls: "border-emerald-300/50 text-emerald-200" },
  outlook: { label: "Outlook model", cls: "border-amber-300/60 text-amber-200" },
  places: { label: "Places · gazetteer", cls: "border-slate-400/60 text-slate-200" },
};

export function SensorBadge({ sensor }) {
  const s = SENSORS[sensor];
  if (!s) return null;
  return (
    <span
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded border bg-slate-950/60 px-1.5 py-0.5 text-[11px] font-medium ${s.cls}`}
      data-testid={`sensor-${sensor}`}
    >
      {s.label}
    </span>
  );
}

const KINDS = {
  observed: { glyph: "●", cls: "border-solid border-sky-300/70 bg-sky-500/10 text-sky-100" },
  derived: { glyph: "◆", cls: "border-solid border-teal-300/70 bg-teal-500/10 text-teal-100" },
  outlook: { glyph: "▲", cls: "border-dashed border-amber-300/80 bg-amber-500/10 text-amber-100" },
  scenario: { glyph: "◇", cls: "border-dotted border-fuchsia-300/80 bg-fuchsia-500/10 text-fuchsia-100" },
  synthetic: {
    glyph: "▨",
    cls: "border-solid border-yellow-300 bg-yellow-400/20 text-yellow-100 font-bold uppercase tracking-wide",
  },
};

// kind = dataKind from the API. "synthetic" always wins and is loud.
export function KindBadge({ kind, label }) {
  const { t } = useLang();
  const k = KINDS[kind] ? kind : null;
  if (!k) return null;
  return (
    <span
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded border-2 px-1.5 py-0.5 text-[11px] font-semibold ${KINDS[k].cls}`}
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
      className="inline-flex h-6 w-6 items-center justify-center rounded-full border border-slate-500 bg-slate-800 text-xs font-bold text-slate-100 hover:bg-slate-700"
    >
      ?
    </button>
  );
}

// A titled block of the findings panel: title, sensor badge, data-kind badge, "?" for the radar cards.
export function Section({ title, sensor, kind, helpCard, onHelp, children, testId, className = "" }) {
  return (
    <section className={`mb-4 ${className}`} aria-label={title} data-testid={testId}>
      <div className="mb-1.5 flex flex-wrap items-center gap-1.5">
        <h3 className="mr-auto text-sm font-bold text-slate-100">{title}</h3>
        {sensor && <SensorBadge sensor={sensor} />}
        {kind && <KindBadge kind={kind} />}
        {helpCard && onHelp && <HelpButton card={helpCard} onOpen={onHelp} />}
      </div>
      {children}
    </section>
  );
}

export function Stat({ label, value, unit, note, tone = "text-slate-100" }) {
  return (
    <div className="rounded-lg border border-slate-700/60 bg-slate-800/70 p-2">
      <div className="text-[11px] text-slate-400">{label}</div>
      <div className={`text-lg font-bold leading-tight ${tone}`}>
        {value ?? "—"}
        {unit && value != null && <span className="ml-1 text-xs font-normal text-slate-300">{unit}</span>}
      </div>
      {note && <div className="text-[11px] text-slate-400">{note}</div>}
    </div>
  );
}

export function fmt(n, d = 1) {
  return typeof n === "number" && Number.isFinite(n) ? n.toLocaleString(undefined, { maximumFractionDigits: d }) : null;
}

export function SourceLine({ data, className = "" }) {
  const { t } = useLang();
  if (!data) return null;
  const src = data.source;
  const when = data.retrievedAt ?? data.generatedAt;
  const name = typeof src === "string" ? src : src?.name;
  const url = typeof src === "object" ? src?.url : null;
  const version = typeof src === "object" ? src?.version : null;
  return (
    <p className={`text-[11px] leading-snug text-slate-400 ${className}`} data-testid="source-line">
      {t("src.label")}:{" "}
      {url ? (
        <a href={url} target="_blank" rel="noreferrer" className="text-sky-300 underline">
          {name ?? url}
        </a>
      ) : (
        <span>{name ?? t("src.none")}</span>
      )}
      {version ? ` (${version})` : ""}
      {when ? ` · ${String(when).slice(0, 10)}` : ""}
      {data.nativeResolution ? ` · ${t("src.resolution")} ${data.nativeResolution}` : ""}
    </p>
  );
}

// Inline warnings plus a collapsed list of limitations for the response a panel shows.
export function Caveats({ data }) {
  const { t } = useLang();
  const w = Array.isArray(data?.warnings) ? data.warnings : [];
  const l = Array.isArray(data?.limitations) ? data.limitations : [];
  if (!w.length && !l.length) return null;
  return (
    <div className="mt-2 text-[11px] text-slate-300">
      {w.map((x) => (
        <p key={x} className="mb-1 rounded border border-amber-400/40 bg-amber-500/10 px-2 py-1 text-amber-100">
          ⚠ {x}
        </p>
      ))}
      {l.length > 0 && (
        <details>
          <summary className="cursor-pointer text-slate-300">{t("limits.inline", { n: l.length })}</summary>
          <ul className="mt-1 list-disc space-y-0.5 pl-4 text-slate-400">
            {l.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

// What a panel shows while data is not there. "No data" is a normal state. Every message says why.
export function StateNote({ tier, label }) {
  const { t } = useLang();
  const { state, error } = tier;
  if (state === "ready" || state === "idle" || !state) return null;
  const detail = error?.detail && typeof error.detail === "object" ? error.detail : null;
  const msg = detail?.message;
  const tone = state === "loading" ? "text-slate-300" : state === "outside" || state === "unavailable" ? "text-slate-100" : "text-amber-200";
  return (
    <div
      className="rounded-lg border border-slate-600 bg-slate-800/70 p-2.5 text-xs"
      role={state === "loading" ? "status" : "alert"}
      data-testid={`state-${state}`}
    >
      <div className={`font-semibold ${tone}`}>
        {label ? `${label}: ` : ""}
        {t(`state.${state}.title`)}
      </div>
      <p className="mt-0.5 text-slate-400">{t(`state.${state}.body`)}</p>
      {msg && state !== "loading" && <p className="mt-0.5 text-slate-400">{msg}</p>}
      {state === "upstream" && detail?.cachedAt && <p className="mt-0.5 text-slate-400">{t("state.cachedAt", { when: detail.cachedAt })}</p>}
    </div>
  );
}

export function reasonFor(tier, t) {
  if (!tier || tier.state === "ready") return null;
  if (tier.state === "loading" || tier.state === "idle") return t("state.loading.title");
  return t(`state.${tier.state}.title`);
}
