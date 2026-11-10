import React from 'react';

// The master switch: one button per tier. Each one shows or hides that tier's map layer and
// its panel. A tier with no published data yet is shown disabled (greyed) instead of hidden.
const TIERS = [
  { key: 'flood', label: 'Tier 1', sub: 'Flood', on: 'bg-blue-600 border-blue-400' },
  { key: 'change', label: 'Tier 2', sub: 'Change', on: 'bg-orange-600 border-orange-400' },
  { key: 'motion', label: 'Tier 3', sub: 'Motion', on: 'bg-cyan-700 border-cyan-400' },
  { key: 'route', label: 'Tier 4A', sub: 'Routes', on: 'bg-emerald-700 border-emerald-400' },
  { key: 'scenario', label: 'Tier 4B', sub: 'Future', on: 'bg-violet-700 border-violet-400' },
];

export default function TierBar({ layers, onToggle, disabled = {} }) {
  return (
    <div className="mt-3 grid grid-cols-3 gap-1.5" role="group" aria-label="Tiers">
      {TIERS.map((t) => {
        const isOff = disabled[t.key];
        const isOn = layers[t.key] && !isOff;
        return (
          <button
            key={t.key}
            type="button"
            disabled={isOff}
            aria-pressed={isOn}
            onClick={() => onToggle(t.key)}
            title={isOff ? 'No published data for this tier yet' : ''}
            className={`rounded-lg border px-2 py-1.5 text-left text-xs transition ${
              isOn ? `${t.on} text-white` : 'border-slate-600 bg-slate-800 text-slate-300'
            } ${isOff ? 'cursor-not-allowed opacity-40' : 'hover:brightness-110'}`}
          >
            <div className="font-semibold">{t.label}</div>
            <div className="text-[10px] opacity-80">{t.sub}</div>
          </button>
        );
      })}
    </div>
  );
}
