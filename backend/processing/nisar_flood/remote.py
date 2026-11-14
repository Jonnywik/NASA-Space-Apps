"""Read HDF5 files over HTTPS with range requests, or download them, using NASA Earthdata Login.

Why not fsspec/requests: they are not in requirements, and the redirect handling needs care.
NISAR download URLs on ``nisar.asf.earthdatacloud.nasa.gov`` redirect (possibly via
``urs.earthdata.nasa.gov``) to a pre-signed object-store URL on a different host. The bearer
token is sent only to NASA / ASF hosts and is removed on any redirect to another host, because a
pre-signed URL rejects an Authorization header and a third party must never receive the token.

The token is read from the EARTHDATA_TOKEN environment variable only. It is never logged,
printed, written to disk or included in an exception message; URLs are logged without their
query string (the query string of a pre-signed URL is itself a credential).
"""
from __future__ import annotations

import hashlib
import io
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict
from pathlib import Path
from typing import Iterator

from .constants import EARTHDATA_TOKEN_ENV

TRUSTED_SUFFIXES = (".earthdata.nasa.gov", ".earthdatacloud.nasa.gov", ".asf.alaska.edu", "earthdata.nasa.gov")
MAX_REDIRECTS = 8


class AuthError(RuntimeError):
    """Earthdata Login refused the request (missing, expired or wrong token)."""


class RemoteError(RuntimeError):
    """A network or protocol failure that retries did not fix."""


def get_token(env: dict | None = None) -> str | None:
    token = (env if env is not None else os.environ).get(EARTHDATA_TOKEN_ENV, "").strip()
    return token or None


def _redact(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _trusted(host: str, original_host: str) -> bool:
    host = (host or "").lower()
    return host == original_host or any(host == s.lstrip(".") or host.endswith(s) for s in TRUSTED_SUFFIXES)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def open_following_redirects(url: str, token: str | None, headers: dict | None = None, *, timeout: int = 60,
                             opener=None):
    """GET ``url`` following redirects by hand. Returns (response, final_url). Caller closes the response."""
    opener = opener or _OPENER
    original_host = urllib.parse.urlsplit(url).hostname or ""
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        host = urllib.parse.urlsplit(current).hostname or ""
        request_headers = {"User-Agent": "tanaw-nisar/1.0", **(headers or {})}
        if token and _trusted(host, original_host):
            request_headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(current, headers=request_headers)
        try:
            response = opener.open(request, timeout=timeout)
        except urllib.error.HTTPError as exc:
            if exc.code in (301, 302, 303, 307, 308) and exc.headers.get("Location"):
                current = urllib.parse.urljoin(current, exc.headers["Location"])
                exc.close()
                continue
            if exc.code in (401, 403):
                where = urllib.parse.urlsplit(current).hostname
                exc.close()
                raise AuthError(
                    f"HTTP {exc.code} from {where}. Check that EARTHDATA_TOKEN is set, unexpired and that the "
                    "Earthdata account has accepted the ASF/NISAR data-use terms.") from None
            code = exc.code
            exc.close()
            raise RemoteError(f"HTTP {code} for {_redact(current)}") from None
        return response, current
    raise RemoteError(f"More than {MAX_REDIRECTS} redirects for {_redact(url)}")


class HttpRangeFile(io.RawIOBase):
    """Read-only, seekable file object backed by HTTP range requests with a block cache."""

    def __init__(self, url: str, token: str | None = None, *, block_size: int = 4 * 1024 * 1024,
                 max_blocks: int = 48, retries: int = 3, timeout: int = 90, opener=None):
        super().__init__()
        self._url = url
        self._token = token
        self._block = int(block_size)
        self._max_blocks = int(max_blocks)
        self._retries = retries
        self._timeout = timeout
        self._opener = opener
        self._cache: "OrderedDict[int, bytes]" = OrderedDict()
        self._pos = 0
        self._resolved: str | None = None
        self.requests_made = 0
        self.bytes_fetched = 0
        self._size = self._probe()

    # -- network ------------------------------------------------------------
    def _probe(self) -> int:
        response, final = open_following_redirects(self._url, self._token, {"Range": "bytes=0-0"},
                                                   timeout=self._timeout, opener=self._opener)
        with response:
            self._resolved = final
            content_range = response.headers.get("Content-Range", "")
            if "/" in content_range and content_range.split("/")[-1].strip().isdigit():
                return int(content_range.split("/")[-1])
            length = response.headers.get("Content-Length")
            if response.status == 200 and length and length.isdigit():
                raise RemoteError("Server ignored the Range header; use the full-download fallback")
        raise RemoteError(f"Cannot determine remote file size for {_redact(self._url)}")

    def _fetch(self, start: int, stop: int) -> bytes:
        last: Exception | None = None
        for attempt in range(self._retries):
            target = self._resolved or self._url
            try:
                response, final = open_following_redirects(
                    target, self._token, {"Range": f"bytes={start}-{stop - 1}"}, timeout=self._timeout, opener=self._opener)
                with response:
                    data = response.read()
                self._resolved = final
                self.requests_made += 1
                self.bytes_fetched += len(data)
                if response.status == 200 and start != 0:
                    raise RemoteError("Server ignored the Range header")
                return data if response.status != 200 else data[start:stop]
            except AuthError as exc:
                if self._resolved and self._resolved != self._url:
                    self._resolved = None  # a pre-signed URL expired: resolve again from the original
                    last = exc
                    continue
                raise
            except (OSError, RemoteError) as exc:
                last = exc
                time.sleep(min(2 ** attempt, 8))
        raise RemoteError(f"Range request failed after {self._retries} attempts: {type(last).__name__}")

    # -- file protocol ------------------------------------------------------
    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self._pos

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self._pos, io.SEEK_END: self._size}[whence]
        self._pos = max(0, base + offset)
        return self._pos

    @property
    def size(self) -> int:
        return self._size

    def _block_bytes(self, index: int) -> bytes:
        if index in self._cache:
            self._cache.move_to_end(index)
            return self._cache[index]
        start = index * self._block
        data = self._fetch(start, min(start + self._block, self._size))
        self._cache[index] = data
        while len(self._cache) > self._max_blocks:
            self._cache.popitem(last=False)
        return data

    def readinto(self, buffer) -> int:
        view = memoryview(buffer).cast("B")
        want = min(len(view), max(self._size - self._pos, 0))
        done = 0
        while done < want:
            index, offset = divmod(self._pos, self._block)
            block = self._block_bytes(index)
            take = min(len(block) - offset, want - done)
            if take <= 0:
                break
            view[done:done + take] = block[offset:offset + take]
            done += take
            self._pos += take
        return done

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            size = max(self._size - self._pos, 0)
        buffer = bytearray(size)
        count = self.readinto(buffer)
        return bytes(buffer[:count])


