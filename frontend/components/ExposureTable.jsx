"use client";

import React from "react";
import { Caveats, SourceLine, StateNote, fmt } from "./ui";
import { useLang } from "../utils/LangContext";

// /places/exposure as a table. Exposure means people and buildings inside a mapped zone, never damage.
export default function ExposureTable({ tier, onPlace, label }) {
  const { t } = useLang();
  const d = tier.data;
  return (
    <div data-testid="exposure-table">
      <StateNote tier={tier} label={label} />
      {d && (
        <>
          <div className="max-h-56 overflow-auto rounded border border-slate-700">
            <table className="w-full border-collapse text-left text-[11px]">
              <thead className="sticky top-0 bg-slate-800 text-slate-300">
                <tr>
                  <th className="px-1.5 py-1 font-medium">{t("col.place")}</th>
                  <th className="px-1.5 py-1 text-right font-medium">{t("col.population")}</th>
                  <th className="px-1.5 py-1 text-right font-medium">{t("col.buildings")}</th>
                  <th className="px-1.5 py-1 text-right font-medium">km²</th>
                </tr>
              </thead>
              <tbody>
                {(d.zones ?? []).map((z) => (
                  <tr key={z.placeId ?? z.name} className="border-t border-slate-700/60">
                    <td className="px-1.5 py-1">
                      <button type="button" className="text-left text-sky-300 underline" onClick={() => onPlace?.(z)}>
                        {z.name}
                      </button>
                      <div className="text-slate-400">{z.city}</div>
                    </td>
                    <td className="px-1.5 py-1 text-right" title={z.population == null ? d.populationUnavailableReason ?? t("missing.notReported") : undefined}>{fmt(z.population, 0) ?? "—"}</td>
                    <td className="px-1.5 py-1 text-right" title={z.buildings == null ? d.buildingsUnavailableReason ?? t("missing.notReported") : undefined}>{fmt(z.buildings, 0) ?? "—"}</td>
                    <td className="px-1.5 py-1 text-right">{fmt(z.areaKm2, 2) ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
              {d.totals && (
                <tfoot className="border-t border-slate-500 font-semibold text-slate-100">
                  <tr>
                    <td className="px-1.5 py-1">{t("col.total")}</td>
                    <td className="px-1.5 py-1 text-right">{fmt(d.totals.population, 0) ?? "—"}</td>
                    <td className="px-1.5 py-1 text-right">{fmt(d.totals.buildings, 0) ?? "—"}</td>
                    <td className="px-1.5 py-1 text-right">{fmt(d.totals.areaKm2, 2) ?? "—"}</td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
          {(d.populationUnavailableReason || d.buildingsUnavailableReason) && (
            <p className="mt-1 text-[11px] text-slate-300">
              {[d.populationUnavailableReason, d.buildingsUnavailableReason].filter(Boolean).join(" ")}
            </p>
          )}
          {d.totals?.unassignedAreaKm2 != null && <p className="text-[11px] text-slate-400">{t("exposure.unassigned", { km2: fmt(d.totals.unassignedAreaKm2, 2) })}</p>}
          <p className="mt-1 text-[11px] font-semibold text-amber-200">{t("exposure.not_damage")}</p>
          <p className="text-[11px] text-slate-400">
            {t("exposure.population")}: {d.populationSource?.name ?? "—"} {d.populationSource?.year ?? ""} · {t("exposure.buildings")}: {d.buildingSource?.snapshotDate ?? "—"}
          </p>
          <SourceLine data={d} />
          <Caveats data={d} />
        </>
      )}
    </div>
  );
}
