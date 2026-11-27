"""Resources on the map: power plants (installed capacity), oil and gas fields (production), mines (SGU).

Thresholds are part of each type's description. Capacity (MW) is never presented as generation; mines are
classed by SGU's economic status and production fields; fields by Sodir's activity status.
"""
from __future__ import annotations

import csv
import io
import json
from collections import defaultdict

import numpy as np
from shapely.geometry import shape

from ..core import geo
from ..core.paths import RAW, WEB_DATA
from ..core.store import read_json, write_json

TYPES = [
    {"id": "hydro", "name": "Hydropower plant", "category": "energy", "emoji": "💧", "icon": "r-hydro", "color": "#4aa3df",
     "unit": "MW", "source": "powerplants", "min": 50,
     "description": "Hydropower stations (reservoir, run-of-river) with ≥ 50 MW installed capacity, in operation. "
                    "Capacity is what the turbines can deliver, not what they produce in a year."},
    {"id": "pumped", "name": "Pumped storage", "category": "energy", "emoji": "🔋", "icon": "r-pumped_storage", "color": "#3f7fbf",
     "unit": "MW", "source": "powerplants", "min": 20, "description": "Pumped-storage hydropower ≥ 20 MW."},
    {"id": "nuclear", "name": "Nuclear power plant", "category": "energy", "emoji": "☢️", "icon": "r-nuclear", "color": "#e8d44d",
     "unit": "MW", "source": "powerplants", "min": 0,
     "description": "Nuclear reactors in operation (units at one site combined). Retired reactors (Barsebäck, Ringhals 1–2, "
                    "Oskarshamn 1–2, Ågesta) are excluded."},
    {"id": "wind", "name": "Wind farm (onshore)", "category": "energy", "emoji": "🌬️", "icon": "r-wind", "color": "#9fd6c8",
     "unit": "MW", "source": "powerplants", "min": 50, "description": "Onshore wind farms with ≥ 50 MW installed capacity."},
    {"id": "offshore_wind", "name": "Offshore wind farm", "category": "energy", "emoji": "🌊", "icon": "r-wind", "color": "#7fd0e8",
     "unit": "MW", "source": "powerplants", "min": 0, "description": "Offshore wind farms in operation (all sizes)."},
    {"id": "solar", "name": "Solar park", "category": "energy", "emoji": "☀️", "icon": "r-solar", "color": "#f2c94c",
     "unit": "MW", "source": "powerplants", "min": 20, "description": "Ground-mounted solar parks ≥ 20 MW."},
    {"id": "thermal", "name": "Thermal power plant", "category": "energy", "emoji": "🏭", "icon": "r-gas_plant", "color": "#c0785a",
     "unit": "MW", "source": "powerplants", "min": 50,
     "description": "Combustion plants ≥ 50 MW (coal, gas, oil, biomass, waste), often combined heat and power for "
                    "district heating."},
    {"id": "oil_gas", "name": "Oil & gas field", "category": "mineral", "emoji": "🛢️", "icon": "r-oil", "color": "#5b4a3a",
     "unit": "million Sm³ o.e./yr", "source": "sodir", "min": 0,
     "description": "Producing fields on the Norwegian continental shelf, at the centre of the field outline, with saleable "
                    "production in the latest complete year (million standard m³ of oil equivalents). Danish North Sea "
                    "fields are not included (no open field-level dataset was reachable)."},
    {"id": "metal_mine", "name": "Metal mine", "category": "mineral", "emoji": "⛏️", "icon": "r-copper", "color": "#b0a090",
     "unit": "", "source": "sgu", "min": 0,
     "description": "Sweden: entries of SGU's mineral resources database classed 'mine/quarry' with a metallic main type "
                    "(sulphide, iron oxide, precious metal). 'Producing' when SGU's production field says so. Norwegian "
                    "mines are not included (the NGU service was not reachable)."},
    {"id": "industrial_mineral", "name": "Industrial mineral mine", "category": "mineral", "emoji": "🪨", "icon": "r-coal_mine", "color": "#c9c0b0",
     "unit": "", "source": "sgu", "min": 0,
     "description": "Sweden: SGU 'mine/quarry' entries of industrial minerals (limestone, dolomite, quartz, feldspar…)."},
]
TYPE = {t["id"]: t for t in TYPES}


