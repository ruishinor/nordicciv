"""Minimal JSON-stat 2.0 reader (PxWebApi 2 at SSB and SCB answer in it)."""
from __future__ import annotations

import itertools
import json
from pathlib import Path


def load(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def records(js: dict):
    """Yield ({dim: code}, value) for every cell; value None when missing/suppressed."""
    ids = js["id"]
    cats = []
    for d in ids:
        idx = js["dimension"][d]["category"]["index"]
        codes = sorted(idx, key=idx.get) if isinstance(idx, dict) else list(idx)
        cats.append(codes)
    vals = js["value"]
    status = js.get("status") or {}
    for n, combo in enumerate(itertools.product(*cats)):
        v = vals[n] if isinstance(vals, list) else vals.get(str(n))
        st = status.get(str(n)) if isinstance(status, dict) else (status[n] if n < len(status) else None)
        yield dict(zip(ids, combo)), v, st


def labels(js: dict, dim: str) -> dict:
    return js["dimension"][dim]["category"].get("label", {})


def updated(js: dict) -> str | None:
    return js.get("updated")
