"use client";

import React from "react";
import { useLang } from "../utils/LangContext";

export default function HypothesesPanel({ items, onMode }) {
  const { t, lang } = useLang();
  if (!items?.length) return null;
  return (
    <section className="mb-4 rounded-xl border border-[#DCE3DB] bg-[#F2F5F1] p-3 text-[#16231B]" aria-label={t("hyp.title")} data-testid="hypotheses">
      <h3 className="font-serif text-[16px] font-semibold text-[#16231B]">{t("hyp.title")}</h3>
      <p className="mb-2 text-[11px] text-[#4A5850]">{t("hyp.lead")}</p>
      <ul className="space-y-2">
        {items.map((h) => (
          <li key={h.id ?? h.title} className="rounded-xl border border-[#DCE3DB] bg-white p-2.5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded border border-dotted border-[#6B5A9E] bg-[#ECE8F4] px-1.5 py-0.5 text-[10px] font-bold uppercase text-[#4E3F80]">
                {t("hyp.label")}
              </span>
              <span className="text-xs font-semibold text-[#16231B]">{((lang === "fil" && h.titleFil) || h.title || "").replace(/^(hypothesis|hipotesis|haypotesis|haka)\s*[:·-]\s*/i, "")}</span>
            </div>
            <p className="mt-1 text-xs leading-relaxed text-[#4A5850]">{(lang === "fil" && h.summaryFil) || h.summary}</p>
            {h.evidence?.length > 0 && (
              <p className="mt-1 text-[11px] text-[#4A5850]">
                {t("hyp.evidence")}:{" "}
                {h.evidence.map((e) => (
                  <button key={e.label} type="button" className="mr-2 font-medium text-[#1E5B3A] underline hover:text-[#123B25]" onClick={() => onMode?.(e.mode)}>
                    {e.label}
                  </button>
                ))}
              </p>
            )}
            {h.references?.length > 0 && (
              <ul className="mt-1 list-disc pl-4 text-[11px] text-[#4A5850]">
                {h.references.map((r) => (
                  <li key={r.url ?? r.title}>
                    {r.url ? (
                      <a href={r.url} target="_blank" rel="noreferrer" className="text-[#1E5B3A] underline">
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
