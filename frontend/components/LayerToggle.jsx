// frontend/components/LayerToggle.jsx
import React from "react";
import {
  AREA_SLIDER_MAX,
  CHANGE_CATEGORIES,
  LOSS_BANDS,
} from "../utils/changeFilter";

export default function LayerToggle({
  visible,
  strength,
  counts,
  minArea,
  onMinArea,
  activeCategories,
  onToggleCategory,
}) {
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
      <label
        htmlFor="area-min"
        className="mt-2 block text-[11px] text-slate-400"
      >
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
      <div className="mt-1 text-[11px] text-slate-500">
        Showing {counts.shown} of {counts.total} areas
      </div>

      {counts.hasCategories && activeCategories && onToggleCategory ? (
        <div className="mt-2">
          <div className="mb-1 text-[11px] font-medium text-slate-300">
            Filter by likely context (land cover + flood overlap)
          </div>
          <div className="space-y-1">
            {CHANGE_CATEGORIES.map((c) => {
              const checked = Boolean(activeCategories[c.key]);
              return (
                <button
                  key={c.key}
                  type="button"
                  onClick={() => onToggleCategory(c.key)}
                  aria-pressed={checked}
                  className={`flex min-h-[36px] w-full items-center justify-between rounded-md border px-2 py-1 text-left text-[11px] transition ${
                    checked
                      ? "border-slate-600 bg-slate-800 text-slate-200"
                      : "border-slate-800 bg-slate-900/50 text-slate-500 line-through"
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <span
                      className="inline-block h-2.5 w-2.5 rounded-sm"
                      style={{ background: c.color }}
                    />
                    {c.label}
                  </span>
                  <span className="text-[10px]">
                    {checked ? "Shown" : "Hidden"}
                  </span>
                </button>
              );
            })}
          </div>
          <p className="mt-1 text-[10px] italic text-slate-500">
            Categories are context from land cover/flood overlap, not confirmed
            radar causes.
          </p>
        </div>
      ) : (
        <>
          <ul className="mt-1.5 space-y-0.5">
            {LOSS_BANDS.map((b) => (
              <li
                key={b.label}
                className="flex items-center gap-1.5 text-[11px] text-slate-400"
              >
                <span
                  className="inline-block h-2.5 w-2.5 rounded-sm"
                  style={{ background: b.color }}
                />
                {b.label}
              </li>
            ))}
          </ul>
          <p className="mt-1 text-[10px] italic text-slate-500">
            Colour = strength of coherence loss, not type of change.
          </p>
        </>
      )}
    </div>
  );
}
