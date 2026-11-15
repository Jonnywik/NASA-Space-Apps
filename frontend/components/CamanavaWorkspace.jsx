"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import FuturePanel from "./FuturePanel";
import { CoherenceChangeCard, RainResponseCard } from "./ExtraOverlayCard";
import HistoryPanel from "./HistoryPanel";
import HypothesesPanel from "./HypothesesPanel";
import LimitsDrawer from "./LimitsDrawer";
import MapTools, { DEFAULT_LAYERS, MODE_FOR_OVERLAY, OVERLAY_FOR_MODE } from "./MapTools";
import MotionPanel from "./MotionPanel";
import NisarMap from "./NisarMap";
import ProjectionPanel from "./ProjectionPanel";
import RadarCards from "./RadarCards";
import RhythmPanel from "./RhythmPanel";
import SearchBox from "./SearchBox";
import SeasonPanel from "./SeasonPanel";
import SpotCheck, { SpotCard, useSpotData } from "./SpotCheck";
import StoryTour from "./StoryTour";
import TimeBar from "./TimeBar";
import ValidationPanel from "./ValidationPanel";
import { fmt } from "./ui";
import {
  AREA_ID,
  FIXTURES_ON,
  FIXTURE_SCOPE,
  checkTimelapseGif,
  getDownloads,
  getFloodScenario,
  getGroundMotion,
  getImergPasses,
  getNisarCoherenceChange,
  getNisarPasses,
  getNisarPolarization,
  getNisarRainResponse,
  getNisarRhythm,
  getNisarSoilMoisture,
  getOutlook,
  getPlaceBoundaries,
  getPlaceExposure,
  getRainfallDaily,
  getRainfallMonthly,
  getRainfallTrend,
  getScenarios,
  getSeasonRank,
  getTimelineAvailability,
  getValidation,
  getRobustness,
  getCrossTrack,
  searchPlaces,
  timelapseGifUrl,
} from "../utils/api";
import { useLang } from "../utils/LangContext";
import { LimitsProvider, useLimits, useReportMany } from "../utils/LimitsContext";
import { makeLosScale } from "../utils/losScale";
import { STORY_KEY, STORY_STEPS } from "../utils/storySteps";
import { buildQuery, MODES, readUrlState } from "../utils/urlState";
import useLatched from "../utils/useLatched";
import useProjection from "../utils/useProjection";
import { useTier } from "../utils/useTier";

const MODE_ORDER = ["rhythm", "season", "motion", "history", "future"];
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

