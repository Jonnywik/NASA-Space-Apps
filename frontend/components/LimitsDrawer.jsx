"use client";

import React, { useEffect, useRef } from "react";
import { KindBadge } from "./ui";
import { useLang } from "../utils/LangContext";
import { useLimits } from "../utils/LimitsContext";

const STANDING = [1, 2, 3, 4, 5, 6, 7];

// U8 Limits drawer: standing caveats plus every limitation / warning string the APIs in view returned.
export default function LimitsDrawer({ open, onClose }) {
  const { t } = useLang();
  const { entries } = useLimits();
  const closeRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    closeRef.current?.focus();
    const onKey = (e) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  const list = Object.entries(entries).filter(([, e]) => e.limitations.length || e.warnings.length);
  return (
    <div className="fixed inset-0 z-[3000] bg-black/50" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <aside role="dialog" aria-modal="true" aria-labelledby="limits-title" className="absolute inset-y-0 right-0 w-full max-w-md overflow-auto border-l border-slate-500 bg-slate-900 p-4 text-white shadow-2xl" data-testid="limits-drawer">
        <div className="flex items-center justify-between">
          <h2 id="limits-title" className="text-lg font-bold">
            {t("limits.title")}
          </h2>
          <button type="button" ref={closeRef} onClick={onClose} className="rounded-md border border-slate-400 px-2.5 py-1 text-sm hover:bg-slate-700">
            {t("radar.close")}
          </button>
        </div>
        <h3 className="mt-3 text-sm font-semibold text-yellow-100">{t("limits.standing")}</h3>
        <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-slate-200">
          {STANDING.map((i) => (
            <li key={i}>{t(`limits.standing.${i}`)}</li>
          ))}
        </ul>
        <h3 className="mt-4 text-sm font-semibold text-yellow-100">{t("sources.title")}</h3>
        <ul className="mt-1 list-disc space-y-1 pl-5 text-xs text-slate-200" data-testid="data-credits">
          {[
            ["NASA–ISRO NISAR · ASF", "https://asf.alaska.edu/datasets/daac/nisar/"],
            ["NASA POWER", "https://power.larc.nasa.gov/"],
            ["WorldPop 2020 · CC BY 4.0", "https://www.worldpop.org/"],
            ["OpenStreetMap contributors · ODbL", "https://www.openstreetmap.org/copyright"],
            ["ESA WorldCover · CC BY 4.0", "https://esa-worldcover.org/en/data-access"],
            ["HDX Philippines COD-AB", "https://data.humdata.org/dataset/cod-ab-phl"],
            ["Open-Meteo / ECMWF", "https://open-meteo.com/en/docs/seasonal-forecast-api"],
          ].map(([label, url]) => <li key={url}><a href={url} target="_blank" rel="noreferrer" className="text-sky-300 underline">{label}</a></li>)}
        </ul>
        <h3 className="mt-4 text-sm font-semibold text-yellow-100">{t("limits.fromApi")}</h3>
        {list.length === 0 && <p className="mt-1 text-sm text-slate-300">{t("limits.none")}</p>}
        {list.map(([key, e]) => (
          <div key={key} className="mt-3 rounded-lg border border-slate-700 bg-slate-800/60 p-2.5" data-testid="limits-entry">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold">{e.label}</span>
              {e.dataKind && <KindBadge kind={e.dataKind} />}
            </div>
            {e.sourceName && <p className="text-[11px] text-slate-400">{e.sourceName}</p>}
            <ul className="mt-1 list-disc space-y-1 pl-5 text-xs text-slate-200">
              {e.warnings.map((w) => (
                <li key={`w-${w}`} className="text-amber-100">
                  ⚠ {w}
                </li>
              ))}
              {e.limitations.map((l) => (
                <li key={`l-${l}`}>{l}</li>
              ))}
            </ul>
          </div>
        ))}
      </aside>
    </div>
  );
}
