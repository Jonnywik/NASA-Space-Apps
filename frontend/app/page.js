// frontend/app/page.js
"use client";

import { useCallback, useEffect, useState } from "react";
import CamanavaWorkspace from "../components/CamanavaWorkspace";
import RegionalWorkspace from "../components/RegionalWorkspace";
import { LangProvider } from "../utils/LangContext";

// The first screen is the CAMANAVA 2026 NISAR workspace. The original Sentinel-1 event workspace stays
// reachable as "Regional context" (?view=regional).
export default function Page() {
  const [view, setView] = useState("camanava");

  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("view") === "regional") setView("regional");
  }, []);

  const toRegional = useCallback(() => {
    window.history.replaceState(null, "", `${window.location.pathname}?view=regional`);
    setView("regional");
  }, []);
  const toCamanava = useCallback(() => {
    window.history.replaceState(null, "", window.location.pathname);
    setView("camanava");
  }, []);

  return (
    <LangProvider>
      <main className="h-screen w-screen overflow-hidden bg-ground text-ink">
        {view === "regional" ? <RegionalWorkspace onBack={toCamanava} /> : <CamanavaWorkspace onRegional={toRegional} />}
      </main>
    </LangProvider>
  );
}
