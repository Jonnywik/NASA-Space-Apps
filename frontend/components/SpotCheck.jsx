"use client";

import React, { useState } from "react";
import PixelChart from "./PixelChart";
import { Caveats, DemoTag, KindBadge, Section, SourceLine, StateNote, fmt } from "./ui";
import { classifyError, exportPlaceBriefing, getPlaceBriefing, getSpotCheck } from "../utils/api";
import { useLang } from "../utils/LangContext";
import { useReportLimits } from "../utils/LimitsContext";
import { useTier } from "../utils/useTier";
import { reasonText } from "../utils/reasons";

const STATE_GLYPH = { water: "■", dry: "□", nodata: "▨" };

function streamTier(tier, key, wrap, t) {
  const stream = tier.data?.streams?.[key];
  // A ready response without this stream must not pass the whole response on as the stream's data.
  if (!stream) return tier.data ? { state: "unavailable", data: null, error: null } : tier;
  if (stream.value == null) return { state: "unavailable", data: null, error: { detail: { message: t ? reasonText(t, stream.reason) : stream.reason } } };
  return { state: "ready", data: { ...stream, ...(wrap ? wrap(stream.value) : stream.value) }, error: null };
}

export function useSpotData(point) {
  const { t } = useLang();
  const lon = point?.lon;
  const lat = point?.lat;
  const spot = useTier(lon != null && lat != null ? () => getSpotCheck(lon, lat) : null, [lon, lat]);
  const briefing = useTier(lon != null && lat != null ? () => getPlaceBriefing(lon, lat, "fil") : null, [lon, lat]);
  useReportLimits("spot", t("spot.title"), spot.data);
  return { spot, briefing };
}

