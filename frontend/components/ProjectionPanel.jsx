'use client';

import React, { useEffect } from 'react';
import DataBadge from './DataBadge';
import DataState from './DataState';
import ModelCard from './ModelCard';

const FIRST = 2026;
const LAST = 2035;

const list = (v) => {
  if (!v) return [];
  if (Array.isArray(v)) return v.map((x) => (typeof x === 'string' ? x : JSON.stringify(x)));
  if (typeof v === 'object') return Object.entries(v).map(([k, x]) => `${k}: ${typeof x === 'string' ? x : JSON.stringify(x)}`);
  return [String(v)];
};
const pick = (m, k) => m?.[k] ?? m?.waterExposure?.[k] ?? null;
const num = (n, d = 1) => (typeof n === 'number' ? n.toLocaleString(undefined, { maximumFractionDigits: d }) : '—');

// Tier 4B: year slider, a loud PROJECTION label, the assumptions, and what the numbers are not.
//   proj    result of useProjection: { tier, geojson, areaKm2 }
export default function ProjectionPanel({ proj, year, setYear, demo, onDemo }) {
  const { tier, areaKm2 } = proj;
  const { state, data, error } = tier;
  const supported = data?.supportedYears ?? error?.detail?.supportedYears ?? null;

  // asked for a year the model does not support: jump to the first supported year
  useEffect(() => {
    const s = error?.detail?.supportedYears;
    if (Array.isArray(s) && s.length && !s.includes(year)) setYear(s[0]);
  }, [error, year, setYear]);

  const metric = data?.annualMetric;
  return (
    <section className="mt-4 border-t border-slate-700 pt-4" aria-label="Future scenario">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-sm font-bold text-slate-100">Future · Scenario</h3>
        {state === 'ready' && <DataBadge dataStatus={data.dataStatus} dataKind={data.dataKind} isSample={demo} />}
      </div>

      <div className="rounded-lg border-2 border-violet-400/60 bg-violet-500/10 px-3 py-2">
        <div className="text-xs font-black uppercase tracking-[0.2em] text-violet-300">Projection</div>
        <div className="text-[11px] text-slate-300">A conditional what-if, not a prediction.</div>
      </div>

      <div className="mt-3">
        <label htmlFor="proj-year" className="flex items-baseline justify-between text-xs text-slate-300">
          <span>Year</span>
          <span className="text-lg font-black text-violet-300">{year}</span>
        </label>
        <input
          id="proj-year"
          type="range"
          min={FIRST}
          max={LAST}
          step={1}
          value={year}
          onChange={(e) => setYear(parseInt(e.target.value, 10))}
          className="mt-1 w-full accent-violet-400"
        />
        <div className="flex justify-between text-[10px] text-slate-500">
          <span>{FIRST}</span>
          <span>{LAST}</span>
        </div>
        {supported && !supported.includes(year) && (
          <p className="mt-1 text-[11px] text-amber-300">Only {supported.join(', ')} are supported by this model.</p>
        )}
      </div>

      {state !== 'ready' && <div className="mt-3"><DataState state={state} tier="Future" error={error} onDemo={demo ? null : onDemo} /></div>}

      {state === 'ready' && (
        <>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <div className="rounded-xl border border-slate-700/50 bg-slate-800/80 p-3">
              <div className="mb-1 text-xs text-slate-400">Potential water-exposed area</div>
              <div className="text-lg font-bold text-violet-300">{areaKm2 == null ? '—' : `${num(areaKm2)} km²`}</div>
            </div>
            <div className="rounded-xl border border-slate-700/50 bg-slate-800/80 p-3">
              <div className="mb-1 text-xs text-slate-400">Median ground movement</div>
              <div className="text-lg font-bold text-slate-100">
                {num(pick(metric, 'medianLosMm'), 0)} <span className="text-xs font-normal">mm</span>
              </div>
            </div>
          </div>
          <p className="mt-1 text-[11px] text-slate-500">
            Baseline {data.baselineEpoch ?? '—'}. Movement is along the satellite’s line of sight, not straight down.
          </p>

          {list(data.assumptions).length > 0 && (
            <details className="mt-2 text-[11px] text-slate-400">
              <summary className="cursor-pointer text-slate-300">Assumptions ({list(data.assumptions).length})</summary>
              <ul className="mt-1 list-disc space-y-1 pl-4">
                {list(data.assumptions).map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ul>
            </details>
          )}
          <p className="mt-2 text-[11px] italic text-slate-500">
            Confidence: {data.uncertainty?.reason ?? 'Uncertainty is not fully quantified. Treat as a scenario, not an expectation.'}
          </p>
        </>
      )}
      <ModelCard kind="projection" />
    </section>
  );
}
