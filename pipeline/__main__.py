"""NordicCiv data pipeline CLI.

  python -m pipeline list                     sources and builders
  python -m pipeline fetch [source ...]       download raw files (cached); unreachable hosts are queued for the relay
  python -m pipeline relay-plan               print queued requests (JSON) for tools/relay.js
  python -m pipeline relay-ingest FILE        store relay answers in the cache (with provenance)
  python -m pipeline process [source ...]     raw -> data/interim/<source>.json
  python -m pipeline build [builder ...]      interim -> web/data/*.json
  python -m pipeline check                    validate web/data, print the data-quality report (exit 1 on FAIL)
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


def cmd_process(names):
    for s in _sources(names):
        t0 = time.time()
        try:
            out = s.process()
        except FileNotFoundError as e:
            print(f"process {s.id}: SKIP ({e})")
            continue
        if out is not None:
            write_json(INTERIM / f"{s.id}.json", out)
        print(f"process {s.id:14s} ok ({time.time()-t0:.1f}s)")


def cmd_build(names):
    from .build import run
    run(names)


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
        cmd_process(args)
    elif cmd == "build":
        cmd_build(args)
    elif cmd == "check":
        from .check import main as check_main
        return check_main()
    elif cmd == "all":
        cmd_fetch([])
        cmd_process([])
        cmd_build([])
        from .check import main as check_main
        return check_main()
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
