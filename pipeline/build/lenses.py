"""Map lenses: one value per hex (null = no data, never 0 for missing).

Each lens says at what resolution it was measured: 'hex' lenses aggregate 1 km grid cells inside the hex;
'municipality' lenses repeat the municipality's published value on each of its hexes; 'region' lenses repeat
the county/län/landsdel value. The legend always shows this.
"""
from __future__ import annotations

import math

import numpy as np

from ..core.paths import INTERIM, WEB_DATA
from ..core.store import read_json, write_json
from .world import HEX_AREA

LENS_ICON = {"density": "l-density", "growth": "l-people", "ageing": "l-age", "youth": "people", "gdp_pc": "y-gdp",
             "jobs_ratio": "l-commute", "share_BC": "i-manufacturing", "share_A": "i-agriculture", "share_J": "i-information",
             "share_I": "i-accommodation", "share_O": "i-public_admin", "specialisation": "d-commercial-hub", "income": "l-income",
             "hospital": "i-health", "school": "i-education", "road_reach": "t-road", "remoteness": "map", "elevation": "terrain",
             "forest": "l-forest", "farmland": "l-farmland", "cover": "layers", "urban_growth": "l-developed"}
GROUPS = [
    {"id": "people", "name": "People", "icon": "g-people"},
    {"id": "economy", "name": "Economy", "icon": "g-prosperity"},
    {"id": "welfare", "name": "Welfare & access", "icon": "g-life"},
    {"id": "land", "name": "Land", "icon": "g-land"},
]
RAMP_SEQ = ["#1d3b5a", "#2f6f8f", "#4fa3a5", "#9fd08a", "#f2e27a"]
RAMP_DIV = ["#b2443a", "#e08a5a", "#f3e6b0", "#7fbf8f", "#2f8f6f"]
RAMP_WARM = ["#253a5e", "#5a4f8f", "#a2557f", "#e0745a", "#f6c45a"]
RAMP_GREEN = ["#3d3a2a", "#6b6a3a", "#7f9a45", "#3f8a4a", "#1f5f3a"]


def _pctl(vals, lo=2, hi=98):
    v = np.array([x for x in vals if x is not None and np.isfinite(x)])
    if not len(v):
        return [0, 1]
    return [float(np.percentile(v, lo)), float(np.percentile(v, hi))]


