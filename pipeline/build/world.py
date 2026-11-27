"""The map itself: hex grid, land/water, relief, land cover, regions, municipalities, population, rivers.

Every tile attribute is aggregated from ~94 one-kilometre cells of European reference grids (EU-DEM, CORINE Land
Cover 2018, Copernicus tree cover density, GEOSTAT population) that fall inside the hex. Statistics published for
municipalities are never presented as if measured per hex: population is apportioned to hexes in proportion to the
1 km population grid inside each municipality (dasymetric allocation), so municipal totals are preserved exactly.
"""
from __future__ import annotations

import json
import math
from collections import Counter

import numpy as np
import shapely
from shapely.geometry import shape
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..core import geo
from ..core.hexgrid import HexGrid
from ..core.paths import INTERIM, RAW, WEB_DATA
from ..core.store import write_json
from . import admin

RADIUS_KM = 6.0  # pointy-top hexes, 10.4 km across the flats, 93.5 km² each
HEX_AREA = 3 * math.sqrt(3) / 2 * RADIUS_KM ** 2
MARGIN_KM = 70
MARGIN_W, MARGIN_E, MARGIN_N, MARGIN_S = 260, 330, 150, 80  # wider E-W context (North Sea, Finland) for wide screens
LAND_SHARE_MIN = 0.42  # share of the hex area that must be land (CLC classes 1-39)
NORDIC = ("NO", "SE", "DK")

FLAT, HILLS, MOUNTAINS, PEAKS = range(4)
RELIEF_TABLE = [
    {"id": FLAT, "name": "Flat", "rule": "Standard deviation of the 1 km EU-DEM cells inside the hex under 55 m."},
    {"id": HILLS, "name": "Hills", "rule": "Standard deviation ≥ 55 m."},
    {"id": MOUNTAINS, "name": "Mountains", "rule": "Standard deviation ≥ 150 m, or mean elevation ≥ 850 m (fjell)."},
    {"id": PEAKS, "name": "Peaks", "rule": "Highest 1 km cell ≥ 1,600 m and standard deviation ≥ 180 m (alpine)."},
]

# CORINE Land Cover grid codes (1..44) -> NordicCiv cover groups.
CLC_GROUP = {}
for c in range(1, 12):
    CLC_GROUP[c] = "developed"
for c in (12, 13, 14, 15, 16, 17, 19, 20, 21, 22):
    CLC_GROUP[c] = "crop"
CLC_GROUP[18] = "pasture"
CLC_GROUP[23] = "forest_deciduous"
CLC_GROUP[24] = "forest_evergreen"
CLC_GROUP[25] = "forest_mixed"
CLC_GROUP[26] = "grass"
CLC_GROUP[27] = "heath"
CLC_GROUP[28] = "shrub"
CLC_GROUP[29] = "shrub"
for c in (30, 31, 32, 33):
    CLC_GROUP[c] = "bare"
CLC_GROUP[34] = "ice"
for c in (35, 36, 37, 38, 39):
    CLC_GROUP[c] = "wetland"
LAND_CLC = set(range(1, 40))
LAKE_CLC = {40, 41}
SEA_CLC = {42, 43, 44}

COVER = [
    (1, "forest_deciduous", "Broadleaf forest", "#5a8a3a", [23], "Forest is the largest group and broad-leaved (CLC 311) the largest forest type."),
    (2, "forest_evergreen", "Conifer forest", "#2f5a3a", [24], "Forest is the largest group and coniferous (CLC 312) the largest type: the boreal taiga."),
    (3, "forest_mixed", "Mixed forest", "#43703f", [25], "Forest is the largest group and mixed forest (CLC 313) the largest type."),
    (4, "scrub", "Woodland & scrub", "#8f9a58", [28, 29], "Transitional woodland-shrub (CLC 324, often clear-cuts and mountain birch) is the largest group."),
    (5, "grassland", "Grassland", "#a9b35a", [26], "Natural grassland (CLC 321) is the largest group."),
    (6, "pasture", "Pasture", "#8fb04e", [18], "Pastures (CLC 231) are the largest group."),
    (7, "cropland", "Farmland", "#c9b955", [12, 13, 14, 15, 16, 17, 19, 20, 21, 22], "Arable land, permanent crops and agricultural mosaics (CLC 211-244) are the largest group."),
    (8, "wetland", "Mire & wetland", "#5f8a74", [35, 36, 37, 38, 39], "Inland marshes, peat bogs, salt marshes and tidal flats (CLC 411-423) are the largest group."),
    (9, "urban", "Urban", "#8a8378", list(range(1, 12)), "Artificial surfaces (CLC 111-142) are ≥ 30% of the hex's land, whatever else is there."),
    (10, "barren", "Bare rock", "#a8a196", [30, 31, 32, 33], "Bare rock, sparsely vegetated areas, beaches and burnt areas (CLC 331-334) are the largest group."),
    (11, "ice", "Glacier", "#e8eef2", [34], "Glaciers and perpetual snow (CLC 335) are ≥ 30% of the hex's land."),
    (12, "tundra", "Fjell heath", "#9c9a6e", [27], "Moors and heathland (CLC 322) are the largest group: the treeless fjell and coastal heath."),
]
COVER_ID = {k: i for i, k, *_ in COVER}
URBAN_MIN = 0.30
ICE_MIN = 0.30
PCT_KEYS = ["forest", "crop", "pasture", "grass", "shrub", "wetland", "developed", "heath", "bare", "ice"]

