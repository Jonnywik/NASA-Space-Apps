import React from 'react';
import DataBadge from './DataBadge';
import DataState from './DataState';
import { describeExposure } from '../utils/changeFilter';

const area = (n) => (typeof n === 'number' ? n.toLocaleString(undefined, { maximumFractionDigits: 1 }) : '—');
const count = (n) => (typeof n === 'number' ? n.toLocaleString() : '—');

// Tier 2 card, shown inside the right-hand sidebar under the flood numbers.
//   tier2   result of useTier(...): { state, data, error, isSample }
//   counts  { total, shown } from useChangeLayer
export default function Tier2Panel({ tier2, counts }) {
  const { state, data, error, isSample } = tier2;
  const exposure = data ? describeExposure(data.exposure) : null;
  const warnings = Array.isArray(data?.warnings) ? data.warnings : [];
  const qa = data?.assets?.qa?.url;

  return (
    <section className="mt-4 border-t border-slate-700 pt-4" aria-label="Tier 2 coherence change">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-sm font-bold text-slate-100">Tier 2 · Coherence change</h3>
        {state === 'ready' && (
          <DataBadge dataStatus={data.dataStatus} dataKind={data.dataKind} isSample={isSample} />
        )}
      </div>

      {state !== 'ready' && <DataState state={state} tier="Tier 2" error={error} />}

      {state === 'ready' && (
        <>
          <p className="mb-3 text-xs text-slate-400">
            Before storm: {data.prePair?.join(' → ') ?? '—'}
            <br />
            Across storm: {data.coPair?.join(' → ') ?? '—'}
          </p>

          <div className="rounded-xl border border-amber-500/20 bg-amber-500/10 p-3">
            <div className="mb-1 text-xs font-medium uppercase tracking-wider text-amber-400">
              Area with coherence loss
            </div>
            <div className="text-2xl font-black text-amber-400">
              {area(data.stats?.km2Changed)}{' '}
              <span className="text-sm font-normal text-slate-300">km²</span>
            </div>
            <div className="mt-1 text-[11px] text-slate-400">
              {count(data.stats?.changedPixelCount)} changed pixels · {counts.total} areas
            </div>
          </div>

          <div className="mt-2 rounded-xl border border-slate-700/50 bg-slate-800/80 p-3">
            <div className="mb-1 text-xs text-slate-400">Mapped buildings in change areas</div>
            <div className="text-lg font-bold text-slate-100">{exposure.value}</div>
            <p className="mt-1 text-[11px] text-slate-500">{exposure.note}</p>
          </div>

          <p className="mt-3 text-[11px] italic text-slate-500">
            {data.interpretation ?? 'Coherence decrease: a change indicator, not confirmed damage.'}
          </p>

          {warnings.length > 0 && (
            <details className="mt-2 text-[11px] text-slate-400">
              <summary className="cursor-pointer text-slate-300">Notes and warnings ({warnings.length})</summary>
              <ul className="mt-1 list-disc space-y-1 pl-4">
                {warnings.map((w, i) => (
                  <li key={i}>{typeof w === 'string' ? w : JSON.stringify(w)}</li>
                ))}
              </ul>
            </details>
          )}

          {qa && (
            <a
              href={qa}
              target="_blank"
              rel="noreferrer"
              className="mt-2 inline-block text-[11px] text-blue-300 underline"
            >
              View the quality-check image
            </a>
          )}
        </>
      )}
    </section>
  );
}
