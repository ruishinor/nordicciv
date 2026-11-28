"""sources.json: the Almanac's bibliography, written from the source registry and the download manifests."""
from __future__ import annotations

from ..core.fetch import read_manifest
from ..core.paths import WEB_DATA
from ..core.store import read_json, write_json

PATH = WEB_DATA / "sources.json"


def source_record(s):
    files = []
    for rel, e in sorted(read_manifest(s.id)["files"].items()):
        files.append({"file": rel, "url": e["url"], "sha256": e["sha256"], "bytes": e["bytes"],
                      "retrieved": e["retrieved"], "via": e.get("via", "direct")})
    info = s.info.to_dict()
    info["files"] = files if len(files) <= 40 else files[:5] + [
        {"file": f"… and {len(files) - 5} more files", "url": s.info.homepage}]
    info["file_count"] = len(files)
    info["bytes"] = sum(f["bytes"] for f in files)
    return info


def update_source(s):
    """Update one catalogue entry without rebuilding the other sources' provenance."""
    records = read_json(PATH) if PATH.exists() else []
    record = source_record(s)
    for i, old in enumerate(records):
        if old["id"] == s.id:
            records[i] = record
            break
    else:
        records.append(record)
    write_json(PATH, records)


def build():
    from ..sources import registry
    out = [source_record(s) for s in registry().values()]
    write_json(PATH, out)
    print(f"    {len(out)} sources, {sum(o['file_count'] for o in out)} files")
