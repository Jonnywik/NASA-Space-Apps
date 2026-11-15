// frontend/utils/api.js  -  the only place that talks to the Tanaw backend.
// The backend must be running:  uvicorn app.main:app --reload   (inside backend/)

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

// Study area of the submission (docs/API_CONTRACT.md, "Shared constants").
export const AREA_ID = "camanava_2026";

// Dev fixtures: ONLY when the app is started with NEXT_PUBLIC_USE_FIXTURES=1. Every fixture answer
// carries dataKind "synthetic" and the UI shows a banner plus the synthetic badge. Without the flag
// this constant is false at build time and the fixture module is never bundled.
// "1" = all v5.1 endpoints; "nisar" = only /nisar/* and camanava_2026 ground motion (the rest is the real backend).
export const FIXTURE_SCOPE =
  process.env.NEXT_PUBLIC_USE_FIXTURES === "1" ? "all" : process.env.NEXT_PUBLIC_USE_FIXTURES === "nisar" ? "nisar" : null;
export const FIXTURES_ON = FIXTURE_SCOPE !== null;

// ---------------------------------------------------------------------------
// Errors. The backend answers "no data yet" with HTTP 404/409 and a body like
//   { "detail": { "code": "data_unavailable", "message": "..." } }
// That is a NORMAL state for our app, not a crash, so every failed call throws
// an ApiError that carries the HTTP status and the backend's code.
// ---------------------------------------------------------------------------
export class ApiError extends Error {
  constructor(message, { status = 0, code = null, detail = null } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status; // HTTP status. 0 = we never reached the server
    this.code = code; // e.g. "data_unavailable", "review_required"
    this.detail = detail;
  }
}

// Turn any error into one of the states the UI knows how to show:
//   unavailable | review | invalid | offline | outside | upstream | error
export function classifyError(err) {
  if (!(err instanceof ApiError)) return "error";
  if (err.status === 0) return "offline";
  switch (err.code) {
    case "outside_coverage":
      return "outside";
    case "upstream_unavailable":
      return "upstream";
    case "invalid_request":
      return "invalid";
    case "data_unavailable":
    case "unknown_area":
    case "unknown_event":
    case "unknown_scenario":
    case "unsupported_year":
    case "year_required":
    case "roads_unavailable":
      return "unavailable";
    case "review_required":
      return "review";
    case "invalid_product":
    case "stale_exposure":
    case "mismatched_run":
    case "invalid_identifier_or_catalog":
      return "invalid";
    default:
      if (err.status === 503) return "upstream";
      return err.status === 404 ? "unavailable" : "error";
  }
}

function queryString(params = {}) {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") q.set(key, String(value));
  });
  const s = q.toString();
  return s ? `?${s}` : "";
}

async function request(path, params, label, responseType = "json") {
  // Composed facts cannot be mixed with a map supplied by unrelated development fixtures.
  if (FIXTURES_ON && ["/api/v1/spot-check", "/api/v1/briefing/place", "/api/v1/validation"].includes(path)) {
    throw new ApiError("This result is unavailable with synthetic frontend fixtures; use the backend data mode.", { status: 404, code: "data_unavailable" });
  }
  if (process.env.NEXT_PUBLIC_USE_FIXTURES === "1" || process.env.NEXT_PUBLIC_USE_FIXTURES === "nisar") {
    const nisarOnly = process.env.NEXT_PUBLIC_USE_FIXTURES === "nisar";
    if (!nisarOnly || path.startsWith("/api/v1/nisar") || path.startsWith("/api/v1/ground-motion")) {
      const { fixtureResponse } = await import("./devFixtures");
      const hit = await fixtureResponse(path, params ?? {});
      if (hit !== undefined) return hit;
    }
  }
  let res;
  try {
    res = await fetch(`${API_BASE}${path}${queryString(params)}`);
  } catch {
    throw new ApiError("Cannot reach the backend. Is uvicorn running on port 8000?", {
      status: 0,
      code: "offline",
    });
  }
  if (!res.ok) {
    let body = null;
    try {
      body = await res.json();
    } catch {
      /* body was not JSON */
    }
    const detail = body?.detail ?? null;
    const code = detail && typeof detail === "object" ? detail.code ?? null : null;
    const text =
      (detail && typeof detail === "object" && detail.message) ||
      (typeof detail === "string" && detail) ||
      null;
    throw new ApiError(`${label} (HTTP ${res.status})${text ? `: ${text}` : ""}`, {
      status: res.status,
      code,
      detail,
    });
  }
  return responseType === "blob" ? res.blob() : res.json();
}

