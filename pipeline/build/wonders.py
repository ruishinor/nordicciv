"""Wonders: discoverable landmarks selected by published rules (never by taste).

* every UNESCO World Heritage Site in Norway, Sweden and Denmark (Wikidata P757),
* national parks of at least 1,000 km² (Wikidata area),
* universities with at least 15,000 students (latest Wikidata P2196 value; Norwegian figures checked against SSB 08585),
* operational fixed links: bridges ≥ 6 km and tunnels ≥ 11 km (Wikidata length).
"""
from __future__ import annotations

import json
import re

import numpy as np
import shapely

from ..core import geo
from ..core.paths import RAW, WEB_DATA
from ..core.store import read_json, write_json
from . import admin

RULES = [
    {"id": "world_heritage", "kind": "heritage", "kinds": ["heritage", "natural"],
     "text": "Every UNESCO World Heritage Site with a component in Norway, Sweden or Denmark (Greenland, the Faroes "
             "and Svalbard are outside this map). Positions are Wikidata coordinates of a component inside the three countries."},
    {"id": "national_park", "kind": "natural", "kinds": ["natural"],
     "text": "National parks with an area of at least 1,000 km² (Wikidata P2046; sea area included where the park includes it)."},
    {"id": "university", "kind": "university", "kinds": ["university"],
     "text": "Universities with at least 15,000 students, or founded in 1975 or earlier with at least 5,000 students or no "
             "recorded count (Wikidata P2196 latest value and P571 inception). Counts are as recorded in Wikidata and "
             "can lag the institutions' own figures; several large universities (e.g. Uppsala, Copenhagen) have none."},
    {"id": "fixed_link", "kind": "engineering", "kinds": ["engineering"],
     "text": "Bridges of at least 6 km and tunnels of at least 11 km in operation (Wikidata P2043 length, opening date present)."},
]
NATURAL_WHS = {"West Norwegian Fjords", "Geirangerfjord", "High Coast", "Laponian Area", "Stevns Klint", "Wadden Sea",
               "Ilulissat", "Kvarken"}


def _pt(wkt):
    m = re.match(r"Point\(([-\d.]+) ([-\d.]+)\)", wkt or "")
    return (float(m.group(1)), float(m.group(2))) if m else None


def _bindings(path):
    return json.loads(path.read_text())["results"]["bindings"]


