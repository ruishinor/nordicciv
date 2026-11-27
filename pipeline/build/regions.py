"""Cities (= municipalities), regions and the nation: cities.json, states.json, nation.json, municipalities.json.

In Norway, Sweden and Denmark the municipality (kommune / kommun) is the basic unit of local government and of
official statistics, and most carry the name of their main town, so each municipality is a 'city' on the map.
Its banner sits on its main settlement (the most prominent Euronym place label inside the municipality whose
name matches, else the most prominent label, else the most populous 1 km cell).
"""
from __future__ import annotations

import csv
import io
import json
import math
import re
import unicodedata

import numpy as np
import shapely

from ..core import jsonstat
from ..core.paths import INTERIM, RAW, WEB_DATA
from ..core.store import read_json, write_json
from ..sources.stats import estat_records
from . import admin, history
from .yields import CITY_TYPES, LQ_MIN, LQ_MIN_JOBS, YIELDS

GDP_YEAR = 2023
GROWTH_YEARS = [2016, 2026]
POP_YEAR = 2026


def _norm(s):
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"\(.*?\)", "", s).split(" - ")[0]
    return re.sub(r"[^a-z]", "", s.replace("ø", "o").replace("æ", "ae").replace("å", "a"))


def regional_gdp():
    """{gdp_region id: {name, nc (national currency, million), eur (million), country}} and extra info."""
    ra = RAW / "regional_accounts"
    fx = {r["currency"]: r["value"] for r in estat_records(json.loads((ra / "ert_bil_eur_a.json").read_text()))
          if r["time"] == str(GDP_YEAR)}
    ppp = {r["geo"]: r["value"] for r in estat_records(json.loads((ra / "prc_ppp_ind.json").read_text()))}
    out, extra = {}, {}
    js = jsonstat.load(ra / "ssb_09391.json")
    lab = jsonstat.labels(js, "Region")
    for d, v, _ in jsonstat.records(js):
        if d["ContentsCode"] != "BNPB" or not v:
            continue
        code = d["Region"]
        if code == "23":
            extra["NO_shelf"] = v
        elif code == "21":
            extra["NO_svalbard"] = v
        elif len(code) == 2 and code not in ("25", "26", "88", "99", "22"):
            out[f"NO-{code}"] = {"name": re.sub(r"\s*\(.*\)$", "", lab[code]).split(" - ")[0], "nc": v, "country": "NO",
                                 "concept": "GVA basic prices"}
    js = jsonstat.load(ra / "scb_TAB3138.json")
    lab = jsonstat.labels(js, "Region")
    for d, v, _ in jsonstat.records(js):
        if d["ContentsCode"] == "NR0105AH" and len(d["Region"]) == 2 and d["Region"] not in ("00", "90"):
            out[f"SE-{d['Region']}"] = {"name": lab[d["Region"]].replace(" county", ""), "nc": v, "country": "SE",
                                        "concept": "GRDP market prices"}
        if d["Region"] == "90" and d["ContentsCode"] == "NR0105AH":
            extra["SE_extra"] = v
    rows = list(csv.DictReader(io.StringIO((ra / "dst_NRHP.csv").read_text(encoding="utf-8-sig")), delimiter=";"))
    for r in rows:
        if r["PRISENHED"] == "V_T" and len(r["OMRÅDE"]) == 2:
            out[f"DK-{r['OMRÅDE']}"] = {"name": r["OMRÅDE"], "nc": float(r["INDHOLD"]), "country": "DK", "concept": "GDP"}
    dst = json.loads((INTERIM / "dst.json").read_text())
    for k, v in dst["landsdele"].items():
        if f"DK-{k}" in out:
            out[f"DK-{k}"]["name"] = v["name"]
    for v in out.values():
        cur = admin.CURRENCY[v["country"]]
        v["eur"] = v["nc"] / fx[cur]
        v["pps"] = v["nc"] / ppp[v["country"]]
    extra["fx"] = fx
    extra["ppp"] = ppp
    return out, extra


