import React from 'react';

// Small label that says what kind of data a panel is showing.
// Always render it next to Tier 2 / Tier 3 numbers: honesty is part of our pitch.
export default function DataBadge({ dataStatus, dataKind, isSample = false }) {
  let label;
  let tone;
  if (isSample || dataStatus === 'synthetic' || dataKind === 'synthetic') {
    label = 'SAMPLE · not real data';
    tone = 'border-amber-500/40 bg-amber-500/15 text-amber-300';
  } else if (dataStatus === 'validated') {
    label = 'Reviewed data';
    tone = 'border-emerald-500/40 bg-emerald-500/15 text-emerald-300';
  } else {
    label = dataStatus ? String(dataStatus) : 'Unknown status';
    tone = 'border-slate-500/40 bg-slate-500/15 text-slate-300';
  }
  return (
    <span className={`inline-block rounded-full border px-2.5 py-0.5 text-xs font-semibold ${tone}`}>
      {label}
    </span>
  );
}
