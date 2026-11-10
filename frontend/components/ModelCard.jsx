import React from 'react';

// "What this is / is not": a plain-language model card for Tier 4. Collapsed by default.
const CARDS = {
  projection: {
    title: 'About this projection',
    is: [
      'A what-if: it carries today’s measured ground movement forward in a straight line and compares it with a water level.',
      'Shown only for years the data can support, with its assumptions listed.',
    ],
    isNot: [
      'Not a prediction of what will happen, and not a forecast of any storm.',
      'Not an observed flood. Observed results live in Tiers 1 to 3.',
      'Not a complete uncertainty range: only the uncertainty terms from the data sources are shown.',
    ],
    sources: 'Ground motion from radar (Tier 3), elevation and water-level inputs (reviewed scenario).',
  },
  route: {
    title: 'About these routes',
    is: [
      'Two routes between your pins on the road network: the shortest, and one that avoids mapped flood and prefers to avoid radar-change areas.',
      'Hazard score = 3 × km through mapped flood + 1 × km through change areas. This weighting is our own simple choice, not a standard.',
    ],
    isNot: [
      'Hazard-aware does not mean safe. It only avoids what was mapped, on the dates shown.',
      'Not live traffic, not road-closure data, and not water depth.',
      'A coherence-change area is a radar signal, not confirmed damage.',
    ],
    sources: 'OpenStreetMap roads (ODbL, © OpenStreetMap contributors) and the Tier 1 and Tier 2 hazard layers.',
  },
};

export default function ModelCard({ kind }) {
  const c = CARDS[kind];
  if (!c) return null;
  return (
    <details className="mt-3 rounded-lg border border-slate-700 bg-slate-800/40 p-2 text-[11px] text-slate-300">
      <summary className="cursor-pointer font-medium text-slate-200">{c.title}</summary>
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