WATER_TABLE = [
    {"id": 0, "name": "Land"},
    {"id": 1, "name": "Ocean", "color": "#1b4266", "rule": "Water deeper than 200 m (Natural Earth bathymetry), away from land."},
    {"id": 2, "name": "Coast", "color": "#2d6d97", "rule": "Water next to land or shallower than 200 m (the continental shelf)."},
    {"id": 3, "name": "Lake", "color": "#3a80b0", "rule": "Inland water (CORINE water bodies and courses) is most of the hex."},
]


def build():
    t = {}
    munis = admin.municipalities()
    regions = admin.regions(munis)
    region_idx = {r["id"]: i for i, r in enumerate(regions)}
    muni_idx = {m["id"]: i for i, m in enumerate(munis)}
    polys = admin.polygons()

    # --- frame: Nordic countries' extent in the Nordic LAEA projection, plus a margin --------------------------
    cntr = {f["properties"]["id"]: shape(f["geometry"])
            for f in json.loads((RAW / "boundaries" / "nuts2024_3035_03M_cntrg.json").read_text())["features"]}
    nordic3035 = unary_union([cntr[c] for c in NORDIC])
    x0b, y0b, x1b, y1b = nordic3035.bounds
    xs, ys = [], []
    for X in np.linspace(x0b, x1b, 60):
        for Y in np.linspace(y0b, y1b, 60):
            if nordic3035.distance(shapely.Point(X, Y)) < 1:
                px, py = geo._from_3035.transform(X, Y)
                xs.append(px)
                ys.append(py)
    # exact bounds from the polygon vertices
    coords = np.vstack([np.asarray(p.exterior.coords) for g in nordic3035.geoms for p in [g]] if hasattr(nordic3035, "geoms")
                       else [np.asarray(nordic3035.exterior.coords)])
    px, py = geo._from_3035.transform(coords[:, 0], coords[:, 1])
    x0, x1, y0, y1 = px.min() - MARGIN_W, px.max() + MARGIN_E, py.min() - MARGIN_S, py.max() + MARGIN_N
    frame = geo.Frame(x0, y1)
    width, height = x1 - x0, y1 - y0
    grid = HexGrid.covering(width, height, RADIUS_KM)
    n = grid.size
    cx, cy = geo.centers(RADIUS_KM, grid.cols, grid.rows)
    print(f"    grid {grid.cols}x{grid.rows} = {n} hexes of {HEX_AREA:.1f} km²; map {width:.0f} x {height:.0f} km")

    # --- 1 km reference grids ---------------------------------------------------------------------------------
    g = np.load(INTERIM / "gisco_grids.npz")
    X = g["X"].astype(float) * 1000 + 500
    Y = g["Y"].astype(float) * 1000 + 500
    mx, my = frame.from_3035(X, Y)
    cell = geo.cell_at(mx, my, RADIUS_KM, grid.cols, grid.rows)
    keep = cell >= 0
    cell = cell[keep]
    arr = {k: g[k][keep] for k in g.files if k not in ("X", "Y")}
    mx, my = mx[keep], my[keep]
    lon, lat = frame.to_ll(mx, my)
    clc = arr["clc2018"]
    ccode = arr["cntr"]
    elev = arr["elev"]
    is_land = np.isin(clc, list(LAND_CLC)) | ((clc < 0) & np.isfinite(elev) & (np.char.str_len(ccode.astype(str)) > 0))
    is_lake = np.isin(clc, list(LAKE_CLC))
    is_sea = np.isin(clc, list(SEA_CLC))
    print(f"    {len(cell):,} 1 km cells in the frame ({is_land.sum():,} land)")

    # --- municipality of each Nordic 1 km cell (point in polygon, nearest for the coastal fringe) --------------
    ids = list(polys)
    geoms = [polys[k] for k in ids]
    tree = STRtree(geoms)
    muni_of_cell = np.full(len(cell), -1, dtype=np.int32)
    cand = np.where(is_land | is_lake)[0]
    pts = shapely.points(lon[cand], lat[cand])
    pi, gi = tree.query(pts, predicate="within")
    tmp = np.full(len(cand), -1, dtype=np.int32)
    tmp[pi] = np.array([muni_idx.get(ids[k], -1) for k in gi], dtype=np.int32)
    # cells outside the (simplified) municipal polygons but inside the Nordic countries: nearest municipality
    nordic_buf = nordic3035.buffer(1500)
    miss = np.where(tmp < 0)[0]
    inside = shapely.contains_xy(nordic_buf, X[keep][cand[miss]], Y[keep][cand[miss]])
    miss = miss[inside]
    if len(miss):
        near = tree.query_nearest(pts[miss], all_matches=False, return_distance=False)
        tmp[miss[near[0]]] = np.array([muni_idx.get(ids[k], -1) for k in near[1]], dtype=np.int32)
    muni_of_cell[cand] = tmp
    nordic_cell = muni_of_cell >= 0
    print(f"    municipality assigned to {np.sum(muni_of_cell >= 0):,} cells")

    # --- per-hex aggregates --------------------------------------------------------------------------------------
    def bc(mask=None, w=None):
        return np.bincount(cell if mask is None else cell[mask], weights=None if w is None else (w if mask is None else w[mask]), minlength=n)

    n_land = bc(is_land)
    n_lake = bc(is_lake)
    n_sea_obs = bc(is_sea)
    land_e = is_land & np.isfinite(elev)
    ne = bc(land_e)
    e_sum = bc(land_e, elev)
    e_sq = bc(land_e, elev * elev)
    e_mean = np.where(ne > 0, e_sum / np.maximum(ne, 1), np.nan)
    e_std = np.sqrt(np.maximum(0, np.where(ne > 0, e_sq / np.maximum(ne, 1) - e_mean ** 2, 0)))
    e_max = np.full(n, -np.inf)
    np.maximum.at(e_max, cell[land_e], elev[land_e])
    # valley floor: the lower 60% of land samples within 60 m and under 400 m
    tcd = arr["tcd2018"]
    tmask = is_land & np.isfinite(tcd)
    tcd_mean = np.where(bc(tmask) > 0, bc(tmask, tcd) / np.maximum(bc(tmask), 1), np.nan)
    grp_counts = {}
    for gname in set(CLC_GROUP.values()):
        codes = [c for c, gg in CLC_GROUP.items() if gg == gname]
        grp_counts[gname] = bc(np.isin(clc, codes))
    pop18 = np.nan_to_num(arr["pop2018"], nan=0.0)

    land_share = n_land / HEX_AREA
    is_land_hex = land_share >= LAND_SHARE_MIN
    # fill single-hex gaps: water hexes with ≥ 30% land and ≥ 4 land neighbours (narrow sounds and skerries)
    nb = [grid.neighbours(i) for i in range(n)]
    for _ in range(2):
        fill = []
        for i in np.where(~is_land_hex & (land_share >= 0.30))[0]:
            if sum(is_land_hex[j] for j in nb[i]) >= 4:
                fill.append(i)
        is_land_hex[fill] = True

    # --- owner: municipality majority among the hex's land cells ------------------------------------------------
    m_ok = (muni_of_cell >= 0) & is_land
    key = cell[m_ok].astype(np.int64) * 1000 + muni_of_cell[m_ok]
    uk, cnt = np.unique(key, return_counts=True)
    hex_muni = np.full(n, -1, dtype=np.int32)
    best = np.zeros(n)
    for k, c in zip(uk, cnt):
        h, m = divmod(int(k), 1000)
        if c > best[h]:
            best[h], hex_muni[h] = c, m
    nordic_land_cells = bc(is_land & nordic_cell)
    foreign_land_cells = n_land - nordic_land_cells

    # foreign land outside European grid coverage (Russia): Natural Earth countries
    ne_c = json.loads((RAW / "natural_earth" / "ne_10m_admin_0_countries.geojson").read_text())
    foreign_polys = [shape(f["geometry"]) for f in ne_c["features"] if f["properties"].get("ISO_A2") in ("RU", "FI", "DE", "EE", "PL", "LT", "LV")]
    clon, clat = frame.to_ll(cx, cy)
    fu = unary_union(foreign_polys)
    centre_foreign = shapely.contains_xy(fu, clon, clat)

    owner = np.full(n, -1, dtype=np.int32)  # -1 water, -2 foreign land, >= 0 region
    water = np.zeros(n, dtype=np.int8)
    for i in range(n):
        if is_land_hex[i]:
            if hex_muni[i] >= 0 and nordic_land_cells[i] >= foreign_land_cells[i]:
                owner[i] = region_idx[munis[hex_muni[i]]["region"]]
            else:
                owner[i] = -2
        elif n_land[i] == 0 and n_lake[i] == 0 and n_sea_obs[i] == 0 and centre_foreign[i]:
            owner[i] = -2  # e.g. Russia, outside CORINE coverage
    # land hexes that got no municipality (pure fringe): nearest Nordic land neighbour's
    for _ in range(3):
        for i in np.where((owner == -2) & is_land_hex & (nordic_land_cells > 0) & (hex_muni < 0))[0]:
            for j in nb[i]:
                if owner[j] >= 0:
                    owner[i], hex_muni[i] = owner[j], hex_muni[j]
                    break
    hex_muni[owner < 0] = -1

    # water classes
    bathy = {}
    for name, depth in (("K_200", 200), ("J_1000", 1000), ("I_2000", 2000), ("H_3000", 3000)):
        fs = json.loads((RAW / "natural_earth" / f"ne_10m_bathymetry_{name}.geojson").read_text())["features"]
        bathy[depth] = unary_union([shape(f["geometry"]) for f in fs])
    deep = np.zeros(n)
    for depth, gg in bathy.items():
        m = shapely.contains_xy(gg, clon, clat)
        deep = np.where(m, depth, deep)
    elev_out = np.zeros(n)
    for i in range(n):
        if owner[i] == -1:
            sea_cells = max(0.0, HEX_AREA - n_land[i] - n_lake[i])
            if n_lake[i] > sea_cells and n_lake[i] > 0:
                water[i] = 3
            else:
                near_land = any(owner[j] != -1 for j in nb[i])
                water[i] = 2 if (near_land or deep[i] < 200) else 1
            elev_out[i] = {0: -80, 200: -450, 1000: -1500, 2000: -2500, 3000: -3300}[int(deep[i])] if water[i] != 3 else 0
        else:
            elev_out[i] = e_mean[i] if np.isfinite(e_mean[i]) else 0
    # lakes enclosed in foreign land stay lakes; sea touching nothing stays ocean

    # relief
    relief = np.zeros(n, dtype=np.int8)
    for i in range(n):
        if owner[i] == -1 or not np.isfinite(e_mean[i]):
            continue
        m, sd, mxe = e_mean[i], e_std[i], e_max[i]
        if mxe >= 1600 and sd >= 180:
            relief[i] = PEAKS
        elif sd >= 150 or m >= 850:
            relief[i] = MOUNTAINS
        elif sd >= 55:
            relief[i] = HILLS

    # cover and shares
    cover = np.zeros(n, dtype=np.int8)
    pct = {k: np.zeros(n, dtype=np.int16) for k in PCT_KEYS}
    for i in range(n):
        if owner[i] == -1:
            continue
        land = n_land[i]
        if land <= 0:
            continue
        sh = {k: grp_counts[k][i] / land for k in grp_counts}
        forest = sh["forest_deciduous"] + sh["forest_evergreen"] + sh["forest_mixed"]
        for k, v in (("forest", forest), ("crop", sh["crop"]), ("pasture", sh["pasture"]), ("grass", sh["grass"]),
                     ("shrub", sh["shrub"]), ("wetland", sh["wetland"]), ("developed", sh["developed"]),
                     ("heath", sh["heath"]), ("bare", sh["bare"]), ("ice", sh["ice"])):
            pct[k][i] = round(100 * v)
        if sh["developed"] >= URBAN_MIN:
            cover[i] = COVER_ID["urban"]
            continue
        if sh["ice"] >= ICE_MIN:
            cover[i] = COVER_ID["ice"]
            continue
        groups = {"forest": forest, "scrub": sh["shrub"], "grassland": sh["grass"], "pasture": sh["pasture"],
                  "cropland": sh["crop"], "wetland": sh["wetland"], "barren": sh["bare"], "tundra": sh["heath"]}
        top = max(groups, key=groups.get)
        if top == "forest":
            ft = max(("forest_deciduous", "forest_evergreen", "forest_mixed"), key=lambda k: sh[k])
            cover[i] = COVER_ID[ft]
        else:
            cover[i] = COVER_ID[top]

    # --- dasymetric population: municipal totals spread by the 1 km grid inside each municipality -------------
    years = [2016, 2026]
    pop_hex = {y: np.zeros(n) for y in years}
    w_cell = np.where(muni_of_cell >= 0, pop18, 0.0)
    W = np.bincount(muni_of_cell[muni_of_cell >= 0], weights=w_cell[muni_of_cell >= 0], minlength=len(munis))
    Lw = np.bincount(muni_of_cell[(muni_of_cell >= 0) & is_land], minlength=len(munis)).astype(float)
    unalloc = []
    for y in years:
        tot = np.array([m["pop"].get(y) or 0 for m in munis], dtype=float)
        sel = muni_of_cell >= 0
        mi = muni_of_cell[sel]
        share = np.where(W[mi] > 0, w_cell[sel] / np.maximum(W[mi], 1e-9),
                         np.where(Lw[mi] > 0, is_land[sel] / np.maximum(Lw[mi], 1), 0))
        contrib = tot[mi] * share
        # cells whose hex is water or foreign: move their people to the municipality's anchor later
        pop_hex[y] = np.bincount(cell[sel], weights=contrib, minlength=n)
    # people that landed on water/foreign hexes (coastal fringe) are moved to the nearest owned land hex
    land_owned = owner >= 0
    idx_land = np.where(land_owned)[0]
    tree_l = None
    from scipy.spatial import cKDTree
    tree_l = cKDTree(np.c_[cx[idx_land], cy[idx_land]])
    for y in years:
        bad = np.where(~land_owned & (pop_hex[y] > 0))[0]
        if len(bad):
            _, nn = tree_l.query(np.c_[cx[bad], cy[bad]])
            np.add.at(pop_hex[y], idx_land[nn], pop_hex[y][bad])
            pop_hex[y][bad] = 0
    for y in years:
        tot = sum(m["pop"].get(y) or 0 for m in munis)
        print(f"    population {y}: hexes {pop_hex[y].sum():,.0f} vs municipal total {tot:,.0f}")

    # --- rivers and lakes from Natural Earth --------------------------------------------------------------------
    rivers = _rivers(frame, width, height)
    lakes = _lakes(frame, width, height)
    seas = _seas(frame, width, height)

    muni_list = [{"id": m["id"], "name": m["name"], "region": region_idx[m["region"]]} for m in munis]
    tables = {
        "water": WATER_TABLE,
        "relief": RELIEF_TABLE,
        "cover": [{"id": i, "key": k, "name": nm, "color": col, "clc": codes, "rule": rule} for i, k, nm, col, codes, rule in COVER],
        "notes": {
            "water": "From CORINE Land Cover 2018 on the 1 km grid: a hex is land when land classes (CLC 1-39) cover at least "
                     f"{int(LAND_SHARE_MIN*100)}% of its area (or ≥ 30% with ≥ 4 land neighbours, so narrow sounds and skerry "
                     "belts read as coast). Sea depth classes come from Natural Earth bathymetry polygons (200/1000/2000/3000 m).",
            "relief": "From the EU-DEM 1 km cells inside the hex (≈ 94 cells): mean, standard deviation and maximum.",
            "cover": "From CORINE Land Cover 2018 (1 km cells): the largest group of the hex's land cells; urban and glacier "
                     "win when they reach 30%. Shares in `pct` are whole percent of land cells.",
            "population": "Dasymetric: each municipality's official population (1 January) is spread over its hexes in "
                          "proportion to the GEOSTAT 2018 1 km population grid. Municipal totals are exact; the split "
                          "inside a municipality is an estimate.",
        },
    }
    world = {
        "version": 2,
        "grid": grid.to_dict(),
        "width": round(width, 1), "height": round(height, 1), "margin": MARGIN_KM,
        "projection": frame.to_dict(),
        "owner": owner.tolist(),
        "county": hex_muni.tolist(),
        "elev": [int(round(v)) for v in elev_out],
        "elev_max": [int(round(v)) if np.isfinite(v) and owner[i] != -1 else 0 for i, v in enumerate(e_max)],
        "water": water.tolist(),
        "relief": relief.tolist(),
        "cover": cover.tolist(),
        "pct": {k: v.tolist() for k, v in pct.items()},
        "tcd": [None if not np.isfinite(v) or owner[i] == -1 else int(round(v)) for i, v in enumerate(tcd_mean)],
        "pop": [int(round(v)) for v in pop_hex[2026]],
        "pop_2016": [int(round(v)) for v in pop_hex[2016]],
        "tables": tables,
        "states": [{"fips": r["id"], "abbr": r["id"], "name": r["name"].replace("Region ", ""), "short": _short(r["name"]),
                    "country": r["country"]} for r in regions],
        "countries": [{"id": c, "name": n_} for c, n_ in admin.COUNTRIES.items()],
        "counties": [{"geoid": m["id"], "name": m["name"], "region": m["region"]} for m in muni_list],
        "rivers": rivers,
        "lakes": lakes,
        "seas": seas,
    }
    write_json(WEB_DATA / "world.json", world)

    _detail(g, frame, grid, owner, water, cx, cy, clc_all=arr["clc2018"], keep=keep, foreign=fu)

    # private build products for the other builders
    np.savez_compressed(INTERIM / "_world_cells.npz", cell=cell, muni=muni_of_cell, land=is_land, pop18=pop18,
                        lon=lon, lat=lat, mx=mx, my=my, clc=clc, clc1990=arr["clc1990"],
                        acc_h=arr["acc_hospital"], acc_s=arr["acc_school"], road=arr["road_reach"],
                        degurba=arr["degurba"])
    stats = Counter()
    for i in range(n):
        stats["water" if owner[i] == -1 else "foreign" if owner[i] == -2 else "nordic"] += 1
    print(f"    hexes: {dict(stats)}; relief {Counter(relief[owner >= 0].tolist())}; cover {Counter(cover[owner >= 0].tolist())}")


