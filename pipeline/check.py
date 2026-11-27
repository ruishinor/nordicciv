"""Validate web/data and print a data-quality report. Every line is PASS, NOTE, WARN or FAIL; any FAIL exits 1.

The checks follow the acceptance criteria: geography recognisable and in place, totals that reconcile with the
agencies' published totals, missing values kept as null, every indicator traceable to a source.
"""
from __future__ import annotations

import json
import math
import sys

from .core.paths import INTERIM, WEB_DATA

# Published national totals used as independent anchors (population 1 January 2026 / 31 December 2025, from the same
# agencies' national series that the pipeline downloads separately from the municipal tables).
TOL_POP = 0.0005  # municipal sums vs national totals: 0.05% (Sweden adds random noise from 2025; Christiansø is excluded)

KNOWN_PLACES = {  # name: (lon, lat) of the main town, for a placement check (±25 km)
    "Oslo": (10.75, 59.91), "Stockholm": (18.07, 59.33), "Copenhagen": (12.57, 55.68), "Bergen": (5.32, 60.39),
    "Göteborg": (11.97, 57.71), "Trondheim": (10.40, 63.43), "Malmö": (13.00, 55.60), "Aarhus": (10.20, 56.16),
    "Tromsø": (18.96, 69.65), "Kiruna": (20.23, 67.86), "Luleå": (22.15, 65.58), "Stavanger": (5.73, 58.97),
}


class Report:
    def __init__(self):
        self.lines = []

    def add(self, level, msg):
        self.lines.append((level, msg))
        print(f"{level:4s}  {msg}")

    @property
    def failed(self):
        return any(l == "FAIL" for l, _ in self.lines)


def load(name):
    p = WEB_DATA / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else None


def check_world(r, world):
    g = world["grid"]
    n = g["cols"] * g["rows"]
    for k in ("owner", "county", "elev", "water", "relief", "cover", "pop"):
        if len(world[k]) != n:
            r.add("FAIL", f"world.{k} has {len(world[k])} cells, expected {n}")
    owned = [i for i in range(n) if world["owner"][i] >= 0]
    area = len(owned) * 3 * math.sqrt(3) / 2 * g["radius"] ** 2
    # Norway mainland 323,800 km² land + Sweden 407,300 + Denmark 42,900 = ~774,000 km² land (plus lakes in hexes)
    lvl = "PASS" if 700_000 < area < 900_000 else "FAIL"
    r.add(lvl, f"world: {len(owned):,} Scandinavian land hexes ≈ {area:,.0f} km² (land of NO+SE+DK ≈ 774,000 km² + inland water)")
    bad = [i for i in owned if world["county"][i] < 0]
    r.add("PASS" if not bad else "FAIL", f"world: every Scandinavian land hex has a municipality ({len(bad)} without)")
    tot = sum(world["pop"])
    r.add("PASS", f"world: hex population sums to {tot:,}")
    return tot


def check_cities(r, cities, world, nation):
    counts = {}
    for c in cities:
        counts[c["country"]] = counts.get(c["country"], 0) + 1
    exp = {"NO": 357, "SE": 290, "DK": 98}
    r.add("PASS" if counts == exp else "FAIL", f"cities: municipalities per country {counts} (expected {exp}, 2024 boundaries)")
    owner = world["owner"]
    off = [c["name"] for c in cities if c["cell"] is None or owner[c["cell"]] < 0]
    r.add("PASS" if not off else "FAIL", f"cities: every banner stands on Scandinavian land ({len(off)} off: {off[:5]})")
    for cc in ("NO", "SE", "DK"):
        s = sum(c["population"] for c in cities if c["country"] == cc)
        n = nation["countries"][cc]["population"]
        r.add("PASS" if s == n else "FAIL", f"cities: {cc} municipal population sum {s:,} = country aggregate {n:,}")
    nulls_as_zero = [c["name"] for c in cities if c.get("growth") == 0 and c["pop_series"].get("2016") is None]
    r.add("PASS" if not nulls_as_zero else "FAIL", f"cities: missing growth is null, not 0 ({len(nulls_as_zero)} violations)")
    no_growth = [c["name"] for c in cities if c.get("growth") is None]
    r.add("NOTE", f"cities: {len(no_growth)} municipalities without a 2016 figure (boundary splits): {', '.join(no_growth)}")
    import pyproj  # placement check against known town coordinates
    from .core import geo
    frame = geo.Frame(world["projection"]["x0_km"], world["projection"]["y1_km"])
    for name, (lon, lat) in KNOWN_PLACES.items():
        c = next((x for x in cities if x["name"] == name), None)
        if not c:
            r.add("FAIL", f"cities: {name} missing")
            continue
        x, y = frame.from_ll(lon, lat)
        d = math.hypot(float(x) - c["x"], float(y) - c["y"])
        r.add("PASS" if d < 25 else "FAIL", f"cities: {name} banner {d:.1f} km from its reference position")
    partial = sum(1 for c in cities if c["yields_partial"])
    r.add("NOTE", f"cities: {partial} municipalities have a yield with a suppressed component (shown as ≥ lower bound)")


