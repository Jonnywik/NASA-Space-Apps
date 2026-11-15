"use client";

import React, { useState } from "react";
import PixelChart from "./PixelChart";
import { Caveats, KindBadge, Section, SourceLine, StateNote, fmt } from "./ui";
import { classifyError, exportPlaceBriefing, getPlaceBriefing, getSpotCheck } from "../utils/api";
import { useLang } from "../utils/LangContext";
import { useReportLimits } from "../utils/LimitsContext";
import { useTier } from "../utils/useTier";

const STATE_GLYPH = { water: "■", dry: "□", nodata: "▨" };

function streamTier(tier, key, wrap) {
  const stream = tier.data?.streams?.[key];
  if (!stream) return tier;
  if (stream.value == null) return { state: "unavailable", data: null, error: { detail: { message: stream.reason } } };
  return { state: "ready", data: { ...stream, ...(wrap ? wrap(stream.value) : stream.value) }, error: null };
}

// U2 spot check: one clicked point, every value with its source, missing values with a reason.
export default function SpotCheck({ point, placeHint, selectedDate, onClose, onCopy, copied, onHelp }) {
  const { t, lang } = useLang();
  const { lon, lat } = point;
  const spot = useTier(() => getSpotCheck(lon, lat), [lon, lat]);
  const briefing = useTier(() => getPlaceBriefing(lon, lat, "fil"), [lon, lat]);
  const [exportState, setExportState] = useState({ state: "idle" });
  const nisar = streamTier(spot, "nisar");
  const locate = streamTier(spot, "place");
  const rain = streamTier(spot, "rainfall", (passes) => ({ passes }));
  const los = streamTier(spot, "motion", (point) => ({ point }));
  const priority = spot.data?.streams?.priority;
  const exposure = spot.data?.streams?.exposure;
  useReportLimits("spot", t("spot.title"), spot.data);

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
    <div data-testid="spot-check">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <h2 className="text-base font-bold text-slate-100" data-testid="spot-title">
            {placeName ? `${placeName}${cityName ? `, ${cityName}` : ""}` : t("spot.title")}
          </h2>
          <p className="text-[11px] text-slate-400">
            {lat.toFixed(5)}°N, {lon.toFixed(5)}°E
          </p>
        </div>
        <div className="flex shrink-0 gap-1.5">
          <button type="button" onClick={onCopy} className="rounded-md border border-sky-400 bg-sky-600/30 px-2 py-1 text-xs font-semibold text-white hover:bg-sky-600/50" data-testid="copy-link">
            {copied ? t("spot.copied") : t("spot.copy")}
          </button>
          <button type="button" onClick={onClose} className="rounded-md border border-slate-500 bg-slate-800 px-2 py-1 text-xs text-slate-100 hover:bg-slate-700" aria-label={t("spot.close")}>
            ✕
          </button>
        </div>
      </div>

      <Section title={t("briefing.title")} kind={briefing.data?.dataKind} testId="place-briefing">
        <StateNote tier={briefing} label={t("briefing.title")} />
        {briefing.data && (
          <>
            <p className="mb-2 text-[11px] text-slate-300">{t("briefing.facts")}</p>
            {briefing.data.translationStatus && <p className="mb-2 text-[11px] text-amber-100" data-testid="translation-review">{t("briefing.review")}</p>}
            <div className="flex flex-wrap gap-2">
              {[["en", "html", "briefing.en"], ["fil", "html", "briefing.fil"], [lang, "csv", "briefing.csv"]].map(([language, format, label]) => (
                <button key={label} type="button" disabled={exportState.state === "loading"} onClick={() => exportBriefing(language, format)} className="rounded-md border border-sky-400 bg-sky-600/30 px-2 py-1.5 text-xs font-semibold text-white hover:bg-sky-600/50 disabled:opacity-50" data-testid={`export-${format}-${language}`}>
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
            <p className="text-xs text-slate-100">
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
            <p className="text-sm text-slate-100" data-testid="flood-count">
              {nd.permanentWater
                ? t("spot.permanent")
                : nd.floodCount == null
                  ? `${t("spot.noCount")}${nd.floodCountReason ? `: ${nd.floodCountReason}` : ""}`
                  : t("spot.floodCount", { k: nd.floodCount, n: nd.validCount ?? "—" })}
            </p>
            {nd.permanentWater && nd.floodCountReason && <p className="text-[11px] text-slate-400">{nd.floodCountReason}</p>}
            {nd.possibleFloodedVegetationPasses > 0 && <p className="text-[11px] text-amber-100">◆ {t("spot.vegPasses", { n: nd.possibleFloodedVegetationPasses })}</p>}
            {nd.cellCenter && <p className="text-[11px] text-slate-400">{t("spot.cell", { lon: nd.cellCenter.lon?.toFixed?.(5), lat: nd.cellCenter.lat?.toFixed?.(5) })}</p>}
            <div className="mt-2 flex flex-wrap gap-1" role="list" aria-label={t("spot.perPass")} data-testid="per-pass">
              {(nd.perPass ?? []).map((p) => (
                <div
                  key={p.date}
                  role="listitem"
                  className={`w-[54px] rounded border px-1 py-0.5 text-center text-[11px] ${p.date === selectedDate ? "border-yellow-300 bg-slate-700" : "border-slate-600 bg-slate-800"}`}
                  title={`${p.date}: ${t(`spot.state.${p.state}`)}${p.possibleFloodedVegetation ? ` · ${t("season.vegetation")}` : ""}${p.reason ? ` · ${p.reason}` : ""}`}
                >
                  <div className="text-sm leading-none" aria-hidden="true">
                    {STATE_GLYPH[p.state] ?? "?"}
                    {p.possibleFloodedVegetation ? "◆" : ""}
                  </div>
                  <div className="text-slate-200">{t(`spot.state.${p.state}.short`)}</div>
                  <div className="text-slate-400">{p.date.slice(5)}</div>
                </div>
              ))}
            </div>
            <p className="mt-1 text-[11px] text-slate-400">
              ■ {t("spot.state.water")} · □ {t("spot.state.dry")} · ▨ {t("spot.state.nodata")} · ◆ {t("season.vegetation")}
            </p>
            <details className="mt-1 text-[11px] text-slate-300">
              <summary className="cursor-pointer">{t("spot.db")}</summary>
              <table className="mt-1 w-full text-left">
                <thead className="text-slate-400">
                  <tr>
                    <th className="font-medium">{t("col.date")}</th>
                    <th className="font-medium">{t("spot.state")}</th>
                    <th className="font-medium">HH dB</th>
                    <th className="font-medium">HV dB</th>
                  </tr>
                </thead>
                <tbody>
                  {(nd.perPass ?? []).map((p) => (
                    <tr key={p.date}>
                      <td>{p.date}</td>
                      <td>
                        {t(`spot.state.${p.state}`)}
                        {p.possibleFloodedVegetation ? " ◆" : ""}
                        {p.reason ? <span className="block text-slate-400">{p.reason}</span> : null}
                      </td>
                      <td>{p.hhDb ?? <span title={t("spot.noValue")}>—</span>}</td>
                      <td>{p.hvDb ?? <span title={t("spot.noValue")}>—</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-1 text-slate-400">{t("spot.noValue")}</p>
            </details>
            {selPass && (
              <p className="mt-1 text-[11px] text-slate-200">
                {t("spot.selected", { date: selectedDate, state: t(`spot.state.${selPass.state}`) })}
              </p>
            )}
            <SourceLine data={nd} className="mt-1" />
            <Caveats data={nd} />
          </>
        )}
      </Section>

      <Section title={t("spot.rain")} sensor="power" kind={rain.data?.dataKind}>
        <p className="mb-1 text-[11px] text-slate-400">{t("spot.rain.cell")}</p>
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
                  <div key={k} className="rounded border border-slate-700 bg-slate-800/70 p-1.5">
                    <div className="text-[11px] text-slate-400">{t(k)}</div>
                    <div className="font-bold text-slate-100" title={v == null ? t("spot.rain.missing") : undefined}>
                      {v == null ? "—" : `${fmt(v)} mm`}
                    </div>
                    {v == null && <div className="text-[10px] text-amber-200">{t("spot.rain.missing")}</div>}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[11px] text-slate-300">{t("spot.rain.nopass")}</p>
            )}
            <details className="mt-1 text-[11px] text-slate-300">
              <summary className="cursor-pointer">{t("spot.rain.all")}</summary>
              <table className="mt-1 w-full text-left">
                <thead className="text-slate-400">
                  <tr>
                    <th className="font-medium">{t("col.date")}</th>
                    <th className="font-medium">{t("spot.rain.same")}</th>
                    <th className="font-medium">3 d</th>
                    <th className="font-medium">7 d</th>
                  </tr>
                </thead>
                <tbody>
                  {rain.data.passes.map((p) => (
                    <tr key={p.date} className={p.date === selectedDate ? "bg-slate-700/60" : ""}>
                      <td>{p.date}</td>
                      <td>{p.sameDayMm ?? "—"}</td>
                      <td>{p.prior3DayMm ?? "—"}</td>
                      <td>{p.prior7DayMm ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>
            {rain.data.windowDefinition && <p className="mt-1 text-[11px] text-slate-400">{rain.data.windowDefinition}</p>}
            <SourceLine data={rain.data} className="mt-1" />
            <Caveats data={rain.data} />
          </>
        )}
        {rain.state === "idle" && <p className="text-[11px] text-slate-400">{t("spot.rain.nopasses")}</p>}
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
        <p className="text-xs text-slate-200">{priority?.value == null ? priority?.reason ?? t("spot.noValue") : t(priority.value ? "spot.priority.yes" : "spot.priority.no")}</p>
        {exposure?.value ? (
          <>
            <p className="mt-2 text-[11px] text-slate-300">{t("spot.exposure.scope")}</p>
            <dl className="mt-1 grid grid-cols-2 gap-1 text-xs text-slate-100">
              {[["exposure.population", "population", "populationReason"], ["exposure.buildings", "buildings", "buildingsReason"]].map(([label, key, reason]) => (
                <React.Fragment key={key}><dt>{t(label)}</dt><dd>{fmt(exposure.value[key], 0) ?? exposure.value[reason] ?? t("spot.noValue")}</dd></React.Fragment>
              ))}
            </dl>
            <KindBadge kind={exposure.dataKind} />
          </>
        ) : <p className="mt-2 text-[11px] text-slate-400">{exposure?.reason ?? t("spot.noValue")}</p>}
        {spot.data && <details className="mt-2 text-[11px] text-slate-300"><summary className="cursor-pointer">{t("sources.title")}</summary><pre className="mt-1 whitespace-pre-wrap break-all">{JSON.stringify({ priority: priority?.source, exposure: exposure?.source }, null, 2)}</pre></details>}
      </Section>
      <Caveats data={spot.data} />
    </div>
  );
}
