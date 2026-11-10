// frontend/utils/routeEngine.js
// DEMO router that runs in the browser. It uses a tiny INVENTED street grid and INVENTED hazard
// shapes, so the route screen always has something to show when the backend has no road data.
// It follows the same rules as the backend router (backend/processing/routing.py):
//   shortest route  = fewest metres, ignores hazards
//   hazard-aware    = never drives through mapped flood (blocked), and prefers to avoid
//                     coherence-change areas (penalty x3). It says so when no such route exists.
// Everything it returns is labelled DEMO by the caller.

export const DEMO_BOUNDS = [
  [14.88, 120.72],
  [14.96, 120.81],
];
export const DEMO_PINS = {
  from: { lng: 120.73, lat: 14.92 },
  to: { lng: 120.8, lat: 14.92 },
};

const N = 13;
const LON0 = 120.72;
const LAT0 = 14.88;
const DLON = 0.0075;
const DLAT = 0.0067;
const CHANGE_PENALTY = 3;
const FLOOD_SCORE = 3; // hazard score = 3 x km through flood + 1 x km through change areas
const CHANGE_SCORE = 1;

// invented hazard shapes (lon, lat)
export const DEMO_FLOOD = [
  [120.75, 14.9],
  [120.785, 14.9],
  [120.785, 14.945],
  [120.75, 14.945],
  [120.75, 14.9],
];
export const DEMO_CHANGE = [
  [120.735, 14.905],
  [120.748, 14.905],
  [120.748, 14.93],
  [120.735, 14.93],
  [120.735, 14.905],
];

export function demoHazardGeojson() {
  const f = (coords, kind) => ({
    type: 'Feature',
    properties: { kind },
    geometry: { type: 'Polygon', coordinates: [coords] },
  });
  const [[s, w], [n, e]] = DEMO_BOUNDS;
  const area = [[w, s], [e, s], [e, n], [w, n], [w, s]];
  return {
    type: 'FeatureCollection',
    features: [f(area, 'area'), f(DEMO_FLOOD, 'flood'), f(DEMO_CHANGE, 'change')],
  };
}

function inside(poly, lng, lat) {
  let c = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i];
    const [xj, yj] = poly[j];
    if (yi > lat !== yj > lat && lng < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) c = !c;
  }
  return c;
}

