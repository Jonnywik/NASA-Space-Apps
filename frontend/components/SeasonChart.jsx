"use client";

import React, { useMemo } from "react";
import { Bar, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useLang } from "../utils/LangContext";
import { PALETTE } from "./ui";

// N2 chart: flooded km² per NISAR pass (line, left axis) and NASA POWER daily rainfall (bars, right axis)
// on ONE shared date axis. Missing rainfall days are gaps, never zeros.
export default function SeasonChart({ passes, days, selectedDate, onSelectDate }) {
  const { t } = useLang();
  const rows = useMemo(() => {
    const map = new Map();
    (days ?? []).forEach((d) => map.set(d.date, { date: d.date, mm: d.mm }));
    (passes ?? []).forEach((p) => {
      const r = map.get(p.date) ?? { date: p.date, mm: null, noRain: true };
      r.km2 = p.floodedKm2;
      r.pass = true;
      map.set(p.date, r);
    });
    return [...map.values()].sort((a, b) => (a.date < b.date ? -1 : 1));
  }, [passes, days]);

  if (!rows.length) return null;
  const missing = (days ?? []).filter((d) => d.mm == null).length;

  return (
    <div>
      <div
        className="h-44 w-full"
        role="img"
        aria-label={t("season.chart.aria", { n: passes?.length ?? 0, from: rows[0].date, to: rows[rows.length - 1].date })}
        data-testid="season-chart"
      >
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart
            data={rows}
            margin={{ top: 6, right: 4, bottom: 0, left: 0 }}
            onClick={(s) => {
              const d = s?.activeLabel;
              if (d && rows.find((r) => r.date === d)?.pass) onSelectDate?.(d);
            }}
          >
            <CartesianGrid stroke="#DCE3DB" strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={{ fill: "#4A5850", fontSize: 10 }} tickFormatter={(d) => d.slice(5)} interval="preserveStartEnd" minTickGap={26} />
            <YAxis yAxisId="km" tick={{ fill: "#4A5850", fontSize: 10 }} width={36} label={{ value: "km²", angle: -90, position: "insideLeft", fill: "#4A5850", fontSize: 10 }} />
            <YAxis yAxisId="mm" orientation="right" tick={{ fill: "#4A5850", fontSize: 10 }} width={34} label={{ value: "mm/d", angle: 90, position: "insideRight", fill: "#4A5850", fontSize: 10 }} />
            <Tooltip
              contentStyle={{ background: "#FFFFFF", border: "1px solid #DCE3DB", borderRadius: "8px", fontSize: 12, color: "#16231B" }}
              labelStyle={{ color: "#16231B", fontWeight: 600 }}
              formatter={(v, name) => (name === "mm" ? [v == null ? t("chart.missing") : `${v} mm`, t("season.rain")] : [`${v} km²`, t("season.flooded")])}
            />
            <Bar yAxisId="mm" dataKey="mm" name="mm" fill={PALETTE.sky} fillOpacity={0.85} isAnimationActive={false} />
            <Line
              yAxisId="km"
              type="linear"
              dataKey="km2"
              name="km2"
              stroke="#2171B5"
              strokeWidth={2}
              connectNulls
              isAnimationActive={false}
              dot={{ r: 3.5, fill: "#FFFFFF", stroke: "#2171B5", strokeWidth: 2 }}
              activeDot={{ r: 5 }}
            />
            {selectedDate && <ReferenceLine yAxisId="km" x={selectedDate} stroke="#1E5B3A" strokeWidth={2} strokeDasharray="4 3" />}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-1.5 flex flex-wrap gap-x-3 text-[11px] text-[#4A5850]">
        <span>
          <span className="mr-1 inline-block h-2 w-3 align-middle" style={{ background: PALETTE.sky }} />
          {t("season.rain")} (mm/day)
        </span>
        <span>
          <span className="mr-1 inline-block h-0.5 w-3 align-middle" style={{ background: "#2171B5" }} />
          ● {t("season.flooded")} (km²)
        </span>
        <span>
          <span className="mr-1 inline-block h-0.5 w-3 border-t-2 border-dashed border-[#1E5B3A] align-middle" />
          {t("season.selected")}
        </span>
        {missing > 0 && <span>{t("season.missingDays", { n: missing })}</span>}
      </p>
    </div>
  );
}
