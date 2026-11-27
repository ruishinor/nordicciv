"""Atomic file writes and compact JSON."""
from __future__ import annotations

import json
import math
import os
import tempfile
from pathlib import Path


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))


def _clean(o):
    """NaN/inf -> None so the JSON is valid; numpy scalars -> python."""
    if isinstance(o, float):
        return None if (math.isnan(o) or math.isinf(o)) else o
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if hasattr(o, "item") and not isinstance(o, (str, bytes)):
        try:
            return _clean(o.item())
        except Exception:
            return o
    return o


def write_json(path: Path, obj, *, indent=None) -> None:
    sep = (",", ":") if indent is None else (",", ": ")
    atomic_write_text(path, json.dumps(_clean(obj), ensure_ascii=False, separators=sep, indent=indent, allow_nan=False))


def read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))
