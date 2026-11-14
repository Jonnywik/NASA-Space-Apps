"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import FuturePanel from "./FuturePanel";
import HistoryPanel from "./HistoryPanel";
import HypothesesPanel from "./HypothesesPanel";
import LimitsDrawer from "./LimitsDrawer";
import MotionPanel from "./MotionPanel";
import NisarMap from "./NisarMap";
import ProjectionPanel from "./ProjectionPanel";
import RadarCards from "./RadarCards";
import RhythmPanel from "./RhythmPanel";
import SearchBox from "./SearchBox";
import SeasonPanel from "./SeasonPanel";
import SpotCheck from "./SpotCheck";
import StoryTour from "./StoryTour";
import TimeBar from "./TimeBar";
import { fmt } from "./ui";
import {
  AREA_ID,
  FIXTURES_ON,
  FIXTURE_SCOPE,
  getFloodScenario,
  getGroundMotion,
  getNisarPasses,
  getNisarPolarization,
  getNisarRhythm,
  getOutlook,
  getPlaceExposure,
  getRainfallDaily,
  getRainfallMonthly,
  getRainfallTrend,
  getScenarios,
  getSeasonRank,
  getTimelineAvailability,
  searchPlaces,
} from "../utils/api";
import { useLang } from "../utils/LangContext";
import { LimitsProvider, useLimits, useReportMany } from "../utils/LimitsContext";
import { makeLosScale } from "../utils/losScale";
import { STORY_KEY, STORY_STEPS } from "../utils/storySteps";
import { buildQuery, MODES, readUrlState } from "../utils/urlState";
import useLatched from "../utils/useLatched";
import useProjection from "../utils/useProjection";
import { useTier } from "../utils/useTier";

const MODE_ORDER = ["season", "rhythm", "motion", "history", "future"];
const addDays = (iso, n) => new Date(Date.parse(`${iso}T00:00:00Z`) + n * 86400000).toISOString().slice(0, 10);

function safeStorage(fn) {
  try {
    return fn(window.localStorage);
  } catch {
    return null;
  }
}

async function fetchJsonArray(path) {
  try {
    const r = await fetch(path, { cache: "no-store" });
    if (!r.ok) return [];
    const j = await r.json();
    return Array.isArray(j) ? j : [];
  } catch {
    return [];
  }
}

function histDateFor(i) {
  const y = 2000 + Math.floor(i / 12);
  const m = (i % 12) + 1;
  return `${y}-${String(m).padStart(2, "0")}-01`;
}

export default function CamanavaWorkspace(props) {
  return (
    <LimitsProvider>
      <Workspace {...props} />
    </LimitsProvider>
  );
}

