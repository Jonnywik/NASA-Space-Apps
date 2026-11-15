"use client";

import React from "react";
import { Caveats, Section, SourceLine, Stat, StateNote, fmt } from "./ui";
import { useLang } from "../utils/LangContext";

function ExtraOverlayCard({ tier, title, testId, stats, medianCol, medianValue, caption, onSources }) {
  const { t } = useLang();
  const safeTier = tier ?? { state: "unavailable" };
  const d = safeTier.data;
  const noteTier = !d && (!safeTier.state || safeTier.state === "ready" || safeTier.state === "idle") ? { state: "unavailable" } : safeTier;
  const rows = Array.isArray(d?.byLandCover) ? d.byLandCover : [];
  const isDemo = d?.dataKind === "synthetic";

  return (
    <Section title={title} sensor="nisar_l" kind={d?.dataKind} testId={testId}>
      <StateNote tier={noteTier} label={title} />

      {d && (
        <div className="flex flex-col gap-3">
          <div className="grid grid-cols-2 gap-2">
            {stats.map((s) => (
              <Stat key={s.label} label={s.label} value={s.value} isDemo={isDemo} compact />
            ))}
          </div>

          {rows.length > 0 && (
            <div className="overflow-hidden rounded-xl border border-[#DCE3DB] bg-white">
              <table className="w-full text-left text-[12px] text-[#16231B]">
                <thead className="bg-[#F2F5F1] text-[11px] text-[#4A5850]">
                  <tr>
                    <th className="px-2.5 py-1.5 font-semibold">{t("rainResp.landCoverCol")}</th>
                    <th className="px-2.5 py-1.5 text-right font-semibold">{t("rainResp.cellsCol")}</th>
                    <th className="px-2.5 py-1.5 text-right font-semibold">{medianCol}</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.class ?? r.name} className="border-t border-[#DCE3DB]">
                      <td className="px-2.5 py-1.5 font-medium">{r.name ?? r.class}</td>
                      <td className="px-2.5 py-1.5 text-right tabular-nums text-[#4A5850]">{fmt(r.cells, 0) ?? "—"}</td>
                      <td className="px-2.5 py-1.5 text-right font-semibold tabular-nums">{fmt(medianValue(r), 3) ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <p className="m-0 rounded-xl border border-[#DCE3DB] bg-[#F2F5F1] px-3 py-2 text-xs font-medium leading-relaxed text-[#16231B]">
            {caption}
          </p>

          <SourceLine data={d} onSources={onSources} />
          <Caveats data={d} />
        </div>
      )}
    </Section>
  );
}

export function RainResponseCard({ tier, onSources }) {
  const { t } = useLang();
  const d = tier?.data;
  return (
    <ExtraOverlayCard
      tier={tier}
      title={t("rainResp.title")}
      testId="rain-response-card"
      stats={[
        { label: t("rainResp.medianRho"), value: fmt(d?.stats?.medianRho, 3) },
        { label: t("rainResp.shareAbove05"), value: `${Math.round((d?.stats?.shareAbove05 ?? 0) * 100)}%` },
      ]}
      medianCol={t("rainResp.medianCol")}
      medianValue={(r) => r.median ?? r.medianRho}
      caption={t("rainResp.caption")}
      onSources={onSources}
    />
  );
}

export function CoherenceChangeCard({ tier, onSources }) {
  const { t } = useLang();
  const d = tier?.data;
  return (
    <ExtraOverlayCard
      tier={tier}
      title={t("cohChange.title")}
      testId="coherence-change-card"
      stats={[
        { label: t("cohChange.km2Over03"), value: `${fmt(d?.stats?.km2DropOver03, 2) ?? "—"} km²` },
        { label: t("cohChange.medianDrop"), value: fmt(d?.stats?.medianDrop, 3) },
      ]}
      medianCol={t("cohChange.medianCol")}
      medianValue={(r) => r.median ?? r.medianDrop}
      caption={t("cohChange.caption")}
      onSources={onSources}
    />
  );
}