// Backend picture/file addresses come without the server name; add it here.
export function assetUrl(path) {
  if (!path) return path;
  return /^(https?:|data:|blob:)/.test(path) ? path : API_BASE + path;
}

function withAssetUrls(data) {
  if (data?.assets) {
    Object.values(data.assets).forEach((a) => {
      if (a?.url) a.url = assetUrl(a.url);
    });
  }
  return data;
}

// Does this event have a published product? (events carry `capabilities`)
// key: "coherence-change" | "change-frequency" | "building-exposure" |
//      "ground-motion" | "biomass" | "scenario-inputs" | "projection"
export function tierAvailable(event, key) {
  return event?.capabilities?.[key]?.available === true;
}

// ---------------------------------------------------------------------------
// Tier 1 - flood (working today)
// ---------------------------------------------------------------------------

// List of events: [{ id, name, aoi, beforeDate, afterDate, ready, capabilities }, ...]
export async function getEvents() {
  return request("/api/v1/events", {}, "Could not load events");
}

// One event. Same shape as mockFloodData, plus:
//   floodGeojson          -> draw this on the map (red flood shapes)
//   overlays              -> null, or { beforeUrl, afterUrl, bounds } for the slider
//                            bounds = [[south, west], [north, east]]  (Leaflet order)
export async function getFloodExtent(eventId) {
  const data = await request(
    "/api/v1/flood-extent",
    { event: eventId },
    `Could not load "${eventId}"`
  );
  if (data.overlays) {
    data.overlays.beforeUrl = assetUrl(data.overlays.beforeUrl);
    data.overlays.afterUrl = assetUrl(data.overlays.afterUrl);
  }
  return data;
}

// ---------------------------------------------------------------------------
// Tier 2 - coherence change (needs a published AND reviewed product)
// product "change"    -> { stats.km2Changed, stats.changedPixelCount, coverage, warnings,
//                          changeGeojson, exposure, assets, dataStatus, ... }
// product "frequency" -> { assets.frequency / detectionCount / validComparisonCount, ... }
// ---------------------------------------------------------------------------
export async function getCoherenceLoss(eventId, { product = "change", runId, regionId, exposureRunId } = {}) {
  const data = await request(
    "/api/v1/coherence-loss",
    { event: eventId, product, runId, regionId, exposureRunId },
    `Could not load change data for "${eventId}"`
  );
  return withAssetUrls(data);
}

// ---------------------------------------------------------------------------
// Tier 3 - ground motion, projection, briefing
// ---------------------------------------------------------------------------

// Whole displacement product (assets = GeoTIFF rasters, see assets.*.url)
export async function getGroundMotion(eventId, runId) {
  return withAssetUrls(
    await request("/api/v1/ground-motion", { event: eventId, runId }, `Could not load ground motion for "${eventId}"`)
  );
}

// Click-a-pixel time series -> { point: { status, epochs[], displacementMm[], rateMmPerYear, ... } }
export async function getGroundMotionPoint(eventId, lon, lat, runId) {
  return request(
    "/api/v1/ground-motion/point",
    { event: eventId, lon, lat, runId },
    "Could not sample that point"
  );
}

// Year slider data. scenarioId and year are required by the backend.
export async function getProjection(eventId, scenarioId, year, runId) {
  return withAssetUrls(
    await request(
      "/api/v1/projection",
      { event: eventId, scenarioId, year, runId },
      `Could not load the ${year} projection`
    )
  );
}

// Briefing paragraph -> { text, facts, provenance, templateVersion, dataKind, sourceRunIds, ... }
export async function getBriefing(eventId, { product = "ground-motion", runId, regionId, year } = {}) {
  return request(
    "/api/v1/briefing",
    { event: eventId, product, runId, regionId, year },
    "Could not load the briefing"
  );
}