function Workspace({ onRegional }) {
  const { t, lang, setLang } = useLang();
  const { entries } = useLimits();
  const limitCount = Object.values(entries).reduce((n, e) => n + e.limitations.length + e.warnings.length, 0);

  const [mode, setMode] = useState("season");
  const [passIdx, setPassIdx] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [polView, setPolView] = useState("flood");
  const [opacity, setOpacity] = useState(0.8);
  const [compareOn, setCompareOn] = useState(false);
  const [cmpBefore, setCmpBefore] = useState(0);
  const [cmpAfter, setCmpAfter] = useState(0);
  const [split, setSplit] = useState(0.5);
  const [point, setPoint] = useState(null);
  const [placeHint, setPlaceHint] = useState(null);
  const [activeStory, setActiveStory] = useState(null);
  const [sideTab, setSideTab] = useState("findings");
  const [view, setView] = useState(null);
  const [tour, setTour] = useState({ open: false, step: 0 });
  const [bare, setBare] = useState(false);
  const [rhythmUnder, setRhythmUnder] = useState(false);
  const [limitsOpen, setLimitsOpen] = useState(false);
  const [radar, setRadar] = useState({ open: false, card: "water" });
  const [copied, setCopied] = useState(false);
  const [scenarioId, setScenarioId] = useState(null);
  const [histIdx, setHistIdx] = useState(0);
  const [projYear, setProjYear] = useState(2026);
  const [panelOpen, setPanelOpen] = useState(true);
  const [searchHighlight, setSearchHighlight] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const [hypotheses, setHypotheses] = useState([]);
  const [stories, setStories] = useState([]);
  const searchRef = useRef(null);
  const pending = useRef({ pass: null, cmp: null });
  const nonce = useRef(0);

  const histMax = useMemo(() => {
    const d = new Date();
    return (d.getUTCFullYear() - 2000) * 12 + d.getUTCMonth();
  }, []);
  useEffect(() => setHistIdx(histMax), [histMax]);

  // ---- data ---------------------------------------------------------------------------------
  const passesTier = useTier(() => getNisarPasses(AREA_ID), []);
  const passes = useMemo(() => passesTier.data?.passes ?? [], [passesTier.data]);
  const passDates = useMemo(() => passes.map((p) => p.date), [passes]);
  const rainStart = passDates.length ? addDays(passDates[0], -14) : null;
  const rainEnd = passDates.length ? passDates[passDates.length - 1] : null;
  const rainTier = useTier(rainStart ? () => getRainfallDaily(AREA_ID, rainStart, rainEnd) : null, [rainStart, rainEnd]);

  const needRhythm = useLatched(mode === "rhythm" || mode === "motion");
  const rhythmTier = useTier(needRhythm ? () => getNisarRhythm(AREA_ID) : null, [needRhythm]);
  const needRhythmTable = useLatched(mode === "rhythm");
  const exposureRhythm = useTier(needRhythmTable ? () => getPlaceExposure(AREA_ID, "rhythm_half") : null, [needRhythmTable]);
  const needMotion = useLatched(mode === "motion");
  const motionTier = useTier(needMotion ? () => getGroundMotion(AREA_ID) : null, [needMotion]);
  const exposurePriority = useTier(needMotion ? () => getPlaceExposure(AREA_ID, "priority") : null, [needMotion]);
  const polDate = passes[passIdx]?.date;
  const polTier = useTier(polView === "rgb" && polDate ? () => getNisarPolarization(AREA_ID, polDate) : null, [polView, polDate]);

  const needHistory = useLatched(mode === "history");
  const availability = useTier(needHistory ? () => getTimelineAvailability(AREA_ID) : null, [needHistory]);
  const monthly = useTier(needHistory ? () => getRainfallMonthly(AREA_ID) : null, [needHistory]);
  const rank = useTier(needHistory ? () => getSeasonRank(AREA_ID, 2026) : null, [needHistory]);
  const trend = useTier(needHistory ? () => getRainfallTrend(AREA_ID) : null, [needHistory]);

  const needFuture = useLatched(mode === "future");
  const outlook = useTier(needFuture ? () => getOutlook(AREA_ID) : null, [needFuture]);
  const scenarios = useTier(needFuture ? () => getScenarios(AREA_ID) : null, [needFuture]);
  const flood = useTier(needFuture && scenarioId ? () => getFloodScenario(AREA_ID, scenarioId) : null, [needFuture, scenarioId]);
  const proj = useProjection({ eventId: AREA_ID, year: projYear, demo: false, active: mode === "future" });

  useReportMany([
    ["passes", t("season.title"), passesTier.data],
    ["rain", t("season.rain"), rainTier.data],
    ["rhythm", t("rhythm.title"), rhythmTier.data],
    ["exp-rhythm", t("exposure.title"), exposureRhythm.data],
    ["motion", t("motion.title"), motionTier.data],
    ["exp-priority", t("priority.title"), exposurePriority.data],
    ["pol", t("season.layer.rgb"), polTier.data],
    ["avail", t("hist.avail.title"), availability.data],
    ["monthly", t("hist.monthly.title"), monthly.data],
    ["rank", t("hist.rank.title"), rank.data],
    ["trend", t("hist.trend.title"), trend.data],
    ["outlook", t("future.outlook.title"), outlook.data],
    ["scenarios", t("future.scenario.title"), scenarios.data],
    ["flood", t("future.flood.title"), flood.data],
  ]);

  // default scenario once the list arrives
  useEffect(() => {
    if (scenarios.data?.scenarios?.length && !scenarioId) setScenarioId(scenarios.data.scenarios[0].id);
  }, [scenarios.data, scenarioId]);

  // optional public JSON: N6 hypotheses and U7 "Our stories" (both ship empty)
  useEffect(() => {
    fetchJsonArray("/hypotheses.json").then(setHypotheses);
    fetchJsonArray("/stories.json").then((list) =>
      setStories(list.filter((s) => s && typeof s.lat === "number" && typeof s.lon === "number" && typeof s.text === "string")),
    );
  }, []);

  // ---- first load: URL state, story ---------------------------------------------------------
  useEffect(() => {
    const u = readUrlState(window.location.search);
    if (u.mode) setMode(u.mode);
    if (u.point) {
      setPoint(u.point);
      setSideTab("spot");
    }
    pending.current = { pass: u.pass, cmp: u.cmp };
    const dismissed = safeStorage((s) => s.getItem(STORY_KEY)) === "1";
    if (!dismissed && !u.mode && !u.point) setTour({ open: true, step: 0 });
    setHydrated(true);
  }, []);

  // apply ?pass= and ?cmp= once the pass list exists
  useEffect(() => {
    if (!passes.length) return;
    const { pass, cmp } = pending.current;
    if (!pass && !cmp) return;
    const idxOf = (id) => passes.findIndex((p) => p.id === id);
    if (pass && idxOf(pass) >= 0) setPassIdx(idxOf(pass));
    if (cmp && idxOf(cmp[0]) >= 0 && idxOf(cmp[1]) >= 0) {
      setCmpBefore(idxOf(cmp[0]));
      setCmpAfter(idxOf(cmp[1]));
      setCompareOn(true);
    }
    pending.current = { pass: null, cmp: null };
  }, [passes]);

  // keep the address bar in step with the view (U8)
  const passId = passes[passIdx]?.id ?? null;
  const cmpIds = compareOn && passes[cmpBefore] && passes[cmpAfter] ? [passes[cmpBefore].id, passes[cmpAfter].id] : null;
  const queryString = buildQuery({ mode, pass: passId, cmp: cmpIds, point, lang });
  useEffect(() => {
    if (!hydrated || pending.current.pass || pending.current.cmp) return;
    try {
      window.history.replaceState(null, "", `${window.location.pathname}${queryString ? `?${queryString}` : ""}`);
    } catch {
      /* ignore */
    }
  }, [hydrated, queryString]);

  // ---- player -------------------------------------------------------------------------------
  useEffect(() => {
    if (!playing || passes.length < 2) return undefined;
    const id = setInterval(() => setPassIdx((i) => (i + 1) % passes.length), 1200);
    return () => clearInterval(id);
  }, [playing, passes.length]);
  useEffect(() => {
    if (mode !== "season" || compareOn) setPlaying(false);
  }, [mode, compareOn]);

  // ---- story --------------------------------------------------------------------------------
  const flyTo = useCallback((v) => {
    nonce.current += 1;
    setView({ nonce: nonce.current, ...v });
  }, []);

  useEffect(() => {
    if (!tour.open) return;
    const s = STORY_STEPS[tour.step];
    setMode(s.mode);
    setBare(Boolean(s.bare));
    setCompareOn(false);
    setPolView("flood");
    setRhythmUnder(Boolean(s.rhythmUnder));
    setSideTab("findings");
    setSearchHighlight(Boolean(s.focusSearch));
    if (s.firstPass) setPassIdx(0);
    const reduce = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    setPlaying(Boolean(s.play) && !reduce);
    flyTo(s.view);
    if (s.scrollTo) setTimeout(() => document.querySelector(`[data-testid="${s.scrollTo}"]`)?.scrollIntoView({ block: "start", behavior: "smooth" }), 400);
  }, [tour.open, tour.step, flyTo]);

  const closeTour = useCallback(() => {
    setTour((s) => ({ ...s, open: false }));
    setBare(false);
    setSearchHighlight(false);
    safeStorage((s) => s.setItem(STORY_KEY, "1"));
  }, []);
  const storyFact = (i) => {
    const step = STORY_STEPS[i].id;
    if (step === "season" && passes.length) return t("story.fact.passes", { n: passes.length, from: passDates[0], to: passDates[passDates.length - 1] });
    if (step === "rhythm" && rhythmTier.data?.halfOrMoreKm2 != null) return t("story.fact.half", { km2: fmt(rhythmTier.data.halfOrMoreKm2), n: rhythmTier.data.passCount });
    if (step === "motion" && motionTier.data?.epochs?.length) return t("story.fact.motion", { n: motionTier.data.epochs.length });
    if (step === "priority" && exposurePriority.data?.totals?.population != null) return t("story.fact.priority", { pop: fmt(exposurePriority.data.totals.population, 0) });
    return null;
  };

  // ---- mode switching -----------------------------------------------------------------------
  function goMode(m) {
    if (tour.open) closeTour();
    setBare(false);
    setMode(m);
    setSideTab("findings");
    setPanelOpen(true);
  }

  // ---- spot check ---------------------------------------------------------------------------
  const openSpot = useCallback((pt, hint = null, story = null) => {
    setPoint(pt);
    setPlaceHint(hint);
    setActiveStory(story);
    setSideTab("spot");
    setPanelOpen(true);
  }, []);
  const onPick = useCallback((lon, lat) => openSpot({ lon, lat }), [openSpot]);

  function onSearchSelect(r) {
    if (tour.open) closeTour();
    setSearchHighlight(false);
    if (Array.isArray(r.bbox) && r.bbox.length === 4 && r.level === "barangay") {
      const [w, s, e, n] = r.bbox;
      flyTo({ bounds: [[s, w], [n, e]], maxZoom: 16 });
    } else flyTo({ center: [r.lat, r.lon], zoom: r.level === "city" ? 13 : 15 });
    openSpot({ lon: r.lon, lat: r.lat }, { name: r.name, city: r.city });
  }

  async function copyLink() {
    const url = `${window.location.origin}${window.location.pathname}${queryString ? `?${queryString}` : ""}`;
    try {
      await navigator.clipboard.writeText(url);
    } catch {
      window.prompt(t("spot.copy"), url);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  // ---- map content --------------------------------------------------------------------------
  const bounds = passesTier.data?.bounds;
  const overlays = useMemo(() => {
    if (bare) return [];
    const out = [];
    if (mode === "season" && passes.length) {
      const cur = passes[passIdx];
      const url = (p) => (polView === "hh" ? p?.backscatterUrl : p?.overlayUrl);
      if (compareOn) {
        const b = passes[cmpBefore];
        const a = passes[cmpAfter];
        out.push({ key: `b-${b?.id}-${polView}`, url: url(b), pane: "beforePane", opacity, bounds, alt: `${b?.date}` });
        out.push({ key: `a-${a?.id}-${polView}`, url: url(a), pane: "afterPane", opacity, bounds, alt: `${a?.date}` });
      } else if (polView === "rgb") {
        if (polTier.data?.rgbUrl) out.push({ key: `rgb-${polTier.data.date ?? cur?.id}`, url: polTier.data.rgbUrl, pane: "afterPane", opacity, bounds: polTier.data.bounds ?? bounds, alt: "RGB" });
      } else {
        out.push({ key: `p-${cur?.id}-${polView}`, url: url(cur), pane: "afterPane", opacity, bounds, alt: `${cur?.date}` });
      }
    }
    if ((mode === "rhythm" || (mode === "motion" && rhythmUnder)) && rhythmTier.data?.overlayUrl) {
      out.push({ key: "rhythm", url: rhythmTier.data.overlayUrl, pane: "rhythmPane", opacity, bounds: rhythmTier.data.bounds ?? bounds, alt: t("rhythm.title") });
    }
    return out;
  }, [bare, mode, passes, passIdx, polView, compareOn, cmpBefore, cmpAfter, opacity, bounds, polTier.data, rhythmTier.data, rhythmUnder, t]);

  const losScale = useMemo(() => makeLosScale(motionTier.data?.heatmapGeojson), [motionTier.data]);
  const geojsons = useMemo(() => {
    const out = [];
    if (mode === "motion" && losScale && motionTier.data?.heatmapGeojson) {
      out.push({
        key: "los",
        data: motionTier.data.heatmapGeojson,
        pane: "motionPane",
        style: (f) => {
          const c = losScale.color(f?.properties?.[losScale.prop]);
          return { color: c, weight: 0.4, fillColor: c, fillOpacity: rhythmUnder ? 0.5 : 0.7 };
        },
        tooltip: (f) => `${t("motion.tip")}: ${fmt(f?.properties?.[losScale.prop]) ?? "—"} ${losScale.unit}`,
      });
    }
    if (mode === "future" && proj.geojson) {
      out.push({
        key: "proj",
        data: proj.geojson,
        pane: "projectionPane",
        style: { color: "#CC79A7", weight: 2, dashArray: "4 4", fillColor: "#CC79A7", fillOpacity: 0.3 },
        tooltip: (f) => `${t("future.projection.tip")} ${f.properties?.year ?? ""}: ${fmt(f.properties?.areaKm2) ?? "—"} km²`,
      });
    }
    return out;
  }, [mode, losScale, motionTier.data, rhythmUnder, proj.geojson, t]);

  const pins = useMemo(() => stories.map((s, i) => ({ id: String(s.id ?? i), lat: s.lat, lon: s.lon, label: s.name ?? s.barangay ?? t("stories.pin") })), [stories, t]);
  const onPin = useCallback(
    (id) => {
      const s = stories.find((x, i) => String(x.id ?? i) === id);
      if (!s) return;
      flyTo({ center: [s.lat, s.lon], zoom: 15 });
      openSpot({ lon: s.lon, lat: s.lat }, { name: s.barangay ?? s.name, city: s.city }, s);
    },
    [stories, flyTo, openSpot],
  );
  const compare = useMemo(
    () => ({ on: compareOn && mode === "season", split, onSplit: setSplit, beforeLabel: passes[cmpBefore]?.date ?? "", afterLabel: passes[cmpAfter]?.date ?? "" }),
    [compareOn, mode, split, passes, cmpBefore, cmpAfter],
  );
  const mapPoint = useMemo(() => (point ? { lon: point.lon, lat: point.lat } : null), [point]);

  const openHelp = useCallback((card) => setRadar({ open: true, card: card ?? "water" }), []);
  const closeHelp = useCallback(() => setRadar((r) => ({ ...r, open: false })), []);
  const closeLimits = useCallback(() => setLimitsOpen(false), []);

  function onZone(z) {
    // table rows jump to the place via the gazetteer
    searchPlaces(z.name, 1)
      .then((d) => d.results?.[0] && onSearchSelect(d.results[0]))
      .catch(() => {});
  }

  const modeLabels = { season: t("mode.season"), rhythm: t("mode.rhythm"), motion: t("mode.motion"), history: t("mode.history"), future: t("mode.future") };
  const histDate = histDateFor(histIdx);
  const scenarioMonths = scenarios.data?.scenarios?.find((s) => s.id === scenarioId)?.months ?? scenarios.data?.scenarios?.[0]?.months ?? [];

  return (
    <div className="flex h-screen w-screen flex-col bg-slate-950 text-white" data-testid="workspace">
      {/* header */}
      <header className="flex flex-wrap items-center gap-x-3 gap-y-1.5 border-b border-slate-700 bg-slate-900 px-3 py-2">
        <div className="mr-1 leading-tight">
          <div className="text-base font-black uppercase tracking-[0.18em] text-blue-300">Tanaw</div>
          <div className="text-[10px] text-slate-400">{t("app.tagline")}</div>
        </div>
        <SearchBox onSelect={onSearchSelect} inputRef={searchRef} highlight={searchHighlight} />
        <nav aria-label={t("nav.modes")} className="order-last flex w-full gap-1 overflow-x-auto md:order-none md:w-auto" data-testid="mode-tabs">
          <button
            type="button"
            onClick={() => setTour({ open: true, step: 0 })}
            aria-current={tour.open ? "page" : undefined}
            className={`whitespace-nowrap rounded-md border px-2.5 py-1 text-xs font-semibold ${tour.open ? "border-yellow-300 bg-yellow-300/20 text-white" : "border-slate-600 bg-slate-800 text-slate-200 hover:bg-slate-700"}`}
            data-testid="tab-story"
          >
            ★ {t("mode.story")}
          </button>
          {MODE_ORDER.map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => goMode(m)}
              aria-current={mode === m && !tour.open ? "page" : undefined}
              className={`whitespace-nowrap rounded-md border px-2.5 py-1 text-xs font-semibold ${mode === m && !tour.open ? "border-sky-300 bg-sky-600/40 text-white" : "border-slate-600 bg-slate-800 text-slate-200 hover:bg-slate-700"}`}
              data-testid={`tab-${m}`}
            >
              {modeLabels[m]}
            </button>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-1.5">
          <button type="button" onClick={() => openHelp("water")} className="rounded-md border border-slate-500 bg-slate-800 px-2 py-1 text-xs hover:bg-slate-700" data-testid="open-radar">
            ? {t("radar.button")}
          </button>
          <button type="button" onClick={() => setLimitsOpen(true)} className="rounded-md border border-amber-300/70 bg-amber-500/10 px-2 py-1 text-xs font-semibold text-amber-100 hover:bg-amber-500/20" data-testid="open-limits">
            {t("limits.button")} ({limitCount})
          </button>
          <div role="group" aria-label={t("lang.label")} className="flex overflow-hidden rounded-md border border-slate-500 text-xs">
            {["en", "fil"].map((l) => (
              <button key={l} type="button" onClick={() => setLang(l)} aria-pressed={lang === l} className={`px-2 py-1 font-semibold ${lang === l ? "bg-sky-600 text-white" : "bg-slate-800 text-slate-300 hover:bg-slate-700"}`} data-testid={`lang-${l}`}>
                {l === "en" ? "EN" : "FIL"}
              </button>
            ))}
          </div>
          <button type="button" onClick={onRegional} className="rounded-md border border-slate-500 bg-slate-800 px-2 py-1 text-xs hover:bg-slate-700" data-testid="open-regional">
            {t("regional.button")}
          </button>
        </div>
      </header>

      {FIXTURES_ON && (
        <div role="status" className="border-b border-yellow-300 bg-yellow-400/20 px-3 py-1 text-center text-xs font-bold text-yellow-100" data-testid="fixture-banner">
          ▨ {t(FIXTURE_SCOPE === "nisar" ? "fixtures.banner.nisar" : "fixtures.banner")}
        </div>
      )}

      <div className="flex min-h-0 flex-1 flex-col md:flex-row">
        {/* map and time bar */}
        <div className="flex min-h-[230px] min-w-0 flex-1 flex-col">
          <div className="relative min-h-0 flex-1">
            <NisarMap overlays={overlays} geojsons={geojsons} pins={pins} point={mapPoint} compare={compare} view={view} onPick={onPick} onPin={onPin} ariaLabel={t("map.aria")} />
            {tour.open && <StoryTour step={tour.step} onStep={(s) => setTour({ open: true, step: s })} onClose={closeTour} fact={storyFact} onTry={() => searchRef.current?.focus()} />}
            <button
              type="button"
              onClick={() => setPanelOpen((o) => !o)}
              className="absolute right-3 top-3 z-[1000] rounded-md border border-slate-500 bg-slate-900/90 px-2 py-1 text-xs text-white md:hidden"
              aria-expanded={panelOpen}
            >
              {panelOpen ? t("panel.hide") : t("panel.show")}
            </button>
          </div>
          <TimeBar
            mode={mode}
            passes={passes}
            idx={passIdx}
            onIdx={setPassIdx}
            playing={playing}
            onPlaying={setPlaying}
            hist={{ value: histIdx, max: histMax, date: histDate, onChange: setHistIdx, datasets: availability.data?.datasets }}
            future={{ months: scenarioMonths }}
          />
        </div>

        {/* findings */}
        <aside
          className={`${panelOpen ? "h-[46vh]" : "h-0 overflow-hidden border-0"} shrink-0 overflow-y-auto border-t border-slate-700 bg-slate-900 md:h-auto md:w-[400px] md:border-l md:border-t-0`}
          aria-label={t("panel.findings")}
          data-testid="findings"
        >
          <div className="p-3">
            {point && (
              <div role="group" aria-label={t("panel.tabs")} className="mb-3 flex gap-1.5">
                {[
                  ["findings", t("panel.findings")],
                  ["spot", t("spot.title")],
                ].map(([k, label]) => (
                  <button key={k} type="button" onClick={() => setSideTab(k)} aria-pressed={sideTab === k} className={`flex-1 rounded-md border px-2 py-1 text-xs font-semibold ${sideTab === k ? "border-sky-300 bg-sky-600/40 text-white" : "border-slate-600 bg-slate-800 text-slate-200 hover:bg-slate-700"}`}>
                    {label}
                  </button>
                ))}
              </div>
            )}

            {point && sideTab === "spot" ? (
              <>
                {activeStory && (
                  <div className="mb-3 rounded-lg border border-fuchsia-300/50 bg-fuchsia-500/10 p-2.5" data-testid="story-pin-card">
                    <div className="text-[11px] font-bold uppercase tracking-wider text-fuchsia-100">{t("stories.pin")}</div>
                    {activeStory.name && <div className="text-sm font-semibold text-slate-100">{activeStory.name}</div>}
                    <p className="mt-1 text-xs text-slate-200">{activeStory.text}</p>
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    {activeStory.photo && <img src={activeStory.photo} alt={activeStory.photoAlt ?? ""} className="mt-2 max-h-40 rounded" />}
                  </div>
                )}
                <SpotCheck
                  key={`${point.lon.toFixed(5)},${point.lat.toFixed(5)}`}
                  point={point}
                  placeHint={placeHint}
                  passDates={passDates}
                  selectedDate={passes[passIdx]?.date}
                  onClose={() => {
                    setPoint(null);
                    setActiveStory(null);
                    setSideTab("findings");
                  }}
                  onCopy={copyLink}
                  copied={copied}
                  onHelp={openHelp}
                />
              </>
            ) : (
              <>
                <p className="mb-3 text-[11px] text-slate-400">{t("panel.click")}</p>
                {mode === "season" && (
                  <SeasonPanel
                    passesTier={passesTier}
                    rainTier={rainTier}
                    polTier={polTier}
                    idx={passIdx}
                    onIdx={setPassIdx}
                    playing={playing}
                    onPlaying={setPlaying}
                    polView={polView}
                    onPolView={setPolView}
                    compare={{
                      on: compareOn,
                      onToggle: (on) => {
                        setCompareOn(on);
                        if (on) {
                          setPlaying(false);
                          if (polView === "rgb") setPolView("flood");
                          setCmpBefore(Math.max(0, passIdx - 1 >= 0 ? passIdx - 1 : 0));
                          setCmpAfter(passIdx);
                          if (passIdx === 0 && passes.length > 1) setCmpAfter(passes.length - 1);
                        }
                      },
                      before: cmpBefore,
                      after: cmpAfter,
                      onBefore: setCmpBefore,
                      onAfter: setCmpAfter,
                      split,
                      onSplit: setSplit,
                    }}
                    opacity={opacity}
                    onOpacity={setOpacity}
                    onHelp={openHelp}
                  />
                )}
                {mode === "rhythm" && (
                  <>
                    <RhythmPanel tier={rhythmTier} exposureTier={exposureRhythm} onHelp={openHelp} onPlace={onZone} />
                    <HypothesesPanel items={hypotheses} onMode={(m) => MODES.includes(m) && goMode(m)} />
                  </>
                )}
                {mode === "motion" && (
                  <>
                    <MotionPanel tier={motionTier} scale={losScale} rhythmUnder={rhythmUnder} onRhythmUnder={setRhythmUnder} priorityTier={exposurePriority} onHelp={openHelp} onPlace={onZone} />
                    <HypothesesPanel items={hypotheses} onMode={(m) => MODES.includes(m) && goMode(m)} />
                  </>
                )}
                {mode === "history" && (
                  <HistoryPanel availabilityTier={availability} monthlyTier={monthly} rankTier={rank} trendTier={trend} date={histDate} onHelp={openHelp} />
                )}
                {mode === "future" && (
                  <FuturePanel
                    outlookTier={outlook}
                    scenariosTier={scenarios}
                    scenarioId={scenarioId}
                    onScenario={setScenarioId}
                    floodTier={flood}
                    onHelp={openHelp}
                    projectionNode={<ProjectionPanel proj={proj} year={projYear} setYear={setProjYear} demo={false} onDemo={null} />}
                  />
                )}
              </>
            )}
          </div>
        </aside>
      </div>

      <RadarCards open={radar.open} initial={radar.card} onClose={closeHelp} />
      <LimitsDrawer open={limitsOpen} onClose={closeLimits} />
    </div>
  );
}
