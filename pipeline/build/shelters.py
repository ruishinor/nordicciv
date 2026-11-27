"""shelters.json: Norway's public civil-defence shelters as published by DSB, placed in the map frame.

What it is: every record of DSB's 'Tilfluktsrom – Offentlige' (public shelters only), with its published identifier,
room number, registered places and address text, its position transformed from ETRS89 (EPSG:4258) into the map
projection, and the municipality whose boundary contains it.

What it is not: a count of all shelters (most Norwegian shelter places are in private shelters, which are not
published), a statement that a shelter is open, ready, inspected or accessible, or a measure of how well anyone is
protected. Registered places are the capacity DSB records for the room; they serve whoever is nearby, not only the
municipality's residents.

Municipal association: point in polygon against the boundary files used everywhere else in the app (Kartverket
2024 municipalities). Those boundaries are simplified, so a shelter on the shore can fall just outside its own
municipality's outline; it is then assigned to the nearest municipality and the distance is recorded. A shelter
further than MAX_NEAREST_M from every municipality is a build error, never silently assigned. Positions are never
moved: the map may group nearby shelters into one symbol, but each record keeps its own coordinates.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np
import shapely
import shapely.ops
from pyproj import Geod, Transformer
from shapely.geometry import Point

from ..core import geo
from ..core.fetch import read_manifest
from ..core.paths import INTERIM, WEB_DATA
from ..core.store import read_json, write_json
from ..sources.shelters import COVERAGE, DATASET_URL, GUIDANCE_URL, MAP_URL, GETFEATURE
from . import admin

MAX_NEAREST_M = 1500  # beyond this from every municipality outline, a record is an error, not a guess
NO_BBOX = (4.0, 57.5, 31.5, 71.5)  # lon/lat envelope of mainland Norway + coast (Svalbard is not in the app)
_TO_MAP = Transformer.from_crs("EPSG:4258", geo.NORDIC_LAEA, always_xy=True)
_GEOD = Geod(ellps="GRS80")


def build():
    src = read_json(INTERIM / "dsb_shelters.json")
    world = read_json(WEB_DATA / "world.json")
    cities = {c["id"]: c for c in read_json(WEB_DATA / "cities.json")}
    g = world["grid"]
    frame = geo.Frame(world["projection"]["x0_km"], world["projection"]["y1_km"])
    rows = src["rows"]

    polys = {k: v for k, v in admin.polygons().items() if k.startswith("NO-")}
    ids = list(polys)
    tree = shapely.STRtree([polys[k] for k in ids])

    lon = np.array([r["lon"] for r in rows], float)
    lat = np.array([r["lat"] for r in rows], float)
    px, py = _TO_MAP.transform(lon, lat)
    mx, my = px - frame.x0, frame.y1 - py
    cells = geo.cell_at(mx, my, g["radius"], g["cols"], g["rows"])

    out, problems = [], []
    by_muni = defaultdict(lambda: {"n": 0, "places": 0, "zero": 0, "missing": 0})
    for k, r in enumerate(rows):
        p = Point(r["lon"], r["lat"])
        hit = [ids[j] for j in tree.query(p, predicate="within")]
        dist_m = 0
        if hit:
            muni = hit[0]
            how = "inside"
        else:
            j = int(tree.nearest(p))
            muni = ids[j]
            q = shapely.ops.nearest_points(polys[muni], p)[0]
            dist_m = round(_GEOD.inv(r["lon"], r["lat"], q.x, q.y)[2])
            how = "nearest"
            if dist_m > MAX_NEAREST_M:
                problems.append(f"{r['id']}: {dist_m} m from the nearest municipality ({muni})")
        rec = {
            "id": r["id"], "room": r["room"], "places": r["places"], "address": r["address"],
            "lat": round(r["lat"], 6), "lon": round(r["lon"], 6),
            "x": round(float(mx[k]), 3), "y": round(float(my[k]), 3), "cell": int(cells[k]),
            "muni": muni,
        }
        if how == "nearest":
            rec["assigned"] = {"method": "nearest municipality outline", "distance_m": dist_m}
        out.append(rec)
        a = by_muni[muni]
        a["n"] += 1
        if r["places"] is None:
            a["missing"] += 1
        else:
            a["places"] += r["places"]
            a["zero"] += r["places"] == 0
    if problems:
        raise SystemExit("shelters: records too far from any municipality:\n  " + "\n  ".join(problems))

    # Regional (fylke) totals for the overview, from the municipality → region mapping the app already uses.
    by_region = defaultdict(lambda: {"n": 0, "places": 0, "munis": 0})
    for m, a in by_muni.items():
        c = cities.get(m)
        reg = (c or {}).get("states", [None])[0] if c else None
        if reg is None:
            raise SystemExit(f"shelters: municipality {m} is not in cities.json")
        b = by_region[reg]
        b["n"] += a["n"]
        b["places"] += a["places"]
        b["munis"] += 1
    # display anchors for grouped symbols: mean of the members' true positions (a label position, not a location)
    pos = defaultdict(list)
    for rec in out:
        pos[rec["muni"]].append((rec["x"], rec["y"]))
        pos[cities[rec["muni"]]["states"][0]].append((rec["x"], rec["y"]))
    anchor = {k: [round(float(np.mean([p[0] for p in v])), 2), round(float(np.mean([p[1] for p in v])), 2)] for k, v in pos.items()}

    no_munis = sorted(k for k, c in cities.items() if c["country"] == "NO")
    man = read_manifest("dsb_shelters")["files"]["tilfluktsrom_4258.gml"]
    extracted = sorted({r["extracted"][:10] for r in rows if r.get("extracted")})
    data = {
        "version": 1,
        "source": {
            "id": "dsb_shelters", "authority": "Direktoratet for samfunnssikkerhet og beredskap (DSB)",
            "dataset": "Tilfluktsrom – Offentlige", "license": "NLOD 1.0", "license_url": "https://data.norge.no/nlod/no/1.0",
            "attribution": "Contains data under the Norwegian licence for Open Government data (NLOD) made available by DSB.",
            "dataset_url": DATASET_URL, "request": GETFEATURE, "guidance_url": GUIDANCE_URL, "official_map_url": MAP_URL,
            "extracted": extracted[-1] if extracted else None,  # DSB's own extraction date on every record
            "retrieved": man["retrieved"], "sha256": man["sha256"],
            "crs": "EPSG:4258 (ETRS89, lat/lon), transformed to the map's Lambert azimuthal equal-area frame",
            "number_matched": src["number_matched"],
        },
        "coverage": COVERAGE,
        "meaning": {
            "places": "Registered places: the capacity DSB records for the shelter room. Not current availability, "
                      "readiness, accessibility or guaranteed protection.",
            "public": "Public shelters are for anyone in the area. Private shelters (housing, schools, workplaces) hold "
                      "most of Norway's shelter places and are not in this dataset.",
            "absence": "A municipality without a public shelter here may still have private shelters or other protection.",
            "residents": "Shelters serve the people present in an area, not only registered residents, so places are "
                         "not compared with population.",
        },
        "rules": {
            "municipality": "Point in polygon against the Kartverket 2024 municipal boundaries used by the app; records "
                            f"just outside a simplified outline go to the nearest municipality (≤ {MAX_NEAREST_M} m), "
                            "and the distance is kept.",
            "position": "Each record keeps its published position. The map groups nearby shelters into one symbol at "
                        "small scales; a group symbol stands at the members' mean position and says how many it holds.",
        },
        "shelters": out,
        "munis": {m: {**by_muni[m], "anchor": anchor[m]} for m in sorted(by_muni)},
        "regions": {r: {**by_region[r], "anchor": anchor[r]} for r in sorted(by_region)},
        "totals": {"shelters": len(out), "places": sum(a["places"] for a in by_muni.values()),
                   "munis_with": len(by_muni), "munis_no": len(no_munis),
                   "assigned_nearest": sum(1 for r in out if "assigned" in r)},
    }
    write_json(WEB_DATA / "shelters.json", data)
    t = data["totals"]
    print(f"    {t['shelters']} public shelters, {t['places']} registered places, in {t['munis_with']} of "
          f"{t['munis_no']} Norwegian municipalities; {t['assigned_nearest']} assigned to the nearest outline")
