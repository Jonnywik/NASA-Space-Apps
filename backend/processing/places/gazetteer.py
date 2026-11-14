"""Gazetteer search and point lookup over the bundled boundary files (no network)."""
from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from shapely.geometry import Point, shape
from shapely.strtree import STRtree

from . import path_for

_PREFIX = re.compile(r'^(?:(?:brgy|bgy|barangay|brg)\b\.?\s*)+', re.I)
_CITY_WORDS = re.compile(r'\b(?:city of|city|municipality of|lungsod ng)\b', re.I)


def normalize(text: str) -> str:
    """Lower-case, strip accents (n with tilde -> n), drop 'Brgy./Barangay' and 'City of'."""
    text = unicodedata.normalize('NFKD', str(text or ''))
    text = ''.join(c for c in text if not unicodedata.combining(c)).lower().strip()
    text = _PREFIX.sub('', text)
    text = _CITY_WORDS.sub(' ', text)
    text = re.sub(r'[^a-z0-9 ]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def load_gazetteer(root=None) -> list[dict]:
    p = path_for('gazetteer', root)
    return json.loads(Path(p).read_text(encoding='utf-8'))['places']


class Gazetteer:
    def __init__(self, places: list[dict]):
        self.places = places
        self._index = [(p, normalize(p['name']), normalize(p.get('city') or '')) for p in places]

    def search(self, query: str, limit: int = 10) -> list[dict]:
        q = normalize(query)
        if not q:
            return []
        ranked = []
        for p, name, city in self._index:
            full = f'{name} {city}'.strip()
            if name == q:
                score = 0
            elif name.startswith(q):
                score = 1
            elif any(w.startswith(q) for w in name.split()) or f' {q}' in f' {name}':
                score = 2
            elif q in name:
                score = 3
            elif full.startswith(q) or q in full:
                score = 4  # e.g. "tonsuya malabon"
            else:
                continue
            ranked.append((score, 0 if p.get('inStudyArea') else 1, 0 if p['level'] == 'city' else 1, name, p['id'], p))
        ranked.sort(key=lambda r: r[:5])
        return [public_place(r[5]) for r in ranked[:max(0, int(limit))]]


def public_place(p: dict) -> dict:
    keys = ('id', 'name', 'level', 'city', 'province', 'lon', 'lat', 'bbox', 'inStudyArea')
    return {k: p.get(k) for k in keys}


@lru_cache(maxsize=4)
def _gazetteer(root_key):
    return Gazetteer(load_gazetteer(root_key or None))


def search(query: str, limit: int = 10, root=None) -> list[dict]:
    return _gazetteer(str(root) if root else '').search(query, limit)


class PointLocator:
    """Which barangay and city contain a lon/lat (boundaries as bundled, simplified)."""

    def __init__(self, barangays: dict, cities: dict | None = None):
        self._b = _Layer(barangays)
        self._c = _Layer(cities) if cities else None

    def locate(self, lon: float, lat: float) -> dict:
        pt = Point(lon, lat)
        b = self._b.find(pt)
        c = self._c.find(pt) if self._c else None
        out = {'lon': lon, 'lat': lat, 'barangay': None, 'city': None}
        if b is not None:
            out['barangay'] = {'id': b['id'], 'name': b['name']}
        if c is None and b is not None and self._c:
            c = self._c.by_id.get(b.get('cityId'))
        if c is not None:
            out['city'] = {'id': c['id'], 'name': c['name'], 'province': c.get('province')}
        elif b is not None:
            out['city'] = {'id': b.get('cityId'), 'name': b.get('city'), 'province': b.get('province')}
        return out


class _Layer:
    def __init__(self, fc: dict):
        self.props, geoms = [], []
        for f in fc['features']:
            self.props.append(f['properties'])
            geoms.append(shape(f['geometry']))
        self.geoms = geoms
        self.tree = STRtree(geoms)
        self.by_id = {p['id']: p for p in self.props}

    def find(self, pt):
        for i in sorted(self.tree.query(pt, predicate='intersects')):
            return self.props[int(i)]
        return None


@lru_cache(maxsize=4)
def _locator(root_key):
    root = root_key or None
    b = json.loads(Path(path_for('barangay', root)).read_text(encoding='utf-8'))
    c = json.loads(Path(path_for('city', root)).read_text(encoding='utf-8'))
    return PointLocator(b, c)


def locate(lon: float, lat: float, root=None) -> dict:
    return _locator(str(root) if root else '').locate(lon, lat)
