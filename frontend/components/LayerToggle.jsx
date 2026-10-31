import React from 'react';

// Layer switches + the "strength of change" filter. Sits in the top-left card.
//   layers        { flood: bool, change: bool }
//   onToggle(key) flip one layer
//   changeReady   false = no Tier 2 data (switch is disabled)
//   strength      { value, min, max, onChange } or null
//   counts        { total, shown }
export default function LayerToggle({ layers, onToggle, changeReady, strength, counts }) {
  return (
    <div className="mt-3 border-t border-slate-700 pt-3">
      <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">Layers</div>

      <label className="mt-2 flex cursor-pointer items-center gap-2 text-xs text-slate-200">
        <input type="checkbox" checked={layers.flood} onChange={() => onToggle('flood')} />
        <span className="inline-block h-3 w-3 rounded-sm bg-red-500" />
        Tier 1 · Flood (before / after)
      </label>

      <label
        className={`mt-1.5 flex items-center gap-2 text-xs ${
          changeReady ? 'cursor-pointer text-slate-200' : 'cursor-not-allowed text-slate-500'
        }`}
        title={changeReady ? '' : 'No published Tier 2 data for this event yet'}
      >
        <input
          type="checkbox"
          checked={changeReady && layers.change}
          disabled={!changeReady}
          onChange={() => onToggle('change')}
        />
        <span className="inline-block h-3 w-3 rounded-sm bg-amber-500" />
        Tier 2 · Coherence change
      </label>

      {changeReady && layers.change && strength && (
        <div className="mt-2 pl-6">
          <label htmlFor="loss-min" className="block text-[11px] text-slate-400">
            Only changes with coherence loss ≥ {strength.value.toFixed(2)}
          </label>
          <input
            id="loss-min"
            type="range"
            min={strength.min}
            max={strength.max}
            step={0.05}
            value={strength.value}
            onChange={(e) => strength.onChange(parseFloat(e.target.value))}
            className="mt-1 w-full"
          />
          <div className="text-[11px] text-slate-500">
            Showing {counts.shown} of {counts.total} areas
          </div>
        </div>
      )}
    </div>
  );
}
