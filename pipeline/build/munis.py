"""Municipal polygons for the map: munis.json (NC-T04).

The hex grid is a terrain abstraction: each 93.5 km² hex is *owned* by the municipality covering most of it, so a
small municipality (Frederiksberg, Solna, Utsira, Røst …) may own no hex at all. This file carries the actual
administrative geometry so every municipality can be drawn, highlighted, hit-tested and coloured on its own,
independently of hex ownership.

Geometry: the boundary files listed under "boundaries" in the source registry (Kartverket 2024 municipalities for
Norway, Valmyndigheten/okfse for Sweden, DAGI for Denmark), projected to the map frame (km, y down) and simplified
with Douglas–Peucker at three tolerances for level of detail. Coordinates are integers in units of `scale` km,
delta-encoded within each ring: [x0, y0, dx1, dy1, dx2, dy2, …]. Rings smaller than the tolerance squared are
dropped at the coarser levels, never at level 0, so islands survive at full detail.
"""
from __future__ import annotations

import numpy as np
import shapely
from shapely.geometry import MultiPolygon, Polygon

from ..core import geo
from ..core.paths import WEB_DATA
from ..core.store import read_json, write_json
from . import admin

SCALE = 0.02  # km per coordinate unit (20 m)
LEVELS = [0.08, 0.4, 1.6]  # simplification tolerance in km for levels 0, 1, 2


def _rings(geom) -> list:
    polys = [geom] if isinstance(geom, Polygon) else list(geom.geoms) if isinstance(geom, MultiPolygon) else []
    out = []
    for p in polys:
        if p.is_empty:
            continue
        out.append((np.asarray(p.exterior.coords), True))
        out.extend((np.asarray(i.coords), False) for i in p.interiors)
    return out


def _encode(xy: np.ndarray) -> list[int]:
    q = np.round(xy / SCALE).astype(np.int64)
    # drop consecutive duplicates after quantisation
    keep = np.ones(len(q), bool)
    keep[1:] = np.any(q[1:] != q[:-1], axis=1)
    q = q[keep]
    if len(q) < 4:
        return []
    d = np.vstack([q[:1], np.diff(q, axis=0)])
    return d.ravel().tolist()


def build():
    world = read_json(WEB_DATA / "world.json")
    frame = geo.Frame(world["projection"]["x0_km"], world["projection"]["y1_km"])
    polys = admin.polygons()
    cities = {c["id"]: c for c in read_json(WEB_DATA / "cities.json")}
    feats, verts = [], 0
    for mid, g in sorted(polys.items()):
        if mid not in cities:
            continue
        # project every vertex: lon/lat -> map km
        def proj(coords):
            x, y = frame.from_ll(coords[:, 0], coords[:, 1])
            return np.column_stack([x, y])

        pg = shapely.transform(g, lambda c: proj(c))
        pg = pg.buffer(0)
        area = pg.area
        f = {"id": mid, "area_km2": round(area, 2)}
        x0, y0, x1, y1 = pg.bounds
        f["bbox"] = [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)]
        for li, tol in enumerate(LEVELS):
            sg = pg.simplify(tol, preserve_topology=True) if tol else pg
            rings = []
            for xy, outer in _rings(sg):
                if li > 0 and outer and Polygon(xy).area < tol * tol * 2:
                    continue
                enc = _encode(xy)
                if enc:
                    rings.append(enc)
                    if li == 0:
                        verts += len(enc) // 2
            if li > 0 and not rings:  # keep the largest ring so the municipality never disappears
                big = max(_rings(sg), key=lambda t: Polygon(t[0]).area)[0]
                rings = [_encode(big)]
            f["rings" if li == 0 else f"r{li}"] = rings
        lab = pg.representative_point()
        f["label"] = [round(lab.x, 2), round(lab.y, 2)]
        feats.append(f)
    borders = _borders(polys, cities, frame)
    write_json(WEB_DATA / "borders.json", borders)
    write_json(WEB_DATA / "munis.json", {
        "scale": SCALE, "levels": LEVELS, "vertices": verts, "frame": "map km, y down (world.json projection)",
        "source": "boundaries (Kartverket 2024 via robhop/fylker-og-kommuner; Valmyndigheten via okfse/sweden-geojson; "
                  "DAGI via Neogeografen/dagi)",
        "note": "Administrative geometry for drawing, selection and municipal choropleths. Simplified for display "
                "(level tolerances in km); not survey-grade boundaries.",
        "features": feats,
    })
    print(f"    {len(feats)} municipal polygons, {verts:,} vertices at level 0")


def _borders(polys, cities, frame):
    """Internal boundary lines (no coastline): country, region and municipality borders, from the same polygons.

    Coast = boundary of the union of all land (the municipal polygons plus Natural Earth Finland, Russia and Germany
    for the land borders beyond Scandinavia); a border is any polygon boundary that is not coast."""
    import json as _json
    from shapely.ops import unary_union
    from shapely.geometry import shape
    from ..core.paths import RAW

    def proj(g):
        return shapely.transform(g, lambda c: np.column_stack(frame.from_ll(c[:, 0], c[:, 1])))

    pm = {mid: proj(g).buffer(0) for mid, g in polys.items() if mid in cities}
    ne = _json.loads((RAW / "natural_earth" / "ne_10m_admin_0_countries.geojson").read_text())
    neigh = [proj(shape(f["geometry"])).buffer(0) for f in ne["features"] if f["properties"].get("ISO_A2") in ("FI", "RU", "DE", "AX")]
    land = unary_union(list(pm.values()) + neigh)
    coast = land.boundary.buffer(0.25)
    by_region, by_country = {}, {}
    for mid, g in pm.items():
        by_region.setdefault(cities[mid]["states"][0], []).append(g)
        by_country.setdefault(cities[mid]["country"], []).append(g)
    regions = {k: unary_union(v) for k, v in by_region.items()}
    countries = {k: unary_union(v) for k, v in by_country.items()}

    def lines(geoms, tol):
        b = unary_union([g.boundary for g in geoms]).difference(coast)
        b = shapely.line_merge(b) if b.geom_type == "MultiLineString" else b
        parts = list(b.geoms) if hasattr(b, "geoms") else [b]
        out = []
        for ln in parts:
            if ln.is_empty or ln.length < 0.3:
                continue
            ln = ln.simplify(tol)
            q = np.round(np.asarray(ln.coords) / SCALE).astype(np.int64)
            out.append(np.vstack([q[:1], np.diff(q, axis=0)]).ravel().tolist())
        return out

    out = {"scale": SCALE, "note": "Internal administrative borders (coastline removed), map km; display only."}
    out["country"] = lines(list(countries.values()), 0.15)
    out["region"] = lines(list(regions.values()), 0.15)
    out["municipality"] = lines(list(pm.values()), 0.1)
    print(f"    borders: {len(out['country'])} country, {len(out['region'])} region, {len(out['municipality'])} municipal lines")
    return out
