'use client';

import { useEffect, useState } from 'react';
import { classifyError } from './api';

// true when the page was opened with ?sample=1
export function useSampleMode() {
  const [sample, setSample] = useState(false);
  useEffect(() => {
    setSample(new URLSearchParams(window.location.search).get('sample') === '1');
  }, []);
  return sample;
}

// One hook for every tier panel.
//   load        function returning a promise (or null to wait, e.g. no event picked yet)
//   deps        values that should trigger a reload, e.g. [eventId]
//   sampleData  shown instead when ?sample=1
// state is one of: idle | loading | ready | unavailable | review | invalid | offline | error
export function useTier(load, deps = [], { sampleData = null } = {}) {
  const sampleMode = useSampleMode();
  const [result, setResult] = useState({ state: 'idle', data: null, error: null });
  const depsKey = JSON.stringify(deps);

  useEffect(() => {
    if (sampleMode && sampleData) {
      setResult({ state: 'ready', data: sampleData, error: null });
      return undefined;
    }
    if (!load) {
      setResult({ state: 'idle', data: null, error: null });
      return undefined;
    }
    let cancelled = false;
    setResult({ state: 'loading', data: null, error: null });
    load()
      .then((data) => {
        if (!cancelled) setResult({ state: 'ready', data, error: null });
      })
      .catch((error) => {
        if (!cancelled) setResult({ state: classifyError(error), data: null, error });
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sampleMode, depsKey]);

  return { ...result, isSample: sampleMode && Boolean(sampleData) };
}
