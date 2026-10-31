import React from 'react';

// What a panel shows instead of data. "No data yet" is a normal state, not an error.
const COPY = {
  loading: { title: 'Loading…', tone: 'text-slate-300', body: null },
  unavailable: {
    title: 'No real data yet',
    tone: 'text-slate-200',
    body: 'The pipeline is built, but real radar products for this event have not been published yet. We show nothing rather than something made up.',
  },
  review: {
    title: 'Waiting for review',
    tone: 'text-amber-300',
    body: 'Results exist but have not passed human review, so they are hidden.',
  },
  invalid: {
    title: 'Data failed its checks',
    tone: 'text-red-300',
    body: 'The published product does not match its checksums or its linked run. Tell the backend team.',
  },
  offline: {
    title: 'Backend not reachable',
    tone: 'text-red-300',
    body: 'Start the API: in backend/ run  python -m uvicorn app.main:app --reload',
  },
  error: { title: 'Something went wrong', tone: 'text-red-300', body: null },
};

export default function DataState({ state, tier = 'This panel', error = null }) {
  const copy = COPY[state];
  if (!copy || state === 'ready' || state === 'idle') return null;
  return (
    <div
      className="rounded-xl border border-slate-700 bg-slate-800/60 p-3 text-sm"
      role={state === 'loading' ? 'status' : 'alert'}
    >
      <div className={`font-semibold ${copy.tone}`}>
        {tier}: {copy.title}
      </div>
      {copy.body && <p className="mt-1 text-xs text-slate-400">{copy.body}</p>}
      {error && (state === 'error' || state === 'invalid') && (
        <p className="mt-1 break-words font-mono text-[11px] text-slate-500">{error.message}</p>
      )}
    </div>
  );
}
