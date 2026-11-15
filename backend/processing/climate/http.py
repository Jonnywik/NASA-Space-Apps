"""Small HTTP helper: bounded timeout, one conservative retry."""
from __future__ import annotations

import time

import httpx

USER_AGENT = "tanaw-climate/1.0 (NASA Space Apps hackathon; open-source)"


class UpstreamError(RuntimeError):
    """A provider could not be reached or returned an unusable answer."""


def get_json(url: str, params: dict | None = None, *, timeout: float = 60.0,
             retries: int = 1, wait: float = 20.0, method: str = "GET", json_body=None):
    """GET/POST JSON. Retries once (default) after `wait` seconds on network errors,
    429 and 5xx. Raises UpstreamError with a plain reason otherwise."""
    last = "unknown error"
    for attempt in range(retries + 1):
        try:
            with httpx.Client(timeout=timeout, headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
                resp = client.request(method, url, params=params, json=json_body)
            if resp.status_code == 200:
                return resp.json(), str(resp.url)
            last = f"HTTP {resp.status_code}: {resp.text[:200]}"
            if resp.status_code not in (429, 500, 502, 503, 504):
                break
        except (httpx.HTTPError, ValueError) as exc:
            last = f"{type(exc).__name__}: {exc}"
        if attempt < retries:
            time.sleep(wait)
    raise UpstreamError(f"{url} failed: {last}")