function ModeIcon({ id, active }) {
  const stroke = active ? "#1E5B3A" : "#4A5850";
  const sw = active ? 2 : 1.75;
  if (id === "rhythm") {
    return (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M12 2.5C12 2.5 5 10.5 5 15a7 7 0 0 0 14 0c0-4.5-7-12.5-7-12.5Z" />
        <path d="M8.5 15.5a3.5 3.5 0 0 0 3.5 3.5" />
      </svg>
    );
  }
  if (id === "season") {
    return (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <rect x="3" y="5" width="18" height="16" rx="2" />
        <path d="M16 3v4M8 3v4M3 10h18" />
        <path d="M8 14h3v3H8z" />
      </svg>
    );
  }
  if (id === "motion") {
    return (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M3 18h18" />
        <path d="M7 14v4M12 10v8M17 12v6" />
        <path d="M12 4v3m0 0-2-2m2 2 2-2" />
      </svg>
    );
  }
  if (id === "history") {
    return (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M4 20V10M10 20V4M16 20v-7M21 20H3" />
      </svg>
    );
  }
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3 17l6-6 4 4 8-8" />
      <path d="M17 7h4v4" />
    </svg>
  );
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

  const [mode, setMode] = useState("rhythm");
  const [passIdx, setPassIdx] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [polView, setPolView] = useState("flood");
  const [opacity, setOpacity] = useState(0.75);
  const [showVeg, setShowVeg] = useState(true);
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
  const [limitsFocusDownloads, setLimitsFocusDownloads] = useState(false);
  const [radar, setRadar] = useState({ open: false, card: "water" });
  const [copied, setCopied] = useState(false);
  const [scenarioId, setScenarioId] = useState(null);
  const [histIdx, setHistIdx] = useState(0);
  const [futureMonthIdx, setFutureMonthIdx] = useState(8);
  const [projYear, setProjYear] = useState(2026);
  const [sheetExpanded, setSheetExpanded] = useState(false);
  const [searchHighlight, setSearchHighlight] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const [hypotheses, setHypotheses] = useState([]);
  const [stories, setStories] = useState([]);
  const [mapMode, setMapMode] = useState("streets");
  const [layers, setLayers] = useState(DEFAULT_LAYERS);
  const [toolsOpen, setToolsOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [extraOverlay, setExtraOverlay] = useState(null);
  const [showSmOverlay, setShowSmOverlay] = useState(false);

  const searchRef = useRef(null);
  const settingsRef = useRef(null);
  const pending = useRef({ pass: null, cmp: null });
  const nonce = useRef(0);

  const histMax = useMemo(() => {
    const d = new Date();
    return (d.getUTCFullYear() - 2000) * 12 + d.getUTCMonth();
  }, []);
  useEffect(() => setHistIdx(histMax), [histMax]);

  useEffect(() => {
    if (!settingsOpen) return undefined;
    const onKey = (e) => {
      if (e.key === "Escape") setSettingsOpen(false);
    };
    const onDown = (e) => {
      if (settingsRef.current && !settingsRef.current.contains(e.target)) {
        setSettingsOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("mousedown", onDown);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mousedown", onDown);
    };
  }, [settingsOpen]);

  // ---- data ---------------------------------------------------------------------------------
  const passesTier = useTier(() => getNisarPasses(AREA_ID), []);
  const passes = useMemo(() => passesTier.data?.passes ?? [], [passesTier.data]);
  const passDates = useMemo(() => passes.map((p) => p.date), [passes]);
  const rainStart = passDates.length ? addDays(passDates[0], -14) : null;
  const rainEnd = passDates.length ? passDates[passDates.length - 1] : null;
  const rainTier = useTier(rainStart ? () => getRainfallDaily(AREA_ID, rainStart, rainEnd) : null, [rainStart, rainEnd]);
  const imergTier = useTier(() => getImergPasses(AREA_ID, true), []);
  const boundariesTier = useTier(() => getPlaceBoundaries("barangay"), []);

  const needRhythm = useLatched(mode === "rhythm" || mode === "motion");
  const rhythmTier = useTier(needRhythm ? () => getNisarRhythm(AREA_ID) : null, [needRhythm]);
  const validationTier = useTier(needRhythm ? () => getValidation(AREA_ID) : null, [needRhythm]);
  const robustnessTier = useTier(needRhythm ? () => getRobustness(AREA_ID) : null, [needRhythm]);
  const crossTrackTier = useTier(needRhythm ? () => getCrossTrack(AREA_ID) : null, [needRhythm]);
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

  const needRainResp = useLatched(extraOverlay === "rainResponse");
  const rainRespTier = useTier(needRainResp ? () => getNisarRainResponse(AREA_ID) : null, [needRainResp]);
  const needCohChange = useLatched(extraOverlay === "coherenceChange");
  const cohChangeTier = useTier(needCohChange ? () => getNisarCoherenceChange(AREA_ID) : null, [needCohChange]);
  const needSoilMoisture = useLatched(mode === "season");
  const soilMoistureTier = useTier(needSoilMoisture ? () => getNisarSoilMoisture(AREA_ID) : null, [needSoilMoisture]);
  const downloadsTier = useTier(() => getDownloads(AREA_ID), []);
  const timelapseTier = useTier(needSoilMoisture ? () => checkTimelapseGif(AREA_ID) : null, [needSoilMoisture]);

  const { spot: spotTier, briefing: briefingTier } = useSpotData(point);

  useReportMany([
    ["passes", t("season.title"), passesTier.data],
    ["rain", t("season.rain"), rainTier.data],
    ["imerg", t("imerg.title"), imergTier.data],
    ["rhythm", t("rhythm.title"), rhythmTier.data],
    ["rain-resp", t("rainResp.title"), rainRespTier.data],
    ["coh-change", t("cohChange.title"), cohChangeTier.data],
    ["soil-moisture", t("sm.title"), soilMoistureTier.data],
    ["validation", t("validation.title"), validationTier.data],
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

  useEffect(() => {
    if (scenarios.data?.scenarios?.length && !scenarioId) setScenarioId(scenarios.data.scenarios[0].id);
  }, [scenarios.data, scenarioId]);

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
    if (u.point) setPoint(u.point);
    pending.current = { pass: u.pass, cmp: u.cmp };
    const dismissed = safeStorage((s) => s.getItem(STORY_KEY)) === "1";
    if (!dismissed && !u.mode && !u.point) setTour({ open: true, step: 0 });
    setHydrated(true);
  }, []);

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
    setExtraOverlay(null);
    setShowSmOverlay(false);
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

  // ---- mode & spot interactions -------------------------------------------------------------
  function goMode(m) {
    if (tour.open) closeTour();
    setBare(false);
    setExtraOverlay(null);
    setShowSmOverlay(false);
    setMode(m);
    setSideTab("findings");
  }

  const openSpot = useCallback((pt, hint = null, story = null) => {
    setPoint(pt);
    setPlaceHint(hint);
    setActiveStory(story);
    // Keep desktop showing floating SpotCard over the map until user clicks "Full details".
    setSideTab("findings");
  }, []);

  const clearSpot = useCallback(() => {
    setPoint(null);
    setPlaceHint(null);
    setActiveStory(null);
    setSideTab("findings");
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
  const activeSmPass = useMemo(
    () => (soilMoistureTier.data?.passes ?? []).find((p) => p.date === passes[passIdx]?.date) ?? null,
    [soilMoistureTier.data, passes, passIdx],
  );
  const effectiveSmOverlay = !extraOverlay && mode === "season" && !compareOn && showSmOverlay && Boolean(activeSmPass?.overlayUrl);
  const extraOverlayKind = extraOverlay ?? (effectiveSmOverlay ? "soilMoisture" : null);
  const extraLegend =
    extraOverlay === "rainResponse"
      ? rainRespTier.data?.legend
      : extraOverlay === "coherenceChange"
        ? cohChangeTier.data?.legend
        : effectiveSmOverlay
          ? soilMoistureTier.data?.legend
          : null;

  const overlays = useMemo(() => {
    if (bare) return [];
    const out = [];
    if (extraOverlay === "rainResponse") {
      if (rainRespTier.data?.overlayUrl) {
        out.push({ key: "extra-rain-response", url: rainRespTier.data.overlayUrl, pane: "afterPane", opacity, bounds: rainRespTier.data.bounds ?? bounds, alt: t("rainResp.title") });
      }
      return out;
    }
    if (extraOverlay === "coherenceChange") {
      if (cohChangeTier.data?.overlayUrl) {
        out.push({ key: "extra-coherence-change", url: cohChangeTier.data.overlayUrl, pane: "afterPane", opacity, bounds: cohChangeTier.data.bounds ?? bounds, alt: t("cohChange.title") });
      }
      return out;
    }
    if (mode === "season" && passes.length) {
      const cur = passes[passIdx];
      const url = (p) => (polView === "hh" ? p?.backscatterUrl : p?.overlayUrl);
      const veg = (p, pane, k) =>
        showVeg && polView === "flood" && p?.floodedVegetationUrl ? [{ key: `${k}-veg-${p.id}`, url: p.floodedVegetationUrl, pane, opacity, bounds, alt: `${p.date} vegetation` }] : [];
      if (compareOn) {
        const b = passes[cmpBefore];
        const a = passes[cmpAfter];
        out.push({ key: `b-${b?.id}-${polView}`, url: url(b), pane: "beforePane", opacity, bounds, alt: `${b?.date}` }, ...veg(b, "beforePane", "b"));
        out.push({ key: `a-${a?.id}-${polView}`, url: url(a), pane: "afterPane", opacity, bounds, alt: `${a?.date}` }, ...veg(a, "afterPane", "a"));
      } else if (effectiveSmOverlay) {
        out.push({ key: `sm-${cur?.id}`, url: activeSmPass.overlayUrl, pane: "afterPane", opacity, bounds: soilMoistureTier.data?.bounds ?? bounds, alt: t("sm.title") });
      } else if (polView === "rgb") {
        const rgb = polTier.data?.rgbUrl ?? cur?.polarizationUrl;
        if (rgb) out.push({ key: `rgb-${cur?.id}`, url: rgb, pane: "afterPane", opacity, bounds: polTier.data?.bounds ?? bounds, alt: "RGB" });
      } else {
        out.push({ key: `p-${cur?.id}-${polView}`, url: url(cur), pane: "afterPane", opacity, bounds, alt: `${cur?.date}` }, ...veg(cur, "afterPane", "p"));
      }
    }
    if ((mode === "rhythm" || (mode === "motion" && rhythmUnder)) && rhythmTier.data?.overlayUrl) {
      out.push({ key: "rhythm", url: rhythmTier.data.overlayUrl, pane: "rhythmPane", opacity, bounds: rhythmTier.data.bounds ?? bounds, alt: t("rhythm.title") });
    }
    return out;
  }, [bare, extraOverlay, rainRespTier.data, cohChangeTier.data, effectiveSmOverlay, activeSmPass, soilMoistureTier.data, mode, passes, passIdx, polView, showVeg, compareOn, cmpBefore, cmpAfter, opacity, bounds, polTier.data, rhythmTier.data, rhythmUnder, t]);

  const losScale = useMemo(() => makeLosScale(motionTier.data?.heatmapGeojson), [motionTier.data]);
  const geojsons = useMemo(() => {
    if (extraOverlay) return [];
    const out = [];
    if (mode === "motion" && losScale && motionTier.data?.heatmapGeojson) {
      out.push({
        key: "los",
        data: motionTier.data.heatmapGeojson,
        pane: "motionPane",
        style: (f) => {
          const c = losScale.color(f?.properties?.[losScale.prop]);
          return { color: c, weight: 0.4, fillColor: c, fillOpacity: Math.min(0.95, opacity * (rhythmUnder ? 0.65 : 0.85)) };
        },
        tooltip: (f) => `${t("motion.tip")}: ${fmt(f?.properties?.[losScale.prop]) ?? "—"} ${losScale.unit}`,
      });
    }
    if (mode === "future" && proj.geojson) {
      out.push({
        key: "proj",
        data: proj.geojson,
        pane: "projectionPane",
        style: { color: "#6B5A9E", weight: 2, dashArray: "4 4", fillColor: "#6B5A9E", fillOpacity: 0.28 },
        tooltip: (f) => `${t("future.projection.tip")} ${f.properties?.year ?? ""}: ${fmt(f.properties?.areaKm2) ?? "—"} km²`,
      });
    }
    return out;
  }, [extraOverlay, mode, losScale, motionTier.data, rhythmUnder, opacity, proj.geojson, t]);

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
  const closeLimits = useCallback(() => {
    setLimitsOpen(false);
    setLimitsFocusDownloads(false);
  }, []);

  function onZone(z) {
    searchPlaces(z.name, 1)
      .then((d) => d.results?.[0] && onSearchSelect(d.results[0]))
      .catch(() => {});
  }

  const railLabels = {
    season: t("mode.season"),
    rhythm: t("mode.rhythm"),
    motion: t("mode.motion"),
    history: t("mode.history"),
    future: t("mode.future"),
  };
  const phoneShortLabels = {
    season: t("mode.season"),
    rhythm: t("rail.rhythm.short"),
    motion: t("rail.motion.short"),
    history: t("mode.history"),
    future: t("mode.future"),
  };
  const histDate = histDateFor(histIdx);
  const scenarioMonths = scenarios.data?.scenarios?.find((s) => s.id === scenarioId)?.months ?? scenarios.data?.scenarios?.[0]?.months ?? [];
  const areaTitle = mode === "history" ? t("header.area.history") : mode === "future" ? t("header.area.future") : t("header.area.season");

  const activeOverlay = extraOverlay ?? OVERLAY_FOR_MODE[mode] ?? "rhythm";
  const isDemoOverlay =
    (extraOverlay === "rainResponse" && rainRespTier.data?.dataKind === "synthetic") ||
    (extraOverlay === "coherenceChange" && cohChangeTier.data?.dataKind === "synthetic") ||
    (effectiveSmOverlay && soilMoistureTier.data?.dataKind === "synthetic") ||
    (!extraOverlay &&
      ((mode === "rhythm" && rhythmTier.data?.dataKind === "synthetic") ||
        (mode === "season" && !effectiveSmOverlay && passesTier.data?.dataKind === "synthetic") ||
        (mode === "motion" && motionTier.data?.dataKind === "synthetic") ||
        (mode === "future" && (flood.data?.dataKind === "synthetic" || scenarios.data?.dataKind === "synthetic"))));

  const resetMapControls = () => {
    setMapMode("streets");
    setLayers(DEFAULT_LAYERS);
    setShowVeg(true);
    setOpacity(0.75);
    setExtraOverlay(null);
    setShowSmOverlay(false);
  };

  const renderFindingsContent = () => (
    <>
      {point && sideTab === "spot" ? (
        <>
          {activeStory && (
            <div className="mb-3 rounded-xl border border-[#C2A5CF] bg-[#F6F1F9] p-3 text-[#16231B]" data-testid="story-pin-card">
              <div className="text-[11px] font-bold uppercase tracking-[0.06em] text-[#5B2370]">{t("stories.pin")}</div>
              {activeStory.name && <div className="mt-0.5 text-[14px] font-semibold">{activeStory.name}</div>}
              <p className="mt-1 text-[13px] leading-relaxed text-[#4A5850]">{activeStory.text}</p>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              {activeStory.photo && <img src={activeStory.photo} alt={activeStory.photoAlt ?? ""} className="mt-2 max-h-40 rounded-lg" />}
            </div>
          )}
          <SpotCheck
            key={`${point.lon.toFixed(5)},${point.lat.toFixed(5)}`}
            point={point}
            placeHint={placeHint}
            selectedDate={passes[passIdx]?.date}
            spotTier={spotTier}
            briefingTier={briefingTier}
            imergTier={imergTier}
            onBack={() => setSideTab("findings")}
            onClose={clearSpot}
            onCopy={copyLink}
            copied={copied}
            onHelp={openHelp}
          />
        </>
      ) : (
        <>
          {point && (
            <div className="mb-3 min-[900px]:hidden">
              <SpotCard
                key={`${point.lon},${point.lat}`}
                point={point}
                placeHint={placeHint}
                spotTier={spotTier}
                imergTier={imergTier}
                mode={mode}
                selectedDate={passes[passIdx]?.date}
                onClose={clearSpot}
                onOpenDetails={() => setSideTab("spot")}
              />
            </div>
          )}

          {extraOverlay === "rainResponse" && (
            <RainResponseCard tier={rainRespTier} onSources={() => setLimitsOpen(true)} />
          )}

          {extraOverlay === "coherenceChange" && (
            <CoherenceChangeCard tier={cohChangeTier} onSources={() => setLimitsOpen(true)} />
          )}

          {!extraOverlay && mode === "rhythm" && (
            <>
              <RhythmPanel
                tier={rhythmTier}
                exposureTier={exposureRhythm}
                passes={passes}
                imergTier={imergTier}
                onHelp={openHelp}
                onPlace={onZone}
                onSources={() => setLimitsOpen(true)}
              />
              <ValidationPanel tier={validationTier} robustness={robustnessTier} crossTrack={crossTrackTier} />
              <HypothesesPanel items={hypotheses} onMode={(m) => MODES.includes(m) && goMode(m)} />
            </>
          )}

          {!extraOverlay && mode === "season" && (
            <SeasonPanel
              passesTier={passesTier}
              rainTier={rainTier}
              imergTier={imergTier}
              polTier={polTier}
              soilMoistureTier={soilMoistureTier}
              showSmOverlay={showSmOverlay}
              onToggleSmOverlay={setShowSmOverlay}
              timelapseUrl={timelapseGifUrl(AREA_ID)}
              timelapseAvailable={Boolean(timelapseTier.data)}
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
                    setCmpAfter(passIdx === 0 && passes.length > 1 ? passes.length - 1 : passIdx);
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
              onSources={() => setLimitsOpen(true)}
            />
          )}

          {!extraOverlay && mode === "motion" && (
            <>
              <MotionPanel
                tier={motionTier}
                scale={losScale}
                rhythmUnder={rhythmUnder}
                onRhythmUnder={setRhythmUnder}
                priorityTier={exposurePriority}
                onHelp={openHelp}
                onPlace={onZone}
                onSources={() => setLimitsOpen(true)}
              />
              <ValidationPanel tier={validationTier} robustness={robustnessTier} crossTrack={crossTrackTier} />
              <HypothesesPanel items={hypotheses} onMode={(m) => MODES.includes(m) && goMode(m)} />
            </>
          )}

          {!extraOverlay && mode === "history" && (
            <HistoryPanel
              availabilityTier={availability}
              monthlyTier={monthly}
              rankTier={rank}
              trendTier={trend}
              date={histDate}
              onHelp={openHelp}
              onSources={() => setLimitsOpen(true)}
            />
          )}

          {!extraOverlay && mode === "future" && (
            <FuturePanel
              outlookTier={outlook}
              scenariosTier={scenarios}
              scenarioId={scenarioId}
              onScenario={setScenarioId}
              floodTier={flood}
              activeMonthIdx={futureMonthIdx}
              onHelp={openHelp}
              onSources={() => setLimitsOpen(true)}
              projectionNode={<ProjectionPanel proj={proj} year={projYear} setYear={setProjYear} demo={false} onDemo={null} />}
            />
          )}
        </>
      )}
    </>
  );

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-[#F2F5F1] text-[#16231B]" data-testid="workspace">
      {/* Header */}
      <header className="relative z-[1200] flex h-[56px] shrink-0 items-center justify-between border-b border-[#DCE3DB] bg-white px-4 min-[900px]:h-[58px] min-[900px]:px-5">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[#1E5B3A] text-white" aria-hidden="true">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2.5C12 2.5 5.5 9.5 5.5 14.5a6.5 6.5 0 0 0 13 0c0-5-6.5-12-6.5-12Z" />
                <path d="M12 10v8M9 14l3-2 3 2" />
              </svg>
            </span>
            <span className="text-[17px] font-bold tracking-[0.14em] text-[#16231B]">TANAW</span>
          </div>
          <span className="hidden h-5 w-px bg-[#DCE3DB] sm:inline-block" aria-hidden="true" />
          <span className="line-clamp-2 min-w-0 text-[12px] font-medium leading-tight text-[#4A5850] sm:line-clamp-none sm:truncate sm:text-[13px]">{areaTitle}</span>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setTour({ open: true, step: 0 })}
            aria-current={tour.open ? "page" : undefined}
            className={`hidden h-9 items-center gap-1.5 rounded-lg border px-3 text-[13px] font-semibold transition-colors min-[900px]:inline-flex ${
              tour.open ? "border-[#1E5B3A] bg-[#1E5B3A] text-white" : "border-[#1E5B3A] bg-white text-[#1E5B3A] hover:bg-[#E3EFE7]"
            }`}
            data-testid="tab-story"
          >
            {t("header.tour")}
          </button>

          <button
            type="button"
            onClick={() => setLimitsOpen(true)}
            className="hidden h-9 items-center rounded-lg border border-[#DCE3DB] bg-white px-3 text-[13px] font-medium text-[#16231B] transition-colors hover:bg-[#F2F5F1] min-[900px]:inline-flex"
            data-testid="open-limits"
          >
            {t("header.sources")} ({limitCount})
          </button>

          <button
            type="button"
            onClick={() => {
              setLimitsFocusDownloads(true);
              setLimitsOpen(true);
            }}
            className="hidden h-9 items-center rounded-lg border border-[#DCE3DB] bg-white px-3 text-[13px] font-medium text-[#16231B] transition-colors hover:bg-[#F2F5F1] min-[900px]:inline-flex"
            data-testid="open-downloads"
          >
            {t("downloads.title")}
          </button>

          <div className="relative" ref={settingsRef}>
            <button
              type="button"
              onClick={() => setSettingsOpen((o) => !o)}
              aria-expanded={settingsOpen}
              aria-label={t("header.settings")}
              title={t("header.settings")}
              className={`flex h-11 w-11 items-center justify-center rounded-lg border transition-colors ${
                settingsOpen ? "border-[#1E5B3A] bg-[#E3EFE7] text-[#123B25]" : "border-[#DCE3DB] bg-white text-[#16231B] hover:bg-[#F2F5F1]"
              }`}
              data-testid="open-settings"
            >
              <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <circle cx="12" cy="12" r="3" />
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9c.26.6.79 1 1.44 1.07H21a2 2 0 0 1 0 4h-.09c-.65.07-1.18.47-1.51 1Z" />
              </svg>
            </button>

            {settingsOpen && (
              <div
                role="dialog"
                aria-label={t("header.settings")}
                className="absolute right-0 top-[50px] z-[1500] w-[280px] rounded-2xl border border-[#DCE3DB] bg-white p-3.5 text-[#16231B] shadow-[0_8px_24px_rgba(20,30,40,0.16)]"
                data-testid="settings-popover"
              >
                <div className="mb-3">
                  <div className="mb-1.5 text-[11px] font-bold uppercase tracking-[0.06em] text-[#4A5850]">{t("lang.label")}</div>
                  <div role="group" aria-label={t("lang.label")} className="grid grid-cols-2 gap-1.5">
                    {["en", "fil"].map((l) => (
                      <button
                        key={l}
                        type="button"
                        onClick={() => setLang(l)}
                        aria-pressed={lang === l}
                        className={`h-9 rounded-lg border text-[12px] font-semibold transition-colors ${
                          lang === l ? "border-[#1E5B3A] bg-[#E3EFE7] text-[#123B25]" : "border-[#DCE3DB] bg-white text-[#4A5850] hover:bg-[#F2F5F1]"
                        }`}
                        data-testid={`lang-${l}`}
                      >
                        {l === "en" ? "English (EN)" : "Filipino (FIL)"}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="mb-3 border-t border-[#DCE3DB] pt-2.5">
                  <div className="mb-1.5 text-[11px] font-bold uppercase tracking-[0.06em] text-[#4A5850]">{t("map.tools.mode")}</div>
                  <div className="grid grid-cols-2 gap-1.5">
                    {["streets", "minimal"].map((mm) => (
                      <button
                        key={mm}
                        type="button"
                        onClick={() => setMapMode(mm)}
                        aria-pressed={mapMode === mm}
                        className={`h-9 rounded-lg border text-[12px] font-medium ${
                          mapMode === mm ? "border-[#1E5B3A] bg-[#E3EFE7] font-semibold text-[#123B25]" : "border-[#DCE3DB] bg-white text-[#4A5850] hover:bg-[#F2F5F1]"
                        }`}
                      >
                        {t(`map.tools.mode.${mm}`)}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="flex flex-col gap-1.5 border-t border-[#DCE3DB] pt-2.5">
                  <button
                    type="button"
                    onClick={() => {
                      setSettingsOpen(false);
                      setTour({ open: true, step: 0 });
                    }}
                    className="flex h-9 items-center justify-between rounded-lg border border-[#DCE3DB] bg-white px-3 text-[12px] font-medium text-[#16231B] hover:bg-[#F2F5F1] min-[900px]:hidden"
                  >
                    <span>{t("header.tour")}</span>
                    <span aria-hidden="true">›</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setSettingsOpen(false);
                      setLimitsOpen(true);
                    }}
                    className="flex h-9 items-center justify-between rounded-lg border border-[#DCE3DB] bg-white px-3 text-[12px] font-medium text-[#16231B] hover:bg-[#F2F5F1] min-[900px]:hidden"
                  >
                    <span>{t("header.sources")} ({limitCount})</span>
                    <span aria-hidden="true">›</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setSettingsOpen(false);
                      openHelp("water");
                    }}
                    className="flex h-9 items-center justify-between rounded-lg border border-[#DCE3DB] bg-white px-3 text-[12px] font-medium text-[#16231B] hover:bg-[#F2F5F1]"
                  >
                    <span>{t("radar.button")}</span>
                    <span aria-hidden="true">?</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setSettingsOpen(false);
                      onRegional();
                    }}
                    className="flex min-h-[38px] items-center justify-between rounded-lg border border-[#DCE3DB] bg-[#F2F5F1] px-3 py-1.5 text-left text-[12px] font-medium text-[#16231B] hover:bg-[#E3EFE7]"
                    data-testid="open-regional"
                  >
                    <span>{t("header.regional")}</span>
                    <span aria-hidden="true">↗</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </header>

      {FIXTURES_ON && (
        <div role="status" className="border-b border-dashed border-[#7A5B00] bg-[#FFF6DE] px-3 py-1 text-center text-[12px] font-semibold text-[#7A5B00]" data-testid="fixture-banner">
          {t(FIXTURE_SCOPE === "nisar" ? "fixtures.banner.nisar" : "fixtures.banner")}
        </div>
      )}

      {/* Main workspace row */}
      <div className="flex min-h-0 flex-1 flex-col min-[900px]:flex-row">
        {/* Desktop left icon rail */}
        <aside className="hidden w-[84px] shrink-0 flex-col justify-between border-r border-[#DCE3DB] bg-white py-2.5 min-[900px]:flex">
          <nav aria-label={t("nav.modes")} className="flex flex-col gap-1 px-1.5" data-testid="mode-tabs">
            {MODE_ORDER.map((m) => {
              const active = mode === m && !tour.open;
              return (
                <button
                  key={m}
                  type="button"
                  onClick={() => goMode(m)}
                  aria-current={active ? "page" : undefined}
                  className={`relative flex min-h-[58px] flex-col items-center justify-center gap-1 rounded-xl px-1 py-1.5 text-center text-[11px] leading-tight transition-colors ${
                    active ? "bg-[#E3EFE7] font-semibold text-[#123B25]" : "font-medium text-[#4A5850] hover:bg-[#F2F5F1] hover:text-[#16231B]"
                  }`}
                  data-testid={`tab-${m}`}
                >
                  {active && <span className="absolute left-0 top-2 bottom-2 w-[3px] rounded-r bg-[#1E5B3A]" aria-hidden="true" />}
                  <ModeIcon id={m} active={active} />
                  <span>{railLabels[m]}</span>
                </button>
              );
            })}
          </nav>

          <div className="flex flex-col gap-1 border-t border-[#DCE3DB] px-1.5 pt-2.5">
            <button
              type="button"
              onClick={() => setToolsOpen((o) => !o)}
              aria-pressed={toolsOpen}
              className={`flex min-h-[48px] flex-col items-center justify-center gap-0.5 rounded-xl px-1 py-1 text-[11px] font-medium ${
                toolsOpen ? "bg-[#E3EFE7] text-[#123B25]" : "text-[#4A5850] hover:bg-[#F2F5F1]"
              }`}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <polygon points="12 2 2 7 12 12 22 7 12 2" />
                <polyline points="2 12 12 17 22 12" />
                <polyline points="2 17 12 22 22 17" />
              </svg>
              <span>{t("rail.layers")}</span>
            </button>

            <button
              type="button"
              onClick={() => openHelp("water")}
              className="flex min-h-[48px] flex-col items-center justify-center gap-0.5 rounded-xl px-1 py-1 text-[11px] font-medium text-[#4A5850] hover:bg-[#F2F5F1]"
              data-testid="open-radar"
            >
              <span className="flex h-5 w-5 items-center justify-center rounded-full border border-[#DCE3DB] text-[11px] font-bold text-[#1E5B3A]" aria-hidden="true">
                ?
              </span>
              <span className="text-[10px] leading-tight">{t("radar.button")}</span>
            </button>
          </div>
        </aside>

        {/* Map column + desktop TimeBar */}
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          <div
            className={`relative shrink-0 min-[900px]:min-h-0 min-[900px]:flex-1 ${
              sheetExpanded ? "h-[160px]" : "h-[310px]"
            }`}
          >
            <NisarMap
              overlays={overlays}
              geojsons={geojsons}
              pins={pins}
              point={mapPoint}
              compare={compare}
              view={view}
              onPick={onPick}
              onPin={onPin}
              ariaLabel={t("map.aria")}
              mapMode={mapMode}
              layers={layers}
              boundariesGeojson={boundariesTier.data}
              mode={mode}
              passCount={passes.length}
              showVeg={showVeg}
              losScale={losScale}
              isDemoOverlay={isDemoOverlay}
              extraOverlayKind={extraOverlayKind}
              extraLegend={extraLegend}
              topLeftSearch={<SearchBox onSelect={onSearchSelect} inputRef={searchRef} highlight={searchHighlight} />}
              topRightTools={
                <MapTools
                  open={toolsOpen}
                  onToggle={() => setToolsOpen((o) => !o)}
                  onClose={() => setToolsOpen(false)}
                  mapMode={mapMode}
                  onMapMode={setMapMode}
                  overlay={activeOverlay}
                  onOverlay={(ov) => {
                    if (ov === "rainResponse" || ov === "coherenceChange") {
                      setExtraOverlay(ov);
                      setShowSmOverlay(false);
                      setSideTab("findings");
                      return;
                    }
                    setExtraOverlay(null);
                    const nextMode = MODE_FOR_OVERLAY[ov];
                    if (nextMode) goMode(nextMode);
                  }}
                  showVeg={showVeg}
                  onShowVeg={setShowVeg}
                  opacity={opacity}
                  onOpacity={setOpacity}
                  layers={layers}
                  onToggleLayer={(k) => setLayers((prev) => ({ ...prev, [k]: !prev[k] }))}
                  onReset={resetMapControls}
                  isDemoOverlay={isDemoOverlay}
                />
              }
              bottomLeftSpot={
                point ? (
                  <div className="hidden min-[900px]:block">
                    <SpotCard
                      key={`${point.lon},${point.lat}`}
                      point={point}
                      placeHint={placeHint}
                      spotTier={spotTier}
                      imergTier={imergTier}
                      mode={mode}
                      selectedDate={passes[passIdx]?.date}
                      onClose={clearSpot}
                      onOpenDetails={() => setSideTab("spot")}
                    />
                  </div>
                ) : null
              }
            />

            {tour.open && (
              <StoryTour
                step={tour.step}
                onStep={(s) => setTour({ open: true, step: s })}
                onClose={closeTour}
                fact={storyFact}
                onTry={() => searchRef.current?.focus()}
              />
            )}
          </div>

          <div className="hidden shrink-0 min-[900px]:block">
            <TimeBar
              mode={mode}
              passes={passes}
              idx={passIdx}
              onIdx={setPassIdx}
              playing={playing}
              onPlaying={setPlaying}
              rainDays={rainTier.data?.days ?? []}
              motionEpochs={motionTier.data?.epochs ?? []}
              hist={{ value: histIdx, max: histMax, date: histDate, onChange: setHistIdx, datasets: availability.data?.datasets }}
              future={{
                months: scenarioMonths,
                activeIdx: futureMonthIdx,
                onSelectMonth: setFutureMonthIdx,
              }}
            />
          </div>
        </div>

        {/* Findings panel (desktop aside + phone bottom sheet) */}
        <aside
          className="relative z-[1050] -mt-[14px] flex min-h-0 flex-1 flex-col overflow-hidden rounded-t-[18px] border-t border-[#DCE3DB] bg-white shadow-[0_-4px_16px_rgba(20,30,40,0.10)] min-[900px]:mt-0 min-[900px]:w-[440px] min-[900px]:flex-none min-[900px]:rounded-none min-[900px]:border-l min-[900px]:border-t-0 min-[900px]:shadow-none xl:w-[460px]"
          aria-label={t("panel.findings")}
          data-testid="findings"
        >
          <div className="flex shrink-0 justify-center py-2 min-[900px]:hidden">
            <button
              type="button"
              onClick={() => setSheetExpanded((e) => !e)}
              aria-expanded={sheetExpanded}
              aria-label={sheetExpanded ? t("panel.hide") : t("panel.show")}
              className="flex h-5 w-16 items-center justify-center rounded-full"
            >
              <span className="h-1 w-10 rounded-full bg-[#C9D1C7]" />
            </button>
          </div>

          <div className="flex min-h-0 flex-1 flex-col overflow-y-auto px-4 pb-5 pt-1 min-[900px]:p-5">
            {renderFindingsContent()}
          </div>

          <div className="shrink-0 min-[900px]:hidden">
            <TimeBar
              mode={mode}
              passes={passes}
              idx={passIdx}
              onIdx={setPassIdx}
              playing={playing}
              onPlaying={setPlaying}
              rainDays={rainTier.data?.days ?? []}
              motionEpochs={motionTier.data?.epochs ?? []}
              hist={{ value: histIdx, max: histMax, date: histDate, onChange: setHistIdx, datasets: availability.data?.datasets }}
              future={{
                months: scenarioMonths,
                activeIdx: futureMonthIdx,
                onSelectMonth: setFutureMonthIdx,
              }}
            />
          </div>
        </aside>
      </div>

      {/* Mobile bottom tab bar (<900px) */}
      <nav
        aria-label={t("nav.modes")}
        className="flex h-[56px] shrink-0 items-stretch border-t border-[#DCE3DB] bg-white min-[900px]:hidden"
      >
        {MODE_ORDER.map((m) => {
          const active = mode === m && !tour.open;
          return (
            <button
              key={m}
              type="button"
              onClick={() => goMode(m)}
              aria-current={active ? "page" : undefined}
              className={`relative flex min-h-[52px] flex-1 flex-col items-center justify-center gap-0.5 text-[11px] leading-none ${
                active ? "bg-[#E3EFE7]/60 font-semibold text-[#1E5B3A]" : "font-medium text-[#4A5850]"
              }`}
            >
              <ModeIcon id={m} active={active} />
              <span>{phoneShortLabels[m]}</span>
            </button>
          );
        })}
      </nav>

      <RadarCards open={radar.open} initial={radar.card} onClose={closeHelp} />
      <LimitsDrawer open={limitsOpen} onClose={closeLimits} downloadsTier={downloadsTier} focusDownloads={limitsFocusDownloads} />
    </div>
  );
}
