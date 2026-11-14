"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

// U8 "Limits" drawer: every panel that shows API data reports that response's `limitations` and
// `warnings` here while it is mounted, so the drawer lists exactly what is in view.
const Ctx = createContext(null);

export function LimitsProvider({ children }) {
  const [entries, setEntries] = useState({});
  const report = useCallback((key, entry) => {
    setEntries((prev) => {
      if (!entry) {
        if (!(key in prev)) return prev;
        const next = { ...prev };
        delete next[key];
        return next;
      }
      const old = prev[key];
      if (old && JSON.stringify(old) === JSON.stringify(entry)) return prev;
      return { ...prev, [key]: entry };
    });
  }, []);
  const value = useMemo(() => ({ entries, report }), [entries, report]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useLimits() {
  return useContext(Ctx) ?? { entries: {}, report: () => {} };
}

// Call with the response body of an endpoint. Unmounting (or data becoming null) removes the entry.
export function useReportLimits(key, label, data) {
  const { report } = useContext(Ctx) ?? {};
  const limitations = data?.limitations;
  const warnings = data?.warnings;
  const sourceName = data?.source?.name ?? null;
  const dataKind = data?.dataKind ?? null;
  const has = Boolean(data);
  useEffect(() => {
    if (!report) return undefined;
    if (!has) {
      report(key, null);
      return undefined;
    }
    report(key, {
      label,
      sourceName,
      dataKind,
      limitations: Array.isArray(limitations) ? limitations : [],
      warnings: Array.isArray(warnings) ? warnings : [],
    });
    return () => report(key, null);
  }, [report, key, label, has, sourceName, dataKind, JSON.stringify(limitations ?? []), JSON.stringify(warnings ?? [])]); // eslint-disable-line react-hooks/exhaustive-deps
}
