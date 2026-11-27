"""sources.json: the Almanac's bibliography, written from the source registry and the download manifests."""
from __future__ import annotations

from ..core.fetch import read_manifest
from ..core.paths import WEB_DATA
from ..core.store import write_json


def build():
    from ..sources import registry
    out = []
    for s in registry().values():
        man = read_manifest(s.id)["files"]
        files = []
        for rel, e in sorted(man.items()):
            files.append({"file": rel, "url": e["url"], "sha256": e["sha256"], "bytes": e["bytes"],
                          "retrieved": e["retrieved"], "via": e.get("via", "direct")})
        info = s.info.to_dict()
        info["files"] = files if len(files) <= 40 else files[:5] + [{"file": f"… and {len(files) - 5} more tiles", "url": s.info.homepage}]
        info["file_count"] = len(files)
        info["bytes"] = sum(f["bytes"] for f in files if "bytes" in f)
        out.append(info)
    write_json(WEB_DATA / "sources.json", out)
    print(f"    {len(out)} sources, {sum(o['file_count'] for o in out)} files")