// Route: shortest route and a hazard-aware route between two points.
//   from / to = { lng, lat }.  The backend answers 404 roads_unavailable until a road graph exists.
export async function getRoute(eventId, from, to, { vehicle = "car" } = {}) {
  return request(
    "/api/v1/route",
    { event: eventId, fromLon: from.lng, fromLat: from.lat, toLon: to.lng, toLat: to.lat, vehicle },
    "Could not calculate the routes"
  );
}

// Fetch a published GeoJSON asset (url already made absolute by withAssetUrls).
export async function getGeojson(url) {
  let res;
  try {
    res = await fetch(url);
  } catch {
    throw new ApiError("Cannot reach the backend.", { status: 0, code: "offline" });
  }
  if (!res.ok) throw new ApiError(`Could not load the map data (HTTP ${res.status})`, { status: res.status });
  return res.json();
}


// ---------------------------------------------------------------------------
// v5.1 contract (docs/API_CONTRACT.md). All GET, all under /api/v1.
// Every success body carries dataKind, source, warnings and limitations.
// ---------------------------------------------------------------------------
const V1 = "/api/v1";

// --- B: NISAR --------------------------------------------------------------

// Passes with per-pass flooded km2, overlay PNG urls and the classification rule.
export async function getNisarPasses(area = AREA_ID) {
  const d = await request(`${V1}/nisar/passes`, { area }, "Could not load NISAR passes");
  (d.passes ?? []).forEach((p) => {
    p.overlayUrl = assetUrl(p.overlayUrl);
    p.backscatterUrl = assetUrl(p.backscatterUrl);
    p.floodedVegetationUrl = assetUrl(p.floodedVegetationUrl);
    p.polarizationUrl = assetUrl(p.polarizationUrl);
  });
  return d;
}

// Flood rhythm: count of passes classified as water, per pixel.
export async function getNisarRhythm(area = AREA_ID) {
  const d = await request(`${V1}/nisar/flood-rhythm`, { area }, "Could not load the flood rhythm");
  d.overlayUrl = assetUrl(d.overlayUrl);
  d.legendUrl = assetUrl(d.legendUrl);
  return d;
}

// One map point: floodCount of validCount, per-pass state. 404 outside_coverage when off the raster.
export async function getNisarPoint(area, lon, lat) {
  return request(`${V1}/nisar/point`, { area, lon, lat }, "Could not sample that point");
}

// HH / HV / ratio RGB for one date.
export async function getNisarPolarization(area, date) {
  const d = await request(`${V1}/nisar/polarization`, { area, date }, "Could not load the polarization view");
  d.rgbUrl = assetUrl(d.rgbUrl);
  return d;
}

export async function getNisarRainResponse(area = AREA_ID) {
  const d = await request(`${V1}/nisar/rain-response`, { area }, "Could not load rain response");
  d.overlayUrl = assetUrl(d.overlayUrl);
  return d;
}

export async function getNisarCoherenceChange(area = AREA_ID) {
  const d = await request(`${V1}/nisar/coherence-change`, { area }, "Could not load coherence change");
  d.overlayUrl = assetUrl(d.overlayUrl);
  return d;
}

export async function getNisarSoilMoisture(area = AREA_ID) {
  const d = await request(`${V1}/nisar/soil-moisture`, { area }, "Could not load soil moisture");
  (d.passes ?? []).forEach((p) => {
    p.overlayUrl = assetUrl(p.overlayUrl);
  });
  return d;
}

export function timelapseGifUrl(area = AREA_ID) {
  return `${API_BASE}${V1}/nisar/timelapse.gif?area=${encodeURIComponent(area)}`;
}

export async function checkTimelapseGif(area = AREA_ID) {
  try {
    const res = await fetch(timelapseGifUrl(area), { method: "HEAD" });
    return Boolean(res?.ok);
  } catch {
    return false;
  }
}