def build():
    world = read_json(WEB_DATA / "world.json")
    g = world["grid"]
    owner, county = world["owner"], world["county"]
    frame = geo.Frame(world["projection"]["x0_km"], world["projection"]["y1_km"])
    polys = admin.polygons()
    nordic = shapely.unary_union(list(polys.values())).buffer(0.05)
    cid = [c["geoid"] for c in world["counties"]]
    wonders = []

    def place(w, lon, lat):
        x, y = frame.from_ll(lon, lat)
        x, y = float(x), float(y)
        c = int(geo.cell_at(np.array([x]), np.array([y]), g["radius"], g["cols"], g["rows"])[0])
        w.update(x=round(x, 1), y=round(y, 1), cell=c, lon=round(lon, 4), lat=round(lat, 4),
                 county=cid[county[c]] if c >= 0 and county[c] >= 0 else None,
                 cbsa=cid[county[c]] if c >= 0 and county[c] >= 0 else None,
                 state=world["states"][owner[c]]["abbr"] if c >= 0 and owner[c] >= 0 else None, curated=False)
        wonders.append(w)

    # --- World Heritage --------------------------------------------------------------------------------------------
    groups = {}
    for b in _bindings(RAW / "wikidata" / "whs.json"):
        wid = b["whs"]["value"]
        m = re.match(r"(\d+)", wid)
        if not m:
            continue
        base = m.group(1)
        pt = _pt(b.get("coord", {}).get("value"))
        main = "-" not in wid
        gr = groups.setdefault(base, {"items": [], "countries": set()})
        gr["countries"].add(b["countryLabel"]["value"])
        gr["items"].append({"name": b["itemLabel"]["value"], "pt": pt, "main": main, "exact": wid == base,
                            "inside": bool(pt and shapely.contains_xy(nordic, *pt)),
                            "year": (b.get("inscribed", {}).get("value") or "")[:4], "qid": b["item"]["value"]})
    rank = 0
    for base, gr in sorted(groups.items(), key=lambda kv: int(kv[0])):
        inside = [it for it in gr["items"] if it["inside"]]
        if not inside:
            continue
        mains = sorted([it for it in gr["items"] if it["main"]], key=lambda it: (not it["exact"], len(it["name"])))
        head = mains[0] if mains else min(inside, key=lambda it: len(it["name"]))
        pos = head if head["inside"] else inside[0]
        years = [it["year"] for it in gr["items"] if it["year"]]
        rank += 1
        name = head["name"]
        kind = "natural" if any(k.lower() in name.lower() for k in NATURAL_WHS) or "fossil" in name.lower() or "klint" in name.lower() else "heritage"
        place({"id": f"whs-{base}", "name": name, "short": name, "kind": kind, "rule": "world_heritage", "rank": rank,
               "metrics": {"whs_id": base, "inscribed": min(years) if years else None,
                           "components_in_scandinavia": len(inside), "countries": sorted(gr["countries"])},
               "wikidata": head["qid"].rsplit("/", 1)[-1]}, *pos["pt"])

    # --- National parks ≥ 1000 km² -------------------------------------------------------------------------------
    parks = {}
    for b in _bindings(RAW / "wikidata" / "national_parks_v3.json"):
        q = b["p"]["value"]
        area = float(b["area_m2"]["value"]) / 1e6 if "area_m2" in b else None
        pt = _pt(b.get("coord", {}).get("value"))
        if area is None or pt is None or not shapely.contains_xy(nordic, *pt):
            continue
        p = parks.setdefault(q, {"name": b["pLabel"]["value"], "area": area, "pt": pt, "country": b["countryLabel"]["value"],
                                 "inception": (b.get("inception", {}).get("value") or "")[:4]})
        p["area"] = max(p["area"], area)
    big = sorted([p for p in parks.values() if p["area"] >= 1000], key=lambda p: -p["area"])
    for i, p in enumerate(big, 1):
        place({"id": f"np-{i}", "name": p["name"], "short": re.sub(r" National Park$", "", p["name"]), "kind": "natural",
               "rule": "national_park", "rank": i,
               "metrics": {"area_km2": round(p["area"]), "established": p["inception"] or None, "country": p["country"]}},
              *p["pt"])

    # --- Universities ≥ 15,000 students ----------------------------------------------------------------------------
    unis = {}
    for b in _bindings(RAW / "wikidata" / "universities.json"):
        q = b["u"]["value"]
        pt = _pt(b.get("coord", {}).get("value"))
        st = float(b["students"]["value"]) if "students" in b else None
        u = unis.setdefault(q, {"name": b["uLabel"]["value"], "pt": pt, "students": st, "country": b["countryLabel"]["value"],
                                "inception": (b.get("inception", {}).get("value") or "")[:4], "place": b.get("placeLabel", {}).get("value")})
        if st and (u["students"] is None or st > u["students"]):
            u["students"] = st
        if not u["pt"] and pt:
            u["pt"] = pt
    def qualifies(u):
        if not u["pt"] or not shapely.contains_xy(nordic, *u["pt"]):
            return False
        if u["students"] and u["students"] >= 15000:
            return True
        founded = int(u["inception"]) if (u["inception"] or "").isdigit() else 9999
        named = re.search(r"Universit|Institut|School of Economics|Business School", u["name"]) and not re.search(
            r"Folkeuniversitet|Department|Film|Design|Arkitekt|Art", u["name"])
        return founded <= 1975 and bool(named) and (u["students"] is None or u["students"] >= 5000)
    big = sorted([u for u in unis.values() if qualifies(u)], key=lambda u: (-(u["students"] or 0), u["inception"] or "9999"))
    for i, u in enumerate(big, 1):
        place({"id": f"uni-{i}", "name": u["name"], "short": u["name"], "kind": "university", "rule": "university", "rank": i,
               "metrics": {"students": int(u["students"]) if u["students"] else None, "founded": u["inception"] or None, "country": u["country"],
                           "students_source": "Wikidata P2196 (latest value)"}}, *u["pt"])

    # --- Fixed links ---------------------------------------------------------------------------------------------------
    links = {}
    for b in _bindings(RAW / "links" / "fixed_links.json"):
        if "opened" not in b:
            continue
        L = float(b["length"]["value"])
        kind = b["kind"]["value"]
        if (kind == "bridge" and L < 6000) or (kind == "tunnel" and L < 11000):
            continue
        pt = _pt(b.get("coord", {}).get("value"))
        if not pt:
            continue
        links.setdefault(b["x"]["value"], {"name": b["xLabel"]["value"], "kind": kind, "len": L, "pt": pt,
                                           "opened": b["opened"]["value"][:4], "country": b["countryLabel"]["value"]})
    for i, l in enumerate(sorted(links.values(), key=lambda l: -l["len"]), 1):
        place({"id": f"link-{i}", "name": l["name"], "short": l["name"], "kind": "engineering", "rule": "fixed_link", "rank": i,
               "metrics": {"length_km": round(l["len"] / 1000, 1), "type": l["kind"], "opened": l["opened"], "country": l["country"]}},
              *l["pt"])

    for w in wonders:
        w["category"] = w["kind"]
        w["kind"] = {"heritage": "landmark", "engineering": "landmark"}.get(w["kind"], w["kind"])
        w["motif"] = _motif(w)
    out = {"version": 1, "vintage": {"wikidata": "Wikidata SPARQL, retrieved 2026-11"},
           "sources": ["wikidata", "links"], "rules": RULES,
           "national": {"world_heritage_sites": sum(1 for w in wonders if w["rule"] == "world_heritage")},
           "wonders": wonders}
    write_json(WEB_DATA / "wonders.json", out)
    from collections import Counter
    print(f"    {len(wonders)} wonders: {dict(Counter(w['rule'] for w in wonders))}")
    for w in wonders:
        print(f"      {w['rule']:15s} {w['name']} {w['metrics']}") if w["rule"] != "world_heritage" else None