export function haversineKm(a, b) {
  const R = 6371.0088;
  const rad = (d) => (d * Math.PI) / 180;
  const dLat = rad(b[1] - a[1]);
  const dLon = rad(b[0] - a[0]);
  const h =
    Math.sin(dLat / 2) ** 2 + Math.cos(rad(a[1])) * Math.cos(rad(b[1])) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

// 0 = clear, 1 = coherence-change area, 2 = mapped flood
function classify(a, b) {
  let level = 0;
  for (const t of [0.15, 0.35, 0.5, 0.65, 0.85]) {
    const lng = a[0] + (b[0] - a[0]) * t;
    const lat = a[1] + (b[1] - a[1]) * t;
    if (inside(DEMO_FLOOD, lng, lat)) return 2;
    if (inside(DEMO_CHANGE, lng, lat)) level = 1;
  }
  return level;
}

function buildGraph() {
  const nodes = [];
  for (let r = 0; r < N; r += 1) for (let c = 0; c < N; c += 1) nodes.push([LON0 + c * DLON, LAT0 + r * DLAT]);
  const adj = nodes.map(() => []);
  const link = (i, j) => {
    const km = haversineKm(nodes[i], nodes[j]);
    const level = classify(nodes[i], nodes[j]);
    adj[i].push({ to: j, km, level });
    adj[j].push({ to: i, km, level });
  };
  for (let r = 0; r < N; r += 1) {
    for (let c = 0; c < N; c += 1) {
      const i = r * N + c;
      if (c + 1 < N) link(i, i + 1);
      if (r + 1 < N) link(i, i + N);
    }
  }
  return { nodes, adj };
}
const GRAPH = buildGraph();

function nearest(p) {
  let best = 0;
  let bd = Infinity;
  GRAPH.nodes.forEach((n, i) => {
    const d = haversineKm(n, [p.lng, p.lat]);
    if (d < bd) {
      bd = d;
      best = i;
    }
  });
  return { index: best, distKm: bd };
}

function dijkstra(src, dst, costOf) {
  const n = GRAPH.nodes.length;
  const dist = new Array(n).fill(Infinity);
  const prev = new Array(n).fill(-1);
  const prevEdge = new Array(n).fill(null);
  const done = new Array(n).fill(false);
  dist[src] = 0;
  for (let k = 0; k < n; k += 1) {
    let u = -1;
    for (let i = 0; i < n; i += 1) if (!done[i] && (u === -1 || dist[i] < dist[u])) u = i;
    if (u === -1 || dist[u] === Infinity) break;
    if (u === dst) break;
    done[u] = true;
    for (const e of GRAPH.adj[u]) {
      const cost = costOf(e);
      if (cost === Infinity) continue;
      if (dist[u] + cost < dist[e.to]) {
        dist[e.to] = dist[u] + cost;
        prev[e.to] = u;
        prevEdge[e.to] = e;
      }
    }
  }
  if (dist[dst] === Infinity) return null;
  const path = [];
  const edges = [];
  for (let v = dst; v !== -1; v = prev[v]) {
    path.push(v);
    if (prevEdge[v]) edges.push(prevEdge[v]);
  }
  return { path: path.reverse(), edges: edges.reverse() };
}

function describe(found, from, to) {
  const coords = [[from.lng, from.lat], ...found.path.map((i) => GRAPH.nodes[i]), [to.lng, to.lat]];
  let distanceKm = 0;
  let floodKm = 0;
  let changeKm = 0;
  const profile = [{ distKm: 0, level: 0 }];
  found.edges.forEach((e) => {
    profile.push({ distKm: distanceKm, level: e.level });
    distanceKm += e.km;
    if (e.level === 2) floodKm += e.km;
    if (e.level === 1) changeKm += e.km;
    profile.push({ distKm: distanceKm, level: e.level });
  });
  return {
    geometry: { type: 'LineString', coordinates: coords },
    distanceKm,
    hazard: { floodKm, changeKm, score: FLOOD_SCORE * floodKm + CHANGE_SCORE * changeKm },
    profile,
  };
}

const f1 = (n) => n.toFixed(1);

export function briefingText(shortest, safe, relation) {
  const s = `The shortest route is ${f1(shortest.distanceKm)} km and passes through ${f1(
    shortest.hazard.floodKm
  )} km of mapped flood and ${f1(shortest.hazard.changeKm)} km of coherence-change areas.`;
  if (relation === 'no_safe_route') {
    return `${s} No route exists that avoids all mapped flood, so no hazard-aware route is shown. Do not treat the shortest route as safe.`;
  }
  const extra = safe.distanceKm - shortest.distanceKm;
  if (relation === 'identical') {
    return `${s} The hazard-aware route follows the same roads, because the shortest route already avoids mapped flood. Hazard-aware does not mean guaranteed safe.`;
  }
  return `${s} The hazard-aware route is ${f1(safe.distanceKm)} km (${extra >= 0 ? '+' : ''}${f1(
    extra
  )} km) and passes through ${f1(safe.hazard.floodKm)} km of mapped flood and ${f1(
    safe.hazard.changeKm
  )} km of coherence-change areas. Hazard-aware does not mean guaranteed safe: it only avoids what was mapped.`;
}

// Same response shape as GET /api/v1/route.
export function demoRoute(from, to) {
  const a = nearest(from);
  const b = nearest(to);
  if (a.distKm > 4 || b.distKm > 4) {
    throw new Error('The demo streets only cover the small orange-bordered demo area. Use the demo pins.');
  }
  const shortest = dijkstra(a.index, b.index, (e) => e.km);
  if (!shortest) throw new Error('No demo route between these pins.');
  const safeFound = dijkstra(a.index, b.index, (e) =>
    e.level === 2 ? Infinity : e.km * (e.level === 1 ? CHANGE_PENALTY : 1)
  );
  const s = describe(shortest, from, to);
  const safe = safeFound ? describe(safeFound, from, to) : null;
  let relation = 'no_safe_route';
  if (safe) {
    if (Math.abs(safe.distanceKm - s.distanceKm) < 1e-9 && s.hazard.score === safe.hazard.score) relation = 'identical';
    else relation = safe.hazard.floodKm === 0 && safe.hazard.changeKm === 0 ? 'detour' : 'reduced';
  }
  return {
    event: 'demo',
    dataKind: 'synthetic',
    dataStatus: 'synthetic',
    vehicle: 'car',
    hazardSources: [
      { id: 'flood-extent', label: 'Invented flood shape (demo)', dataStatus: 'synthetic' },
      { id: 'coherence-change', label: 'Invented change area (demo)', dataStatus: 'synthetic' },
    ],
    shortest: s,
    safe,
    relation,
    detourKm: safe ? safe.distanceKm - s.distanceKm : null,
    briefing: { text: briefingText(s, safe, relation), templateVersion: 'route-demo-1' },
    limitations: [
      'DEMO: invented streets and invented hazard shapes. Not real roads, not real flooding.',
      'Hazard-aware does not mean guaranteed safe.',
    ],
  };
}