export function SpotCard({ point, placeHint, spotTier, imergTier, mode, selectedDate, onClose, onOpenDetails }) {
  const { t, lang } = useLang();
  const [exportState, setExportState] = useState({ state: "idle" });
  if (!point) return null;

  const { lon, lat } = point;
  const nisar = streamTier(spotTier, "nisar", undefined, t);
  const locate = streamTier(spotTier, "place", undefined, t);
  const los = streamTier(spotTier, "motion", (pt) => ({ point: pt }), t);
  const imergPasses = imergTier?.data?.passes ?? [];
  const imergPass = imergPasses.find((p) => p.date === selectedDate) ?? imergPasses[imergPasses.length - 1];
  const imerg24h = imergPass ? (imergPass.last24hMm != null ? `${fmt(imergPass.last24hMm, 1)} mm` : t("imerg.incomplete")) : null;

  const nd = nisar.data;
  const ld = locate.data;
  const placeName = ld?.barangay?.name ?? placeHint?.name ?? t("spot.title");
  const cityName = ld?.city?.name ?? placeHint?.city ?? null;
  const subtitle = cityName ? `${cityName} · ${lat.toFixed(4)}°N, ${lon.toFixed(4)}°E` : `${lat.toFixed(4)}°N, ${lon.toFixed(4)}°E`;
  const isNisarDemo = nd?.dataKind === "synthetic";
  const isLosDemo = los.data?.dataKind === "synthetic";

  async function doExport(language, format) {
    const tab = format === "html" ? window.open("", "_blank") : null;
    if (tab) tab.opener = null;
    setExportState({ state: "loading" });
    try {
      const blob = await exportPlaceBriefing(lon, lat, language, format);
      const url = URL.createObjectURL(blob);
      if (format === "html" && tab) tab.location.href = url;
      else {
        const link = document.createElement("a");
        link.href = url;
        link.download = `tanaw-${lon}-${lat}-${language}.${format}`;
        link.click();
      }
      setTimeout(() => URL.revokeObjectURL(url), 60000);
      setExportState({ state: "idle" });
    } catch (error) {
      tab?.close();
      setExportState({ state: classifyError(error), error });
    }
  }

  // Mini motion SVG polyline when mode === "motion"
  const motionPts = los.data?.point?.status === "ok" ? los.data.point.displacementMm ?? [] : [];
  const motionEpochs = los.data?.point?.epochs ?? [];
  const lastMm = motionPts.length ? motionPts[motionPts.length - 1] : null;
  const polyPoints = (() => {
    const valid = motionPts.filter((v) => typeof v === "number");
    if (motionPts.length < 2 || !valid.length) return null;
    const min = Math.min(0, ...valid);
    const max = Math.max(1, ...valid);
    const span = Math.max(1, max - min);
    return motionPts
      .map((v, i) => {
        const x = (i / Math.max(1, motionPts.length - 1)) * 280;
        const val = typeof v === "number" ? v : 0;
        const y = 30 - ((val - min) / span) * 24;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
  })();

  return (
    <div
      data-testid="spot-card"
      className="flex w-[min(328px,calc(100%-32px))] flex-col gap-2.5 rounded-[14px] border border-[#DCE3DB] bg-white p-3.5 text-[#16231B] shadow-[0_6px_24px_rgba(20,30,40,0.14)]"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <span className="text-[11px] font-bold uppercase tracking-[0.07em] text-[#1E5B3A]">{t("spot.selected.eyebrow")}</span>
          <h2 className="m-0 truncate font-serif text-[19px] font-semibold leading-tight text-[#16231B]">{placeName}</h2>
          <p className="m-0 truncate text-[12px] text-[#4A5850]">{subtitle}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label={t("spot.clear")}
          className="-mr-1.5 -mt-1.5 flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border-0 bg-transparent text-[20px] text-[#4A5850] hover:bg-[#F2F5F1] hover:text-[#16231B]"
        >
          ×
        </button>
      </div>

      {spotTier.state === "loading" ? (
        <div className="rounded-lg bg-[#F2F5F1] p-2.5 text-xs text-[#4A5850]">{t("state.loading.title")}</div>
      ) : spotTier.state !== "ready" ? (
        <StateNote tier={spotTier} />
      ) : mode === "motion" ? (
        <div className="flex flex-col gap-1.5">
          <div className="flex items-baseline justify-between gap-2 text-[12px]">
            <span className="text-[#4A5850]">{t("spot.card.losLabel")}</span>
            <span className="flex items-center gap-1.5 font-bold text-[#7B3294]">
              {lastMm != null ? `${lastMm >= 0 ? "+" : ""}${fmt(lastMm)} mm` : "—"}
              {isLosDemo && <DemoTag compact />}
            </span>
          </div>
          {polyPoints ? (
            <svg viewBox="0 0 280 34" className="h-[34px] w-full" aria-hidden="true">
              <polyline fill="none" stroke="#7B3294" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" points={polyPoints} />
            </svg>
          ) : (
            <div className="text-[11px] text-[#4A5850]">{reasonText(t, los.data?.point?.reason) ?? t("spot.noValue")}</div>
          )}
          {motionEpochs.length >= 2 && (
            <span className="text-[11px] text-[#4A5850]">
              {t("spot.card.losPeriod", { from: motionEpochs[0], to: motionEpochs[motionEpochs.length - 1] })}
            </span>
          )}
        </div>
      ) : (
        <div className="flex flex-col gap-1.5">
          <div className="flex flex-wrap items-baseline justify-between gap-x-2 gap-y-0.5 text-[12px]">
            <span className="text-[#4A5850]">{t("spot.card.waterPasses")}</span>
            <span className="flex items-center gap-1.5 font-bold text-[#16231B]" data-testid="spot-card-water-count">
              {nd?.permanentWater
                ? t("spot.permanent")
                : nd?.floodCount === 0
                  ? t("spot.card.waterZero", { n: nd.validCount ?? 11 })
                  : nd?.floodCount != null
                    ? t("spot.card.waterCount", { k: nd.floodCount, n: nd.validCount ?? "—" })
                    : "—"}
              {isNisarDemo && <DemoTag compact />}
            </span>
          </div>
          {Array.isArray(nd?.perPass) && nd.perPass.length > 0 && (
            <div className="flex gap-1" aria-label={t("spot.perPass")}>
              {nd.perPass.map((p) => {
                const isSelected = p.date === selectedDate;
                const bg =
                  p.state === "water"
                    ? "#2171B5"
                    : p.possibleFloodedVegetation
                      ? "#E69F00"
                      : p.state === "dry"
                        ? "#DCE3DB"
                        : "#EEF1EC";
                return (
                  <span
                    key={p.date}
                    title={`${p.date}: ${t(`spot.state.${p.state}`)}`}
                    className={`h-2.5 flex-1 rounded-[3px] ${isSelected ? "ring-2 ring-[#1E5B3A] ring-offset-1" : ""}`}
                    style={{ background: bg }}
                  />
                );
              })}
            </div>
          )}
          {nd?.possibleFloodedVegetationPasses > 0 && (
            <span className="text-[11px] text-[#4A5850]">◆ {t("spot.vegPasses", { n: nd.possibleFloodedVegetationPasses })}</span>
          )}
          {imerg24h && (
            <div className="text-[11px] text-[#0B4F79]" data-testid="spot-imerg-24h">
              {t("spot.card.imerg24h", { mm: imerg24h })}
            </div>
          )}
        </div>
      )}

      <div className="flex flex-wrap gap-1.5 pt-0.5">
        <button
          type="button"
          disabled={exportState.state === "loading"}
          onClick={() => doExport(lang, "html")}
          className="h-9 rounded-lg bg-[#1E5B3A] px-3 text-[12px] font-semibold text-white hover:bg-[#123B25] disabled:opacity-50"
          data-testid="card-briefing"
        >
          {t("spot.briefing")}
        </button>
        <button
          type="button"
          disabled={exportState.state === "loading"}
          onClick={() => doExport(lang, "csv")}
          className="h-9 rounded-lg border border-[#DCE3DB] bg-[#F2F5F1] px-2.5 text-[12px] font-medium text-[#16231B] hover:bg-[#E3EFE7] disabled:opacity-50"
          data-testid="card-csv"
        >
          {t("spot.csv")}
        </button>
        <button
          type="button"
          onClick={onOpenDetails}
          className="h-9 rounded-lg border border-[#DCE3DB] bg-white px-2.5 text-[12px] font-medium text-[#1E5B3A] hover:bg-[#E3EFE7]"
          data-testid="card-full-details"
        >
          {t("spot.fullDetails")}
        </button>
      </div>
      {exportState.state !== "idle" && exportState.state !== "loading" && <StateNote tier={exportState} label={t("briefing.title")} />}
    </div>
  );
}

// U2 spot check: one clicked point, every value with its source, missing values with a reason.
export default function SpotCheck({ point, placeHint, selectedDate, spotTier: externalSpot, briefingTier: externalBriefing, imergTier, onClose, onBack, onCopy, copied, onHelp }) {
  const { t, lang } = useLang();
  const { lon, lat } = point;
  const fallbackSpot = useTier(!externalSpot ? () => getSpotCheck(lon, lat) : null, [lon, lat]);
  const fallbackBriefing = useTier(!externalBriefing ? () => getPlaceBriefing(lon, lat, "fil") : null, [lon, lat]);
  const spot = externalSpot ?? fallbackSpot;
  const briefing = externalBriefing ?? fallbackBriefing;
  const [exportState, setExportState] = useState({ state: "idle" });
  const nisar = streamTier(spot, "nisar", undefined, t);
  const locate = streamTier(spot, "place", undefined, t);
  const rain = streamTier(spot, "rainfall", (passes) => ({ passes }), t);
  const los = streamTier(spot, "motion", (pt) => ({ point: pt }), t);
  const priority = spot.data?.streams?.priority;
  const exposure = spot.data?.streams?.exposure;
  const imergPasses = imergTier?.data?.passes ?? [];
  const imergPass = imergPasses.find((p) => p.date === selectedDate) ?? imergPasses[imergPasses.length - 1];
  const imerg24h = imergPass ? (imergPass.last24hMm != null ? `${fmt(imergPass.last24hMm, 1)} mm` : t("imerg.incomplete")) : null;
  useReportLimits("spot", t("spot.title"), !externalSpot ? spot.data : null);

  async function exportBriefing(language, format) {
    const tab = format === "html" ? window.open("", "_blank") : null;
    if (tab) tab.opener = null;
    setExportState({ state: "loading" });
    try {
      const blob = await exportPlaceBriefing(lon, lat, language, format);
      const url = URL.createObjectURL(blob);
      if (format === "html" && tab) tab.location.href = url;
      else {
        const link = document.createElement("a");
        link.href = url;
        link.download = `tanaw-${lon}-${lat}-${language}.${format}`;
        link.click();
      }
      setTimeout(() => URL.revokeObjectURL(url), 60000);
      setExportState({ state: "idle" });
    } catch (error) {
      tab?.close();
      setExportState({ state: classifyError(error), error });
    }
  }

  const nd = nisar.data;
  const ld = locate.data;
  const placeName = ld?.barangay?.name ?? placeHint?.name ?? null;
  const cityName = ld?.city?.name ?? placeHint?.city ?? null;
  const selRain = rain.data?.passes?.find((p) => p.date === selectedDate);
  const selPass = nd?.perPass?.find((p) => p.date === selectedDate);

  return (
    <div data-testid="spot-check" className="text-[#16231B]">
      {onBack && (
        <button
          type="button"
          onClick={onBack}
          className="mb-3 inline-flex items-center gap-1.5 rounded-lg border border-[#DCE3DB] bg-[#F2F5F1] px-2.5 py-1.5 text-xs font-semibold text-[#1E5B3A] hover:bg-[#E3EFE7]"
          data-testid="back-to-findings"
        >
          ← {t("spot.backToFindings")}
        </button>
      )}
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <span className="text-[11px] font-bold uppercase tracking-[0.07em] text-[#1E5B3A]">{t("spot.selected.eyebrow")}</span>
          <h2 className="font-serif text-xl font-semibold text-[#16231B]" data-testid="spot-title">
            {placeName ? `${placeName}${cityName ? `, ${cityName}` : ""}` : t("spot.title")}
          </h2>
          <p className="text-[11px] text-[#4A5850]">
            {lat.toFixed(5)}°N, {lon.toFixed(5)}°E
          </p>
        </div>
        <div className="flex shrink-0 gap-1.5">
          <button type="button" onClick={onCopy} className="h-9 rounded-lg border border-[#DCE3DB] bg-[#F2F5F1] px-2.5 text-xs font-semibold text-[#1E5B3A] hover:bg-[#E3EFE7]" data-testid="copy-link">
            {copied ? t("spot.copied") : t("spot.copy")}
          </button>
          <button type="button" onClick={onClose} className="h-9 w-9 rounded-lg border border-[#DCE3DB] bg-white text-sm text-[#4A5850] hover:bg-[#F2F5F1]" aria-label={t("spot.close")}>
            ✕
          </button>
        </div>
      </div>

      <Section title={t("briefing.title")} kind={briefing.data?.dataKind} testId="place-briefing">
        <StateNote tier={briefing} label={t("briefing.title")} />
        {briefing.data && (
          <>
            <p className="mb-2 text-[11px] text-[#4A5850]">{t("briefing.facts")}</p>
            {briefing.data.translationStatus && <p className="mb-2 rounded border border-dashed border-[#7A5B00]/50 bg-[#FFF6DE] px-2 py-1 text-[11px] text-[#7A5B00]" data-testid="translation-review">{t("briefing.review")}</p>}
            <div className="flex flex-wrap gap-2">
              {[["en", "html", "briefing.en"], ["fil", "html", "briefing.fil"], [lang, "csv", "briefing.csv"]].map(([language, format, label]) => (
                <button
                  key={label}
                  type="button"
                  disabled={exportState.state === "loading"}
                  onClick={() => exportBriefing(language, format)}
                  className={`h-9 rounded-lg px-3 text-xs font-semibold disabled:opacity-50 ${
                    format === "html" && language === lang
                      ? "bg-[#1E5B3A] text-white hover:bg-[#123B25]"
                      : "border border-[#DCE3DB] bg-[#F2F5F1] text-[#16231B] hover:bg-[#E3EFE7]"
                  }`}
                  data-testid={`export-${format}-${language}`}
                >
                  {t(label)}
                </button>
              ))}
            </div>
            <StateNote tier={exportState} label={t("briefing.title")} />
          </>
        )}
      </Section>

      <Section title={t("spot.place")} sensor="places" kind={ld?.dataKind}>
        {locate.state === "ready" ? (
          <>
            <p className="text-xs text-[#16231B]">
              {ld.barangay ? <>{t("spot.barangay")}: <b>{ld.barangay.name}</b></> : t("spot.noBarangay")}
              {ld.city ? <> · {t("spot.city")}: <b>{ld.city.name}</b></> : ""}
            </p>
            <SourceLine data={ld} />
            <Caveats data={ld} />
          </>
        ) : (
          <StateNote tier={locate} label={t("spot.place")} />
        )}
      </Section>

      <Section title={t("spot.nisar")} sensor="nisar_l" kind={nd?.dataKind} helpCard="water" onHelp={onHelp}>
        <StateNote tier={nisar} label={t("spot.nisar")} />
        {nd && (
          <>
            <p className="text-sm font-medium text-[#16231B]" data-testid="flood-count">
              {nd.permanentWater
                ? t("spot.permanent")
                : nd.floodCount == null
                  ? `${t("spot.noCount")}${nd.floodCountReason ? `: ${nd.floodCountReason}` : ""}`
                  : nd.floodCount === 0
                    ? t("spot.card.waterZero", { n: nd.validCount ?? 11 })
                    : t("spot.floodCount", { k: nd.floodCount, n: nd.validCount ?? "—" })}
            </p>
            {nd.permanentWater && nd.floodCountReason && <p className="text-[11px] text-[#4A5850]">{nd.floodCountReason}</p>}
            {nd.possibleFloodedVegetationPasses > 0 && <p className="text-[11px] text-[#7A5B00]">◆ {t("spot.vegPasses", { n: nd.possibleFloodedVegetationPasses })}</p>}
            {nd.cellCenter && <p className="text-[11px] text-[#4A5850]">{t("spot.cell", { lon: nd.cellCenter.lon?.toFixed?.(5), lat: nd.cellCenter.lat?.toFixed?.(5) })}</p>}
            <div className="mt-2 flex flex-wrap gap-1" role="list" aria-label={t("spot.perPass")} data-testid="per-pass">
              {(nd.perPass ?? []).map((p) => (
                <div
                  key={p.date}
                  role="listitem"
                  className={`w-[54px] rounded-md border px-1 py-1 text-center text-[11px] ${p.date === selectedDate ? "border-[#1E5B3A] bg-[#E3EFE7] font-semibold text-[#123B25]" : "border-[#DCE3DB] bg-[#F2F5F1] text-[#16231B]"}`}
                  title={`${p.date}: ${t(`spot.state.${p.state}`)}${p.possibleFloodedVegetation ? ` · ${t("season.vegetation")}` : ""}${p.reason ? ` · ${reasonText(t, p.reason)}` : ""}`}
                >
                  <div className="text-sm leading-none" aria-hidden="true">
                    {STATE_GLYPH[p.state] ?? "?"}
                    {p.possibleFloodedVegetation ? "◆" : ""}
                  </div>
                  <div>{t(`spot.state.${p.state}.short`)}</div>
                  <div className="text-[#4A5850]">{p.date.slice(5)}</div>
                </div>
              ))}
            </div>
            <p className="mt-1 text-[11px] text-[#4A5850]">
              ■ {t("spot.state.water")} · □ {t("spot.state.dry")} · ▨ {t("spot.state.nodata")} · ◆ {t("season.vegetation")}
            </p>
            <details className="mt-1.5 text-[11px] text-[#4A5850]">
              <summary className="cursor-pointer font-medium text-[#1E5B3A]">{t("spot.db")}</summary>
              <table className="mt-1 w-full text-left text-[#16231B]">
                <thead className="text-[#4A5850]">
                  <tr>
                    <th className="font-medium">{t("col.date")}</th>
                    <th className="font-medium">{t("spot.state")}</th>
                    <th className="font-medium">HH dB</th>
                    <th className="font-medium">HV dB</th>
                  </tr>
                </thead>
                <tbody>
                  {(nd.perPass ?? []).map((p) => (
                    <tr key={p.date} className="border-t border-[#DCE3DB]">
                      <td className="py-1">{p.date}</td>
                      <td>
                        {t(`spot.state.${p.state}`)}
                        {p.possibleFloodedVegetation ? " ◆" : ""}
                        {p.reason ? <span className="block text-[#4A5850]">{reasonText(t, p.reason)}</span> : null}
                      </td>
                      <td>{p.hhDb ?? <span title={t("spot.noValue")}>—</span>}</td>
                      <td>{p.hvDb ?? <span title={t("spot.noValue")}>—</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-1 text-[#4A5850]">{t("spot.noValue")}</p>
            </details>
            {selPass && (
              <p className="mt-1 text-[11px] text-[#16231B]">
                {t("spot.selected", { date: selectedDate, state: t(`spot.state.${selPass.state}`) })}
              </p>
            )}
            <SourceLine data={nd} className="mt-1" />
            <Caveats data={nd} />
          </>
        )}
      </Section>

      <Section title={t("spot.rain")} sensor="power" kind={rain.data?.dataKind}>
        <p className="mb-1 text-[11px] text-[#4A5850]">{t("spot.rain.cell")}</p>
        {imerg24h && (
          <p className="mb-2 rounded-lg border border-[#2171B5]/30 bg-[#EEF5FA] px-2.5 py-1.5 text-[11px] font-medium text-[#0B4F79]" data-testid="spot-detail-imerg-24h">
            {t("spot.card.imerg24h", { mm: imerg24h })}
          </p>
        )}
        <StateNote tier={rain} label={t("spot.rain")} />
        {rain.data && (
          <>
            {selRain ? (
              <div className="grid grid-cols-3 gap-1.5 text-center text-xs">
                {[
                  ["spot.rain.same", selRain.sameDayMm],
                  ["spot.rain.p3", selRain.prior3DayMm],
                  ["spot.rain.p7", selRain.prior7DayMm],
                ].map(([k, v]) => (
                  <div key={k} className="rounded-lg border border-[#DCE3DB] bg-[#F2F5F1] p-2">
                    <div className="text-[11px] text-[#4A5850]">{t(k)}</div>
                    <div className="font-bold text-[#16231B]" title={v == null ? t("spot.rain.missing") : undefined}>
                      {v == null ? "—" : `${fmt(v)} mm`}
                    </div>
                    {v == null && <div className="text-[10px] text-[#7A5B00]">{t("spot.rain.missing")}</div>}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[11px] text-[#4A5850]">{t("spot.rain.nopass")}</p>
            )}
            <details className="mt-1.5 text-[11px] text-[#4A5850]">
              <summary className="cursor-pointer font-medium text-[#1E5B3A]">{t("spot.rain.all")}</summary>
              <table className="mt-1 w-full text-left text-[#16231B]">
                <thead className="text-[#4A5850]">
                  <tr>
                    <th className="font-medium">{t("col.date")}</th>
                    <th className="font-medium">{t("spot.rain.same")}</th>
                    <th className="font-medium">3 d</th>
                    <th className="font-medium">7 d</th>
                  </tr>
                </thead>
                <tbody>
                  {rain.data.passes.map((p) => (
                    <tr key={p.date} className={`border-t border-[#DCE3DB] ${p.date === selectedDate ? "bg-[#E3EFE7] font-semibold" : ""}`}>
                      <td className="py-1">{p.date}</td>
                      <td>{p.sameDayMm ?? "—"}</td>
                      <td>{p.prior3DayMm ?? "—"}</td>
                      <td>{p.prior7DayMm ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>
            {rain.data.windowDefinition && <p className="mt-1 text-[11px] text-[#4A5850]">{rain.data.windowDefinition}</p>}
            <SourceLine data={rain.data} className="mt-1" />
            <Caveats data={rain.data} />
          </>
        )}
        {rain.state === "idle" && <p className="text-[11px] text-[#4A5850]">{t("spot.rain.nopasses")}</p>}
      </Section>

      <Section title={t("spot.los")} sensor="insar" kind={los.data?.dataKind} helpCard="insar" onHelp={onHelp}>
        <StateNote tier={los} label={t("spot.los")} />
        {los.state === "ready" && (
          <>
            <PixelChart point={los.data.point} cumulative />
            <SourceLine data={los.data} className="mt-1" />
            <Caveats data={los.data} />
          </>
        )}
      </Section>

      <Section title={t("priority.title")} kind={priority?.dataKind} testId="spot-priority">
        <p className="text-xs text-[#16231B]">{priority?.value == null ? reasonText(t, priority?.reason) ?? t("spot.noValue") : t(priority.value ? "spot.priority.yes" : "spot.priority.no")}</p>
        {exposure?.value ? (
          <>
            <p className="mt-2 text-[11px] text-[#4A5850]">{t("spot.exposure.scope")}</p>
            <dl className="mt-1 grid grid-cols-2 gap-1 text-xs text-[#16231B]">
              {[["exposure.population", "population", "populationReason"], ["exposure.buildings", "buildings", "buildingsReason"]].map(([label, key, reason]) => (
                <React.Fragment key={key}><dt className="text-[#4A5850]">{t(label)}</dt><dd className="font-semibold">{fmt(exposure.value[key], 0) ?? reasonText(t, exposure.value[reason]) ?? t("spot.noValue")}</dd></React.Fragment>
              ))}
            </dl>
            <div className="mt-1"><KindBadge kind={exposure.dataKind} /></div>
          </>
        ) : <p className="mt-2 text-[11px] text-[#4A5850]">{exposure?.reason ?? t("spot.noValue")}</p>}
        {spot.data && <details className="mt-2 text-[11px] text-[#4A5850]"><summary className="cursor-pointer font-medium text-[#1E5B3A]">{t("sources.title")}</summary><pre className="mt-1 whitespace-pre-wrap break-all rounded-lg bg-[#F2F5F1] p-2 text-[#16231B]">{JSON.stringify({ priority: priority?.source, exposure: exposure?.source }, null, 2)}</pre></details>}
      </Section>
      <Caveats data={spot.data} />
    </div>
  );
}
