// frontend/utils/devFixtures.js
// DEV ONLY. Used when the app is started with NEXT_PUBLIC_USE_FIXTURES=1 (see api.js) so the UI can be
// built and checked while the backend routers are still being written.
//
// Everything here is SYNTHETIC. It is shaped like docs/API_CONTRACT.md, every body carries
// dataKind "synthetic", and the app shows a banner and the synthetic badge. None of these numbers
// describe the real world. Nothing in this file is imported unless the flag is set.
import { ApiError } from "./api";

const AREA = "camanava_2026";
const BOUNDS = [
  [14.6, 120.88],
  [14.82, 121.04],
];
const W = 128;
const H = 176;
const CELL_KM2 = ((0.16 / W) * 107.6) * ((0.22 / H) * 111.0);
const SRC = {
  name: "Dev fixture (SYNTHETIC, invented for layout testing)",
  url: null,
  version: "fixture-0",
};
const NOW = "2026-11-14T00:00:00Z";
const base = (extra = {}) => ({
  area: AREA,
  dataKind: "synthetic",
  source: SRC,
  generatedAt: NOW,
  nativeResolution: "fixture grid",
  warnings: ["SYNTHETIC dev fixture: not a real result."],
  limitations: ["Fixture data. Every number here is invented to test the layout."],
  ...extra,
});

// ---- tiny deterministic helpers -------------------------------------------------------------
function hash(n) {
  let x = Math.imul(n ^ 0x9e3779b9, 0x85ebca6b);
  x ^= x >>> 13;
  x = Math.imul(x, 0xc2b2ae35);
  x ^= x >>> 16;
  return (x >>> 0) / 4294967296;
}
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const dayNumber = (iso) => Math.floor(Date.parse(`${iso}T00:00:00Z`) / 86400000);
const isoFromDay = (n) => new Date(n * 86400000).toISOString().slice(0, 10);

