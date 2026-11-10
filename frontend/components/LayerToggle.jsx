import React from 'react';
import { AREA_SLIDER_MAX, LOSS_BANDS } from '../utils/changeFilter';

// Tier 2 details (strength filter + colour legend). Shown only while Tier 2 is switched on.
//   strength  { value, min, max, onChange }
//   counts    { total, shown }
export default function LayerToggle({ visible, strength, counts, minArea, onMinArea }) {
  if (!visible) return null;
  return (
    <div className="mt-3 border-t border-slate-700 pt-3">
      <label htmlFor="loss-min" className="block text-[11px] text-slate-400">
        Tier 2 strength filter: coherence loss ≥ {strength.value.toFixed(2)}
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
      <label htmlFor="area-min" className="mt-2 block text-[11px] text-slate-400">
        Hide areas smaller than {minArea.toFixed(3)} km² (display filter only)
      </label>
      <input
        id="area-min"
        type="range"
        min={0}
        max={AREA_SLIDER_MAX}
        step={0.005}
        value={minArea}
        onChange={(e) => onMinArea(parseFloat(e.target.value))}
        className="mt-1 w-full"
      />
      <div className="text-[11px] text-slate-500">
        Showing {counts.shown} of {counts.total} areas
      </div>
      <ul className="mt-1.5 space-y-0.5">
        {LOSS_BANDS.map((b) => (
          <li key={b.label} className="flex items-center gap-1.5 text-[11px] text-slate-400">
            <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: b.color }} />
            {b.label}
          </li>
        ))}
      </ul>
      <p className="mt-1 text-[10px] italic text-slate-500">Colour = strength of coherence loss, not type of change.</p>
    </div>
  );
}