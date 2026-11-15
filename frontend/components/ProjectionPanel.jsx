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
    <section className="mt-3 border-t border-[#DCE3DB] pt-3 text-[#16231B]" aria-label="Future scenario">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="font-serif text-sm font-semibold text-[#16231B]">Future · Scenario</h3>
        {state === 'ready' && <DataBadge dataStatus={data.dataStatus} dataKind={data.dataKind} isSample={demo} />}
      </div>

      <div className="rounded-xl border border-dashed border-[#6B5A9E] bg-[#ECE8F4] px-3 py-2">
        <div className="text-[11px] font-bold uppercase tracking-[0.14em] text-[#4E3F80]">Projection</div>
        <div className="text-[12px] text-[#4A5850]">A conditional what-if, not a prediction.</div>
      </div>

      <div className="mt-3">
        <label htmlFor="proj-year" className="flex items-baseline justify-between text-xs text-[#4A5850]">
          <span>Year</span>
          <span className="text-lg font-bold text-[#6B5A9E]">{year}</span>
        </label>
        <input
          id="proj-year"
          type="range"
          min={FIRST}
          max={LAST}
          step={1}
          value={year}
          onChange={(e) => setYear(parseInt(e.target.value, 10))}
          className="mt-1 w-full accent-[#6B5A9E]"
        />
        <div className="flex justify-between text-[10px] text-[#4A5850]">
          <span>{FIRST}</span>
          <span>{LAST}</span>
        </div>
        {supported && !supported.includes(year) && (
          <p className="mt-1 text-[11px] text-[#7A5B00]">Only {supported.join(', ')} are supported by this model.</p>
        )}
      </div>

      {state !== 'ready' && <div className="mt-3"><DataState state={state} tier="Future" error={error} onDemo={demo ? null : onDemo} /></div>}

      {state === 'ready' && (
        <>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <div className="rounded-xl border border-[#DCE3DB] bg-[#F2F5F1] p-3">
              <div className="mb-1 text-xs text-[#4A5850]">Potential water-exposed area</div>
              <div className="text-lg font-bold text-[#6B5A9E]">{areaKm2 == null ? '—' : `${num(areaKm2)} km²`}</div>
            </div>
            <div className="rounded-xl border border-[#DCE3DB] bg-[#F2F5F1] p-3">
              <div className="mb-1 text-xs text-[#4A5850]">Median ground movement</div>
              <div className="text-lg font-bold text-[#16231B]">
                {num(pick(metric, 'medianLosMm'), 0)} <span className="text-xs font-normal text-[#4A5850]">mm</span>
              </div>
            </div>
          </div>
          <p className="mt-1 text-[11px] text-[#4A5850]">
            Baseline {data.baselineEpoch ?? '—'}. Movement is along the satellite’s line of sight, not straight down.
          </p>

          {list(data.assumptions).length > 0 && (
            <details className="mt-2 text-[11px] text-[#4A5850]">
              <summary className="cursor-pointer font-medium text-[#16231B]">Assumptions ({list(data.assumptions).length})</summary>
              <ul className="mt-1 list-disc space-y-1 pl-4">
                {list(data.assumptions).map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ul>
            </details>
          )}
          <p className="mt-2 text-[11px] text-[#4A5850]">
            Confidence: {data.uncertainty?.reason ?? 'Uncertainty is not fully quantified. Treat as a scenario, not an expectation.'}
          </p>
        </>
      )}
      <ModelCard kind="projection" />
    </section>
  );
}