def download(url: str, dest_dir: Path, token: str | None, *, expected_md5: str | None = None,
             expected_size: int | None = None, chunk: int = 8 * 1024 * 1024, progress=None) -> Path:
    """Download ``url`` into ``dest_dir`` (resumable, atomic rename). Verifies size and MD5 when given."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = Path(urllib.parse.urlsplit(url).path).name
    final = dest_dir / name
    if final.is_file() and (expected_size is None or final.stat().st_size == expected_size):
        return final
    part = dest_dir / (name + ".part")
    have = part.stat().st_size if part.exists() else 0
    headers = {"Range": f"bytes={have}-"} if have else {}
    response, _ = open_following_redirects(url, token, headers, timeout=120)
    with response:
        resumed = response.status == 206
        mode = "ab" if (have and resumed) else "wb"
        with part.open(mode) as out:
            written = out.tell()
            started = time.time()
            while True:
                data = response.read(chunk)
                if not data:
                    break
                out.write(data)
                written += len(data)
                if progress:
                    progress(written, expected_size, time.time() - started)
    size = part.stat().st_size
    if expected_size is not None and size != expected_size:
        raise RemoteError(f"Downloaded {size} bytes, expected {expected_size}; re-run to resume")
    if expected_md5:
        digest = hashlib.md5()
        with part.open("rb") as stream:
            for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                digest.update(block)
        if digest.hexdigest().lower() != expected_md5.lower():
            part.unlink()
            raise RemoteError("MD5 of the downloaded file does not match the catalogue; file deleted, re-run")
    part.replace(final)
    return final


def print_progress(written: int, total: int | None, seconds: float) -> None:
    rate = written / max(seconds, 1e-6) / 1e6
    done = f"{written / 1e9:.2f} GB" + (f" of {total / 1e9:.2f} GB" if total else "")
    print(f"\r  downloaded {done} ({rate:.1f} MB/s)", end="", file=sys.stderr, flush=True)
