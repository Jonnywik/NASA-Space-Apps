"use client";

import React from "react";
import { Caveats, DemoTag, SourceLine, StateNote, fmt } from "./ui";
import { useLang } from "../utils/LangContext";

// /places/exposure as a table. Exposure means people and buildings inside a mapped zone, never damage.
export default function ExposureTable({ tier, onPlace, label }) {
  const { t } = useLang();
  const d = tier.data;
  const isDemo = d?.dataKind === "synthetic";
  return (
    <div data-testid="exposure-table" className="text-[#16231B]">
      <StateNote tier={tier} label={label} />
      {d && (
        <>
          <div className="max-h-56 overflow-auto rounded-xl border border-[#DCE3DB] bg-white">
            <table className="w-full border-collapse text-left text-[11px]">
              <thead className="sticky top-0 bg-[#F2F5F1] text-[#4A5850]">
                <tr>
                  <th className="px-2 py-1.5 font-semibold">{t("col.place")}</th>
                  <th className="px-2 py-1.5 text-right font-semibold">{t("col.population")}</th>
                  <th className="px-2 py-1.5 text-right font-semibold">{t("col.buildings")}</th>
                  <th className="px-2 py-1.5 text-right font-semibold">km²</th>
                </tr>
              </thead>
              <tbody>
                {(d.zones ?? []).map((z) => (
                  <tr key={z.placeId ?? z.name} className="border-t border-[#DCE3DB]">
                    <td className="px-2 py-1.5">
                      <button type="button" className="text-left font-medium text-[#1E5B3A] underline hover:text-[#123B25]" onClick={() => onPlace?.(z)}>
                        {z.name}
                      </button>
                      <div className="text-[#4A5850]">{z.city}</div>
                    </td>
                    <td className="px-2 py-1.5 text-right tabular-nums" title={z.population == null ? d.populationUnavailableReason ?? t("missing.notReported") : undefined}>
                      {fmt(z.population, 0) ?? "—"}
                    </td>
                    <td className="px-2 py-1.5 text-right tabular-nums" title={z.buildings == null ? d.buildingsUnavailableReason ?? t("missing.notReported") : undefined}>
                      {fmt(z.buildings, 0) ?? "—"}
                    </td>
                    <td className="px-2 py-1.5 text-right tabular-nums">{fmt(z.areaKm2, 2) ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
              {d.totals && (
                <tfoot className="border-t border-[#C9D1C7] bg-[#F2F5F1] font-semibold text-[#16231B]">
                  <tr>
                    <td className="px-2 py-1.5">
                      <span className="inline-flex items-center gap-1.5">
                        {t("col.total")}
                        {isDemo && <DemoTag compact />}
                      </span>
                    </td>
                    <td className="px-2 py-1.5 text-right tabular-nums">{fmt(d.totals.population, 0) ?? "—"}</td>
                    <td className="px-2 py-1.5 text-right tabular-nums">{fmt(d.totals.buildings, 0) ?? "—"}</td>
                    <td className="px-2 py-1.5 text-right tabular-nums">{fmt(d.totals.areaKm2, 2) ?? "—"}</td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
          {d.maskDefinition && <p className="mt-1.5 text-[11px] text-[#4A5850]">{t("exposure.mask")}: {d.maskDefinition}</p>}
          {(d.populationUnavailableReason || d.buildingsUnavailableReason) && (
            <p className="mt-1 text-[11px] text-[#4A5850]">
              {[d.populationUnavailableReason, d.buildingsUnavailableReason].filter(Boolean).join(" ")}
            </p>
          )}
          {d.totals?.unassignedAreaKm2 != null && <p className="text-[11px] text-[#4A5850]">{t("exposure.unassigned", { km2: fmt(d.totals.unassignedAreaKm2, 2) })}</p>}
          <p className="mt-1.5 rounded-lg bg-[#FFF6DE] px-2.5 py-1.5 text-[11px] font-medium text-[#5A4300]">{t("exposure.not_damage")}</p>
          <p className="mt-1 text-[11px] text-[#4A5850]">
            {t("exposure.population")}: {d.populationSource?.name ?? "—"} {d.populationSource?.year ?? ""} · {t("exposure.buildings")}: {d.buildingSource?.snapshotDate ?? "—"}
          </p>
          <SourceLine data={d} />
          <Caveats data={d} />
        </>
      )}
    </div>
  );
}