def _anchors(munis):
    """Main-settlement position of each municipality."""
    polys = admin.polygons()
    labels = []
    for cc in ("NO", "SE", "DK"):
        for r in csv.DictReader(io.StringIO((RAW / "euronym" / f"{cc}.csv").read_text(encoding="utf-8"))):
            labels.append((r["name"], float(r["lon"]), float(r["lat"]), float(r["rs"])))
    names = np.array([l[0] for l in labels])
    lon = np.array([l[1] for l in labels])
    lat = np.array([l[2] for l in labels])
    rs = np.array([l[3] for l in labels])
    cells = np.load(INTERIM / "_world_cells.npz")
    out = {}
    for m in munis:
        g = polys[m["id"]]
        inside = shapely.contains_xy(g, lon, lat)
        idx = np.where(inside)[0]
        target = _norm(m["name"])
        best = None
        for k in idx:
            if _norm(names[k]) == target and (best is None or rs[k] > rs[best]):
                best = k
        how = "euronym-name"
        if best is None and len(idx):
            best = idx[np.argmax(rs[idx])]
            how = "euronym-prominent"
        if best is not None:
            out[m["id"]] = (float(lon[best]), float(lat[best]), str(names[best]), how)
        else:
            out[m["id"]] = None
    # fallback: most populous 1 km cell
    mi = cells["muni"]
    pop = cells["pop18"]
    for i, m in enumerate(munis):
        if out[m["id"]] is None:
            sel = np.where(mi == i)[0]
            if len(sel):
                k = sel[np.argmax(pop[sel])]
                out[m["id"]] = (float(cells["lon"][k]), float(cells["lat"][k]), None, "grid-peak")
            else:
                c = polys[m["id"]].representative_point()
                out[m["id"]] = (c.x, c.y, None, "polygon")
    return out


