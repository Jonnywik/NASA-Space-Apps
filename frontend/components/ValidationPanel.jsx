"use client";

import { Caveats, Section, StateNote, Stat, fmt } from "./ui";
import { useLang } from "../utils/LangContext";

export default function ValidationPanel({ tier }) {
  const { t } = useLang();
  const data = tier.data;
  return (
    <Section title={t("validation.title")} kind={data?.dataKind} testId="validation-panel">
      <p className="mb-2 text-[11px] text-slate-300">{t("validation.lead")}</p>
      <StateNote tier={tier} label={t("validation.title")} />
      {data && (
        <>
          <div className="grid grid-cols-2 gap-2">
            <Stat label={t("validation.pixels")} value={fmt(data.agreement?.validPixels, 0)} />
            <Stat label="Intersection over union" value={fmt(data.agreement?.iou, 3)} />
            <Stat label="F1" value={fmt(data.agreement?.f1, 3)} />
            <Stat label={t("validation.accuracy")} value={fmt(data.agreement?.overallAgreement, 3)} />
          </div>
          {Object.entries(data.source ?? {}).map(([key, source]) => (
            <p key={key} className="mt-2 text-[11px] text-slate-400">
              {key}: <a href={source.url} target="_blank" rel="noreferrer" className="text-sky-300 underline">{source.source}</a> · {source.date}
            </p>
          ))}
          <Caveats data={data} />
        </>
      )}
    </Section>
  );
}
