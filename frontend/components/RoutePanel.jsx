'use client';

import React from 'react';
import DataBadge from './DataBadge';
import DataState from './DataState';
import ModelCard from './ModelCard';
import RouteProfile from './RouteProfile';
import { DEMO_PINS } from '../utils/routeEngine';

const km = (n) => (typeof n === 'number' ? `${n.toFixed(1)} km` : '—');

const RELATION = {
  detour: { text: 'The hazard-aware route goes around everything mapped.', tone: 'text-emerald-300' },
  reduced: { text: 'The hazard-aware route reduces exposure but still touches mapped hazard.', tone: 'text-amber-300' },
  identical: { text: 'Both routes are the same: the shortest route already avoids mapped flood.', tone: 'text-slate-200' },
  no_safe_route: { text: 'No route avoids all mapped flood. Only the shortest route is shown, and it is not safe.', tone: 'text-red-300' },
};

function Row({ label, a, b }) {
  return (
    <tr className="border-t border-slate-700/60">
      <td className="py-1 pr-2 text-slate-400">{label}</td>
      <td className="py-1 pr-2 text-right text-slate-200">{a}</td>
      <td className="py-1 text-right text-emerald-300">{b}</td>
    </tr>
  );
}

// Tier 4A: pins, two routes, a plain metric comparison, a profile chart and a template briefing.
//   pins  from useRoutePins; routeTier from useTier; demo / onDemo for the explicit DEMO switch
export default function RoutePanel({ pins, routeTier, demo, onDemo, hasEvent }) {
  const { state, data, error } = routeTier;
  const rel = data ? RELATION[data.relation] : null;
  const s = data?.shortest;
  const g = data?.safe;
  const score = (r) => (r ? r.hazard.score.toFixed(1) : '—');

  return (
    <section className="mt-4 border-t border-slate-700 pt-4" aria-label="Route planning">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-sm font-bold text-slate-100">Routes · Vehicle</h3>
        {state === 'ready' && <DataBadge dataStatus={data.dataStatus} dataKind={data.dataKind} isSample={demo} />}
      </div>

      <p className="text-xs text-slate-400">
        {!pins.from && 'Click the map to place the start (A).'}
        {pins.from && !pins.to && 'Now click the map to place the end (B).'}
        {pins.from && pins.to && 'Drag A or B to change the trip.'}
      </p>

      <div className="mt-2 flex flex-wrap gap-2 text-[11px]">
        <button type="button" onClick={() => pins.setMode('from')} className={`rounded-md border px-2 py-1 ${pins.mode === 'from' ? 'border-blue-400 bg-blue-600 text-white' : 'border-slate-600 text-slate-300'}`}>
          Set start A
        </button>
        <button type="button" onClick={() => pins.setMode('to')} className={`rounded-md border px-2 py-1 ${pins.mode === 'to' ? 'border-red-400 bg-red-600 text-white' : 'border-slate-600 text-slate-300'}`}>
          Set end B
        </button>
        {demo && (
          <button type="button" onClick={() => pins.setBoth(DEMO_PINS.from, DEMO_PINS.to)} className="rounded-md border border-amber-500/50 px-2 py-1 text-amber-300">
            Use demo pins
          </button>
        )}
        <button type="button" onClick={pins.clear} className="rounded-md border border-slate-600 px-2 py-1 text-slate-300">
          Clear
        </button>
      </div>

      {!hasEvent && !demo && (
        <p className="mt-3 text-xs text-slate-400">Pick an event first, or open DEMO data.</p>
      )}
      {state !== 'ready' && state !== 'idle' && (
        <div className="mt-3">
          <DataState state={state} tier="Routes" error={error} onDemo={demo ? null : onDemo} />
        </div>
      )}
      {!demo && state === 'idle' && !hasEvent && (
        <button type="button" onClick={onDemo} className="mt-2 rounded-md border border-amber-500/50 bg-amber-500/10 px-2 py-1 text-xs font-medium text-amber-300">
          Show DEMO data (invented streets)
        </button>
      )}

      {state === 'ready' && (
        <>
          <p className={`mt-3 text-xs font-medium ${rel?.tone}`}>{rel?.text}</p>
          <table className="mt-2 w-full text-[11px]">
            <thead>
              <tr className="text-slate-500">
                <th className="text-left font-normal" />
                <th className="text-right font-normal">
                  <span className="mr-1 inline-block h-2 w-2 rounded-sm bg-slate-400" />
                  Shortest
                </th>
                <th className="text-right font-normal">
                  <span className="mr-1 inline-block h-2 w-2 rounded-sm bg-green-500" />
                  Hazard-aware
                </th>
              </tr>
            </thead>
            <tbody>
              <Row label="Distance" a={km(s?.distanceKm)} b={g ? km(g.distanceKm) : '—'} />
              <Row label="Through mapped flood" a={km(s?.hazard.floodKm)} b={g ? km(g.hazard.floodKm) : '—'} />
              <Row label="Through change areas" a={km(s?.hazard.changeKm)} b={g ? km(g.hazard.changeKm) : '—'} />
              <Row label="Hazard score" a={score(s)} b={score(g)} />
              <Row label="Extra distance" a="—" b={typeof data.detourKm === 'number' ? `${data.detourKm >= 0 ? '+' : ''}${data.detourKm.toFixed(1)} km` : '—'} />
            </tbody>
          </table>

          <RouteProfile shortest={s} safe={g} />

          <div className="mt-3 rounded-lg border border-slate-700 bg-slate-800/60 p-3">
            <div className="mb-1 text-xs font-semibold text-slate-200">Briefing</div>
            <p className="text-xs leading-relaxed text-slate-300">{data.briefing?.text}</p>
            <p className="mt-2 text-[10px] italic text-slate-500">
              Written from a fixed template and the numbers above, not by an AI model.
            </p>
          </div>

          <ul className="mt-2 list-disc space-y-1 pl-4 text-[11px] text-slate-500">
            {(data.limitations ?? []).map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
          {data.hazardSources?.length > 0 && (
            <p className="mt-1 text-[10px] text-slate-500">
              Hazards used: {data.hazardSources.map((h) => h.label ?? h.id).join('; ')}
            </p>
          )}
        </>
      )}
      <ModelCard kind="route" />
    </section>
  );
}