def build():
    from ..core import geo

    world = read_json(WEB_DATA / "world.json")
    grid = world["grid"]
    R, cols, rows = grid["radius"], grid["cols"], grid["rows"]
    frame = geo.Frame(world["projection"]["x0_km"], world["projection"]["y1_km"])
    owner, county = world["owner"], world["county"]
    munis = admin.municipalities()
    regs = admin.regions(munis)
    reg_idx = {r["id"]: i for i, r in enumerate(regs)}
    n = cols * rows
    cx, cy = geo.centers(R, cols, rows)

    # --- GDP apportioning ------------------------------------------------------------------------------------------
    gdp, extra = regional_gdp()
    jobs_by_gdp_region = {}
    for m in munis:
        jobs_by_gdp_region[m["gdp_region"]] = jobs_by_gdp_region.get(m["gdp_region"], 0) + (m["jobs_total"] or 0)
    for gid, v in gdp.items():
        v["jobs"] = jobs_by_gdp_region.get(gid)
    missing = sorted({m["gdp_region"] for m in munis} - set(gdp))
    if missing:
        print("    WARN: no GDP for regions", missing)

    # --- benchmark structure (three countries combined) for location quotients -------------------------------
    tot_jobs = sum(m["jobs_total"] or 0 for m in munis)
    group_tot = {g: sum(m["jobs"][g] for m in munis) for g in admin.GROUP_KEYS}
    share_bench = {g: group_tot[g] / tot_jobs for g in admin.GROUP_KEYS}
    country_income = admin.country_income()

    country_pop = history.country_series()
    hist_all = history.classify(munis, country_pop)
    hist = hist_all["munis"]
    write_json(INTERIM / "_population_review.json", {"review": hist_all["review"]})

    anchors = _anchors(munis)
    land_cells = np.array([i for i in range(n) if owner[i] >= 0])
    footprints = {}
    for i in land_cells:
        footprints.setdefault(county[i], []).append(int(i))
    pop_hex = world["pop"]

    cities = []
    for mi, m in enumerate(munis):
        lon, lat, place, how = anchors[m["id"]]
        x, y = frame.from_ll(lon, lat)
        x, y = float(x), float(y)
        fp = footprints.get(mi, [])
        cell = _cell_for(x, y, fp, land_cells, cx, cy, R, cols, rows, owner)
        h = hist[m["id"]]
        pop = h["series"].get(POP_YEAR)
        series = {str(yr): h["series"].get(yr) for yr in range(2008, POP_YEAR + 1)}
        growth = history.growth(h, *GROWTH_YEARS)
        growth_note = None
        if growth is None:
            growth_note = next((b["note"] for b in h["breaks"] if b["years"][0] <= GROWTH_YEARS[1]), "no comparable figures")
        age = m.get("age") or {}
        age_tot = sum(v for v in age.values() if v) or None
        jobs = m["jobs"]
        jt = m["jobs_total"]
        yields = {}
        partial = []
        for y_ in YIELDS:
            if y_["key"] == "gold":
                g = gdp.get(m["gdp_region"])
                yields["gold"] = (g["eur"] * 1e6 * (jt or 0) / g["jobs"]) if g and g.get("jobs") and jt is not None else None
            else:
                yields[y_["key"]] = sum(jobs[k] for k in y_["groups"])
                if any(k in m["jobs_partial"] for k in y_["groups"]):
                    partial.append(y_["key"])
        lqs = {}
        if jt:
            for gk in admin.GROUP_KEYS:
                if gk == "X" or not share_bench[gk]:
                    continue
                lqs[gk] = (jobs[gk] / jt) / share_bench[gk]
        specs = sorted([(gk, lq) for gk, lq in lqs.items() if lq >= LQ_MIN and jobs[gk] >= LQ_MIN_JOBS],
                       key=lambda t: -t[1])
        spec_list = [{"group": gk, "lq": round(lq, 2), "jobs": int(jobs[gk]), "label": dict(admin.GROUPS)[gk],
                      "partial": gk in m["jobs_partial"]} for gk, lq in specs]
        if spec_list:
            ct = CITY_TYPES.get(spec_list[0]["group"])
            ctype = {"label": ct[0], "color": ct[1], "group": spec_list[0]["group"], "rule": f"largest location quotient ≥ {LQ_MIN} with ≥ {LQ_MIN_JOBS} jobs"}
        else:
            ctype = {"label": "Diversified", "color": "#9aa4b0", "group": None, "rule": f"no industry group reaches LQ {LQ_MIN} with {LQ_MIN_JOBS}+ jobs"}
        inc = m.get("income")
        cinc = country_income.get(m["country"])
        city = {
            "id": m["id"], "name": m["name"], "full": f"{m.get('official_name') or m['name']}, {m['region_name']}, {admin.COUNTRIES[m['country']]}",
            "country": m["country"], "states": [m["region"]], "region": reg_idx[m["region"]],
            "metro": False, "capital": m["id"] in admin.CAPITALS,
            "place": place, "anchor": how,
            "x": round(x, 1), "y": round(y, 1), "lon": round(lon, 4), "lat": round(lat, 4), "cell": cell,
            "population": pop, "pop_series": series, "growth": growth, "growth_years": GROWTH_YEARS,
            "growth_note": growth_note,
            "pop_terr": {str(y): t for y, t in h["terr"].items()},
            "pop_status": {str(y): st for y, st in h["status"].items() if st != "observed"},
            "pop_terr_notes": {str(k): v for k, v in h["terr_notes"].items()},
            "pop_breaks": h["breaks"],
            "land_km2": m.get("land_km2"), "density": (pop / m["land_km2"]) if pop and m.get("land_km2") else None,
            "age": {"0_19": age.get("F0-19"), "20_64": age.get("F20-64"), "65_plus": age.get("F65+")},
            "share_65plus": (age.get("F65+") / age_tot) if age_tot and age.get("F65+") is not None else None,
            "share_0_19": (age.get("F0-19") / age_tot) if age_tot and age.get("F0-19") is not None else None,
            "employed": jt, "jobs_total": jt, "employed_residents": m.get("employed_res"),
            "jobs": {k: int(v) for k, v in jobs.items()}, "jobs_detail": m["jobs_detail"], "jobs_partial": m["jobs_partial"],
            "jobs_per_100": (100 * jt / pop) if jt and pop else None,
            "yields": yields, "yields_partial": partial, "yields_estimated": ["gold"],
            "gdp": yields.get("gold"), "gdp_year": GDP_YEAR, "gdp_region": m["gdp_region"],
            "gdp_region_name": gdp.get(m["gdp_region"], {}).get("name"),
            "income": inc, "income_currency": admin.CURRENCY[m["country"]],
            "income_index": (inc / cinc) if inc and cinc else None,
            "lq": {k: round(v, 3) for k, v in lqs.items()},
            "specialisations": spec_list, "type": ctype,
            "footprint": sorted(fp) if fp else [cell],
        }
        cities.append(city)

    # regional centres: largest municipality of each region; prominence orders the banners
    best_in_region = {}
    for c in cities:
        r = c["states"][0]
        if c["population"] and (r not in best_in_region or c["population"] > best_in_region[r]["population"]):
            best_in_region[r] = c
    for c in cities:
        c["regional_centre"] = best_in_region.get(c["states"][0]) is c
        boost = 4.0 if c["capital"] else 2.5 if c["regional_centre"] else 1.0
        # sparse north: a town that is the biggest within 150 km matters more than its size suggests
        c["prominence"] = round((c["population"] or 0) * boost)
    _nearest_bigger(cities)
    cities.sort(key=lambda c: -c["prominence"])
    _ranks(cities)
    write_json(WEB_DATA / "cities.json", cities)

    # --- regions (states.json) ---------------------------------------------------------------------------------
    states = []
    pct = world["pct"]
    published_regions = {**history.norway_counties(), **history.sweden_lan()}
    for ri, r in enumerate(regs):
        members = [c for c in cities if c["states"][0] == r["id"]]
        st = _aggregate(members)
        rs, basis, cover = history.region_series([{"id": c["id"]} for c in members], hist, published_regions.get(r["id"]))
        st["pop_series"] = {str(y): v for y, v in rs.items()}
        st["pop_basis"] = {str(y): b for y, b in basis.items()}
        st["pop_coverage"] = {str(y): v for y, v in cover.items()}
        p0, p1 = rs.get(GROWTH_YEARS[0]), rs.get(GROWTH_YEARS[1])
        st["growth"] = (p1 / p0 - 1) if p0 and p1 else None
        cells_r = [i for i in range(n) if owner[i] == ri]
        land = {}
        for k in ("forest", "crop", "pasture", "grass", "shrub", "wetland", "developed", "heath", "bare", "ice"):
            vals = [pct[k][i] for i in cells_r]
            land[k] = round(sum(vals) / len(vals) / 100, 4) if vals else None
        st.update({"fips": r["id"], "abbr": r["id"], "name": r["name"], "country": r["country"],
                   "municipalities": len(members), "land": land, "hexes": len(cells_r)})
        states.append(st)
    _rank_states(states)
    write_json(WEB_DATA / "states.json", states)

    # --- nation ----------------------------------------------------------------------------------------------------
    nat = _aggregate(cities)
    countries = {}
    for cc in ("NO", "SE", "DK"):
        countries[cc] = _aggregate([c for c in cities if c["country"] == cc])
        countries[cc]["name"] = admin.COUNTRIES[cc]
        _published(countries[cc], country_pop[cc], history.COUNTRY_SOURCE[cc])
    scand = {y: sum(country_pop[cc].get(y) or 0 for cc in ("NO", "SE", "DK")) if all(country_pop[cc].get(y) for cc in ("NO", "SE", "DK")) else None
             for y in history.YEARS}
    _published(nat, scand, "sum of the three national totals (SSB 07459, SCB TAB628, DST FOLK1A)")
    shelf_eur = extra.get("NO_shelf", 0) / extra["fx"]["NOK"] * 1e6
    nation = {
        "name": "Scandinavia", "vintage": f"Population 1 January {POP_YEAR}; jobs November/Q4 2024; GDP {GDP_YEAR}",
        "year": POP_YEAR, "gdp_vintage": f"Regional accounts {GDP_YEAR} (SSB 09391, SCB TAB3138, DST NRHP), euro at "
                                         f"Eurostat {GDP_YEAR} average rates",
        "nation": nat, "countries": countries,
        "extra_regio": {"NO_continental_shelf_eur": shelf_eur,
                        "note": "Norway's continental shelf (oil and gas extraction, pipeline transport) produced "
                                f"≈ €{shelf_eur/1e9:.0f} bn of gross value added in {GDP_YEAR}. It belongs to no county "
                                "or municipality, so it is not in any city's or region's Gold."},
        "fx": extra["fx"], "ppp": extra["ppp"],
        "yields": [{k: v for k, v in y.items() if k != "groups"} | {"groups": y["groups"], "industries": y["groups"]} for y in YIELDS],
        "industries": dict(admin.GROUPS),
        "lq_rule": {"min_lq": LQ_MIN, "min_jobs": LQ_MIN_JOBS, "benchmark": "Norway, Sweden and Denmark combined"},
        "banner_floors": [[5, 4e5], [8, 2e5], [14, 6e4], [24, 3e4], [40, 1.2e4], [70, 4e3], [9999, 0]],
    }
    nation["electricity"] = _electricity()
    write_json(WEB_DATA / "nation.json", nation)
    gdp_rows = {k: {kk: (round(vv, 1) if isinstance(vv, float) else vv) for kk, vv in v.items()} for k, v in gdp.items()}
    write_json(INTERIM / "_gdp_regions.json", {"regions": gdp_rows, "extra": extra})
    print(f"    {len(cities)} cities, {len(states)} regions; Scandinavia population {nat['population']:,}, "
          f"jobs {nat['jobs_total']:,}, GDP €{nat['gdp']/1e9:,.0f} bn (+ shelf €{shelf_eur/1e9:,.0f} bn)")