def build():
    world = read_json(WEB_DATA / "world.json")
    cities = read_json(WEB_DATA / "cities.json")
    states = read_json(WEB_DATA / "states.json")
    owner, county = world["owner"], world["county"]
    n = len(owner)
    by_idx = {c["id"]: c for c in cities}
    muni_ids = [m["geoid"] for m in world["counties"]]
    muni_of = [by_idx.get(muni_ids[county[i]]) if county[i] >= 0 else None for i in range(n)]
    lenses = []

    def muni_lens(fn, digits=4):
        out = []
        for i in range(n):
            c = muni_of[i]
            v = fn(c) if (c is not None and owner[i] >= 0) else None
            out.append(None if v is None else round(v, digits))
        return out

    def add(id, group, name, emoji, unit, fmt, values, scale="linear", ramp=RAMP_SEQ, higher="neutral", source="",
            description="", note=None, resolution="hex", domain=None, categories=None):
        d = domain or _pctl(values)
        if scale == "log":
            d = [max(d[0], 0.1), max(d[1], 1)]
        lens = {"id": id, "group": group, "name": name, "icon": LENS_ICON.get(id, f"l-{id}"), "emoji": emoji, "unit": unit, "format": fmt,
                "scale": scale, "domain": [round(d[0], 4), round(d[1], 4)], "ramp": ramp, "higher_is": higher,
                "source": source, "description": description, "resolution": resolution, "values": values}
        res_note = {"hex": "Measured on the 1 km grid and aggregated to the hex.",
                    "municipality": "One published value per municipality, repeated on each of its hexes.",
                    "region": "One value per county/län/landsdel, repeated on each of its hexes.",
                    "derived": "Derived estimate: municipal totals spread over the 1 km population grid."}[resolution]
        lens["note"] = (note + " " if note else "") + res_note
        if categories:
            lens["categories"] = categories
        lenses.append(lens)

    # --- people ------------------------------------------------------------------------------------------------
    pop = world["pop"]
    pct = world["pct"]
    dens = []
    for i in range(n):
        if owner[i] < 0:
            dens.append(None)
            continue
        dens.append(round(pop[i] / HEX_AREA, 2))
    add("density", "people", "Population density", "👥", "people / km²", "float", dens, scale="log", ramp=RAMP_WARM,
        source="ssb, scb, dst, gisco_grids", resolution="derived",
        description="Residents on 1 January 2026 per km² of hex area. Each municipality's official population is spread "
                    "over its hexes in proportion to the GEOSTAT 1 km population grid (2018).",
        domain=[0.3, 3000])
    add("growth", "people", "Population change 2016–26", "📈", "% change", "pct",
        muni_lens(lambda c: c["growth"]), ramp=RAMP_DIV, higher="neutral", resolution="municipality",
        source="ssb, scb, dst", domain=[-0.15, 0.15],
        description="Change in resident population between 1 January 2016 and 1 January 2026 on today's municipal "
                    "borders (Norway: SSB's aggregated series for the 2024 municipalities).",
        note="Five Norwegian municipalities formed by splitting old ones have no 2016 figure and show no value.")
    add("ageing", "people", "Aged 65+", "👴", "share of residents", "pct", muni_lens(lambda c: c["share_65plus"]),
        ramp=RAMP_WARM, resolution="municipality", source="ssb, scb, dst",
        description="Share of residents aged 65 or older, 1 January 2026 (Sweden: 31 December 2025).")
    add("youth", "people", "Aged 0–19", "🧒", "share of residents", "pct", muni_lens(lambda c: c["share_0_19"]),
        ramp=RAMP_SEQ, resolution="municipality", source="ssb, scb, dst",
        description="Share of residents aged 0–19, 1 January 2026 (Sweden: 31 December 2025).")

    # --- economy -------------------------------------------------------------------------------------------------
    gdp = read_json(INTERIM / "_gdp_regions.json")["regions"]
    reg_pop = {}
    for c in cities:
        p = c["pop_series"]
        avg = ((p.get("2023") or 0) + (p.get("2024") or 0)) / 2
        reg_pop[c["gdp_region"]] = reg_pop.get(c["gdp_region"], 0) + avg
    gdp_pc = {k: v["pps"] * 1e6 / reg_pop[k] for k, v in gdp.items() if reg_pop.get(k)}
    add("gdp_pc", "economy", "GDP per person (PPS)", "🪙", "PPS per resident", "int",
        muni_lens(lambda c: gdp_pc.get(c["gdp_region"]), 0), ramp=RAMP_SEQ, higher="good", resolution="region",
        source="regional_accounts", domain=[25000, 70000],
        description="Regional GDP 2023 divided by the region's average population, converted to purchasing power "
                    "standards (Eurostat PPP, EU27 = 1). Norway: gross value added at basic prices, on the 2020–2023 "
                    "counties, without the continental shelf; this understates Norway relative to Sweden and Denmark "
                    "by roughly the size of taxes on products.",
        note="Norway shows value added at basic prices (no product taxes) and excludes offshore oil and gas.")
    add("jobs_ratio", "economy", "Jobs per 100 residents", "🏢", "jobs per 100 residents", "float",
        muni_lens(lambda c: c["jobs_per_100"], 1), ramp=RAMP_SEQ, resolution="municipality", source="ssb, scb, dst",
        domain=[20, 80],
        description="Jobs located in the municipality (place of work, Nov/Q4 2024) per 100 residents. Above ~50 marks "
                    "a commuting centre that draws workers from its neighbours.")
    for gid, name, emoji in (("BC", "Industry jobs", "🏭"), ("A", "Primary sector jobs", "🌾"),
                             ("J", "ICT jobs", "💻"), ("I", "Tourism & hospitality jobs", "🏨"),
                             ("O", "Public administration jobs", "🏛️")):
        add(f"share_{gid}", "economy", name, emoji, "share of jobs", "pct",
            muni_lens(lambda c, g=gid: (c["jobs"][g] / c["jobs_total"]) if c["jobs_total"] else None),
            ramp=RAMP_WARM, resolution="municipality", source="ssb, scb, dst",
            description=f"Share of the municipality's jobs (place of work, 2024) in: {name.replace(' jobs','').lower()} "
                        f"(harmonised NACE group {gid}).",
            note="Small municipalities: Norwegian cells with fewer than a handful of jobs are suppressed (shown as part of 'unknown').")
    types = sorted({c["type"]["label"] for c in cities})
    cats = []
    for t in types:
        col = next(c["type"]["color"] for c in cities if c["type"]["label"] == t)
        cats.append({"id": t.lower().replace(" & ", "_").replace(" ", "_"), "name": t, "color": col})
    tindex = {t: k for k, t in enumerate(types)}
    add("specialisation", "economy", "Specialisation", "🎯", "", "category",
        muni_lens(lambda c: tindex[c["type"]["label"]], 0), resolution="municipality", source="ssb, scb, dst",
        ramp=[c["color"] for c in cats], domain=[0, len(cats) - 1], categories=cats,
        description="The industry group with the highest location quotient (share of local jobs ÷ share in Norway, "
                    "Sweden and Denmark combined) of at least 1.5 with at least 250 jobs; 'Diversified' when none qualifies.")
    add("income", "economy", "Income vs national median", "💶", "% of national level", "pct",
        muni_lens(lambda c: c["income_index"]), ramp=RAMP_DIV, higher="good", resolution="municipality",
        source="ssb, scb, dst, regional_accounts", domain=[0.8, 1.25],
        description="Experimental. Municipal income relative to the national figure of the same statistic: Norway median "
                    "household income after tax (2024), Sweden median net income of residents 20+ (2024), Denmark average "
                    "disposable income per person (2024). Compare within a country only.",
        note="Definitions differ between countries: read colours within one country.")

    # --- welfare & access ------------------------------------------------------------------------------------------
    cells = np.load(INTERIM / "_world_cells.npz")
    cell, pop18 = cells["cell"], cells["pop18"]

    def popw(arr):
        ok = np.isfinite(arr) & (pop18 > 0)
        w = np.bincount(cell[ok], weights=pop18[ok], minlength=n)
        s = np.bincount(cell[ok], weights=(arr * pop18)[ok], minlength=n)
        return [None if owner[i] < 0 or w[i] <= 0 else round(float(s[i] / w[i]), 1) for i in range(n)]

    add("hospital", "welfare", "Time to hospital", "🏥", "minutes by road", "minutes", popw(cells["acc_h"]),
        ramp=list(reversed(RAMP_SEQ)), higher="bad", source="gisco_grids", domain=[3, 60],
        description="Average road travel time from where people live to the nearest hospital (Eurostat/GISCO 1 km "
                    "accessibility grid), weighted by the population of each 1 km cell in the hex.",
        note="Hexes with no inhabited 1 km cell have no value.")
    add("school", "welfare", "Time to primary school", "🏫", "minutes by road", "minutes", popw(cells["acc_s"]),
        ramp=list(reversed(RAMP_SEQ)), higher="bad", source="gisco_grids", domain=[1, 20],
        description="Average road travel time to the nearest primary school (Eurostat/GISCO), population-weighted.")
    add("road_reach", "welfare", "Reachable population", "🛣️", "people within 90 min by road", "int", popw(cells["road"]),
        scale="log", ramp=RAMP_WARM, higher="good", source="gisco_grids", domain=[2e4, 8e6],
        description="Population that can be reached within 90 minutes by road (EC road transport performance, 1 km "
                    "grid), averaged over the hex's inhabitants: a measure of market and labour access.")
    # remoteness: distance from each hex to the nearest town of 50,000+ residents (municipality main settlement)
    from ..core.geo import centers
    g = world["grid"]
    cx, cy = centers(g["radius"], g["cols"], g["rows"])
    towns = np.array([[c["x"], c["y"]] for c in cities if (c["population"] or 0) >= 50000])
    from scipy.spatial import cKDTree
    d, _ = cKDTree(towns).query(np.c_[cx, cy])
    add("remoteness", "welfare", "Distance to a large town", "🧭", "km to a municipality of 50,000+", "float",
        [None if owner[i] < 0 else round(float(d[i]), 1) for i in range(n)], ramp=RAMP_SEQ, higher="bad",
        source="ssb, scb, dst", domain=[0, 300], resolution="hex",
        description="Straight-line distance from the hex centre to the main settlement of the nearest municipality with "
                    "at least 50,000 residents (2026).",
        note="Straight line, not travel time; fjords and mountains make real journeys longer.")

    # --- land ------------------------------------------------------------------------------------------------------
    add("elevation", "land", "Elevation", "⛰️", "metres", "int",
        [None if owner[i] < 0 else world["elev"][i] for i in range(n)], ramp=RAMP_GREEN[::-1] + ["#f4f4f4"],
        source="gisco_grids", domain=[0, 1500], description="Mean elevation of the hex's 1 km EU-DEM cells.")
    add("forest", "land", "Tree cover", "🌲", "% tree cover", "int",
        [None if owner[i] < 0 else world["tcd"][i] for i in range(n)], ramp=RAMP_GREEN, source="gisco_grids",
        domain=[0, 80], description="Mean Copernicus Tree Cover Density (2018) of the hex's 1 km cells.")
    add("farmland", "land", "Farmland", "🌾", "% of land", "int",
        [None if owner[i] < 0 else pct["crop"][i] + pct["pasture"][i] for i in range(n)], ramp=RAMP_WARM,
        source="gisco_grids", domain=[0, 90], description="Share of the hex's land in CORINE arable, permanent crop, "
                                                        "agricultural mosaic and pasture classes (2018).")
    cov = world["tables"]["cover"]
    cov_ids = [c["id"] for c in cov]
    add("cover", "land", "Land cover", "🗺️", "", "category",
        [None if owner[i] < 0 or world["cover"][i] == 0 else cov_ids.index(world["cover"][i]) for i in range(n)],
        source="gisco_grids", ramp=[c["color"] for c in cov], domain=[0, len(cov) - 1],
        categories=[{"id": c["key"], "name": c["name"], "color": c["color"], "description": c["rule"]} for c in cov],
        description="Dominant CORINE Land Cover 2018 group of the hex (rules in the Almanac).")
    # urban expansion 1990-2018: artificial 1 km cells added
    clc, clc90 = cells["clc"], cells["clc1990"]
    art18 = (clc >= 1) & (clc <= 11)
    art90 = (clc90 >= 1) & (clc90 <= 11)
    ok = clc90 > 0
    grow = np.bincount(cell[ok & art18 & ~art90], minlength=n)
    add("urban_growth", "land", "New built-up land 1990–2018", "🏗️", "km² (1 km cells)", "int",
        [None if owner[i] < 0 else int(grow[i]) for i in range(n)], ramp=RAMP_WARM, source="gisco_grids",
        domain=[0, 10], description="Number of 1 km cells in the hex whose CORINE class became artificial (built-up, "
                                    "industrial, mines, transport) between 1990 and 2018.",
        note="1 km cells take one class each, so only substantial change registers.")

    owned = [i for i in range(n) if owner[i] >= 0]
    for l in lenses:  # pack: only Scandinavian land hexes carry values (the browser expands them)
        assert all(l["values"][i] is None for i in range(n) if owner[i] < 0), l["id"]
        l["values"] = [l["values"][i] for i in owned]
    out = {"vintage": "Population 2026, jobs 2024, GDP 2023, land cover 2018", "packed": "owned",
           "packed_note": "values[k] belongs to the k-th hex (in cell order) whose world.json owner is >= 0",
           "groups": GROUPS, "lenses": lenses}
    write_json(WEB_DATA / "lenses.json", out)
    print(f"    {len(lenses)} lenses: " + ", ".join(l["id"] for l in lenses))
