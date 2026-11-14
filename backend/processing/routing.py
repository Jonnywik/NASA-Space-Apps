"""Vehicle routing over an exported road graph, with hazard-aware costs.

Pure Python (heapq + shapely), no network access. Roads come from ``roads.geojson`` made by
``scripts/18_export_roads.py`` (OpenStreetMap via osmnx). Hazards are the Tier 1 flood polygons
and, when a reviewed product exists, the Tier 2 coherence-change polygons.

Rules (kept identical to frontend/utils/routeEngine.js, so the DEMO behaves like the real thing):
  shortest route  = fewest kilometres, ignores hazards
  hazard-aware    = never uses an edge that touches mapped flood (blocked);
                    edges that touch a coherence-change area cost x CHANGE_PENALTY
  hazard score    = FLOOD_SCORE x km on flood edges + CHANGE_SCORE x km on change edges
Limits (also returned to the caller): hazards are matched per road segment, not per metre; the road
network is directed exactly as exported; hazard-aware does not mean safe; no traffic or closures.
"""
from __future__ import annotations

import heapq
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from shapely.geometry import LineString, MultiLineString, shape
from shapely.ops import unary_union
from shapely.prepared import prep

CHANGE_PENALTY = 3.0
FLOOD_SCORE = 3.0
CHANGE_SCORE = 1.0
SNAP_LIMIT_KM = 1.5
TEMPLATE_VERSION = "route-template-1"


