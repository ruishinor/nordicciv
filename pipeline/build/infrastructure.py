"""Tile improvements: roads and rail rasterised onto hex links, ferry routes as lines, ports and airports as sites.

Roads and rail are Natural Earth 1:10m line work (map art, generalised, not a statistic). Ports and airports
carry measured traffic from Eurostat (2024): gross weight of goods handled, and passengers carried.
"""
from __future__ import annotations

import csv
import io
import json
import re
import unicodedata

import numpy as np
import shapely
from shapely.geometry import shape

from ..core import geo
from ..core.paths import RAW, WEB_DATA
from ..core.store import read_json, write_json
from ..sources.stats import estat_records

ROAD_CLASSES = [{"id": "motorway", "name": "Motorway / expressway"}, {"id": "major", "name": "Major road"}]
RAIL_TIERS = [{"id": "main", "name": "Main line"}, {"id": "secondary", "name": "Secondary line"}]
HUBS = {"L": "Large airport (≥ 10 M passengers)", "M": "Medium (≥ 2 M)", "S": "Small (≥ 0.3 M)", "N": "Regional"}


def _norm(s):
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).replace("ø", "o").replace("æ", "ae").replace("å", "a")
    return re.sub(r"[^a-z]", "", s)


def build():
    world = read_json(WEB_DATA / "world.json")
    g = world["grid"]
    R, cols, rows = g["radius"], g["cols"], g["rows"]
    owner, county = world["owner"], world["county"]
    frame = geo.Frame(world["projection"]["x0_km"], world["projection"]["y1_km"])
    hexgrid = __import__("pipeline.core.hexgrid", fromlist=["HexGrid"]).HexGrid(R, cols, rows)
    cities = read_json(WEB_DATA / "cities.json")
    cid = [c["geoid"] for c in world["counties"]]

    def cells_along(coords):
        x, y = frame.from_ll(coords[:, 0], coords[:, 1])
        ls = shapely.LineString(np.c_[x, y])
        n = max(2, int(ls.length / 1.0) + 1)
        pts = [ls.interpolate(d) for d in np.linspace(0, ls.length, n)]
        px = np.array([p.x for p in pts])
        py = np.array([p.y for p in pts])
        return geo.cell_at(px, py, R, cols, rows), np.round(np.c_[x, y], 1)

    links = {}
    ferries = []
    roads = json.loads((RAW / "natural_earth" / "ne_10m_roads.geojson").read_text())["features"]
    for f in roads:
        p = f["properties"]
        geom = shape(f["geometry"])
        parts = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
        typ = p.get("type") or ""
        for part in parts:
            c = np.asarray(part.coords)
            if not ((c[:, 0] > 3).any() and (c[:, 0] < 33).any() and (c[:, 1] > 54).any() and (c[:, 1] < 72).any()):
                continue
            cells, xy = cells_along(c)
            if typ.startswith("Ferry"):
                if (np.array([owner[k] for k in cells if k >= 0]) >= 0).any():
                    ferries.append({"name": p.get("name") or None, "pts": xy.ravel().tolist(),
                                    "seasonal": "seasonal" in typ.lower()})
                continue
            if p.get("expressway") == 1 or typ == "Major Highway":
                cls = 0
            elif typ == "Secondary Highway" or (p.get("scalerank") or 10) <= 6:
                cls = 1
            else:
                continue
            _add_links(links, cells, owner, hexgrid, cls, p.get("name") or p.get("label") or None)
    road_list = [[a, b, v[0], v[1]] for (a, b), v in sorted(links.items())]

    rlinks = {}
    rail = json.loads((RAW / "natural_earth" / "ne_10m_railroads.geojson").read_text())["features"]
    for f in rail:
        p = f["properties"]
        tier = 0 if (p.get("scalerank") or 10) <= 7 else 1
        geom = shape(f["geometry"])
        for part in (list(geom.geoms) if hasattr(geom, "geoms") else [geom]):
            c = np.asarray(part.coords)
            if not ((c[:, 0] > 3).any() and (c[:, 0] < 33).any() and (c[:, 1] > 54).any() and (c[:, 1] < 72).any()):
                continue
            cells, _ = cells_along(c)
            _add_links(rlinks, cells, owner, hexgrid, tier, None)
    rail_list = [[a, b, v[0]] for (a, b), v in sorted(rlinks.items())]

    def site_cell(x, y):
        c = int(geo.cell_at(np.array([x]), np.array([y]), R, cols, rows)[0])
        if c >= 0 and owner[c] >= 0:
            return c
        best, bd = c, 1e9
        for k in hexgrid.neighbours(c) if c >= 0 else []:
            if owner[k] >= 0:
                d = (hexgrid.center(k % cols, k // cols)[0] - x) ** 2 + (hexgrid.center(k % cols, k // cols)[1] - y) ** 2
                if d < bd:
                    best, bd = k, d
        return best

    def attach(site, x, y):
        c = site_cell(x, y)
        site.update(x=round(float(x), 1), y=round(float(y), 1), cell=c,
                    county=cid[county[c]] if c >= 0 and county[c] >= 0 else None,
                    cbsa=cid[county[c]] if c >= 0 and county[c] >= 0 else None,
                    state=world["states"][owner[c]]["abbr"] if c >= 0 and owner[c] >= 0 else None)
        return site

    # --- airports: OurAirports positions + Eurostat passengers 2024 --------------------------------------------
    pax = {}
    for r in estat_records(json.loads((RAW / "eurostat" / "avia_paoa.json").read_text())):
        if r.get("schedule") == "TOTAL" and r.get("tra_cov") == "TOTAL" and r["rep_airp"][:2] in ("NO", "SE", "DK"):
            pax[r["rep_airp"].split("_", 1)[1]] = r["value"]
    airports = []
    for r in csv.DictReader(io.StringIO((RAW / "ourairports" / "airports.csv").read_text(encoding="utf-8"))):
        if r["iso_country"] not in ("NO", "SE", "DK") or r["type"] not in ("large_airport", "medium_airport", "small_airport"):
            continue
        p = pax.get(r["ident"])
        if p is None and r["type"] != "large_airport":
            continue
        x, y = frame.from_ll(float(r["longitude_deg"]), float(r["latitude_deg"]))
        hub = None if p is None else "L" if p >= 1e7 else "M" if p >= 2e6 else "S" if p >= 3e5 else "N"
        airports.append(attach({"id": r["ident"], "iata": r["iata_code"] or None, "name": r["name"],
                                "city": r["municipality"], "hub": hub, "passengers": p, "enplanements": p,
                                "cargo_lbs": None, "year": 2024, "country": r["iso_country"]}, x, y))
    airports.sort(key=lambda a: -(a["passengers"] or 0))

    # --- ports: Eurostat main ports 2024, placed at the matching municipality's main settlement / NE port ------
    js = json.loads((RAW / "links" / "mar_go_aa.json").read_text())
    lab = js["dimension"]["rep_mar"]["category"]["label"]
    by_name = {}
    for c in cities:
        for nm in {c["name"], c.get("place") or ""}:
            if nm:
                by_name.setdefault(_norm(nm), c)
    ne_ports = {}
    for f in json.loads((RAW / "natural_earth" / "ne_10m_ports.geojson").read_text())["features"]:
        lon, lat = f["geometry"]["coordinates"][:2]
        ne_ports[_norm(f["properties"]["name"])] = (lon, lat)
    ports = []
    for r in estat_records(js):
        code = r["rep_mar"]
        if code[:2] not in ("NO", "SE", "DK") or len(code) < 8 or code.endswith(("888", "88S", "88N", "88D")):
            continue
        name = lab[code]
        first = re.split(r"[,/(]", name)[0].strip()
        key = _norm(first.replace("Københavns Havn", "København").replace(" S", "").replace(" N", ""))
        pos = None
        if key in ne_ports:
            pos = ne_ports[key]
        else:
            c = by_name.get(key) or by_name.get(_norm(first.split()[0]))
            if c:
                pos = (c["lon"], c["lat"])
        if pos is None:
            continue
        x, y = frame.from_ll(*pos)
        ports.append(attach({"id": code, "name": name, "short": first, "type": "coastal", "tons": r["value"] * 1000,
                             "tonnes": r["value"] * 1000, "year": 2024, "country": code[:2]}, x, y))
    ports.sort(key=lambda p: -p["tonnes"])
    for i, p in enumerate(ports, 1):
        p["rank"] = i

    out = {
        "version": 1,
        "vintage": {"roads": "Natural Earth 1:10m (v5)", "rail": "Natural Earth 1:10m railroads", "ferries": "Natural Earth 1:10m ferry routes",
                    "ports": "Eurostat mar_go_aa, 2024 (gross weight of goods handled)",
                    "airports": "Eurostat avia_paoa, 2024 (passengers carried); positions OurAirports"},
        "sources": ["natural_earth", "links", "eurostat", "ourairports"],
        "rules": {
            "roads": "Natural Earth roads in the three countries: expressways and 'Major Highway' as motorways; secondary "
                     "highways and roads at scale rank ≤ 6 as major roads. Generalised map art.",
            "rail": "Natural Earth railroads: scale rank ≤ 7 main lines, others secondary. Generalised, incomplete.",
            "ferries": "Natural Earth ferry routes touching Scandinavian land (a selection, not every ferry).",
            "ports": "Ports reported by Eurostat's maritime statistics as 'main ports' with goods handled in 2024. Aggregate "
                     "'other ports' rows are left out.",
            "airports": "Airports with passenger figures in Eurostat avia_paoa 2024, plus every 'large airport' in OurAirports. "
                        "Passengers carried count arrivals and departures.",
        },
        "road_classes": ROAD_CLASSES, "rail_tiers": RAIL_TIERS, "hubs": HUBS,
        "roads": road_list, "rail": rail_list, "ferries": ferries, "ports": ports, "airports": airports,
    }
    write_json(WEB_DATA / "infrastructure.json", out)
    print(f"    roads {len(road_list)} links, rail {len(rail_list)}, ferries {len(ferries)}, ports {len(ports)}, airports {len(airports)}")


def _add_links(links, cells, owner, grid, cls, name):
    seq = [c for i, c in enumerate(cells) if c >= 0 and (i == 0 or c != cells[i - 1])]
    for a, b in zip(seq, seq[1:]):
        if a == b or b not in grid.neighbours(a):
            continue
        if owner[a] == -2 or owner[b] == -2 or (owner[a] < 0 and owner[b] < 0):
            continue
        k = (min(a, b), max(a, b))
        if k not in links or links[k][0] > cls:
            links[k] = (cls, name)
