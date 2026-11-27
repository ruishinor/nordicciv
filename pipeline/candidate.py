"""Release candidate identity (NC-A01).

A candidate is the exact set of files that a release ships and that the tests exercise:

    app      every file under web/ except web/data (HTML, CSS, JavaScript, icons, fonts)
    data     every file under web/data (generated datasets, relief tiles, polygons)
    tests    the test implementation: tests/*.py, tests/*.mjs, tests/fixtures/*
    pipeline the pipeline and its checks: pipeline/**/*.py

Each part gets a SHA-256 over its sorted (path, file SHA-256) pairs; the candidate id is the SHA-256 of the four part
hashes. Evidence (browser journeys, unit tests, data checks) records the candidate id it ran against, and the release
gate recomputes it, so evidence from another build, or with the data hash alone, cannot certify a release.

    python -m pipeline.candidate [ROOT]     # prints the manifest summary as JSON
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

PARTS = ("app", "data", "tests", "pipeline")
SKIP_DIRS = {"__pycache__", ".node", "results", "node_modules", ".last-good"}
SKIP_NAMES = {".DS_Store", "Thumbs.db"}


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _part(root: Path, rel: str) -> str | None:
    parts = Path(rel).parts
    if any(x in SKIP_DIRS for x in parts) or parts[-1] in SKIP_NAMES or rel.endswith(".pyc"):
        return None
    if parts[0] == "web":
        return "data" if len(parts) > 1 and parts[1] == "data" else ("app" if parts[1] != "dev" else None)
    if parts[0] == "tests":
        if len(parts) == 2 and (rel.endswith(".py") or rel.endswith(".mjs")):
            return "tests"
        if len(parts) == 3 and parts[1] == "fixtures":
            return "tests"
        return None
    if parts[0] == "pipeline" and rel.endswith(".py"):
        return "pipeline"
    return None


def manifest(root: Path) -> dict:
    root = Path(root)
    files = {}
    for top in ("web", "tests", "pipeline"):
        base = root / top
        if not base.exists():
            continue
        for f in sorted(base.rglob("*")):
            if not f.is_file():
                continue
            rel = f.relative_to(root).as_posix()
            part = _part(root, rel)
            if part:
                files[rel] = {"part": part, "sha256": _sha(f), "bytes": f.stat().st_size}
    hashes = {}
    for part in PARTS:
        h = hashlib.sha256()
        for rel in sorted(k for k, v in files.items() if v["part"] == part):
            h.update(f"{rel}\0{files[rel]['sha256']}\n".encode())
        hashes[part] = h.hexdigest()
    cid = hashlib.sha256("".join(f"{p}:{hashes[p]}\n" for p in PARTS).encode()).hexdigest()
    return {"id": cid, "parts": hashes, "files": files,
            "counts": {p: sum(1 for v in files.values() if v["part"] == p) for p in PARTS}}


def web_files(m: dict) -> dict:
    """{path relative to web/: sha256} for the files a browser can load (app + data)."""
    return {k[4:]: v["sha256"] for k, v in m["files"].items() if v["part"] in ("app", "data")}


if __name__ == "__main__":
    m = manifest(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1])
    print(json.dumps({"id": m["id"], "parts": m["parts"], "counts": m["counts"]}, indent=1))
