'use client';

// INTERNAL component gallery at /dev. Lets us check every panel state without real data.
// Delete this folder before the final submission (it is on the Phase P4 to-do list).

import { useEffect, useState } from 'react';
import DataState from '../../components/DataState';
import DataBadge from '../../components/DataBadge';
import { classifyError, getCoherenceLoss } from '../../utils/api';
import { sampleBriefing, sampleCoherenceLoss, sampleGroundMotionPoint } from '../../utils/sampleData';

const STATES = ['loading', 'unavailable', 'review', 'invalid', 'offline', 'error'];

export default function DevGallery() {
  const [live, setLive] = useState({ text: 'checking…' });

  useEffect(() => {
    getCoherenceLoss('karding_2022')
      .then((d) => setLive({ text: `ready (dataStatus: ${d.dataStatus})` }))
      .catch((e) => setLive({ text: `${classifyError(e)}  (HTTP ${e.status}, code ${e.code})` }));
  }, []);

  return (
    <main className="min-h-screen bg-slate-950 p-6 text-white">
      <h1 className="text-xl font-bold">Tanaw component gallery (internal)</h1>
      <p className="mt-1 text-sm text-slate-400">Delete app/dev before submission.</p>

      <h2 className="mt-6 text-sm font-semibold text-blue-300">1. Panel states</h2>
      <div className="mt-2 grid max-w-md gap-2">
        {STATES.map((s) => (
          <DataState key={s} state={s} tier="Tier 2" error={new Error('example error text')} />
        ))}
      </div>

      <h2 className="mt-6 text-sm font-semibold text-blue-300">2. Data badges</h2>
      <div className="mt-2 flex flex-wrap gap-2">
        <DataBadge isSample />
        <DataBadge dataStatus="validated" />
        <DataBadge dataStatus="pending" />
      </div>

      <h2 className="mt-6 text-sm font-semibold text-blue-300">3. Live backend check (coherence-loss, karding_2022)</h2>
      <p className="mt-2 font-mono text-sm text-slate-300">{live.text}</p>
      <p className="mt-1 text-xs text-slate-500">
        Today this should say &quot;unavailable (HTTP 404, code data_unavailable)&quot;. After Drei publishes and reviews a
        product it should say &quot;ready&quot;.
      </p>

      <h2 className="mt-6 text-sm font-semibold text-blue-300">4. Sample data loaded</h2>
      <pre className="mt-2 max-w-xl overflow-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-300">
        {JSON.stringify(
          {
            changePolygons: sampleCoherenceLoss.changeGeojson.features.length,
            km2Changed: sampleCoherenceLoss.stats.km2Changed,
            pointEpochs: sampleGroundMotionPoint.point.epochs.length,
            briefingChars: sampleBriefing.text.length,
          },
          null,
          2
        )}
      </pre>
    </main>
  );
}
