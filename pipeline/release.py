"""Consolidated release: gates, package, verification (§25).

    python -m pipeline release [--allow-dirty]

1. Gate: `check --mode release` must pass (source reconciliation, cache integrity, browser journeys on these exact
   data files, accepted key totals). A failed gate stops here; nothing is packaged.
2. Package dist/nordicciv-<version>.zip: the complete source (pipeline, web incl. generated data, tests, tools, docs,
   licences), without raw downloads, caches, credentials or local tooling, plus RELEASE_MANIFEST.json (version, git
   commit, data hash, environment, SHA-256 of every file, gate results).
3. Verify: unzip into a temporary folder, run the built-data validation there, scan for secrets, and record the zip's
   SHA-256 next to it. The static site alone is dist/site/ (deploy that folder to any static host).
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
EXCLUDE_DIRS = {"__pycache__", ".node", ".last-good", "node_modules"}
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


def main(argv):
    from .check import main as check_main, data_hash
    version = (ROOT / "VERSION").read_text().strip()
    dirty = _git("status", "--porcelain")
    if dirty and "--allow-dirty" not in argv:
        print("release: the working tree has uncommitted changes; commit them first (or pass --allow-dirty)")
        print(dirty[:2000])
        return 2
    print(f"release {version}: running the release gates…")
    if check_main(["--mode", "release"]) != 0:
        print("release: gates FAILED — nothing packaged (see docs/CHECK_REPORT.txt)")
        return 1

    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    site = dist / "site"
    if site.exists():
        shutil.rmtree(site)
    shutil.copytree(WEB, site, ignore=shutil.ignore_patterns("dev", "*.map", ".DS_Store"))

    files = list(_files())
    report = (ROOT / "docs" / "CHECK_REPORT.txt").read_text().strip().splitlines()[-1]
    browser = json.loads((ROOT / "tests" / "results" / "browser.json").read_text())
    manifest = {
        "name": "NordicCiv", "version": version, "built": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "git_commit": _git("rev-parse", "HEAD") or None, "git_describe": _git("describe", "--tags", "--always") or None,
        "data_hash": data_hash(), "environment": _env(),
        "gates": {"check": report, "browser": {k: browser.get(k) for k in ("passed", "failed", "skipped", "browser", "when", "data_hash")}},
        "files": {str(f.relative_to(ROOT)).replace(os.sep, "/"): {"sha256": sha256(f), "bytes": f.stat().st_size} for f in files},
    }
    zpath = dist / f"nordicciv-{version}.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in files:
            z.write(f, f"nordicciv-{version}/" + str(f.relative_to(ROOT)).replace(os.sep, "/"))
        z.writestr(f"nordicciv-{version}/RELEASE_MANIFEST.json", json.dumps(manifest, indent=1, ensure_ascii=False))
    zsha = sha256(zpath)
    (dist / f"{zpath.name}.sha256").write_text(f"{zsha}  {zpath.name}\n")
    (dist / "RELEASE_MANIFEST.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False))

    # verify the package as a user would get it
    print("release: verifying the package (extract, built-data validation, secret scan)…")
    with tempfile.TemporaryDirectory() as td:
        with zipfile.ZipFile(zpath) as z:
            z.extractall(td)
        root = Path(td) / f"nordicciv-{version}"
        r = subprocess.run([sys.executable, "-m", "pipeline", "check", "--mode", "built"], cwd=root, capture_output=True, text=True)
        last = (r.stdout.strip().splitlines() or ["(no output)"])[-1]
        hits = []
        for f in root.rglob("*"):
            if f.is_file() and f.suffix in (".py", ".js", ".json", ".md", ".txt", ".html", ".css", ".yml", ".ps1", ".sh"):
                txt = f.read_text(errors="ignore")
                hits += [f"{f.relative_to(root)}: {p.pattern}" for p in SECRET_PATTERNS if p.search(txt)]
        n_files = sum(1 for _ in root.rglob("*") if _.is_file())
    ok = r.returncode == 0 and not hits
    print(f"release: extracted package — {n_files} files; built-data check: {last}; secrets found: {len(hits)}")
    for h in hits[:10]:
        print("   ", h)
    if not ok:
        print("release: package verification FAILED")
        return 1
    print(f"release: {zpath} ({zpath.stat().st_size / 1e6:.1f} MB) sha256 {zsha}")
    print(f"release: static site in {site}")
    return 0
