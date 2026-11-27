"""Consolidated release with staged verification and promotion (NC-A01..A03).

    python -m pipeline release [--allow-dirty]

1. Candidate: the working tree must be clean. Its identity is pipeline/candidate.py (app, data, tests, pipeline).
2. Stage: the package tree is copied to dist/.staging/<version>-<id>/; its candidate id must equal the repository's.
3. Gates on the staged copy: unit tests (tests/run_unit.py), browser journeys (tests/smoke_browser.py) against a server
   that serves the staged web/ folder, then `check --mode release` with that evidence (source reconciliation, cache
   integrity, accepted key totals, evidence bound to this candidate, every mandatory journey PASS).
4. Package and verify, still in staging: zip + RELEASE_MANIFEST.json (+ the evidence), extract it into a temporary
   folder, compare every file's SHA-256 with the manifest, run the built-data validation there, scan for secrets.
5. Promote: only now is dist/release/ (the last known-good release) moved to dist/previous/ and the verified staging
   folder moved to dist/release/. A failure at any step leaves dist/release/ untouched and moves the staging folder to
   dist/.failed/ for inspection: an unverified candidate is never in the release location.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

from .core.paths import ROOT, WEB, WEB_DATA

INCLUDE = ["pipeline", "web", "tests", "tools", "docs", "README.md", "LICENSE", "VERSION", "requirements.txt",
           "requirements-lock.txt", ".gitignore", "scripts", ".github"]
EXCLUDE_DIRS = {"__pycache__", ".node", ".last-good", "node_modules", "results"}
EXCLUDE_FILES = re.compile(r"(\.pyc$|\.env$|\.DS_Store$|credentials|secret|\.pem$|\.key$)", re.I)
SECRET_PATTERNS = [re.compile(p) for p in (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", r"(?i)aws_secret_access_key\s*=",
                                           r"ghp_[A-Za-z0-9]{30,}", r"(?i)api[_-]?key\s*[:=]\s*['\"][A-Za-z0-9]{16,}")]


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _files():
    for item in INCLUDE:
        p = ROOT / item
        if p.is_file():
            yield p
        elif p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file() and not any(part in EXCLUDE_DIRS for part in f.relative_to(ROOT).parts) and not EXCLUDE_FILES.search(f.name):
                    yield f


def _git(*args):
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:
        return ""


def _env():
    from importlib.metadata import version, PackageNotFoundError
    out = {"python": platform.python_version(), "platform": platform.platform()}
    for m in ("numpy", "pyproj", "shapely", "pyarrow", "scipy", "pillow", "scikit-image", "playwright"):
        try:
            out[m] = version(m)
        except PackageNotFoundError:
            out[m] = None
    try:
        import pyproj
        import shapely
        out["proj"], out["geos"] = pyproj.proj_version_str, shapely.geos_version_string
    except Exception:
        pass
    return out


def _copy_tree(dst: Path):
    for f in _files():
        rel = f.relative_to(ROOT)
        (dst / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dst / rel)


def _serve(directory: Path):
    """A static server for the staged web/ folder on a free local port (subprocess, stopped by the caller)."""
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "--directory", str(directory)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    import urllib.request
    for _ in range(50):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/index.html", timeout=1)
            break
        except Exception:
            time.sleep(0.2)
    return proc, f"http://127.0.0.1:{port}/"


def _fail(stage: Path, why: str) -> int:
    failed = ROOT / "dist" / ".failed"
    failed.mkdir(parents=True, exist_ok=True)
    if stage.exists():
        dest = failed / f"{stage.name}-{time.strftime('%Y%m%d-%H%M%S')}"
        shutil.move(str(stage), dest)
        print(f"release: FAILED — {why}. Staging moved to {dest.relative_to(ROOT)}; dist/release/ unchanged.")
    else:
        print(f"release: FAILED — {why}; dist/release/ unchanged.")
    return 1


def main(argv):
    from .candidate import manifest
    from .check import data_hash
    version = (ROOT / "VERSION").read_text().strip()
    dirty = _git("status", "--porcelain")
    if dirty and "--allow-dirty" not in argv:
        print("release: the working tree has uncommitted changes; commit them first (or pass --allow-dirty)")
        print(dirty[:2000])
        return 2
    cand = manifest(ROOT)
    dist = ROOT / "dist"
    stage = dist / ".staging" / f"{version}-{cand['id'][:12]}"
    if stage.exists():
        shutil.rmtree(stage)
    tree = stage / f"nordicciv-{version}"
    print(f"release {version}: staging candidate {cand['id'][:12]} in {stage.relative_to(ROOT)}…")
    _copy_tree(tree)
    staged = manifest(tree)
    if staged["id"] != cand["id"]:
        return _fail(stage, "the staged copy is not identical to the repository candidate")
    evidence = tree / "tests" / "results"

    # --- gates, on the staged copy
    print("release: unit tests on the staged copy…")
    u = subprocess.run([sys.executable, str(tree / "tests" / "run_unit.py")], cwd=tree)
    print("release: browser journeys against the staged web/ folder…")
    proc, url = _serve(tree / "web")
    try:
        env = dict(os.environ)
        axe = ROOT / "tests" / ".node" / "node_modules" / "axe-core" / "axe.min.js"  # test tool, not part of the candidate
        if axe.exists():
            env.setdefault("NORDICCIV_AXE", str(axe))
        b = subprocess.run([sys.executable, str(tree / "tests" / "smoke_browser.py"), url, "--candidate", str(tree), "--out", str(evidence)],
                           cwd=tree, env=env)
    finally:
        proc.terminate()
        proc.wait(timeout=10)
    print("release: release gates (data, sources, cache, evidence for this candidate)…")
    from .check import main as check_main
    g = check_main(["--mode", "release", "--evidence", str(evidence), "--candidate", str(tree)])
    if u.returncode or b.returncode or g:
        return _fail(stage, f"gates (unit {u.returncode}, browser {b.returncode}, release check {g})")
    if manifest(tree)["id"] != cand["id"] or manifest(ROOT)["id"] != cand["id"]:
        return _fail(stage, "the candidate changed while the gates ran")

    # --- package, in staging
    out = stage / "release"
    out.mkdir()
    shutil.copytree(tree / "web", out / "site", ignore=shutil.ignore_patterns("dev", "*.map", ".DS_Store"))
    files = [p for p in sorted(tree.rglob("*")) if p.is_file() and "results" not in p.relative_to(tree).parts and "__pycache__" not in p.parts]
    report = (ROOT / "docs" / "CHECK_REPORT.txt").read_text()
    bj, uj = (json.loads((evidence / n).read_text()) for n in ("browser.json", "unit.json"))
    manifest_doc = {
        "name": "NordicCiv", "version": version, "built": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "git_commit": _git("rev-parse", "HEAD") or None, "git_describe": _git("describe", "--tags", "--always") or None,
        "candidate": {"id": cand["id"], "parts": cand["parts"], "counts": cand["counts"]}, "data_hash": data_hash(),
        "environment": _env(),
        "gates": {"check": report.strip().splitlines()[-1],
                  "unit": {k: uj.get(k) for k in ("ran", "failures", "errors", "skipped", "when")},
                  "browser": {k: bj.get(k) for k in ("passed", "failed", "skipped", "browser", "when", "missing")}},
        "files": {p.relative_to(tree).as_posix(): {"sha256": sha256(p), "bytes": p.stat().st_size} for p in files},
    }
    zpath = out / f"nordicciv-{version}.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in files:
            z.write(p, f"nordicciv-{version}/" + p.relative_to(tree).as_posix())
        z.writestr(f"nordicciv-{version}/RELEASE_MANIFEST.json", json.dumps(manifest_doc, indent=1, ensure_ascii=False))
        for n in ("browser.json", "unit.json"):
            z.write(evidence / n, f"nordicciv-{version}/RELEASE_EVIDENCE/{n}")
        z.writestr(f"nordicciv-{version}/RELEASE_EVIDENCE/CHECK_REPORT.txt", report)
    zsha = sha256(zpath)
    (out / f"{zpath.name}.sha256").write_text(f"{zsha}  {zpath.name}\n")
    (out / "RELEASE_MANIFEST.json").write_text(json.dumps(manifest_doc, indent=1, ensure_ascii=False))

    # --- verify the package as a user would get it
    print("release: verifying the package (extract, file hashes, built-data validation, secret scan)…")
    with tempfile.TemporaryDirectory() as td:
        with zipfile.ZipFile(zpath) as z:
            z.extractall(td)
        root = Path(td) / f"nordicciv-{version}"
        mism = [k for k, v in manifest_doc["files"].items() if not (root / k).exists() or sha256(root / k) != v["sha256"]]
        extracted_id = manifest(root)["id"]
        r = subprocess.run([sys.executable, "-m", "pipeline", "check", "--mode", "built"], cwd=root, capture_output=True, text=True)
        last = (r.stdout.strip().splitlines() or ["(no output)"])[-1]
        hits = []
        for f in root.rglob("*"):
            if f.is_file() and f.suffix in (".py", ".js", ".json", ".md", ".txt", ".html", ".css", ".yml", ".ps1", ".sh"):
                txt = f.read_text(errors="ignore")
                hits += [f"{f.relative_to(root)}: {p.pattern}" for p in SECRET_PATTERNS if p.search(txt)]
        n_files = sum(1 for _ in root.rglob("*") if _.is_file())
    print(f"release: extracted package — {n_files} files; {len(mism)} hash mismatches; candidate {extracted_id[:12]}; "
          f"built-data check: {last}; secrets found: {len(hits)}")
    for h in hits[:10]:
        print("   ", h)
    if mism or extracted_id != cand["id"] or r.returncode != 0 or hits:
        return _fail(stage, "package verification")

    # --- promote: last known-good → dist/previous, verified staging → dist/release
    rel, prev = dist / "release", dist / "previous"
    if rel.exists():
        if prev.exists():
            shutil.rmtree(prev)
        rel.rename(prev)
    out.rename(rel)
    shutil.rmtree(stage)
    print(f"release: promoted {rel.relative_to(ROOT)}/{zpath.name} ({(rel / zpath.name).stat().st_size / 1e6:.1f} MB) sha256 {zsha}")
    print(f"release: previous release kept in {prev.relative_to(ROOT)}/; static site in {(rel / 'site').relative_to(ROOT)}/")
    return 0
