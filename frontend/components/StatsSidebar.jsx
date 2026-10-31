// -------------------------------------------------------------
// BLOCK 1: Imports & helpers
// -------------------------------------------------------------
import React from 'react';

// Numbers that are still null (not measured yet) show a dash instead of "0.0k".
// Careful: in JavaScript, null / 1000 is 0, so we must check for null first.
const formatArea = (n) =>
  n == null ? '—' : n.toLocaleString(undefined, { maximumFractionDigits: 1 });
const formatThousands = (n) => (n == null ? '—' : `${(n / 1000).toFixed(1)}k`);

export default function StatsSidebar({ data, children }) {
  // Before the API answers, `data` is null: show a small loading box.
  if (!data) {
    return (
      <div className="absolute top-4 right-4 z-[1000] w-80 bg-slate-900/90 text-white p-5 rounded-2xl shadow-xl border border-slate-700 backdrop-blur-md">
        <div className="text-sm text-slate-400">Loading flood data…</div>
      </div>
    );
  }

  const { aoi, beforeDate, afterDate, stats } = data;
  const noExposureYet = stats.peopleExposed == null && stats.householdsExposed == null;

  // -------------------------------------------------------------
  // BLOCK 2: Floating Box Container & Top Badge
  // -------------------------------------------------------------
  return (
    <div className="absolute top-4 right-4 z-[1000] max-h-[calc(100vh-2rem)] w-80 overflow-y-auto bg-slate-900/90 text-white p-5 rounded-2xl shadow-xl border border-slate-700 backdrop-blur-md">
      {/* Header Tag */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-blue-500/20 text-blue-400 border border-blue-500/30">
          Sentinel-1 Radar
        </span>
        <span className="text-xs text-slate-400 font-mono">Tier 1</span>
      </div>

      {/* -------------------------------------------------------------
          BLOCK 3: Primary Highlight (Area Underwater)
      ------------------------------------------------------------- */}
      <h2 className="text-lg font-bold text-slate-100">{aoi}</h2>
      <p className="text-xs text-slate-400 mb-4">
        Comparing {beforeDate} vs {afterDate}
      </p>

      <div className="bg-red-500/10 border border-red-500/20 p-3 rounded-xl mb-3">
        <div className="text-xs font-medium text-red-400 uppercase tracking-wider mb-1">
          Area Underwater
        </div>
        <div className="text-2xl font-black text-red-400">
          {formatArea(stats.km2Flooded)}{' '}
          <span className="text-sm font-normal text-slate-300">km²</span>
        </div>
      </div>

      {/* -------------------------------------------------------------
          BLOCK 4: Secondary Grid Stats (Residents & Households)
      ------------------------------------------------------------- */}
      <div className="grid grid-cols-2 gap-2">
        <div className="bg-slate-800/80 p-3 rounded-xl border border-slate-700/50">
          <div className="text-xs text-slate-400 mb-1">Residents Affected</div>
          <div className="text-lg font-bold text-slate-100">
            {formatThousands(stats.peopleExposed)}
          </div>
        </div>

        <div className="bg-slate-800/80 p-3 rounded-xl border border-slate-700/50">
          <div className="text-xs text-slate-400 mb-1">Households</div>
          <div className="text-lg font-bold text-slate-100">
            {formatThousands(stats.householdsExposed)}
          </div>
        </div>
      </div>

      {noExposureYet && (
        <p className="mt-3 text-xs text-slate-500">
          Exposure numbers need population data and are not available yet.
        </p>
      )}

      {/* Extra tier panels (Tier 2, later Tier 3) are passed in from page.js */}
      {children}
    </div>
  );
}
