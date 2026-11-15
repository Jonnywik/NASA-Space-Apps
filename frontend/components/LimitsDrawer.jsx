"use client";

import React, { useEffect, useRef } from "react";
import { KindBadge } from "./ui";
import { useLang } from "../utils/LangContext";
import { useLimits } from "../utils/LimitsContext";

const STANDING = [1, 2, 3, 4, 5, 6, 7];

function formatBytes(bytes) {
  if (typeof bytes !== "number" || !Number.isFinite(bytes) || bytes < 0) return null;
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(kb >= 100 ? 0 : 1)} KB`;
  const mb = kb / 1024;
  return `${mb.toFixed(mb >= 100 ? 0 : 1)} MB`;
}

// U8 Limits drawer: standing caveats plus every limitation / warning string returned by APIs in view.
export default function LimitsDrawer({ open, onClose, downloadsTier = null, focusDownloads = false }) {
  const { t } = useLang();
  const { entries } = useLimits();
  const closeRef = useRef(null);
  const downloadsRef = useRef(null);
  const downloadCount = Array.isArray(downloadsTier) ? downloadsTier.length : downloadsTier?.data?.length ?? 0;

  useEffect(() => {
    if (!open || !focusDownloads) return undefined;
    // after the drawer has focused its Close button (which would scroll back to the top)
    const id = window.setTimeout(() => downloadsRef.current?.scrollIntoView({ block: "start" }), 60);
    return () => window.clearTimeout(id);
  }, [open, focusDownloads, downloadCount]);

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
  const downloads = Array.isArray(downloadsTier) ? downloadsTier : downloadsTier?.data ?? [];
  return (
    <div className="fixed inset-0 z-[3000] bg-black/35 backdrop-blur-[1px]" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <aside
        role="dialog"
        aria-modal="true"
        aria-labelledby="limits-title"
        className="absolute inset-y-0 right-0 w-full max-w-md overflow-auto border-l border-[#DCE3DB] bg-white p-5 text-[#16231B] shadow-2xl"
        data-testid="limits-drawer"
      >
        <div className="flex items-center justify-between border-b border-[#DCE3DB] pb-3">
          <h2 id="limits-title" className="font-serif text-[20px] font-semibold text-[#16231B]">
            {t("limits.title")}
          </h2>
          <button
            type="button"
            ref={closeRef}
            onClick={onClose}
            className="h-9 rounded-lg border border-[#DCE3DB] bg-[#F2F5F1] px-3 text-[13px] font-medium text-[#16231B] hover:bg-[#E3EFE7]"
          >
            {t("radar.close")}
          </button>
        </div>

        <h3 className="mt-4 font-serif text-[15px] font-semibold text-[#1E5B3A]">{t("limits.standing")}</h3>
        <ul className="mt-1.5 list-disc space-y-1.5 pl-5 text-[13px] leading-relaxed text-[#16231B]">
          {STANDING.map((i) => (
            <li key={i}>{t(`limits.standing.${i}`)}</li>
          ))}
        </ul>

        <h3 className="mt-5 font-serif text-[15px] font-semibold text-[#1E5B3A]">{t("sources.title")}</h3>
        <ul className="mt-1.5 list-disc space-y-1 pl-5 text-[12px] text-[#4A5850]" data-testid="data-credits">
          {[
            ["NASA–ISRO NISAR · ASF", "https://nisar-docs.asf.alaska.edu/"],
            ["NASA POWER", "https://power.larc.nasa.gov/"],
            ["NASA GPM IMERG · GES DISC", "https://disc.gsfc.nasa.gov/datasets/GPM_3IMERGHHL_07/summary"],
            ["NASA OPERA DSWx-S1 · PO.DAAC", "https://podaac.jpl.nasa.gov/dataset/OPERA_L3_DSWX-S1_V1"],
            ["WorldPop 2020 · CC BY 4.0", "https://www.worldpop.org/"],
            ["OpenStreetMap contributors · ODbL", "https://www.openstreetmap.org/copyright"],
            ["ESA WorldCover · CC BY 4.0", "https://esa-worldcover.org/en/data-access"],
            ["HDX Philippines COD-AB", "https://data.humdata.org/dataset/cod-ab-phl"],
            ["Open-Meteo / ECMWF", "https://open-meteo.com/en/docs/seasonal-forecast-api"],
          ].map(([label, url]) => (
            <li key={url}>
              <a href={url} target="_blank" rel="noreferrer" className="font-medium text-[#1E5B3A] underline hover:text-[#123B25]">
                {label}
              </a>
            </li>
          ))}
        </ul>

        <h3 className="mt-5 font-serif text-[15px] font-semibold text-[#1E5B3A]">{t("limits.learn")}</h3>
        <ul className="mt-1.5 list-disc space-y-1 pl-5 text-[12px] text-[#4A5850]" data-testid="further-reading">
          {[
            [t("limits.learn.products"), "https://nisar-docs.asf.alaska.edu/products-overview/"],
            [t("limits.learn.gcov"), "https://nisar-docs.asf.alaska.edu/gcov/"],
            [t("limits.learn.phase"), "https://nisar-docs.asf.alaska.edu/phase/"],
            [t("limits.learn.arset"), "https://forum.earthdata.nasa.gov/viewtopic.php?t=6022"],
          ].map(([label, url]) => (
            <li key={url}>
              <a href={url} target="_blank" rel="noreferrer" className="font-medium text-[#1E5B3A] underline hover:text-[#123B25]">
                {label}
              </a>
            </li>
          ))}
        </ul>

        <h3 className="mt-5 font-serif text-[15px] font-semibold text-[#1E5B3A]">{t("limits.fromApi")}</h3>
        {list.length === 0 && <p className="mt-1 text-[13px] text-[#4A5850]">{t("limits.none")}</p>}
        {list.map(([key, e]) => (
          <div key={key} className="mt-3 rounded-xl border border-[#DCE3DB] bg-[#F2F5F1] p-3" data-testid="limits-entry">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[13px] font-semibold text-[#16231B]">{e.label}</span>
              {e.dataKind && <KindBadge kind={e.dataKind} />}
            </div>
            {e.sourceName && <p className="mt-0.5 text-[11px] text-[#4A5850]">{e.sourceName}</p>}
            <ul className="mt-1.5 list-disc space-y-1 pl-5 text-[12px] leading-relaxed text-[#16231B]">
              {e.warnings.map((w) => (
                <li key={`w-${w}`} className="font-medium text-[#7A5B00]">
                  ⚠ {w}
                </li>
              ))}
              {e.limitations.map((l) => (
                <li key={`l-${l}`}>{l}</li>
              ))}
            </ul>
          </div>
        ))}

        {downloads.length > 0 && (
          <section ref={downloadsRef} className="mt-6 border-t border-[#DCE3DB] pt-4" data-testid="downloads-list">
            <h3 className="font-serif text-[15px] font-semibold text-[#1E5B3A]">{t("downloads.title")}</h3>
            <p className="mt-1 text-[12px] text-[#4A5850]">{t("downloads.lead")}</p>
            <ul className="mt-2.5 space-y-2">
              {downloads.map((item, i) => {
                const size = formatBytes(item.sizeBytes);
                const meta = [item.format, size, item.licence].filter(Boolean).join(" · ");
                return (
                  <li
                    key={item.id ?? item.url ?? i}
                    className="flex items-center justify-between gap-3 rounded-xl border border-[#DCE3DB] bg-[#F2F5F1] px-3 py-2.5"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="text-[13px] font-semibold text-[#16231B]">{item.title}</span>
                        {item.dataKind && <KindBadge kind={item.dataKind} />}
                      </div>
                      {meta && <p className="mt-0.5 text-[11px] text-[#4A5850]">{meta}</p>}
                    </div>
                    {item.url && (
                      <a
                        href={item.url}
                        download
                        className="shrink-0 rounded-lg border border-[#DCE3DB] bg-white px-2.5 py-1 text-[12px] font-semibold text-[#1E5B3A] hover:bg-[#E3EFE7]"
                      >
                        {t("downloads.action")}
                      </a>
                    )}
                  </li>
                );
              })}
            </ul>
          </section>
        )}
      </aside>
    </div>
  );
}