MOTIF_RULES = [  # visual only: which sprite stands on the wonder's plinth
    (r"rock art|rock carvings|tanum|alta|falun|copper mountain", "carved"), (r"bryggen|visby|r.ros|hälsingland|christiansfeld|church town|gammelstad|hanseatic", "quarter"),
    (r"urnes|stave", "spire"), (r"jelling|birka|ring fortress|hovg", "mound"), (r"struve", "obelisk"),
    (r"rjukan|notodden|engelsberg|ironworks", "brickhall"), (r"roskilde|kronborg|drottningholm|cathedral|castle", "rotunda"),
    (r"grimeton|radio", "gantry"), (r"skogskyrkog|woodland cemetery", "memorial"), (r"karlskrona|naval", "coast"),
    (r"wadden|klint|vega|high coast|kvarken|fossil|archipelago", "coast"), (r"laponia|fjord", "peak"), (r"öland|oland|par force|hunting", "forest"),
    (r"bridge|belt", "bridge"),
]


def _motif(w):
    name = w["name"].lower()
    for pat, m in MOTIF_RULES:
        if re.search(pat, name):
            return m
    if w["rule"] == "national_park":
        return "forest" if re.search(r"skog|forest|ånderdalen|tyresta|söderåsen", name) else "peak"
    if w["rule"] == "fixed_link":
        return "bridge" if w["metrics"].get("type") == "bridge" else "carved"
    return None
