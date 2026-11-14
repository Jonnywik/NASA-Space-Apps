// frontend/components/ModelCard.jsx
import React from "react";

// "What this is / is not": a plain-language model card for Tiers 2, 3, and 4. Collapsed by default.
const CARDS = {
  change: {
    title: "About coherence change (Tier 2)",
    is: [
      "Places where radar echo similarity (coherence) dropped sharply across the storm window compared to a pre-storm pair.",
      "A surface-change indicator filtered to remove tiny isolated radar speckle.",
    ],
    isNot: [
      "Not confirmed building damage or storm causation.",
      "Low coherence in dense vegetation or water is normal in the tropics and is excluded where baseline coherence was already low.",
    ],
    sources:
      "Sentinel-1 C-band InSAR coherence pairs (ASF HyP3) and OpenStreetMap building footprints (ODbL).",
  },
  motion: {
    title: "About ground motion & sensors (Tier 3)",
    is: [
      "Line-of-sight (LOS) surface displacement (mm) and annual rate (mm/yr) solved across multiple radar passes relative to a local reference area.",
      "Positive values mean movement away from the satellite (which includes ground sinking); negative values mean movement toward the satellite.",
    ],
    isNot: [
      "Never straight-down vertical sinking alone — radar measures along its angled line of sight.",
      "Optical satellites see cloud tops during typhoons; C-band (Sentinel-1) bounces off dense tree canopy; L-band (NISAR, available from 17 June 2026) penetrates deeper into vegetation.",
    ],
    sources:
      "Sentinel-1 / JPL ARIA GUNW interferograms and NISAR L-band GUNW (where dates after 17 June 2026 apply).",
  },
  projection: {
    title: "About this projection",
    is: [
      "A what-if: it carries today's measured ground movement forward in a straight line and compares it with a water level.",
      "Shown only for years the data can support, with its assumptions listed.",
    ],
    isNot: [
      "Not a prediction of what will happen, and not a forecast of any storm.",
      "Not an observed flood. Observed results live in Tiers 1 to 3.",
      "Not a complete uncertainty range: only the uncertainty terms from the data sources are shown.",
    ],
    sources:
      "Ground motion from radar (Tier 3), elevation and water-level inputs (reviewed scenario).",
  },
  route: {
    title: "About these routes",
    is: [
      "Two routes between your pins on the road network: the shortest, and one that avoids mapped flood and prefers to avoid radar-change areas.",
      "Hazard score = 3 × km through mapped flood + 1 × km through change areas. This weighting is our own simple choice, not a standard.",
    ],
    isNot: [
      "Hazard-aware does not mean safe. It only avoids what was mapped, on the dates shown.",
      "Not live traffic, not road-closure data, and not water depth.",
      "A coherence-change area is a radar signal, not confirmed damage.",
    ],
    sources:
      "OpenStreetMap roads (ODbL, © OpenStreetMap contributors) and the Tier 1 and Tier 2 hazard layers.",
  },
};

export default function ModelCard({ kind }) {
  const c = CARDS[kind];
  if (!c) return null;
  return (
    <details className="mt-3 rounded-lg border border-slate-700 bg-slate-800/40 p-2 text-[11px] text-slate-300">
      <summary className="cursor-pointer font-medium text-slate-200">
        {c.title}
      </summary>
      <div className="mt-2 font-semibold text-emerald-300">What it is</div>
      <ul className="list-disc space-y-1 pl-4">
        {c.is.map((t) => (
          <li key={t}>{t}</li>
        ))}
      </ul>
      <div className="mt-2 font-semibold text-rose-300">What it is not</div>
      <ul className="list-disc space-y-1 pl-4">
        {c.isNot.map((t) => (
          <li key={t}>{t}</li>
        ))}
      </ul>
      <p className="mt-2 text-slate-400">Data: {c.sources}</p>
    </details>
  );
}
