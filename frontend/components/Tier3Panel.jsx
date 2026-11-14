// frontend/components/Tier3Panel.jsx
"use client";

import React from "react";
import DataBadge from "./DataBadge";
import DataState from "./DataState";
import ModelCard from "./ModelCard";
import PixelChart from "./PixelChart";
import { getGroundMotionPoint } from "../utils/api";
import { sampleGroundMotionPoint } from "../utils/sampleData";
import { useTier } from "../utils/useTier";

export const MOTION_LEGEND = [
  { min: 25, color: "#dc2626", label: "≥ 25 mm/yr away (fast LOS drop)" },
  { min: 10, color: "#f97316", label: "10 to 25 mm/yr away (moderate)" },
  { min: 0, color: "#facc15", label: "0 to 10 mm/yr away (slight)" },
  {
    min: -Infinity,
    color: "#38bdf8",
    label: "< 0 mm/yr (toward satellite / uplift)",
  },
];

export function motionRateColor(rate) {
  if (typeof rate !== "number") return "#94a3b8";
  return (MOTION_LEGEND.find((b) => rate >= b.min) ?? MOTION_LEGEND[3]).color;
}

export default function Tier3Panel({ eventId, motionTier, point, onClear }) {
  const pointTier = useTier(
    point && eventId
      ? () => getGroundMotionPoint(eventId, point.lng, point.lat)
      : null,
    [eventId, point?.lng, point?.lat],
    { sampleData: sampleGroundMotionPoint },
  );

  const mState = motionTier?.state;
  const mData = motionTier?.data;
  const summary = mData?.regionalSummary;

  return (
    <section
      className="mt-4 border-t border-slate-700 pt-4"
      aria-label="Tier 3 ground motion"
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-sm font-bold text-slate-100">
          Tier 3 · Ground motion
        </h3>
        {mState === "ready" && (
          <DataBadge
            dataStatus={mData.dataStatus}
            dataKind={mData.dataKind}
            isSample={motionTier.isSample}
          />
        )}
      </div>

      <p className="mb-2 text-[10px] text-slate-500">
        Data sources: Sentinel-1 (C-band). NISAR (L-band) public data only
        exists for observations from 17 June 2026, so the three historical storm
        events have no L-band measurements.
      </p>

      {mState && mState !== "ready" && (
        <div className="mb-3">
          <DataState
            state={mState}
            tier="Tier 3 regional motion"
            error={motionTier.error}
            onDemo={motionTier.onDemo}
          />
        </div>
      )}

      {mState === "ready" && summary && (
        <div className="mb-3 rounded-xl border border-cyan-500/20 bg-cyan-500/10 p-3">
          <div className="text-xs font-medium uppercase tracking-wider text-cyan-300">
            Regional median LOS rate
          </div>
          <div className="mt-0.5 text-xl font-black text-cyan-300">
            {typeof summary.medianRateMmPerYear === "number"
              ? summary.medianRateMmPerYear.toFixed(1)
              : "—"}{" "}
            <span className="text-xs font-normal text-slate-300">
              mm/yr (positive = away from satellite)
            </span>
          </div>
          <div className="mt-1 text-[11px] text-slate-400">
            Ref date: {mData.referenceEpoch ?? "—"} ·{" "}
            {summary.validRateCellCount ?? "—"} valid cells
          </div>
        </div>
      )}

      {/* LOS Rate & Risk-Tier Legend */}
      <div className="mb-3 rounded-lg border border-slate-700/60 bg-slate-800/50 p-2.5">
        <div className="mb-1 text-[11px] font-medium text-slate-300">
          Line-of-sight (LOS) motion rate scale
        </div>
        <ul className="space-y-1">
          {MOTION_LEGEND.map((b) => (
            <li
              key={b.label}
              className="flex items-center gap-2 text-[11px] text-slate-400"
            >
              <span
                className="inline-block h-2.5 w-2.5 rounded-sm"
                style={{ background: b.color }}
              />
              {b.label}
            </li>
          ))}
        </ul>
      </div>

      {!point && (
        <p className="text-xs text-slate-300">
          Click anywhere on the map to inspect that spot&apos;s displacement
          time-series chart.
        </p>
      )}

      {point && (
        <div className="mt-2 border-t border-slate-700/60 pt-2">
          <div className="mb-2 flex items-center justify-between text-[11px] text-slate-400">
            <span>
              Point: {point.lat.toFixed(4)}°N, {point.lng.toFixed(4)}°E
            </span>
            <button
              type="button"
              onClick={onClear}
              className="text-blue-300 underline"
            >
              Clear point
            </button>
          </div>
          {pointTier.state !== "ready" && (
            <DataState
              state={pointTier.state}
              tier="Point time-series"
              error={pointTier.error}
              onDemo={pointTier.onDemo}
            />
          )}
          {pointTier.state === "ready" && (
            <PixelChart point={pointTier.data.point} />
          )}
        </div>
      )}

      <ModelCard kind="motion" />
    </section>
  );
}
