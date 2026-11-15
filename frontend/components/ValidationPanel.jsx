"use client";

import { Caveats, Section, StateNote, Stat, fmt } from "./ui";
import { useLang } from "../utils/LangContext";

export default function ValidationPanel({ tier }) {
  const { t } = useLang();
  const data = tier.data;
  const isDemo = data?.dataKind === "synthetic";
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
    </Section>
  );
}