def check_totals(r, cities):
    for cc, src in (("NO", "ssb"), ("SE", "scb"), ("DK", "dst")):
        p = INTERIM / f"{src}.json"
        if not p.exists():
            r.add("NOTE", f"totals: {src} interim missing (skipped)")
            continue
        d = json.loads(p.read_text())
        nat = d["country"].get("pop", {})
        key = "2026"
        nat_v = nat.get(key) if nat else None
        s = sum(c["population"] for c in cities if c["country"] == cc)
        if nat_v:
            dev = abs(s - nat_v) / nat_v
            r.add("PASS" if dev <= TOL_POP else "FAIL", f"totals: {cc} municipalities {s:,} vs national table {int(nat_v):,} (Δ {dev:.4%}, tolerance {TOL_POP:.2%})")
        jt = d["country"].get("jobs", {}).get("00-99") or d["country"].get("jobs_total")
        if jt:
            sj = sum(c["jobs_total"] or 0 for c in cities if c["country"] == cc)
            dev = abs(sj - jt) / jt
            r.add("PASS" if dev <= 0.01 else "WARN", f"totals: {cc} jobs {sj:,.0f} vs national {jt:,.0f} (Δ {dev:.3%}; jobs abroad/unknown municipality excluded)")


def check_lenses(r, lenses, sources):
    ids = {s["id"] for s in sources}
    for l in lenses["lenses"]:
        srcs = [x.strip() for x in (l.get("source") or "").split(",") if x.strip()]
        missing = [s for s in srcs if s not in ids]
        ok = srcs and not missing and l.get("description") and l.get("unit") is not None and l.get("resolution")
        r.add("PASS" if ok else "FAIL", f"lens {l['id']}: source {srcs or '—'}, resolution {l.get('resolution')}" + (f", unknown {missing}" if missing else ""))
        vals = [v for v in l["values"] if v is not None]
        if any(isinstance(v, float) and (math.isnan(v) or math.isinf(v)) for v in vals):
            r.add("FAIL", f"lens {l['id']}: NaN/inf values")


def check_resources(r, res, world):
    owner = world["owner"]
    for it in res["items"]:
        if it["cell"] < 0:
            r.add("FAIL", f"resource {it['name']} outside the map")
    on_foreign = [it["name"] for it in res["items"] if it["cell"] >= 0 and owner[it["cell"]] == -2]
    r.add("PASS" if not on_foreign else "WARN", f"resources: {len(res['items'])} sites; {len(on_foreign)} on foreign hexes {on_foreign[:4]}")
    caps = {t: v for t, v in res["summary"]["national"].items()}
    r.add("NOTE", "resources: " + ", ".join(f"{k} {v['count']} ({v['value']} {v['unit']})" for k, v in caps.items()))


def check_sources(r, sources):
    for s in sources:
        ok = s.get("license") and s.get("publisher") and s.get("file_count", 0) > 0
        r.add("PASS" if ok else "FAIL", f"source {s['id']}: {s.get('file_count', 0)} files, licence: {s.get('license', '')[:60]}")


def main():
    r = Report()
    world, cities, nation, lenses, sources, res = (load(n) for n in ("world", "cities", "nation", "lenses", "sources", "resources"))
    for name, obj in (("world", world), ("cities", cities), ("nation", nation), ("lenses", lenses), ("sources", sources)):
        if obj is None:
            r.add("FAIL", f"{name}.json missing")
    if r.failed:
        return 1
    if lenses.get("packed") == "owned":  # expand like the browser does
        idx = [i for i, o in enumerate(world["owner"]) if o >= 0]
        for l in lenses["lenses"]:
            full = [None] * len(world["owner"])
            for k, i in enumerate(idx):
                full[i] = l["values"][k]
            l["values"] = full
    hex_pop = check_world(r, world)
    city_pop = sum(c["population"] for c in cities)
    dev = abs(hex_pop - city_pop) / city_pop
    r.add("PASS" if dev < 1e-4 else "FAIL", f"dasymetric: hex population {hex_pop:,} vs municipal total {city_pop:,} (Δ {dev:.5%}, rounding only)")
    check_cities(r, cities, world, nation)
    check_totals(r, cities)
    check_lenses(r, lenses, sources)
    if res:
        check_resources(r, res, world)
    check_sources(r, sources)
    worst = "FAIL" if r.failed else "WARN" if any(l == "WARN" for l, _ in r.lines) else "PASS"
    print(f"\n{sum(1 for l, _ in r.lines if l == 'PASS')} pass, {sum(1 for l, _ in r.lines if l == 'NOTE')} note, "
          f"{sum(1 for l, _ in r.lines if l == 'WARN')} warn, {sum(1 for l, _ in r.lines if l == 'FAIL')} fail → {worst}")
    (WEB_DATA.parent.parent / "docs").mkdir(exist_ok=True)
    (WEB_DATA.parent.parent / "docs" / "CHECK_REPORT.txt").write_text("\n".join(f"{l:4s}  {m}" for l, m in r.lines) + "\n")
    return 1 if r.failed else 0


if __name__ == "__main__":
    sys.exit(main())
