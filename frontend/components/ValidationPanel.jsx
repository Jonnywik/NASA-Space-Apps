"use client";

import { Caveats, Section, StateNote, Stat, fmt } from "./ui";
import { useLang } from "../utils/LangContext";

export default function ValidationPanel({ tier, robustness, crossTrack }) {
  const { t } = useLang();
  const data = tier.data;
  const isDemo = data?.dataKind === "synthetic";
  const rob = robustness?.data;
  const xt = crossTrack?.data;
  return (
    <Section title={t("validation.title")} kind={data?.dataKind} testId="validation-panel">
      <p className="mb-2 text-[12px] text-[#4A5850]">{t("validation.lead")}</p>
      <StateNote tier={tier} label={t("validation.title")} />
      {data && (
        <>
          <div className="grid grid-cols-2 gap-2">
            <Stat compact isDemo={isDemo} label={t("validation.pixels")} value={fmt(data.agreement?.validPixels, 0)} />
            <Stat compact isDemo={isDemo} label="Intersection over union" value={fmt(data.agreement?.iou, 3)} />
            <Stat compact isDemo={isDemo} label="F1" value={fmt(data.agreement?.f1, 3)} />
            <Stat compact isDemo={isDemo} label={t("validation.accuracy")} value={fmt(data.agreement?.overallAgreement, 3)} />
          </div>
          {Object.entries(data.source ?? {}).map(([key, source]) => (
            <p key={key} className="mt-2 text-[11px] text-[#4A5850]">
              {key}: <a href={source.url} target="_blank" rel="noreferrer" className="font-medium text-[#1E5B3A] underline">{source.source}</a> · {source.date}
            </p>
          ))}
          <Caveats data={data} />
        </>
      )}
      {xt && (
        <div className="mt-3 flex flex-col gap-2" data-testid="cross-track-block">
          <h4 className="m-0 text-[13px] font-semibold text-[#16231B]">{t("xtrack.title")}</h4>
          <p className="m-0 text-[12px] text-[#4A5850]">{t("xtrack.lead")}</p>
          <div className="grid grid-cols-2 gap-2">
            <Stat compact label={t("xtrack.sameSpots")} value={`${Math.round((xt.geometryAgreement?.shareAscendingNearDescending ?? 0) * 100)}%`} />
            <Stat compact label={t("xtrack.chance")} value={`${((xt.geometryAgreement?.chanceShareMean ?? 0) * 100).toFixed(2)}%`} />
            <Stat compact label={t("xtrack.descRhythm")} value={`${fmt(xt.descending?.halfOrMoreKm2, 2)} km²`} />
            <Stat compact label={t("xtrack.ascRhythm")} value={`${fmt(xt.ascending?.halfOrMoreKm2, 2)} km²`} />
          </div>
          {xt.operaSummary && (
            <>
              <p className="m-0 text-[12px] font-medium text-[#16231B]">{t("xtrack.operaTitle", { n: xt.operaSummary.n })}</p>
              <div className="grid grid-cols-2 gap-2">
                <Stat compact label="F1 (median)" value={fmt(xt.operaSummary.medianF1, 2)} />
                <Stat compact label="IoU (median)" value={fmt(xt.operaSummary.medianIoU, 2)} />
                <Stat compact label={t("xtrack.precision")} value={fmt(xt.operaSummary.medianPrecision, 2)} />
                <Stat compact label={t("xtrack.recall")} value={fmt(xt.operaSummary.medianRecall, 2)} />
              </div>
            </>
          )}
          {xt.descending?.rainCorrelation && (
            <p className="m-0 text-[12px] text-[#4A5850]">
              {t(xt.rainLinkReplicated ? "xtrack.rainYes" : "xtrack.rain", {
                rho: fmt(xt.descending.rainCorrelation.rho, 2),
                p: fmt(xt.descending.rainCorrelation.pPermutation, 2),
                bright: fmt(xt.descending.brighteningCorrelations?.[0]?.rho, 2),
                bp: fmt(xt.descending.brighteningCorrelations?.[0]?.pPermutation, 2),
              })}
            </p>
          )}
          <p className="m-0 text-[12px] text-[#4A5850]">{t("xtrack.builtUp", { km2: fmt(xt.geometryAgreement?.builtUpOverlapKm2, 2) })}</p>
          <Caveats data={xt} />
        </div>
      )}
      {rob && (
        <div className="mt-3 flex flex-col gap-2" data-testid="robustness-block">
          <h4 className="m-0 text-[13px] font-semibold text-[#16231B]">{t("robust.title")}</h4>
          <p className="m-0 text-[12px] text-[#4A5850]">{t("robust.lead")}</p>
          <ul className="m-0 flex list-none flex-col gap-1.5 p-0">
            {(rob.correlations ?? []).map((c) => (
              <li key={c.label} className="rounded-xl border border-[#DCE3DB] bg-white px-3 py-2 text-[12px] text-[#16231B]">
                <div className="font-medium">{c.label}</div>
                <div className="tabular-nums text-[#4A5850]">
                  ρ {fmt(c.rho, 2)} · p {c.pPermutation < 0.001 ? "< 0.001" : fmt(c.pPermutation, 3)} · {t("robust.ci")} {fmt(c.bootstrap95?.[0], 2)} {t("robust.to")} {fmt(c.bootstrap95?.[1], 2)} · {c.signHoldsWithoutAnyOnePass ? t("robust.looHolds") : t("robust.looFails")}
                </div>
              </li>
            ))}
            {rob.rainResponseField && (
              <li className="rounded-xl border border-[#DCE3DB] bg-white px-3 py-2 text-[12px] text-[#16231B]">
                <div className="font-medium">{t("robust.fieldTitle")}</div>
                <div className="tabular-nums text-[#4A5850]">
                  {t("robust.fieldBody", {
                    obs: Math.round((rob.rainResponseField.observedShareAbove05 ?? 0) * 100),
                    chance: Math.round((rob.rainResponseField.nullShareAbove05_95 ?? 0) * 100),
                  })}
                </div>
              </li>
            )}
            {rob.coherenceLoss && (
              <li className="rounded-xl border border-[#E69F00] bg-[#FFF7E6] px-3 py-2 text-[12px] text-[#16231B]">
                <div className="font-medium">{t("robust.cohTitle")}</div>
                <div className="tabular-nums text-[#4A5850]">
                  {t("robust.cohBody", {
                    naive: fmt(rob.coherenceLoss.naiveKm2DropOver03, 1),
                    corrected: fmt(rob.coherenceLoss.intervalCorrectedKm2DropOver03, 2),
                    calmMax: fmt(Math.max(...(rob.coherenceLoss.calmPairsKm2DropOver03 ?? [0])), 1),
                  })}
                </div>
              </li>
            )}
          </ul>
        </div>
      )}
    </Section>
  );
}