function hexToRgb(h) {
  const n = parseInt(h.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}
function makePng(fn) {
  const c = document.createElement("canvas");
  c.width = W;
  c.height = H;
  const ctx = c.getContext("2d");
  const img = ctx.createImageData(W, H);
  for (let j = 0; j < H; j += 1) {
    for (let i = 0; i < W; i += 1) {
      const [r, g, b, a] = fn(i, j) ?? [0, 0, 0, 0];
      const o = (j * W + i) * 4;
      img.data[o] = r;
      img.data[o + 1] = g;
      img.data[o + 2] = b;
      img.data[o + 3] = a;
    }
  }
  ctx.putImageData(img, 0, 0);
  return c.toDataURL("image/png");
}

// ---- synthetic terrain: which cells flood easily ---------------------------------------------
let model = null;
function getModel() {
  if (model) return model;
  const wet = new Float32Array(W * H);
  const permanent = new Uint8Array(W * H);
  for (let j = 0; j < H; j += 1) {
    for (let i = 0; i < W; i += 1) {
      const x = i / W;
      const y = 1 - j / H; // 0 = south
      const noise =
        0.5 +
        0.22 * Math.sin(9 * x + 4 * y + 1.3) +
        0.18 * Math.sin(17 * y - 7 * x + 0.4) +
        0.1 * Math.sin(31 * x + 23 * y);
      const coast = Math.pow(1 - x, 1.4);
      wet[j * W + i] = clamp(0.5 * coast + 0.5 * noise, 0, 1);
      const bay = x < 0.09 + 0.03 * Math.sin(y * 9);
      const river = Math.abs(y - (0.55 + 0.1 * Math.sin(5 * x))) < 0.008 && x > 0.1;
      permanent[j * W + i] = bay || river ? 1 : 0;
    }
  }
  // synthetic pass list: 10 provisional dates (one gap) and one later date
  const dates = ["2026-06-23", "2026-07-05", "2026-07-17", "2026-07-29", "2026-08-22", "2026-09-03", "2026-09-15", "2026-09-27", "2026-10-09", "2026-10-21", "2026-11-02"];
  const passes = dates.map((date, p) => {
    const prior7 = [0, 1, 2, 3, 4, 5, 6, 7].reduce((s, k) => s + (dayRain(isoFromDay(dayNumber(date) - k)) ?? 0), 0);
    const thr = 0.86 - 0.5 * clamp(prior7 / 300, 0, 1);
    const state = new Uint8Array(W * H); // 0 dry, 1 water, 2 nodata, 3 flooded vegetation
    let flooded = 0;
    let valid = 0;
    let veg = 0;
    let perm = 0;
    for (let k = 0; k < W * H; k += 1) {
      const patch = hash(Math.floor((k % W) / 6) * 977 + Math.floor(k / W / 6) * 31 + p * 7919);
      if (permanent[k]) {
        perm += 1;
        state[k] = 0;
        continue;
      }
      if (patch > 0.965) {
        state[k] = 2;
        continue;
      }
      valid += 1;
      if (wet[k] > thr) {
        if (hash(k + p * 13) > 0.93) {
          state[k] = 3;
          veg += 1;
        } else {
          state[k] = 1;
          flooded += 1;
        }
      }
    }
    return { date, state, prior7, flooded, valid, veg, perm };
  });
  model = { wet, permanent, passes };
  return model;
}

// ---- rainfall ---------------------------------------------------------------------------------
const BASELINE = [10, 8, 12, 25, 130, 260, 430, 480, 360, 210, 80, 30];
function dayRain(iso) {
  const d = dayNumber(iso);
  const month = new Date(d * 86400000).getUTCMonth();
  if (hash(d * 3 + 1) > 0.985) return null; // a missing day, never counted as dry
  const wetness = BASELINE[month] / 30;
  const u = hash(d * 5 + 2);
  return Math.round(Math.max(0, (u < 0.45 ? 0.1 : -Math.log(1 - hash(d * 7 + 3) * 0.97) * wetness * 1.6)) * 10) / 10;
}
const FIRST_YEAR = 2000;
const LAST = { year: 2026, month: 10 };
function monthlySeries() {
  const out = [];
  for (let y = FIRST_YEAR; y <= LAST.year; y += 1) {
    for (let m = 1; m <= 12; m += 1) {
      if (y === LAST.year && m > LAST.month) break;
      const f = 0.45 + 1.3 * hash(y * 31 + m);
      const total = Math.round(BASELINE[m - 1] * f * 10) / 10;
      const missing = hash(y * 71 + m * 13) > 0.97 ? 3 : 0;
      out.push({
        year: y,
        month: m,
        totalMm: total,
        totalMm: missing ? null : total,
        partialMm: missing ? total : null,
        complete: !missing,
        anomalyMm: missing ? null : Math.round((total - BASELINE[m - 1]) * 10) / 10,
        anomalyPct: missing ? null : Math.round(((total - BASELINE[m - 1]) / BASELINE[m - 1]) * 1000) / 10,
        missingDays: missing,
      });
    }
  }
  return out;
}
function seasons() {
  const s = monthlySeries();
  const by = {};
  s.forEach((r) => {
    if (r.month >= 6 && r.month <= 11) {
      by[r.year] = by[r.year] ?? { year: r.year, totalMm: 0, n: 0 };
      by[r.year].totalMm += r.totalMm ?? r.partialMm ?? 0;
      by[r.year].n += 1;
    }
  });
  return Object.values(by).map((r) => ({ year: r.year, totalMm: Math.round(r.totalMm), toDateMm: Math.round(r.totalMm), complete: r.n === 6 }));
}

// ---- places -----------------------------------------------------------------------------------
const CITIES = [
  { name: "Caloocan", lon: 120.98, lat: 14.65 },
  { name: "Malabon", lon: 120.957, lat: 14.662 },
  { name: "Navotas", lon: 120.94, lat: 14.667 },
  { name: "Valenzuela", lon: 120.983, lat: 14.7 },
  { name: "Obando", lon: 120.93, lat: 14.705 },
  { name: "Meycauayan", lon: 120.96, lat: 14.737 },
  { name: "Marilao", lon: 120.95, lat: 14.76 },
];
const PLACES = [
  ...CITIES.map((c, i) => ({ id: `fx-city-${i}`, name: c.name, level: "city", city: c.name, province: "(fixture)", lon: c.lon, lat: c.lat })),
  ...CITIES.flatMap((c, i) => [0, 1].map((k) => ({
    id: `fx-brgy-${i}-${k}`,
    name: `Sample barangay ${i * 2 + k + 1}`,
    level: "barangay",
    city: c.name,
    province: "(fixture)",
    lon: c.lon + (k ? 0.006 : -0.005),
    lat: c.lat + (k ? -0.004 : 0.005),
  }))),
].map((p) => ({ ...p, bbox: [p.lon - 0.004, p.lat - 0.004, p.lon + 0.004, p.lat + 0.004] }));

function nearestPlace(lon, lat, level) {
  let best = null;
  PLACES.filter((p) => !level || p.level === level).forEach((p) => {
    const d = Math.hypot((p.lon - lon) * 0.96, p.lat - lat);
    if (!best || d < best.d) best = { d, p };
  });
  return best;
}

// ---- ground motion (synthetic cumulative LOS displacement) -------------------------------------
const GM_EPOCHS = ["2026-06-23", "2026-07-05", "2026-07-17", "2026-07-29", "2026-08-22", "2026-09-03", "2026-09-15", "2026-09-27", "2026-10-09", "2026-10-21"];
function losAt(lon, lat) {
  const x = (lon - 120.88) / 0.16;
  const y = (lat - 14.6) / 0.22;
  const bowl = Math.exp(-(((x - 0.3) / 0.22) ** 2 + ((y - 0.42) / 0.2) ** 2));
  const second = Math.exp(-(((x - 0.55) / 0.12) ** 2 + ((y - 0.78) / 0.1) ** 2));
  return Math.round((26 * bowl + 14 * second - 4 + 3 * Math.sin(20 * x + 11 * y)) * 10) / 10;
}
function gmGeojson() {
  const nx = 16;
  const ny = 22;
  const features = [];
  for (let j = 0; j < ny; j += 1) {
    for (let i = 0; i < nx; i += 1) {
      const w = 120.88 + (i * 0.16) / nx;
      const e = 120.88 + ((i + 1) * 0.16) / nx;
      const s = 14.6 + (j * 0.22) / ny;
      const n = 14.6 + ((j + 1) * 0.22) / ny;
      const d = losAt((w + e) / 2, (s + n) / 2);
      features.push({
        type: "Feature",
        properties: { id: `g${i}-${j}`, displacementMm: d, rateMmPerYear: Math.round(d * 3 * 10) / 10 },
        geometry: { type: "Polygon", coordinates: [[[w, s], [e, s], [e, n], [w, n], [w, s]]] },
      });
    }
  }
  return { type: "FeatureCollection", features };
}

// ---- the response table ------------------------------------------------------------------------
export async function fixtureResponse(path, q) {
  const m = getModel;
  const area = q.area ?? AREA;
  if (path.startsWith("/api/v1/nisar") || path.startsWith("/api/v1/climate") || path.startsWith("/api/v1/timeline") || path.startsWith("/api/v1/places")) {
    if (q.area && q.area !== AREA) {
      throw new ApiError("Unknown area", { status: 404, code: "unknown_area", detail: { code: "unknown_area", message: "Fixtures only know camanava_2026" } });
    }
  }
  switch (path) {
    case "/api/v1/nisar/passes": {
      const { passes } = m();
      return base({
        sensor: "NISAR L-band SAR (fixture)",
        product: "L2 GCOV (fixture)",
        track: 133,
        direction: "descending",
        frame: 81,
        polarizations: ["HH", "HV"],
        rule: {
          description: "Fixture rule: a cell is water when its synthetic wetness is above a threshold set by prior rainfall. Not the real classification.",
          hhThresholdDb: -18.0,
          hvThresholdDb: -26.0,
          calibration: "none (synthetic)",
        },
        legend: [
          { id: "water", label: "Open water on this pass", color: "#0072B2" },
          { id: "vegetation", label: "Possible flooded vegetation (L-band)", color: "#E69F00" },
        ],
        bounds: BOUNDS,
        passes: passes.map((p, i) => ({
          id: p.date.replaceAll("-", ""),
          date: p.date,
          acquisitionTime: `${p.date}T10:32:${String(20 + (i % 5)).padStart(2, "0")}Z`,
          productId: `FIXTURE_GCOV_${p.date}`,
          maturity: i === passes.length - 1 ? "v1" : "provisional",
          floodedKm2: Math.round(p.flooded * CELL_KM2 * 10) / 10,
          permanentWaterKm2: Math.round(p.perm * CELL_KM2 * 10) / 10,
          floodedVegetationKm2: Math.round(p.veg * CELL_KM2 * 10) / 10,
          validKm2: Math.round(p.valid * CELL_KM2 * 10) / 10,
          validFraction: Math.round((p.valid / (W * H - p.perm)) * 1000) / 1000,
          overlayUrl: makePng((x, y) => {
            const s = p.state[y * W + x];
            if (s === 1) return [0, 114, 178, 190];
            if (s === 3) return [230, 159, 0, 190];
            return null;
          }),
          backscatterUrl: makePng((x, y) => {
            const k = y * W + x;
            const water = p.state[k] === 1 || m().permanent[k];
            const v = water ? 25 + 25 * hash(k) : 90 + 110 * hash(k + 5) * (0.5 + m().wet[k]);
            return [v, v, v, 235];
          }),
        })),
      });
    }
    case "/api/v1/nisar/flood-rhythm": {
      const { passes, permanent } = m();
      const n = passes.length;
      const counts = new Uint8Array(W * H);
      const valids = new Uint8Array(W * H);
      passes.forEach((p) => {
        for (let k = 0; k < W * H; k += 1) {
          if (permanent[k] || p.state[k] === 2) continue;
          valids[k] += 1;
          if (p.state[k] === 1 || p.state[k] === 3) counts[k] += 1;
        }
      });
      const ramp = ["#fde725", "#bddf26", "#7ad151", "#44bf70", "#22a884", "#21908d", "#2a788e", "#355f8d", "#414487", "#472d7b", "#440154"];
      const colorFor = (c) => ramp[clamp(Math.round(((c - 1) / Math.max(1, n - 1)) * (ramp.length - 1)), 0, ramp.length - 1)];
      const km2 = new Array(n + 1).fill(0);
      for (let k = 0; k < W * H; k += 1) if (counts[k] > 0) km2[counts[k]] += CELL_KM2;
      let half = 0;
      for (let k = 0; k < W * H; k += 1) if (valids[k] > 0 && counts[k] / valids[k] >= 0.5) half += CELL_KM2;
      return base({
        dataKind: "synthetic",
        passCount: n,
        overlayUrl: makePng((x, y) => {
          const c = counts[y * W + x];
          if (!c) return null;
          return [...hexToRgb(colorFor(c)), 215];
        }),
        bounds: BOUNDS,
        legend: Array.from({ length: n }, (_, i) => ({ count: i + 1, color: colorFor(i + 1) })),
        km2ByCount: km2.slice(1).map((v, i) => ({ count: i + 1, km2: Math.round(v * 10) / 10 })),
        halfOrMoreKm2: Math.round(half * 10) / 10,
        permanentWaterMasked: true,
        method: "FIXTURE: count of synthetic passes classified as water, over the count of valid passes, per pixel; permanent water excluded",
      });
    }
    case "/api/v1/nisar/point": {
      const lon = Number(q.lon);
      const lat = Number(q.lat);
      if (!(lon >= 120.88 && lon <= 121.04 && lat >= 14.6 && lat <= 14.82)) {
        throw new ApiError("Outside coverage", { status: 404, code: "outside_coverage", detail: { code: "outside_coverage", message: "This point is outside the NISAR frame for the area." } });
      }
      const i = clamp(Math.floor(((lon - 120.88) / 0.16) * W), 0, W - 1);
      const j = clamp(Math.floor((1 - (lat - 14.6) / 0.22) * H), 0, H - 1);
      const k = j * W + i;
      const { passes, permanent } = m();
      const perPass = passes.map((p) => {
        const s = p.state[k];
        const state = permanent[k] ? "nodata" : s === 2 ? "nodata" : s === 0 ? "dry" : "water";
        return {
          date: p.date,
          state,
          hhDb: state === "nodata" ? null : Math.round((state === "water" ? -21 + 3 * hash(k + 1) : -9 - 5 * hash(k + 2)) * 10) / 10,
          hvDb: state === "nodata" ? null : Math.round((state === "water" ? -29 + 3 * hash(k + 3) : -17 - 5 * hash(k + 4)) * 10) / 10,
        };
      });
      return base({
        lon,
        lat,
        cellCenter: { lon: 120.88 + ((i + 0.5) / W) * 0.16, lat: 14.6 + (1 - (j + 0.5) / H) * 0.22 },
        floodCount: perPass.filter((r) => r.state === "water").length,
        validCount: perPass.filter((r) => r.state !== "nodata").length,
        permanentWater: Boolean(permanent[k]),
        perPass,
      });
    }
    case "/api/v1/nisar/polarization": {
      const { wet, passes } = m();
      const p = passes.find((r) => r.date === q.date) ?? passes[0];
      return base({
        date: p.date,
        rgbUrl: makePng((x, y) => {
          const k = y * W + x;
          const water = p.state[k] === 1 || m().permanent[k];
          const veg = p.state[k] === 3;
          const hh = water ? 20 : veg ? 235 : 70 + 120 * wet[k];
          const hv = water ? 15 : 50 + 90 * hash(k + 9);
          const ratio = veg ? 230 : 60 + 90 * hash(k + 11);
          return [hh, hv, ratio, 235];
        }),
        bounds: BOUNDS,
        channels: { r: "HH", g: "HV", b: "HH/HV" },
        explanation: [
          "Red is HH: the radar sends and receives horizontally polarised waves. It is strong on rough ground and on water-under-plants double bounce.",
          "Green is HV: the radar sends horizontal and receives vertical. Tall, dense vegetation scatters in this way.",
          "Blue is the HH/HV ratio. Open water is dark in all three channels, so it stays dark in the picture.",
        ],
      });
    }
    case "/api/v1/climate/rainfall/daily": {
      const start = q.start ?? "2026-06-01";
      const end = q.end ?? "2026-11-02";
      const a = dayNumber(start);
      const b = Math.min(dayNumber(end), a + 800);
      const days = [];
      for (let d = a; d <= b; d += 1) days.push({ date: isoFromDay(d), mm: dayRain(isoFromDay(d)) });
      return base({ point: { lon: 120.96, lat: 14.7 }, units: "mm/day", nativeResolution: "0.5° x 0.625° (fixture)", days, source: { ...SRC, name: "Dev fixture standing in for NASA POWER (SYNTHETIC)" } });
    }
    case "/api/v1/climate/rainfall/monthly":
      return base({
        point: { lon: 120.96, lat: 14.7 },
        units: "mm",
        baseline: { period: "1991-2020", monthlyMeanMm: BASELINE },
        series: monthlySeries(),
        nativeResolution: "0.5° x 0.625° (fixture)",
        retrievedAt: NOW,
        dataKind: "synthetic",
        limitations: ["Fixture: one grid cell, not a city average", "SYNTHETIC numbers."],
      });
    case "/api/v1/climate/rainfall/season-rank": {
      const list = seasons();
      const cur = list.find((r) => r.year === Number(q.year ?? 2026)) ?? list[list.length - 1];
      const rank = 1 + list.filter((r) => r.totalMm > cur.totalMm).length;
      return base({ season: "Jun-Nov", year: cur.year, totalMm: cur.complete ? cur.totalMm : null, toDateMm: cur.totalMm, observedThrough: "2026-10-31", rank, of: list.length, rankBasis: cur.complete ? "full_season_total" : "to_date_same_window", rankMeaning: "1 = wettest", complete: cur.complete, seasons: list });
    }
    case "/api/v1/climate/rainfall/trend": {
      const s = monthlySeries();
      const n = s.length;
      const xs = s.map((_, i) => i / 120);
      const ys = s.map((r) => r.anomalyMm ?? 0);
      const mx = xs.reduce((a, b) => a + b, 0) / n;
      const my = ys.reduce((a, b) => a + b, 0) / n;
      const sxx = xs.reduce((a, x) => a + (x - mx) ** 2, 0);
      const slope = xs.reduce((a, x, i) => a + (x - mx) * (ys[i] - my), 0) / sxx;
      const res = ys.map((y, i) => y - (my + slope * (xs[i] - mx)));
      const se = Math.sqrt(res.reduce((a, r) => a + r * r, 0) / (n - 2) / sxx);
      const r1 = (v) => Math.round(v * 10) / 10;
      return base({
        method: "linear fit on monthly anomalies, seasonal cycle removed (fixture)",
        period: "2000-2026",
        slopeMmPerDecade: r1(slope),
        ci95: [r1(slope - 1.96 * se), r1(slope + 1.96 * se)],
        n,
        significant: Math.abs(slope) > 1.96 * se,
        limitations: ["Fixture trend on invented numbers.", "One grid cell; monthly series is autocorrelated, so the interval is optimistic.", "No cause is claimed."],
      });
    }
    case "/api/v1/climate/pass-rainfall": {
      const dates = (q.dates ? String(q.dates).split(",") : m().passes.map((p) => p.date)).filter(Boolean);
      const sum = (date, k) => {
        let any = false;
        let tot = 0;
        for (let i = 0; i < k; i += 1) {
          const v = dayRain(isoFromDay(dayNumber(date) - i));
          if (v != null) {
            any = true;
            tot += v;
          }
        }
        return any ? Math.round(tot * 10) / 10 : null;
      };
      return base({ units: "mm", passes: dates.map((date) => ({ date, sameDayMm: dayRain(date), prior3DayMm: sum(date, 3), prior7DayMm: sum(date, 7) })), nativeResolution: "0.5° x 0.625° (fixture)" });
    }
    case "/api/v1/climate/outlook": {
      const months = [12, 1, 2, 3, 4, 5].map((mo, i) => {
        const yr = mo === 12 ? 2026 : 2027;
        const mean = Math.round(BASELINE[mo - 1] * (0.8 + 0.4 * hash(i + 90)));
        return { year: yr, month: mo, fullMonth: true, meanMm: mean, memberMinMm: Math.round(mean * 0.5), memberMaxMm: Math.round(mean * 1.7), anomalyVsModelClimatologyMm: null, members: 51 };
      });
      return base({ dataKind: "synthetic", model: "Dev fixture ensemble (not a real model)", runDate: "2026-11-01", ensembleMembers: 51, nativeResolution: "~36 km (fixture)", months, horizonMonths: 6, limitations: ["Fixture outlook months. Not a street-level forecast."] });
    }
    case "/api/v1/climate/scenarios": {
      const outlook = await fixtureResponse("/api/v1/climate/outlook", { area });
      const monthsOrder = [12, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11];
      const mk = (id, label, basis, valueFor) => ({
        id,
        label,
        basis,
        months: monthsOrder.map((mo, i) => {
          const yr = mo === 12 ? 2026 : 2027;
          const row = { year: yr, month: mo, rainfallMm: Math.round(valueFor(mo, yr) * 10) / 10, rainfallSource: "scenario_value", status: i < 6 ? "outlook" : "scenario" };
          return i < 6 ? { ...row, outlook: outlookOf(i) } : row;
        }),
      });
      const like = (y) => (mo) => monthlySeries().find((r) => r.year === y && r.month === mo)?.totalMm ?? BASELINE[mo - 1];
      const outlookOf = (i) => ({ meanMm: outlook.months[i].meanMm, memberMinMm: outlook.months[i].memberMinMm, memberMaxMm: outlook.months[i].memberMaxMm, members: 51 });
      const ss = seasons().filter((r) => r.complete);
      const wettest = ss.reduce((a, b) => (b.totalMm > a.totalMm ? b : a));
      const driest = ss.reduce((a, b) => (b.totalMm < a.totalMm ? b : a));
      const wetLike = ss.filter((r) => r.year !== wettest.year).reduce((a, b) => (b.totalMm > a.totalMm ? b : a));
      return base({
        dataKind: "synthetic",
        startMonth: "2026-12",
        scenarios: [
          mk("normal", "A normal year (1991-2020 mean)", "Fixture baseline monthly means", (mo) => BASELINE[mo - 1]),
          mk(`wet_like_${wetLike.year}`, `A wet year like ${wetLike.year}`, `Fixture monthly totals of ${wetLike.year}`, like(wetLike.year)),
          mk("wettest_since_2000", `The wettest season since 2000 (${wettest.year})`, `Fixture monthly totals of ${wettest.year}`, like(wettest.year)),
          mk(`dry_like_${driest.year}`, `A dry year like ${driest.year}`, `Fixture monthly totals of ${driest.year}`, like(driest.year)),
        ],
        limitations: ["conditional scenario, not a prediction", "Fixture numbers."],
      });
    }
    case "/api/v1/climate/flood-scenario": {
      const sc = await fixtureResponse("/api/v1/climate/scenarios", { area });
      const chosen = sc.scenarios.find((s) => s.id === q.scenarioId) ?? sc.scenarios[0];
      const pts = m().passes.map((p) => ({ date: p.date, prior7DayMm: Math.round(p.prior7 * 10) / 10, floodedKm2: Math.round(p.flooded * CELL_KM2 * 10) / 10 }));
      const n = pts.length;
      const mx = pts.reduce((a, r) => a + r.prior7DayMm, 0) / n;
      const my = pts.reduce((a, r) => a + r.floodedKm2, 0) / n;
      const slope = pts.reduce((a, r) => a + (r.prior7DayMm - mx) * (r.floodedKm2 - my), 0) / pts.reduce((a, r) => a + (r.prior7DayMm - mx) ** 2, 0);
      const icpt = my - slope * mx;
      return base({
        exploratory: true,
        scenarioId: chosen.id,
        assumptions: ["Fixture: monthly rainfall divided by 4.3 stands in for a 7-day total.", "Low and high are 0.7x and 1.4x of base. They are not probabilities."],
        relationship: { n, method: "FIXTURE straight-line fit of flooded km2 on prior 7-day rainfall", points: pts },
        months: chosen.months.map((mo) => {
          const b = Math.max(0, icpt + slope * (mo.rainfallMm / 4.3));
          const r1 = (v) => Math.round(v * 10) / 10;
          return { year: mo.year, month: mo.month, rainfallMm: mo.rainfallMm, expectedFloodedKm2: { low: r1(b * 0.7), base: r1(b), high: r1(b * 1.4) }, status: mo.status };
        }),
        limitations: ["Exploratory: n is about 11 passes and no model is validated.", "Flood conditions are a function of rainfall alone here; tides, drainage and pumping are not included."],
      });
    }
    case "/api/v1/timeline/availability":
      return base({
        datasets: [
          { id: "nasa_power_rainfall", label: "NASA POWER daily rainfall", kind: "climate", start: "2000-01-01", end: "2026-11-13", cadence: "daily", access: "API", status: "integrated" },
          { id: "era5_open_meteo", label: "ERA5 via Open-Meteo (comparison)", kind: "climate", start: "2000-01-01", end: "2026-11-08", cadence: "hourly", access: "API", status: "catalogue_only" },
          { id: "landsat", label: "Landsat optical imagery", kind: "optical", start: "2000-01-01", end: "2026-11-01", cadence: "16 days per satellite", access: "Planetary Computer STAC", status: "catalogue_only" },
          { id: "sentinel1", label: "Sentinel-1 C-band SAR", kind: "sar_c", start: "2014-10-03", end: "2026-11-01", cadence: "6 to 12 days", access: "ASF", status: "integrated" },
          { id: "nisar_gcov", label: "NISAR L-band backscatter (GCOV)", kind: "sar_l", start: "2026-06-23", end: "2026-11-02", cadence: "12 days", access: "ASF / Earthdata", status: "integrated" },
          { id: "nisar_gunw", label: "NISAR L-band interferograms (GUNW)", kind: "insar", start: "2026-06-23", end: "2026-10-21", cadence: "12 days", access: "ASF / Earthdata", status: "integrated" },
        ],
      });
    case "/api/v1/places/search": {
      const needle = String(q.q ?? "").trim().toLowerCase();
      const hits = PLACES.filter((p) => needle && (p.name.toLowerCase().includes(needle) || p.city.toLowerCase().includes(needle)));
      return base({ query: q.q, results: hits.slice(0, Number(q.limit ?? 10)).map((r) => ({ ...r, inStudyArea: true })), source: { ...SRC, name: "Dev fixture gazetteer (SYNTHETIC barangays)" } });
    }
    case "/api/v1/places/locate": {
      const lon = Number(q.lon);
      const lat = Number(q.lat);
      if (!(lon >= 120.88 && lon <= 121.04 && lat >= 14.6 && lat <= 14.82)) {
        throw new ApiError("Outside coverage", { status: 404, code: "outside_coverage", detail: { code: "outside_coverage", message: "No barangay polygon here." } });
      }
      const near = nearestPlace(lon, lat, "barangay");
      const city = nearestPlace(lon, lat, "city");
      return base({ lon, lat, barangay: { id: near.p.id, name: near.p.name }, city: { id: city.p.id, name: city.p.name, province: "(fixture)" }, source: { ...SRC, name: "Dev fixture gazetteer (SYNTHETIC: nearest sample point, not a boundary lookup)" } });
    }
    case "/api/v1/places/exposure": {
      const priority = q.mask === "priority";
      const zones = PLACES.filter((p) => p.level === "barangay")
        .filter((_, i) => (priority ? i % 4 === 0 : i % 2 === 0))
        .map((p, i) => ({ placeId: p.id, name: p.name, city: p.city, areaKm2: Math.round((0.4 + hash(i + 3)) * 100) / 100, population: Math.round(800 + hash(i + 50) * 9000), buildings: Math.round(200 + hash(i + 70) * 2200) }));
      return base({
        zones,
        area,
        mask: q.mask,
        level: q.level ?? "barangay",
        passCount: m().passes.length,
        totals: { population: zones.reduce((a, z) => a + z.population, 0), buildings: zones.reduce((a, z) => a + z.buildings, 0), areaKm2: Math.round(zones.reduce((a, z) => a + z.areaKm2, 0) * 100) / 100, unassignedAreaKm2: 0.3 },
        populationSource: { name: "Fixture (synthetic)", year: 2020 },
        buildingSource: { snapshotDate: "fixture" },
        limitations: ["exposure, not damage", "Fixture numbers."],
      });
    }
    case "/api/v1/ground-motion": {
      if (q.event !== AREA) return undefined;
      const gj = gmGeojson();
      const vals = gj.features.map((f) => f.properties.displacementMm).sort((a, b) => a - b);
      return base({
        event: AREA,
        product: "ground-motion",
        dataStatus: "synthetic",
        referenceEpoch: GM_EPOCHS[0],
        latestEpoch: GM_EPOCHS[GM_EPOCHS.length - 1],
        epochs: GM_EPOCHS,
        sourcePairCount: GM_EPOCHS.length - 1,
        regionalSummary: { medianRateMmPerYear: Math.round(vals[Math.floor(vals.length / 2)] * 3 * 10) / 10, medianDisplacementMm: vals[Math.floor(vals.length / 2)], validRateCellCount: vals.length, selectedCellCount: vals.length },
        spatialReferenceId: "FIXTURE reference area (synthetic, not a real stable site)",
        correctionState: "FIXTURE: no ionospheric or tropospheric correction (synthetic)",
        correctionsApplied: [],
        sensor: "NISAR (fixture)",
        frequency: "L-band",
        flightDirection: "descending",
        track: 133,
        frame: 81,
        maturity: "provisional",
        heatmapGeojson: gj,
      });
    }
    case "/api/v1/ground-motion/point": {
      if (q.event !== AREA) return undefined;
      const lon = Number(q.lon);
      const lat = Number(q.lat);
      if (!(lon >= 120.88 && lon <= 121.04 && lat >= 14.6 && lat <= 14.82)) {
        return base({ event: AREA, point: { status: "nodata", reason: "outside_coverage", longitude: lon, latitude: lat } });
      }
      const total = losAt(lon, lat);
      const series = GM_EPOCHS.map((e, i) => Math.round(((total * i) / (GM_EPOCHS.length - 1) + (hash(i + Math.round(lon * 1000)) - 0.5) * 1.6) * 10) / 10);
      series[0] = 0;
      return base({
        event: AREA,
        point: {
          status: "ok",
          reason: null,
          longitude: lon,
          latitude: lat,
          epochs: GM_EPOCHS,
          displacementMm: series,
          validEpochCount: GM_EPOCHS.length,
          spanDays: dayNumber(GM_EPOCHS[GM_EPOCHS.length - 1]) - dayNumber(GM_EPOCHS[0]),
          rateMmPerYear: Math.round(total * 3 * 10) / 10,
          rateStandardErrorMmPerYear: 2.4,
        },
      });
    }
    default:
      return undefined;
  }
}
