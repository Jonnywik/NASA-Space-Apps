'use client';

import React from 'react';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

const NO_DATA_TEXT = {
  outside_coverage: 'This spot is outside the area the radar product covers.',
  nodata: 'This spot has no valid radar measurement (water, steep ground or low quality).',
};

const MIN_EPOCHS = 6;
const MIN_SPAN_DAYS = 90;

export default function PixelChart({ point, cumulative = false }) {
  if (!point) return null;

  if (point.status !== 'ok') {
    return (
      <p className="rounded-xl border border-[#DCE3DB] bg-[#F2F5F1] p-3 text-xs text-[#4A5850]">
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
            <CartesianGrid stroke="#DCE3DB" strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={{ fill: '#4A5850', fontSize: 10 }} tickFormatter={(d) => d.slice(5)} />
            <YAxis tick={{ fill: '#4A5850', fontSize: 10 }} unit=" mm" width={48} />
            <Tooltip
              contentStyle={{ background: '#FFFFFF', border: '1px solid #DCE3DB', borderRadius: '8px', fontSize: 12, color: '#16231B' }}
              labelStyle={{ color: '#16231B', fontWeight: 600 }}
              formatter={(v) => [`${Number(v).toFixed(1)} mm`, 'Movement']}
            />
            <Line type="monotone" dataKey="mm" stroke="#7B3294" strokeWidth={2.2} dot={{ r: 3, fill: '#7B3294' }} connectNulls isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-2 rounded-xl border border-[#C2A5CF] bg-[#F6F1F9] p-3">
        <div className="text-[11px] font-bold uppercase tracking-wider text-[#7B3294]">
          {cumulative ? 'Extrapolated rate along line of sight (not measured over a year)' : 'Rate along line of sight'}
        </div>
        {hasRate ? (
          <div className="text-xl font-bold text-[#16231B]">
            {point.rateMmPerYear.toFixed(1)}
            {typeof se === 'number' && <span className="text-sm font-normal text-[#4A5850]"> ± {se.toFixed(1)}</span>}
            <span className="text-sm font-normal text-[#4A5850]"> mm/yr</span>
          </div>
        ) : (
          <div className="text-sm text-[#16231B]">
            Not computed: a rate needs at least {MIN_EPOCHS} dates over at least {MIN_SPAN_DAYS} days.
          </div>
        )}
        <div className="mt-1 text-[11px] text-[#4A5850]">
          {point.validEpochCount ?? '—'} dates over {point.spanDays ?? '—'} days
        </div>
      </div>

      <p className="mt-2 text-[11px] text-[#4A5850]">
        Movement is measured along the satellite&apos;s line of sight, relative to the first date. It is not
        straight-down sinking, and it is not a prediction.
        {cumulative && ' The per-year figure extends a short record and is shown only as an extrapolation.'}
      </p>
    </div>
  );
}
