'use client';

import React, { useState } from 'react';
import DataBadge from './DataBadge';
import DataState from './DataState';
import { getBriefing } from '../utils/api';
import { sampleBriefing } from '../utils/sampleData';
import { useTier } from '../utils/useTier';

const words = (key) => key.replace(/([A-Z])/g, ' $1').replace(/^./, (c) => c.toUpperCase());

function showValue(v) {
  if (v == null) return '—';
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : v.toFixed(1);
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
}

// Plain-language summary of the Tier 3 product for the selected event.
// The backend writes it from a fixed template plus the measured numbers (no AI model), so the
// card says so, and shows the exact numbers underneath.
export default function BriefingCard({ eventId }) {
  const [refreshKey, setRefreshKey] = useState(0);
  const briefing = useTier(eventId ? () => getBriefing(eventId) : null, [eventId, refreshKey], {
    sampleData: sampleBriefing,
  });
  const { state, data, error, isSample } = briefing;
  const facts = data?.facts && typeof data.facts === 'object' ? Object.entries(data.facts) : [];

  return (
    <section className="mt-4 border-t border-slate-700 pt-4" aria-label="Briefing">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-sm font-bold text-slate-100">Briefing</h3>
        {state === 'ready' && <DataBadge dataKind={data.dataKind} isSample={isSample} />}
      </div>

      {state !== 'ready' && <DataState state={state} tier="Briefing" error={error} />}

      {state === 'ready' && (
        <>
          <p className="text-sm leading-relaxed text-slate-200">{data.text}</p>

          {facts.length > 0 && (
            <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-1 text-[11px]">
              {facts.map(([k, v]) => (
                <React.Fragment key={k}>
                  <dt className="text-slate-400">{words(k)}</dt>
                  <dd className="text-right text-slate-200">{showValue(v)}</dd>
                </React.Fragment>
              ))}
            </dl>
          )}

          <p className="mt-3 text-[11px] italic text-slate-500">
            Written from a fixed template and the numbers above, not by an AI model. Template{' '}
            {data.templateVersion ?? '—'}.
          </p>
          <button
            type="button"
            onClick={() => setRefreshKey((n) => n + 1)}
            className="mt-2 text-[11px] text-blue-300 underline"
          >
            Reload briefing
          </button>
        </>
      )}
    </section>
  );
}
