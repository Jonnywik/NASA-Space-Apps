// frontend/utils/api.js  -  the only place that talks to the Tanaw backend.
// The backend must be running:  uvicorn app.main:app --reload   (inside backend/)

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

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
//   unavailable | review | invalid | offline | error
export function classifyError(err) {
  if (!(err instanceof ApiError)) return "error";
  if (err.status === 0) return "offline";
  switch (err.code) {
    case "data_unavailable":
    case "unknown_event":
      return "unavailable";
    case "review_required":
      return "review";
    case "invalid_product":
    case "stale_exposure":
    case "mismatched_run":
    case "invalid_identifier_or_catalog":
      return "invalid";
    default:
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

async function request(path, params, label) {
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
  return res.json();
}

// Backend picture/file addresses come without the server name; add it here.
export function assetUrl(path) {
  if (!path) return path;
  return /^https?:\/\//.test(path) ? path : API_BASE + path;
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