export async function getDownloads(area = AREA_ID) {
  try {
    const res = await fetch(`${API_BASE}${V1}/downloads?area=${encodeURIComponent(area)}`);
    if (!res.ok) return [];
    const body = await res.json();
    const items = Array.isArray(body) ? body : body?.entries ?? body?.downloads ?? [];
    return items.map((item) => ({ ...item, url: assetUrl(item?.url) }));
  } catch {
    return [];
  }
}

// --- A: climate, history, outlook, scenarios -------------------------------

// Incomplete months have totalMm null, a partialMm and no anomaly.
export async function getRainfallMonthly(area = AREA_ID, since = 2000) {
  return request(`${V1}/climate/rainfall/monthly`, { area, since }, "Could not load monthly rainfall");
}

export async function getRainfallDaily(area, start, end) {
  return request(`${V1}/climate/rainfall/daily`, { area, start, end }, "Could not load daily rainfall");
}

export async function getSeasonRank(area = AREA_ID, year = 2026) {
  return request(`${V1}/climate/rainfall/season-rank`, { area, year }, "Could not load the season rank");
}

// Extra endpoint: ERA5 next to POWER, never merged. { series, meanByCalendarMonth2000to2020, gridCell }
export async function getEra5Compare(area = AREA_ID) {
  return request(`${V1}/climate/rainfall/era5-compare`, { area }, "Could not load the ERA5 comparison");
}

export async function getRainfallTrend(area = AREA_ID) {
  return request(`${V1}/climate/rainfall/trend`, { area }, "Could not load the rainfall trend");
}

// dates: array of YYYY-MM-DD (optional; the backend falls back to the NISAR pass list)
export async function getPassRainfall(area, dates) {
  return request(
    `${V1}/climate/pass-rainfall`,
    { area, dates: Array.isArray(dates) ? dates.join(",") : dates },
    "Could not load pass rainfall"
  );
}

export async function getImergPasses(area = AREA_ID, series = true) {
  return request(`${V1}/climate/imerg/passes`, { area, series }, "Could not load IMERG rain timing");
}

export async function getOutlook(area = AREA_ID) {
  return request(`${V1}/climate/outlook`, { area }, "Could not load the seasonal outlook");
}

export async function getScenarios(area = AREA_ID) {
  return request(`${V1}/climate/scenarios`, { area }, "Could not load the scenarios");
}

export async function getFloodScenario(area, scenarioId) {
  return request(`${V1}/climate/flood-scenario`, { area, scenarioId }, "Could not load the flood scenario");
}

export async function getTimelineAvailability(area = AREA_ID) {
  return request(`${V1}/timeline/availability`, { area }, "Could not load the data timeline");
}

// --- D: places and exposure -------------------------------------------------

export async function searchPlaces(q, limit = 10) {
  return request(`${V1}/places/search`, { q, limit }, "Could not search places");
}

// Reverse lookup: { lon, lat, barangay: {id, name} | null, city: {id, name, province} | null }.
// 404 outside_coverage outside the study bbox; 200 with nulls and a warning over open water.
export async function locatePlace(lon, lat) {
  return request(`${V1}/places/locate`, { lon, lat }, "Could not look up the barangay");
}

export async function getPlaceBoundaries(level = "barangay") {
  return request(`${V1}/places/boundaries`, { level }, "Could not load boundaries");
}

// mask: "rhythm_half" | "priority"; level: "barangay" | "city".
// population / buildings are null (with populationUnavailableReason / buildingsUnavailableReason) when absent.
export async function getPlaceExposure(area, mask, level = "barangay") {
  return request(`${V1}/places/exposure`, { area, mask, level }, "Could not load exposure");
}

export async function getSpotCheck(lon, lat) {
  return request(`${V1}/spot-check`, { lon, lat }, "Could not load the spot check");
}

export async function getPlaceBriefing(lon, lat, lang = "en") {
  return request(`${V1}/briefing/place`, { lon, lat, lang }, "Could not load the briefing");
}

export async function exportPlaceBriefing(lon, lat, lang, format) {
  return request(`${V1}/briefing/place`, { lon, lat, lang, format }, "Could not export the briefing", "blob");
}

export async function getValidation(area = AREA_ID) {
  return request(`${V1}/validation`, { area }, "Could not load validation");
}
