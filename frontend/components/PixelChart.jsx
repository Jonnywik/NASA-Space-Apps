'use client';

import React from 'react';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

const NO_DATA_TEXT = {
  outside_coverage: 'This spot is outside the area the radar product covers.',
  nodata: 'This spot has no valid radar measurement (water, steep ground or low quality).',
};

const MIN_EPOCHS = 6;
const MIN_SPAN_DAYS = 90;

// Time series for one clicked point. `point` is the `point` object from /ground-motion/point.
export default function PixelChart({ point }) {
  if (!point) return null;

  if (point.status !== 'ok') {
    return (
      <p className="rounded-lg border border-slate-700 bg-slate-800/60 p-3 text-xs text-slate-300">
        {NO_DATA_TEXT[point.reason] ?? 'No usable measurement at this spot.'}
      </p>
    );
  }

  const rows = (point.epochs ?? []).map((date, i) => ({ date, mm: point.displacementMm?.[i] ?? null }));
  const hasRate = typeof point.rateMmPerYear === 'number';
  const se = point.rateStandardErrorMmPerYear;

  return (
    <div>
      <div className="h-40 w-full" data-testid="pixel-chart">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={{ fill: '#94a3b8', fontSize: 9 }} tickFormatter={(d) => d.slice(5)} />
            <YAxis tick={{ fill: '#94a3b8', fontSize: 10 }} unit=" mm" width={48} />
            <Tooltip
              contentStyle={{ background: '#0f172a', border: '1px solid #334155', fontSize: 12 }}
              labelStyle={{ color: '#e2e8f0' }}
              formatter={(v) => [`${Number(v).toFixed(1)} mm`, 'Movement']}
            />
            <Line type="monotone" dataKey="mm" stroke="#06b6d4" strokeWidth={2} dot={{ r: 3 }} connectNulls />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-2 rounded-xl border border-cyan-500/20 bg-cyan-500/10 p-3">
        <div className="text-xs font-medium uppercase tracking-wider text-cyan-300">Rate along line of sight</div>
        {hasRate ? (
          <div className="text-xl font-black text-cyan-300">
            {point.rateMmPerYear.toFixed(1)}
            {typeof se === 'number' && <span className="text-sm font-normal text-slate-300"> ± {se.toFixed(1)}</span>}
            <span className="text-sm font-normal text-slate-300"> mm/yr</span>
          </div>
        ) : (
          <div className="text-sm text-slate-200">
            Not computed: a rate needs at least {MIN_EPOCHS} dates over at least {MIN_SPAN_DAYS} days.
          </div>
        )}
        <div className="mt-1 text-[11px] text-slate-400">
          {point.validEpochCount ?? '—'} dates over {point.spanDays ?? '—'} days
        </div>
      </div>

      <p className="mt-2 text-[11px] italic text-slate-500">
        Movement is measured along the satellite&apos;s line of sight, relative to the first date. It is not
        straight-down sinking, and it is not a prediction.
      </p>
    </div>
  );
}