def _short(name):
    n = name.replace("Region ", "").replace(" og ", " & ")
    return n if len(n) <= 12 else n.split(" ")[0].split("-")[0]


def _clip_lines(features, frame, width, height, min_len_km=8):
    out = []
    for f in features:
        g = shape(f["geometry"])
        parts = list(g.geoms) if hasattr(g, "geoms") else [g]
        for p in parts:
            c = np.asarray(p.coords)
            if len(c) < 2:
                continue
            x, y = frame.from_ll(c[:, 0], c[:, 1])
            inside = (x > -50) & (x < width + 50) & (y > -50) & (y < height + 50)
            if not inside.any():
                continue
            ls = shapely.LineString(np.c_[x, y]).simplify(0.6)
            if ls.length < min_len_km:
                continue
            out.append((f["properties"], np.round(np.asarray(ls.coords), 1).ravel().tolist()))
    return out


def _rivers(frame, width, height):
    feats = []
    for name in ("rivers_lake_centerlines", "rivers_europe"):
        fs = json.loads((RAW / "natural_earth" / f"ne_10m_{name}.geojson").read_text())["features"]
        feats += [f for f in fs if f["properties"].get("featurecla", "").lower().startswith("river")]
    out = []
    for props, pts in _clip_lines(feats, frame, width, height):
        rank = props.get("scalerank") or props.get("min_zoom") or 9
        out.append({"name": props.get("name") or props.get("name_en") or "", "rank": int(rank), "pts": pts})
    out.sort(key=lambda r: r["rank"])
    return out


