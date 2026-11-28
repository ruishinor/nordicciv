"""Reconcile a recovered DSB snapshot when only lokalId values and source metadata changed.

Run from the candidate repository: python -m tools.reconcile_shelter_snapshot
No network access, no general rebuild. Refuse any change to rooms, capacities, addresses
or stored coordinates; use the normal shelter builder for substantive changes.
"""
from __future__ import annotations

import copy
import re
from pipeline.core.fetch import read_manifest, verify
from pipeline.core.paths import WEB_DATA
from pipeline.core.store import read_json, write_json
from pipeline.sources.shelters import Shelters
from pipeline.build.catalog import source_record


def reconcile(old, fresh, manifest):
    new = copy.deepcopy(old)
    rows = new["shelters"]
    raw = fresh["rows"]

    def index(items):
        result = {r["room"]: r for r in items}
        if len(result) != len(items) or any(type(k) is not int for k in result):
            raise ValueError("duplicate or invalid room number")
        return result

    a, b = index(rows), index(raw)
    if set(a) != set(b) or len(a) != fresh["number_matched"]:
        raise ValueError("room coverage differs; use the shelter builder and review changes")
    ids = [r["id"] for r in raw]
    if len(set(ids)) != len(ids) or not all(isinstance(i, str) and re.fullmatch(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", i) for i in ids):
        raise ValueError("invalid or duplicate source identifiers")
    for room, x in a.items():
        y = b[room]
        if (x["places"], x.get("address"), x["lat"], x["lon"]) != (
                y["places"], y.get("address"), round(y["lat"], 6), round(y["lon"], 6)):
            raise ValueError(f"substantive change in room {room}; review normal rebuild")
        x["id"] = y["id"]
    extracted = sorted({r["extracted"][:10] for r in raw if r.get("extracted")})
    new["source"].update(sha256=manifest["sha256"], retrieved=manifest["retrieved"],
                         extracted=extracted[-1] if extracted else None,
                         number_matched=fresh["number_matched"])
    return new


def main():
    source = Shelters()
    for f in source.files():
        ok, reason = verify(source.id, f.rel_path, url=f.url, method=f.method, body=f.body)
        if not ok:
            raise ValueError(f"{f.rel_path}: {reason}")
    manifest = read_manifest(source.id)["files"]["tilfluktsrom_4258.gml"]
    path = WEB_DATA / "shelters.json"
    cat_path = WEB_DATA / "sources.json"
    old = read_json(path)
    new = reconcile(old, source.process(), manifest)
    catalogue = read_json(cat_path)
    matches = [i for i, record in enumerate(catalogue) if record["id"] == source.id]
    if len(matches) != 1:
        raise ValueError("expected exactly one DSB catalogue record")
    catalogue[matches[0]] = source_record(source)
    changed = sum(a["id"] != b["id"] for a, b in zip(old["shelters"], new["shelters"]))
    print(f"DSB snapshot: {changed} changed identifiers; all {len(new['shelters'])} rooms, capacities, addresses and positions unchanged")
    print(f"Previous SHA-256: {old['source']['sha256']}")
    print(f"Recovered SHA-256: {new['source']['sha256']}")
    write_json(path, new)
    write_json(cat_path, catalogue)
    print("Updated shelters.json and only the DSB source catalogue entry.")


if __name__ == "__main__":
    main()
