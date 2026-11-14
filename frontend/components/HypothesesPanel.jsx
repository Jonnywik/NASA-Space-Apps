"use client";

import React from "react";
import { useLang } from "../utils/LangContext";

// N6 "Why might this be happening?". The list comes from public/hypotheses.json (the coordinator fills
// it with verified references). An empty file renders nothing: no placeholder claims.
//   item: { id, title, summary, titleFil?, summaryFil?, evidence?: [{label, mode}], references: [{title, url, year}] }
export default function HypothesesPanel({ items, onMode }) {
  const { t, lang } = useLang();
  if (!items?.length) return null;
  return (
    <section className="mb-4 rounded-lg border border-fuchsia-300/40 bg-fuchsia-500/5 p-2.5" aria-label={t("hyp.title")} data-testid="hypotheses">
      <h3 className="text-sm font-bold text-slate-100">{t("hyp.title")}</h3>
      <p className="mb-2 text-[11px] text-slate-400">{t("hyp.lead")}</p>
      <ul className="space-y-2">
        {items.map((h) => (
          <li key={h.id ?? h.title} className="rounded border border-slate-700 bg-slate-800/60 p-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded border border-dotted border-fuchsia-300 bg-fuchsia-500/20 px-1.5 py-0.5 text-[11px] font-bold uppercase text-fuchsia-100">{t("hyp.label")}</span>
              <span className="text-xs font-semibold text-slate-100">{(lang === "fil" && h.titleFil) || h.title}</span>
            </div>
            <p className="mt-1 text-xs text-slate-300">{(lang === "fil" && h.summaryFil) || h.summary}</p>
            {h.evidence?.length > 0 && (
              <p className="mt-1 text-[11px] text-slate-400">
                {t("hyp.evidence")}:{" "}
                {h.evidence.map((e) => (
                  <button key={e.label} type="button" className="mr-2 text-sky-300 underline" onClick={() => onMode?.(e.mode)}>
                    {e.label}
                  </button>
                ))}
              </p>
            )}
            {h.references?.length > 0 && (
              <ul className="mt-1 list-disc pl-4 text-[11px] text-slate-400">
                {h.references.map((r) => (
                  <li key={r.url ?? r.title}>
                    {r.url ? (
                      <a href={r.url} target="_blank" rel="noreferrer" className="text-sky-300 underline">
                        {r.title}
                      </a>
                    ) : (
                      r.title
                    )}
                    {r.year ? ` (${r.year})` : ""}
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
