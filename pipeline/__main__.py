"""NordicCiv data pipeline CLI.

  python -m pipeline list                     sources and builders
  python -m pipeline fetch [source ...]       download raw files (cached); unreachable hosts are queued for the relay
  python -m pipeline relay-plan               print queued requests (JSON) for tools/relay.js
  python -m pipeline relay-ingest FILE        store relay answers in the cache (with provenance)
  python -m pipeline process [source ...] [--strict]
                                              raw -> data/interim/<source>.json (--strict: missing source = error)
  python -m pipeline build [builder ...] [--no-guard]
                                              interim -> web/data/*.json, validated; restored on failure
  python -m pipeline release                  release gates + static site + versioned zip with hashes (dist/)
  python -m pipeline check [--mode built|source|release] [--accept]
                                              validation gates (exit 1 on FAIL); see pipeline/check.py
  python -m pipeline verify-cache             check every cached download against its manifest
  python -m pipeline all [--offline]          fetch + process + build + check
  python -m pipeline serve [--port 8765]      serve web/
"""
from __future__ import annotations

import json
import sys
import time

from .core import fetch
from .core.paths import INTERIM, RELAY, WEB
from .core.store import write_json


def _sources(names):
    from .sources import registry
    reg = registry()
    if not names:
        return list(reg.values())
    return [reg[n] for n in names]


def cmd_fetch(names):
    queued = []
    for s in _sources(names):
        t0 = time.time()
        q = s.fetch()
        queued += q
        print(f"fetch {s.id:14s} {len(s.files()) - len(q):4d} cached, {len(q):3d} queued  ({time.time()-t0:.1f}s)")
    if queued:
        print(f"{len(queued)} request(s) queued in data/relay/pending.json (network refused); run them with tools/relay.js")
    return queued


def cmd_process(names, strict=False):
    skipped = []
    for s in _sources(names):
        t0 = time.time()
        try:
            out = s.process()
        except FileNotFoundError as e:
            print(f"process {s.id}: SKIP ({e})")
            skipped.append(s.id)
            continue
        if out is not None:
            write_json(INTERIM / f"{s.id}.json", out)
        print(f"process {s.id:14s} ok ({time.time()-t0:.1f}s)")
    if skipped and strict:
        raise SystemExit(f"process: required sources missing ({', '.join(skipped)}); a release build cannot continue. "
                         "Run `python -m pipeline fetch` (or the relay) first.")
    return skipped


def cmd_build(names, guard=True):
    """Build web/data. Guarded by default: the current files are kept aside, the new ones are validated in
    'built' mode, and on any failure (an exception or a FAIL) the previous files are restored, so a failed build
    never replaces the last good data."""
    import shutil
    from .build import run
    from .core.paths import DATA, WEB_DATA
    keep = DATA / ".last-good"
    if guard and WEB_DATA.exists():
        if keep.exists():
            shutil.rmtree(keep)
        shutil.copytree(WEB_DATA, keep)
    try:
        run(names)
        if guard:
            from .check import main as check_main
            print("build: validating the new files (built mode)…")
            if check_main(["--mode", "built"]) != 0:
                raise RuntimeError("validation failed")
    except BaseException as e:
        if guard and keep.exists():
            shutil.rmtree(WEB_DATA)
            shutil.copytree(keep, WEB_DATA)
            print(f"build FAILED ({e}); web/data restored to the last good version")
        raise
    return 0


def main(argv):
    if not argv:
        print(__doc__)
        return 0
    if "--offline" in argv:
        fetch.OFFLINE = True
        argv = [a for a in argv if a != "--offline"]
    cmd, args = argv[0], argv[1:]
    if cmd == "list":
        from .build import BUILDERS
        for s in _sources([]):
            print(f"source  {s.id:14s} {s.info.title}")
        for b in BUILDERS:
            print(f"builder {b.__name__.split('.')[-1]}")
    elif cmd == "fetch":
        cmd_fetch(args)
    elif cmd == "relay-plan":
        p = RELAY / "pending.json"
        print(p.read_text() if p.exists() else "[]")
    elif cmd == "relay-ingest":
        res = json.loads(open(args[0]).read())
        done = fetch.ingest_relay(res)
        print(f"ingested {len(done)} file(s)")
    elif cmd == "process":
        cmd_process([a for a in args if not a.startswith("--")], strict="--strict" in args)
    elif cmd == "build":
        cmd_build([a for a in args if not a.startswith("--")], guard="--no-guard" not in args)
    elif cmd == "release":
        from .release import main as release_main
        return release_main(args)
    elif cmd == "check":
        from .check import main as check_main
        return check_main(args)
    elif cmd == "verify-cache":
        from .check import Report, check_cache
        r = Report("source")
        check_cache(r)
        return 1 if r.failed else 0
    elif cmd == "all":
        queued = cmd_fetch([])
        if queued and "--offline" not in sys.argv:
            print("all: some downloads are queued for the relay; finish them before building a release")
        cmd_process([], strict=True)
        cmd_build([])
        from .check import main as check_main
        return check_main(["--mode", "source"])
    elif cmd == "serve":
        import functools
        import http.server
        port = int(args[args.index("--port") + 1]) if "--port" in args else 8765
        h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(WEB))
        print(f"serving {WEB} at http://127.0.0.1:{port}")
        http.server.ThreadingHTTPServer(("127.0.0.1", port), h).serve_forever()
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) or 0)
