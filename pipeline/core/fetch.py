"""Cached downloads with provenance, plus a browser *relay* for blocked networks.

Every file a source downloads lands in data/raw/<source_id>/ and is recorded in
that folder's manifest.json (url, method, request body, sha256, size, retrieval
time, how it was retrieved). The manifest feeds the in-app Almanac, so every
number on screen can be traced back to an exact request.

Direct download is tried first (urllib, retried with backoff). When the network
refuses a host (some build sandboxes only allow package registries), the request
is queued in data/relay/pending.json instead. Any ordinary browser can then run
the queued requests (see tools/relay.js) and `python -m pipeline relay-ingest`
stores the answers in the cache exactly as a direct download would, with
"via": "browser-relay" in the manifest. On a normal machine the relay is never
needed: `python -m pipeline fetch` downloads everything directly.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .paths import RAW, RELAY
from .store import atomic_write_bytes, atomic_write_text

USER_AGENT = "nordicciv/0.1 (open data pipeline; https://github.com/)"
OFFLINE = False  # --offline: never touch the network
RETRIES = 3
BACKOFF = 2.0
TIMEOUT = 120
_REFUSED: set[str] = set()  # hosts that refused a connection in this run: queue their requests straight away


class OfflineError(RuntimeError):
    pass


class Pending(RuntimeError):
    """The file is not cached and could not be downloaded directly; it was queued for the relay."""


def manifest_path(source_id: str) -> Path:
    return RAW / source_id / "manifest.json"


def read_manifest(source_id: str) -> dict:
    p = manifest_path(source_id)
    if p.exists():
        return json.loads(p.read_text())
    return {"source": source_id, "files": {}}


def write_manifest(source_id: str, man: dict) -> None:
    atomic_write_text(manifest_path(source_id), json.dumps(man, indent=1, ensure_ascii=False, sort_keys=True))


def record(source_id: str, rel_path: str, url: str, data: bytes, *, method: str = "GET", body: str | None = None,
           via: str = "direct", note: str | None = None) -> Path:
    """Store bytes in the cache and write their provenance."""
    path = RAW / source_id / rel_path
    atomic_write_bytes(path, data)
    man = read_manifest(source_id)
    entry = {
        "url": url, "method": method, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
        "retrieved": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "via": via,
    }
    if body:
        entry["body"] = body
    if note:
        entry["note"] = note
    man["files"][rel_path] = entry
    write_manifest(source_id, man)
    return path


def _queue(source_id: str, rel_path: str, url: str, method: str, body: str | None, headers: dict | None) -> None:
    RELAY.mkdir(parents=True, exist_ok=True)
    p = RELAY / "pending.json"
    pending = json.loads(p.read_text()) if p.exists() else []
    key = f"{source_id}/{rel_path}"
    pending = [r for r in pending if r["key"] != key]
    req = {"key": key, "url": url, "method": method}
    if body:
        req["body"] = body
    if headers:
        req["headers"] = headers
    pending.append(req)
    atomic_write_text(p, json.dumps(pending, indent=1, ensure_ascii=False))


def cached(source_id: str, rel_path: str) -> Path | None:
    path = RAW / source_id / rel_path
    return path if path.exists() and rel_path in read_manifest(source_id)["files"] else None


def download(source_id: str, url: str, rel_path: str, *, method: str = "GET", body: str | None = None,
             headers: dict | None = None, force: bool = False, relay: bool = True) -> Path:
    """Return the cached path for (url, body); download it if needed.

    Raises Pending if the file had to be queued for the browser relay.
    """
    hit = cached(source_id, rel_path)
    if hit and not force:
        return hit
    if OFFLINE:
        raise OfflineError(f"--offline: {source_id}/{rel_path} is not cached")
    from urllib.parse import urlsplit
    host = urlsplit(url).netloc
    err = "host refused earlier in this run" if host in _REFUSED else None
    for attempt in range(0 if host in _REFUSED else RETRIES):
        try:
            data_bytes = body.encode() if body is not None else None
            req = urllib.request.Request(url, data=data_bytes, method=method,
                                         headers={"User-Agent": USER_AGENT, **(headers or {})})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                data = r.read()
            return record(source_id, rel_path, url, data, method=method, body=body)
        except urllib.error.HTTPError as exc:
            err = exc
            if exc.code < 500 and exc.code not in (403, 407, 429):
                raise
            if exc.code in (403, 407):  # proxy policy denial: no point retrying
                break
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            err = exc
        time.sleep(BACKOFF * (2 ** attempt) if attempt < RETRIES - 1 else 0)
    _REFUSED.add(host)
    if relay:
        _queue(source_id, rel_path, url, method, body, headers)
        raise Pending(f"{source_id}/{rel_path}: queued for relay ({err})")
    raise RuntimeError(f"download failed: {url}: {err}")


def ingest_relay(results: dict) -> list[str]:
    """Store relay answers: {key: {"status": int, "b64"|"text": ...}} for keys in pending.json."""
    import base64

    p = RELAY / "pending.json"
    pending = json.loads(p.read_text()) if p.exists() else []
    by_key = {r["key"]: r for r in pending}
    done, left = [], []
    for key, req in by_key.items():
        res = results.get(key)
        if not res or res.get("status") != 200:
            left.append(req)
            continue
        data = base64.b64decode(res["b64"]) if "b64" in res else res["text"].encode()
        source_id, rel_path = key.split("/", 1)
        record(source_id, rel_path, req["url"], data, method=req["method"], body=req.get("body"), via="browser-relay")
        done.append(key)
    atomic_write_text(p, json.dumps(left, indent=1, ensure_ascii=False))
    return done