def _published(agg, series, source):
    """Replace a municipal-sum population series by the agency's own published totals (NC-T02): sums of today's
    municipalities are incomplete in years where some could not be reconstructed."""
    agg["pop_series_municipal_sum"] = agg["pop_series"]
    agg["pop_series"] = {str(y): series.get(y) for y in history.YEARS}
    agg["pop_series_source"] = source
    agg["population_published"] = series.get(POP_YEAR)
    p0, p1 = series.get(GROWTH_YEARS[0]), series.get(GROWTH_YEARS[1])
    agg["growth"] = (p1 / p0 - 1) if p0 and p1 else None
    agg["growth_basis"] = "published national totals"


def _cell_for(x, y, fp, land_cells, cx, cy, R, cols, rows, owner):
    from ..core.geo import cell_at
    c = int(cell_at(np.array([x]), np.array([y]), R, cols, rows)[0])
    if c >= 0 and (owner[c] >= 0 and (not fp or c in fp)):
        return c
    cand = np.array(fp) if fp else land_cells
    d = (cx[cand] - x) ** 2 + (cy[cand] - y) ** 2
    return int(cand[np.argmin(d)])


def _nearest_bigger(cities):
    """Distance (km) to the nearest more populous municipality: a measure of regional isolation/centrality."""
    xs = np.array([c["x"] for c in cities])
    ys = np.array([c["y"] for c in cities])
    ps = np.array([c["population"] or 0 for c in cities])
    for i, c in enumerate(cities):
        bigger = ps > ps[i]
        if bigger.any():
            d = np.sqrt((xs[bigger] - xs[i]) ** 2 + (ys[bigger] - ys[i]) ** 2).min()
            c["nearest_bigger_km"] = round(float(d), 1)
        else:
            c["nearest_bigger_km"] = None
        if c["nearest_bigger_km"] and c["nearest_bigger_km"] > 120 and not c["regional_centre"] and not c["capital"]:
            c["prominence"] = round(c["prominence"] * 2)