class RoutingError(Exception):
    """Carries an HTTP status and a stable machine-readable code."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code = status, code


def haversine_km(a, b) -> float:
    r = 6371.0088
    la1, la2 = math.radians(a[1]), math.radians(b[1])
    dla, dlo = la2 - la1, math.radians(b[0] - a[0])
    h = math.sin(dla / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(dlo / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _length_km(coords) -> float:
    return sum(haversine_km(coords[i], coords[i + 1]) for i in range(len(coords) - 1))


def _key(pt) -> tuple[float, float]:
    return (round(pt[0], 6), round(pt[1], 6))


@dataclass
class Edge:
    to: int
    km: float
    coords: list
    level: int = 0  # 0 clear, 1 change area, 2 mapped flood


@dataclass
class Graph:
    nodes: list = field(default_factory=list)
    adj: list = field(default_factory=list)
    index: dict = field(default_factory=dict)

    def node(self, pt) -> int:
        k = _key(pt)
        if k not in self.index:
            self.index[k] = len(self.nodes)
            self.nodes.append(k)
            self.adj.append([])
        return self.index[k]


def load_graph(roads_path: Path) -> Graph:
    """Directed graph: each LineString is one edge from its first to its last coordinate."""
    data = json.loads(Path(roads_path).read_text(encoding="utf-8"))
    g = Graph()
    for feat in data.get("features", []):
        geom = feat.get("geometry") or {}
        lines = [geom["coordinates"]] if geom.get("type") == "LineString" else (
            geom.get("coordinates", []) if geom.get("type") == "MultiLineString" else [])
        for coords in lines:
            if len(coords) < 2:
                continue
            u, v = g.node(coords[0]), g.node(coords[-1])
            if u == v:
                continue
            g.adj[u].append(Edge(v, _length_km(coords), [list(c[:2]) for c in coords]))
    if not g.nodes:
        raise RoutingError(404, "roads_unavailable", "The road file has no usable roads.")
    return g


def classify(graph: Graph, flood, change) -> None:
    """Mark every edge: 2 if it touches mapped flood, 1 if it touches a change area, else 0."""
    flood_p = prep(flood) if flood is not None and not flood.is_empty else None
    change_p = prep(change) if change is not None and not change.is_empty else None
    for edges in graph.adj:
        for e in edges:
            line = LineString(e.coords)
            if flood_p is not None and flood_p.intersects(line):
                e.level = 2
            elif change_p is not None and change_p.intersects(line):
                e.level = 1
            else:
                e.level = 0


def _nearest(graph: Graph, lon: float, lat: float, leaving: bool) -> int:
    """Nearest node a trip can start from (leaving=True: has a road out) or finish at (has a road in)."""
    if not leaving:
        has_in = {e.to for edges in graph.adj for e in edges}
    best, bd = -1, float("inf")
    for i, n in enumerate(graph.nodes):
        if leaving and not graph.adj[i]:
            continue
        if not leaving and i not in has_in:
            continue
        d = haversine_km(n, (lon, lat))
        if d < bd:
            best, bd = i, d
    if best < 0 or bd > SNAP_LIMIT_KM:
        raise RoutingError(422, "point_outside_roads",
                           f"A pin is more than {SNAP_LIMIT_KM:g} km from any mapped road.")
    return best


def _dijkstra(graph: Graph, src: int, dst: int, cost):
    dist = {src: 0.0}
    prev: dict[int, tuple[int, Edge]] = {}
    heap = [(0.0, src)]
    done = set()
    while heap:
        d, u = heapq.heappop(heap)
        if u in done:
            continue
        if u == dst:
            break
        done.add(u)
        for e in graph.adj[u]:
            c = cost(e)
            if c is None:
                continue
            nd = d + c
            if nd < dist.get(e.to, float("inf")):
                dist[e.to] = nd
                prev[e.to] = (u, e)
                heapq.heappush(heap, (nd, e.to))
    if dst not in dist:
        return None
    edges = []
    v = dst
    while v != src:
        u, e = prev[v]
        edges.append(e)
        v = u
    return list(reversed(edges))


def _describe(edges, start, end) -> dict:
    coords = [list(start)]
    dist = 0.0
    flood = change = 0.0
    profile = [{"distKm": 0.0, "level": 0}]
    for e in edges:
        profile.append({"distKm": round(dist, 4), "level": e.level})
        coords.extend(e.coords)
        dist += e.km
        flood += e.km if e.level == 2 else 0.0
        change += e.km if e.level == 1 else 0.0
        profile.append({"distKm": round(dist, 4), "level": e.level})
    coords.append(list(end))
    return {
        "geometry": {"type": "LineString", "coordinates": coords},
        "distanceKm": dist,
        "hazard": {"floodKm": flood, "changeKm": change,
                   "score": FLOOD_SCORE * flood + CHANGE_SCORE * change},
        "profile": profile,
    }


def _f1(x: float) -> str:
    return f"{x:.1f}"


def briefing_text(shortest: dict, safe: dict | None, relation: str) -> str:
    s = (f"The shortest route is {_f1(shortest['distanceKm'])} km and passes through "
         f"{_f1(shortest['hazard']['floodKm'])} km of mapped flood and "
         f"{_f1(shortest['hazard']['changeKm'])} km of coherence-change areas.")
    if relation == "no_safe_route":
        return f"{s} No route exists that avoids all mapped flood, so no hazard-aware route is shown. Do not treat the shortest route as safe."
    if relation == "identical":
        return f"{s} The hazard-aware route follows the same roads, because the shortest route already avoids mapped flood. Hazard-aware does not mean guaranteed safe."
    extra = safe["distanceKm"] - shortest["distanceKm"]
    return (f"{s} The hazard-aware route is {_f1(safe['distanceKm'])} km ({'+' if extra >= 0 else ''}{_f1(extra)} km) "
            f"and passes through {_f1(safe['hazard']['floodKm'])} km of mapped flood and "
            f"{_f1(safe['hazard']['changeKm'])} km of coherence-change areas. "
            "Hazard-aware does not mean guaranteed safe: it only avoids what was mapped.")


def route(graph: Graph, start: tuple[float, float], end: tuple[float, float]) -> dict:
    """Shortest and hazard-aware routes between two (lon, lat) points on a classified graph."""
    a, b = _nearest(graph, *start, leaving=True), _nearest(graph, *end, leaving=False)
    shortest_edges = _dijkstra(graph, a, b, lambda e: e.km)
    if shortest_edges is None:
        raise RoutingError(404, "no_route", "No drivable route connects these two points.")
    safe_edges = _dijkstra(graph, a, b,
                           lambda e: None if e.level == 2 else e.km * (CHANGE_PENALTY if e.level == 1 else 1.0))
    s = _describe(shortest_edges, start, end)
    g = _describe(safe_edges, start, end) if safe_edges is not None else None
    if g is None:
        relation = "no_safe_route"
    elif abs(g["distanceKm"] - s["distanceKm"]) < 1e-9 and g["hazard"]["score"] == s["hazard"]["score"]:
        relation = "identical"
    else:
        relation = "detour" if g["hazard"]["floodKm"] == 0 and g["hazard"]["changeKm"] == 0 else "reduced"
    return {"shortest": s, "safe": g, "relation": relation,
            "detourKm": (g["distanceKm"] - s["distanceKm"]) if g else None,
            "briefing": {"text": briefing_text(s, g, relation), "templateVersion": TEMPLATE_VERSION}}


def union_of(geojson: dict | None):
    if not geojson:
        return None
    geoms = [shape(f["geometry"]) for f in geojson.get("features", []) if f.get("geometry")]
    return unary_union(geoms) if geoms else None
