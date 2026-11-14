"use client";

import React from "react";
import PixelChart from "./PixelChart";
import { Caveats, Section, SourceLine, StateNote, fmt, reasonFor } from "./ui";
import { AREA_ID, getGroundMotionPoint, getNisarPoint, getPassRainfall, locatePlace } from "../utils/api";
import { useLang } from "../utils/LangContext";
import { useReportLimits } from "../utils/LimitsContext";
import { useTier } from "../utils/useTier";

const STATE_GLYPH = { water: "■", dry: "□", nodata: "▨" };

// U2 spot check: one clicked point, every value with its source, missing values with a reason.
export default function SpotCheck({ point, placeHint, passDates, selectedDate, onClose, onCopy, copied, onHelp }) {
  const { t } = useLang();
  const { lon, lat } = point;
  const nisar = useTier(() => getNisarPoint(AREA_ID, lon, lat), [lon, lat]);
  const locate = useTier(() => locatePlace(lon, lat), [lon, lat]);
  const rain = useTier(passDates?.length ? () => getPassRainfall(AREA_ID, passDates) : null, [passDates?.join(",")]);
  const los = useTier(() => getGroundMotionPoint(AREA_ID, lon, lat), [lon, lat]);
  useReportLimits("spot-nisar", t("spot.nisar"), nisar.data);
  useReportLimits("spot-locate", t("spot.place"), locate.data);
  useReportLimits("spot-rain", t("spot.rain"), rain.data);
  useReportLimits("spot-los", t("spot.los"), los.data);

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
              {nd.permanentWater ? t("spot.permanent") : t("spot.floodCount", { k: nd.floodCount ?? "—", n: nd.validCount ?? "—" })}
            </p>
            {nd.cellCenter && <p className="text-[11px] text-slate-400">{t("spot.cell", { lon: nd.cellCenter.lon?.toFixed?.(5), lat: nd.cellCenter.lat?.toFixed?.(5) })}</p>}
            <div className="mt-2 flex flex-wrap gap-1" role="list" aria-label={t("spot.perPass")} data-testid="per-pass">
              {(nd.perPass ?? []).map((p) => (
                <div
                  key={p.date}
                  role="listitem"
                  className={`w-[54px] rounded border px-1 py-0.5 text-center text-[11px] ${p.date === selectedDate ? "border-yellow-300 bg-slate-700" : "border-slate-600 bg-slate-800"}`}
                  title={`${p.date}: ${t(`spot.state.${p.state}`)}`}
                >
                  <div className="text-sm leading-none" aria-hidden="true">{STATE_GLYPH[p.state] ?? "?"}</div>
                  <div className="text-slate-200">{t(`spot.state.${p.state}.short`)}</div>
                  <div className="text-slate-400">{p.date.slice(5)}</div>
                </div>
              ))}
            </div>
            <p className="mt-1 text-[11px] text-slate-400">■ {t("spot.state.water")} · □ {t("spot.state.dry")} · ▨ {t("spot.state.nodata")}</p>
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
                      <td>{t(`spot.state.${p.state}`)}</td>
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
        {los.state !== "ready" && los.state !== "loading" && <p className="mt-1 text-[11px] text-slate-400">{reasonFor(los, t)}</p>}
      </Section>
    </div>
  );
}