def _aggregate(members):
    pop = sum(c["population"] or 0 for c in members)
    series = {}
    for yr in range(2008, POP_YEAR + 1):
        vals = [c["pop_series"].get(str(yr)) for c in members]
        series[str(yr)] = sum(vals) if all(v is not None for v in vals) else None
    p0, p1 = series.get(str(GROWTH_YEARS[0])), series.get(str(GROWTH_YEARS[1]))
    jobs = {k: sum(c["jobs"][k] for c in members) for k in admin.GROUP_KEYS}
    jt = sum(c["jobs_total"] or 0 for c in members)
    yields = {}
    for y_ in YIELDS:
        vals = [c["yields"].get(y_["key"]) for c in members]
        yields[y_["key"]] = sum(v for v in vals if v is not None) if any(v is not None for v in vals) else None
    age = {k: sum((c["age"].get(k) or 0) for c in members) for k in ("0_19", "20_64", "65_plus")}
    at = sum(age.values()) or None
    land = sum(c["land_km2"] or 0 for c in members)
    return {
        "population": pop, "pop_series": series, "growth": (p1 / p0 - 1) if p0 and p1 else None,
        "growth_years": GROWTH_YEARS, "jobs": jobs, "jobs_total": jt, "employed": jt, "yields": yields,
        "gdp": yields.get("gold"), "gdp_year": GDP_YEAR, "age": age,
        "share_65plus": age["65_plus"] / at if at else None, "share_0_19": age["0_19"] / at if at else None,
        "land_km2": land, "density": pop / land if land else None,
        "yields_partial": sorted({k for c in members for k in c.get("yields_partial", [])}),
    }