def _lakes(frame, width, height):
    out = []
    for name in ("lakes", "lakes_europe"):
        fs = json.loads((RAW / "natural_earth" / f"ne_10m_{name}.geojson").read_text())["features"]
        for f in fs:
            p = f["properties"]
            nm = p.get("name") or p.get("name_en")
            if not nm:
                continue
            g = shape(f["geometry"])
            c = g.representative_point()
            x, y = frame.from_ll(c.x, c.y)
            if not (0 < x < width and 0 < y < height):
                continue
            area = g.area * 111 * 111 * math.cos(math.radians(c.y))
            out.append({"name": nm, "x": round(float(x), 1), "y": round(float(y), 1), "area_km2": round(area)})
    seen = {}
    for l in sorted(out, key=lambda l: -l["area_km2"]):
        seen.setdefault(l["name"], l)
    return [l for l in seen.values() if l["area_km2"] >= 40]


def _seas(frame, width, height):
    out = []
    fs = json.loads((RAW / "natural_earth" / "ne_10m_geography_marine_polys.geojson").read_text())["features"]
    for f in fs:
        p = f["properties"]
        g = shape(f["geometry"])
        c = g.representative_point()
        x, y = frame.from_ll(c.x, c.y)
        if 0 < x < width and 0 < y < height and p.get("name"):
            out.append({"name": p.get("name"), "x": round(float(x), 1), "y": round(float(y), 1),
                        "rank": int(p.get("scalerank") or 5), "kind": p.get("featurecla")})
    return out


