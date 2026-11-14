'use client';

import React from 'react';
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

const LEVELS = { 0: 'Clear', 1: 'Change area', 2: 'Mapped flood' };

// Route profile: along the route (km), is the road clear, in a change area, or in mapped flood?
export default function RouteProfile({ shortest, safe }) {
  const merge = (a, b) => {
    // two series on one x axis
    const xs = new Set([...(a?.profile ?? []).map((p) => p.distKm), ...(b?.profile ?? []).map((p) => p.distKm)]);
    const at = (prof, x) => {
      if (!prof?.length) return null;
      let last = prof[0].level;
      for (const p of prof) {
        if (p.distKm <= x) last = p.level;
        else break;
      }
      return last;
    };
    return [...xs]
      .sort((m, n) => m - n)
      .map((x) => ({ km: Number(x.toFixed(2)), shortest: at(a?.profile, x), safe: at(b?.profile, x) }));
  };
  const rows = merge(shortest, safe);
  if (!rows.length) return null;
  return (
    <div className="mt-3" data-testid="route-profile">
      <div className="mb-1 text-xs text-slate-300">Route profile (0 clear · 1 change area · 2 mapped flood)</div>
      <div className="h-32 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={rows} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
            <XAxis dataKey="km" type="number" domain={[0, 'dataMax']} tick={{ fill: '#94a3b8', fontSize: 10 }} unit=" km" />
            <YAxis domain={[0, 2]} ticks={[0, 1, 2]} tick={{ fill: '#94a3b8', fontSize: 10 }} width={22} />
            <Tooltip
              contentStyle={{ background: '#0f172a', border: '1px solid #334155', fontSize: 12 }}
              formatter={(v, name) => [LEVELS[v] ?? '—', name === 'safe' ? 'Hazard-aware' : 'Shortest']}
              labelFormatter={(l) => `${l} km`}
            />
            <Area type="stepAfter" dataKey="shortest" stroke="#94a3b8" fill="#94a3b8" fillOpacity={0.25} isAnimationActive={false} />
            {safe && <Area type="stepAfter" dataKey="safe" stroke="#22c55e" fill="#22c55e" fillOpacity={0.25} isAnimationActive={false} />}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