def _ranks(cities):
    keys = ["population", "gdp", "growth", "density"] + [y["key"] for y in YIELDS]
    for k in keys:
        vals = []
        for c in cities:
            v = c["yields"].get(k) if k in c["yields"] else c.get(k)
            vals.append(v)
        order = sorted([i for i, v in enumerate(vals) if v is not None], key=lambda i: (-vals[i], -(cities[i]["population"] or 0)))
        for c in cities:
            c.setdefault("ranks", {})[k] = None
        for r, i in enumerate(order, 1):
            cities[i]["ranks"][k] = r
    pops = np.array([c["population"] or 1 for c in cities], dtype=float)
    for i, c in enumerate(cities):
        d = np.abs(np.log(pops / pops[i]))
        d[i] = np.inf
        c["peers"] = [cities[j]["id"] for j in np.argsort(d)[:5]]


def _rank_states(states):
    for k in [y["key"] for y in YIELDS] + ["population"]:
        vals = [(s["yields"].get(k) if k != "population" else s["population"]) for s in states]
        order = sorted([i for i, v in enumerate(vals) if v is not None], key=lambda i: -vals[i])
        for s in states:
            s.setdefault("ranks", {})[k] = None
        for r, i in enumerate(order, 1):
            states[i]["ranks"][k] = r


def _electricity():
    """Gross electricity production by source (Eurostat nrg_bal_peh, GWh), latest year, per country."""
    js = json.loads((RAW / "eurostat" / "nrg_bal_peh.json").read_text())
    recs = list(estat_records(js))
    year = max(r["time"] for r in recs)
    keys = {"RA100": "Hydro", "N900H": "Nuclear", "RA300": "Wind", "RA420": "Solar", "BIOE": "Bioenergy", "FE": "Fossil",
            "TOTAL": "Total"}
    out = {"year": int(year), "unit": "GWh", "source": "Eurostat nrg_bal_peh (gross electricity production)", "countries": {}}
    for cc in ("NO", "SE", "DK"):
        d = {keys[r["siec"]]: r["value"] for r in recs if r["geo"] == cc and r["time"] == year and r["siec"] in keys}
        out["countries"][cc] = d
    return out
