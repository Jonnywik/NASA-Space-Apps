'use client';

import React from 'react';
import DataBadge from './DataBadge';
import DataState from './DataState';
import PixelChart from './PixelChart';
import { getGroundMotionPoint } from '../utils/api';
import { sampleGroundMotionPoint } from '../utils/sampleData';
import { useTier } from '../utils/useTier';

// Tier 3 card: click the map, see that point's movement over time.
//   eventId  selected event
//   point    {lng, lat} from useMapPick, or null
//   onClear  forget the point
export default function Tier3Panel({ eventId, point, onClear }) {
  const tier3 = useTier(
    point && eventId ? () => getGroundMotionPoint(eventId, point.lng, point.lat) : null,
    [eventId, point?.lng, point?.lat],
    { sampleData: sampleGroundMotionPoint }
  );
  const { state, data, error, isSample } = tier3;

  return (
    <section className="mt-4 border-t border-slate-700 pt-4" aria-label="Tier 3 ground motion">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-sm font-bold text-slate-100">Tier 3 · Ground motion</h3>
        {point && state === 'ready' && (
          <DataBadge dataStatus={data.dataStatus} dataKind={data.dataKind} isSample={isSample} />
        )}
      </div>

      {!point && <p className="text-xs text-slate-400">Click anywhere on the map to see how that spot moved over time.</p>}

      {point && (
        <>
          <div className="mb-2 flex items-center justify-between text-[11px] text-slate-400">
            <span>
              {point.lat.toFixed(4)}°N, {point.lng.toFixed(4)}°E
            </span>
            <button type="button" onClick={onClear} className="text-blue-300 underline">
              Clear
            </button>
          </div>
          {state !== 'ready' && <DataState state={state} tier="Tier 3" error={error} />}
          {state === 'ready' && <PixelChart point={data.point} />}
        </>
      )}
    </section>
  );
}