def _detail(g, frame, grid, owner, water, cx, cy, clc_all, keep, foreign=None):
    """Sub-hex coastline detail at 1 km: sea and lake cells inside land hexes (fjords, sounds, lakes narrower than a
    hex) and land cells inside water hexes (skerries, small islands). The 1 km grids hold only cells with data, so a
    lattice position with no record inside the area is open sea. Written to web/data/detail.json (lazy-loaded)."""
    X = g["X"].astype(np.int64)
    Y = g["Y"].astype(np.int64)
    clc = g["clc2018"]
    x0, x1 = 3800, 5250
    y0, y1 = 3350, 5450
    W, H = x1 - x0, y1 - y0
    present = np.full((W, H), -2, dtype=np.int16)  # -2 = no record (sea)
    m = (X >= x0) & (X < x1) & (Y >= y0) & (Y < y1)
    present[X[m] - x0, Y[m] - y0] = clc[m]
    LX, LY = np.meshgrid(np.arange(x0, x1), np.arange(y0, y1), indexing="ij")
    LX, LY = LX.ravel(), LY.ravel()
    val = present.ravel()
    mx, my = frame.from_3035(LX * 1000.0 + 500, LY * 1000.0 + 500)
    hx = geo.cell_at(mx, my, grid.radius, grid.cols, grid.rows)
    ok = hx >= 0
    own = np.full(len(hx), -9)
    own[ok] = np.asarray(owner)[hx[ok]]
    land_hex = own >= 0
    sea = land_hex & ((val == -2) | np.isin(val, [42, 43, 44]))
    if foreign is not None:  # absent cells across the Russian border are land outside CORINE, not sea
        idx = np.where(sea)[0]
        lon, lat = frame.to_ll(mx[idx], my[idx])
        sea[idx[shapely.contains_xy(foreign, lon, lat)]] = False
    lake = land_hex & np.isin(val, [40, 41])
    wet_hex = own == -1
    isl = wet_hex & (val >= 1) & (val <= 39)
    cover_of = {}
    for cid, key, _n, _c, codes, _r in COVER:
        for code in codes:
            cover_of[code] = cid
    def pack(mask):
        return np.c_[np.round(mx[mask] * 2), np.round(my[mask] * 2)].astype(int).ravel().tolist()
    isl_cov = [cover_of.get(int(v), 0) for v in val[isl]]
    land_pts = np.c_[np.round(mx[isl] * 2), np.round(my[isl] * 2), isl_cov].astype(int).ravel().tolist()
    out = {"unit": "map km × 2 (0.5 km precision)", "cell_km": 1.0,
           "note": "1 km CORINE/EU grid cells: sea and lake cells inside land hexes, land cells inside water hexes. "
                   "Drawn at close zoom to show fjords, sounds, small lakes and skerries finer than the hexes.",
           "sea": pack(sea), "lake": pack(lake), "land": land_pts}
    write_json(WEB_DATA / "detail.json", out)
    print(f"    detail: {sea.sum():,} sea and {lake.sum():,} lake cells in land hexes, {isl.sum():,} land cells in water hexes")