def build():
    world = read_json(WEB_DATA / "world.json")
    g = world["grid"]
    frame = geo.Frame(world["projection"]["x0_km"], world["projection"]["y1_km"])
    cities = read_json(WEB_DATA / "cities.json")
    owner, county = world["owner"], world["county"]
    states = world["states"]
    items = []

    def place(lon, lat):
        x, y = frame.from_ll(lon, lat)
        x, y = float(x), float(y)
        c = int(geo.cell_at(np.array([x]), np.array([y]), g["radius"], g["cols"], g["rows"])[0])
        return round(x, 1), round(y, 1), c

    # --- power plants ------------------------------------------------------------------------------------------
    rows = [r for r in csv.DictReader(io.StringIO((RAW / "powerplants" / "powerplants.csv").read_text(encoding="utf-8")))
            if r["Country"] in ("Norway", "Sweden", "Denmark")]
    sites = defaultdict(lambda: {"cap": 0.0, "units": 0, "names": set()})
    for r in rows:
        out = r.get("DateOut") or ""
        if out and float(out) <= 2026:
            continue
        if r["Name"].startswith(("Barseback", "Agesta")):
            continue
        ft, tech = r["Fueltype"], r["Technology"]
        if ft == "Hydro":
            typ = "pumped" if tech == "Pumped Storage" else "hydro"
        elif ft == "Nuclear":
            typ = "nuclear"
        elif ft == "Wind":
            typ = "offshore_wind" if tech == "Offshore" else "wind"
        elif ft == "Solar":
            typ = "solar"
        elif ft in ("Hard Coal", "Natural Gas", "Oil", "Solid Biomass", "Waste", "Lignite", "Other"):
            typ = "thermal"
        else:
            continue
        try:
            lat, lon, cap = float(r["lat"]), float(r["lon"]), float(r["Capacity"] or 0)
        except ValueError:
            continue
        key = (typ, round(lat, 2), round(lon, 2)) if typ == "nuclear" else (typ, r["id"])
        s = sites[key]
        s["cap"] += cap
        s["units"] += 1
        s["names"].add(_site_name(r["Name"]) if typ == "nuclear" else r["Name"])
        s.update(lat=lat, lon=lon, fuel=ft, country=r["Country"], date=r.get("DateIn"))
    for (typ, *_), s in sites.items():
        if s["cap"] < TYPE[typ]["min"]:
            continue
        x, y, c = place(s["lon"], s["lat"])
        name = sorted(s["names"])[0]
        detail = f"{s['units']} units, " if s["units"] > 1 else ""
        detail += f"{s['fuel'].lower()}" + (f", in service since {int(float(s['date']))}" if s.get("date") else "")
        items.append({"type": typ, "name": name, "x": x, "y": y, "cell": c, "value": round(s["cap"]), "detail": detail,
                      "country": _cc(s["country"])})

    # --- oil and gas fields ------------------------------------------------------------------------------------------
    prod = defaultdict(dict)
    for r in csv.DictReader(io.StringIO((RAW / "sodir" / "field_production_yearly.csv").read_text(encoding="utf-8-sig"))):
        try:
            prod[r["prfNpdidInformationCarrier"]][int(r["prfYear"])] = float(r["prfPrdOeNetMillSm3"] or 0)
        except ValueError:
            pass
    years = sorted({y for p in prod.values() for y in p})
    full_year = years[-2] if len(years) > 1 else years[-1]  # the latest year is usually incomplete
    fields = json.loads((RAW / "sodir" / "fields.geojson").read_text())["features"]
    for f in fields:
        p = f["properties"]
        if p.get("fldCurrentActivitySatus") != "Producing" or not f.get("geometry"):
            continue
        c0 = shape(f["geometry"]).representative_point()
        x, y, c = place(c0.x, c0.y)
        val = prod.get(str(p["fldNpdidField"]), {}).get(full_year)
        items.append({"type": "oil_gas", "name": p["fldName"].title(), "x": x, "y": y, "cell": c,
                      "value": round(val, 2) if val is not None else None,
                      "detail": f"{p.get('fldHcType','').lower()}, {p.get('fldMainArea','')}; operator {p.get('cmpLongName','')}; "
                                f"discovered {p.get('fldDiscoveryYear','')}; production {full_year}",
                      "country": "NO", "year": full_year})

    # --- mines (SGU) --------------------------------------------------------------------------------------------------
    mines = json.loads((RAW / "sgu" / "mines.json").read_text())["features"]
    for f in mines:
        p = f["properties"]
        mt = p.get("main_type")
        if mt in ("Sulphide", "Iron oxide", "Precious metal", "Oxide"):
            typ = "metal_mine"
        elif mt == "Industrial mineral":
            typ = "industrial_mineral"
        else:
            continue
        lon, lat = f["geometry"]["coordinates"][:2]
        x, y, c = place(lon, lat)
        producing = (p.get("prod_compl") or "").strip().lower() == "prod"
        items.append({"type": typ, "name": p["name"].strip("*"), "x": x, "y": y, "cell": c, "value": None,
                      "detail": f"{(p.get('main_commo') or '').strip('; ')}; " + ("producing (SGU)" if producing else "mine/quarry (SGU)")
                                + (f"; since {p['prod_ini']}" if p.get("prod_ini") else ""),
                      "producing": producing, "country": "SE", "commodities": p.get("main_commo")})

    # owner region and municipality
    cid = {i: c["geoid"] for i, c in enumerate(world["counties"])}
    for it in items:
        c = it["cell"]
        o = owner[c] if c >= 0 else -1
        it["state"] = states[o]["abbr"] if o >= 0 else None
        it["cbsa"] = cid.get(county[c]) if c >= 0 and county[c] >= 0 else None
    items.sort(key=lambda it: (TYPES.index(TYPE[it["type"]]), -(it["value"] or 0)))

    national, by_state = {}, defaultdict(dict)
    for t in TYPES:
        sel = [it for it in items if it["type"] == t["id"]]
        vals = [it["value"] for it in sel if it["value"] is not None]
        national[t["id"]] = {"count": len(sel), "value": round(sum(vals), 2) if vals else None, "unit": t["unit"]}
        for it in sel:
            if it["state"]:
                s = by_state[it["state"]].setdefault(t["id"], {"count": 0, "value": 0, "unit": t["unit"]})
                s["count"] += 1
                s["value"] = round(s["value"] + (it["value"] or 0), 2)
    out = {"types": [{k: v for k, v in t.items() if k != "min"} for t in TYPES], "items": items,
           "summary": {"note": "Totals of the mapped sites only (each type's threshold applies); capacity is not generation.",
                       "national": national, "states": dict(by_state)},
           "production_year": full_year}
    write_json(WEB_DATA / "resources.json", out)
    print(f"    {len(items)} resource sites: " + ", ".join(f"{k} {v['count']}" for k, v in national.items()))


def _site_name(n):
    import re
    return re.sub(r"\s*\d+$", "", n)


def _cc(country):
    return {"Norway": "NO", "Sweden": "SE", "Denmark": "DK"}[country]
