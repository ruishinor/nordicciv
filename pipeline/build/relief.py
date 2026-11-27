"""Continuous shaded-relief land-cover raster for the map: web/data/relief/ (NC-V01–V03).

The hexes summarise ~94 one-kilometre cells each, which is right for statistics but makes a poor landscape: every
hex is one flat colour and mountains, valleys and coasts break into tiles. This builder paints the landscape once,
from the same 1 km evidence, as a continuous image in the map frame:

  colour    CORINE Land Cover 2018 class of each 1 km cell (painted palette), forest tone modulated by Copernicus
            tree cover density; foreign land (outside NO/SE/DK) muted
  relief    multidirectional hillshade of EU-DEM (1 km mean elevation, bicubically interpolated to the raster
            resolution; vertical exaggeration ×3 for legibility at map scale); high-alpine tint above an elevation
            that falls with latitude (no snow is drawn where there is no high ground)
  water     sea is transparent (the map's water art shows through); lakes (CORINE water bodies) are painted in
  coast     Norway and Denmark: the municipal polygons (Kartverket / DAGI, finer than 1 km); elsewhere the CORINE
            1 km land/sea cells, smoothed

World style (v0.3, NC-V06): shading at the scale of ranges (2 km) is added to the detail shading and crests are lifted,
so ranges read as connected masses; one north-west light with warm highlights and blue-violet shadows; snow on the
crests of high ground; farmland carries slow illustrative crop tones; lakes are smoothed from a signed distance field
(same total area as the 1 km cells); the three countries are identified from Natural Earth (the grid's country code is
empty for most unpopulated cells). Class masks at 1 km (relief/cover) feed the browser's illustration layer.

Below 1 km the image interpolates: class boundaries are blended over about one cell and wobbled by a fixed noise
field so they do not read as a grid, and canopy texture is a deterministic noise pattern. Neither adds information
the 1 km data does not have; the Almanac says so. Levels: L0 = 1 km per pixel (one image), L1 = 0.5 km per pixel in
512-px tiles (loaded only when zoomed in), gray = L0 hillshade without colour for Analyze mode.
"""
from __future__ import annotations

import hashlib
import json
import math

import numpy as np
from PIL import Image, ImageDraw
from pyproj import Transformer
from scipy import ndimage

from ..core import geo
from ..core.paths import INTERIM, RAW, WEB_DATA
from ..core.store import read_json, write_json

OUT = WEB_DATA / "relief"
RES = 0.5  # km per pixel at L1
TILE = 512
SEED = 20261127
Z_EXAG = 3.0

# CORINE grid class index (1..44) -> painted RGB
PAL = {
    1: (150, 128, 112), 2: (166, 146, 124), 3: (150, 136, 124), 4: (146, 140, 130), 5: (138, 142, 150),
    6: (156, 150, 140), 7: (166, 150, 126), 8: (150, 144, 128), 9: (150, 152, 120), 10: (132, 160, 92),
    11: (140, 162, 98),
    12: (184, 174, 108), 13: (180, 170, 104), 14: (172, 166, 100), 15: (170, 168, 96), 16: (176, 170, 100),
    17: (160, 160, 88), 18: (128, 168, 76), 19: (160, 166, 90), 20: (160, 166, 96), 21: (128, 156, 76),
    22: (122, 148, 72),
    23: (80, 132, 52), 24: (44, 92, 46), 25: (60, 112, 50), 26: (150, 168, 92), 27: (150, 144, 92),
    28: (130, 132, 86), 29: (100, 138, 64), 30: (222, 208, 160), 31: (146, 142, 134), 32: (160, 154, 132),
    33: (110, 100, 86), 34: (236, 242, 246), 35: (106, 130, 80), 36: (128, 126, 78), 37: (124, 132, 96),
    38: (180, 176, 160), 39: (180, 170, 140),
}
FOREST = {23, 24, 25}
OPEN_HIGH = {26, 27, 31, 32, 29}
LAKE = {40, 41}
SEA = {42, 43, 44}
LAKE_RGB = np.array([58, 112, 156], np.float32)


def _noise(shape, scales, seed):
    """Deterministic multi-octave value noise in [-1, 1] (fixed seed: same image every build)."""
    rng = np.random.default_rng(seed)
    out = np.zeros(shape, np.float32)
    amp_tot = 0
    for k, sc in enumerate(scales):
        gh, gw = max(2, int(shape[0] / sc) + 3), max(2, int(shape[1] / sc) + 3)
        g = rng.standard_normal((gh, gw)).astype(np.float32)
        z = ndimage.zoom(g, (shape[0] / (gh - 2), shape[1] / (gw - 2)), order=3)[: shape[0], : shape[1]]
        z = np.pad(z, ((0, max(0, shape[0] - z.shape[0])), (0, max(0, shape[1] - z.shape[1]))), mode="edge")
        a = 1 / (k + 1)
        out += a * z
        amp_tot += a
    out /= amp_tot
    return np.clip(out / (np.std(out) * 2.5 + 1e-6), -1, 1)


def _decode_rings(f, scale):
    for ring in f["rings"]:
        a = np.array(ring, np.float64).reshape(-1, 2).cumsum(axis=0) * scale
        yield a


def build():
    world = read_json(WEB_DATA / "world.json")
    W, H = world["width"], world["height"]
    frame = geo.Frame(world["projection"]["x0_km"], world["projection"]["y1_km"])
    nx, ny = int(math.ceil(W / RES)), int(math.ceil(H / RES))
    print(f"    raster {nx}x{ny} px at {RES} km")

    # --- dense 1 km grids in EPSG:3035 ---------------------------------------------------------------------------
    g = np.load(INTERIM / "gisco_grids.npz")
    X, Y = g["X"].astype(np.int64), g["Y"].astype(np.int64)  # km, lower-left corner of each cell
    # map raster pixel centres -> EPSG:3035 km
    to3035 = Transformer.from_crs(geo.NORDIC_LAEA, "EPSG:3035", always_xy=True)
    jj, ii = np.mgrid[0:ny, 0:nx].astype(np.float32)
    mx = ((ii + 0.5) * RES).astype(np.float32)
    my = ((jj + 0.5) * RES).astype(np.float32)
    px, py = to3035.transform(mx.ravel() + frame.x0, frame.y1 - my.ravel())
    px = (px / 1000.0).reshape(ny, nx).astype(np.float32)
    py = (py / 1000.0).reshape(ny, nx).astype(np.float32)
    del jj, ii
    xmin, xmax = int(np.floor(px.min())) - 2, int(np.ceil(px.max())) + 2
    ymin, ymax = int(np.floor(py.min())) - 2, int(np.ceil(py.max())) + 2
    keep = (X >= xmin) & (X <= xmax) & (Y >= ymin) & (Y <= ymax)
    gx, gy = X[keep] - xmin, Y[keep] - ymin
    shp = (ymax - ymin + 1, xmax - xmin + 1)

    def dense(arr, fill):
        d = np.full(shp, fill, np.float32)
        d[gy, gx] = arr[keep]
        return d

    clc = g["clc2018"][keep].astype(np.int16)
    elev = dense(np.nan_to_num(g["elev"], nan=np.nan), np.nan)
    tcd = dense(g["tcd2018"], np.nan)
    cls = np.full(shp, -1, np.int16)
    cls[gy, gx] = clc
    cntr = g["cntr"][keep]
    nordic = np.zeros(shp, np.float32)
    nordic[gy, gx] = np.isin(cntr, ["NO", "SE", "DK"]).astype(np.float32)
    # the grid's country code is empty for most unpopulated cells, so the three countries are also taken from the
    # Natural Earth boundaries (v0.2 muted much of the Scandinavian mountains as if they were foreign land)
    nordic = np.maximum(nordic, _countries_on_grid(("NO", "SE", "DK"), xmin, ymin, shp))
    present = np.zeros(shp, np.float32)
    present[gy, gx] = 1.0
    ccode = np.zeros(shp, np.float32)  # 0 none/sea, 1 NO, 2 SE, 3 DK, 4 other
    ccode[gy, gx] = np.select([cntr == "NO", cntr == "SE", cntr == "DK", np.char.str_len(cntr.astype(str)) > 0], [1, 2, 3, 4], 0)
    land1 = np.zeros(shp, np.float32)
    land1[gy, gx] = (~np.isin(clc, list(SEA | LAKE)) & ((clc > 0) | np.isfinite(g["elev"][keep]))).astype(np.float32)
    lake1 = np.isin(cls, list(LAKE)).astype(np.float32)
    known = np.isfinite(elev)
    if (~known).any():  # extend elevation into the sea and beyond the data so the hillshade has no edge cliffs
        idx = ndimage.distance_transform_edt(~known, return_distances=False, return_indices=True)
        elev = np.where(known, elev, np.minimum(elev[idx[0], idx[1]], 0) - 5 * (land1 < 0.5))
    elev = elev.astype(np.float32)
    # fill unclassified land from neighbours (nearest classified cell)
    unk = (cls <= 0) & (land1 > 0)
    if unk.any():
        idx = ndimage.distance_transform_edt(unk | (cls <= 0), return_distances=False, return_indices=True)
        cls_f = cls[tuple(idx)]
        cls = np.where(unk, cls_f, cls)

    # colour per 1 km cell
    rgb1 = np.zeros(shp + (3,), np.float32)
    for k, col in PAL.items():
        rgb1[cls == k] = col
    t = np.nan_to_num(tcd, nan=50) / 100
    forest = np.isin(cls, list(FOREST))
    rgb1[forest] *= (1.12 - 0.3 * t[forest])[:, None]
    # land-cover masks for the illustration layer (NC-V06): which kind of ground each cell is, 0..1. The browser draws
    # illustrative patterns (tree crowns, field patchwork, scree, mire tufts) through these masks at closer zooms; a
    # pattern shows the class, never the position of a real tree or field.
    def m1(weights):
        arr = np.zeros(shp, np.float32)
        for k_, w_ in weights.items():
            arr[cls == k_] = w_
        return arr
    tf = 0.45 + 0.55 * t
    cover1 = {
        "conifer": m1({24: 1, 25: 0.5, 29: 0.35}) * tf, "broadleaf": m1({23: 1, 25: 0.5, 29: 0.15}) * tf,
        "farm": m1({12: 1, 13: 1, 14: 1, 15: 1, 16: 1, 17: 1, 19: 0.9, 20: 0.85, 21: 0.55, 22: 0.5, 18: 0.5}),
        "rock": m1({31: 1, 32: 0.75, 7: 0.6, 33: 0.4}), "wet": m1({35: 1, 36: 1, 37: 0.7, 39: 0.5}),
        "heath": m1({26: 1, 27: 1, 28: 0.8, 29: 0.4}),
        "urban": m1({1: 1, 2: 0.85, 3: 0.65, 4: 0.4, 5: 0.5, 6: 0.35, 9: 0.4, 10: 0.25, 11: 0.25}),
    }
    for k_ in cover1:
        cover1[k_] *= np.where(nordic > 0.5, 1.0, 0.5)
    # elevation tint on open ground: valleys warmer, high ground paler and cooler
    hi = np.clip((elev - 600) / 900, 0, 1)
    openh = np.isin(cls, list(OPEN_HIGH))
    rgb1[openh] = rgb1[openh] * (1 - 0.22 * hi[openh, None]) + np.float32([178, 176, 166]) * 0.22 * hi[openh, None]
    # foreign land muted toward a neutral parchment so the three countries stand out
    fmask = (land1 > 0) & (nordic < 0.5)
    grey = rgb1[fmask].mean(axis=1, keepdims=True)
    rgb1[fmask] = 0.45 * rgb1[fmask] + 0.55 * (0.8 * grey + np.float32([40, 36, 28]))

    # extend land colours over water cells so interpolation at the shore never blends toward black
    wet = land1 < 0.5
    if wet.any():
        idx = ndimage.distance_transform_edt(wet, return_distances=False, return_indices=True)
        rgb1 = rgb1[idx[0], idx[1]]

    # a painted, not photographic, surface: soften the 1 km colour field so single cells do not speckle
    rgb1 = np.stack([ndimage.gaussian_filter(rgb1[..., c], 0.7) for c in range(3)], axis=-1)
    # --- sample at the raster resolution -------------------------------------------------------------------------
    fx = px - xmin - 0.5
    fy = py - ymin - 0.5
    warp = 0.45
    nxw = (_noise((ny, nx), [24, 9], SEED) * warp).astype(np.float32)
    nyw = (_noise((ny, nx), [24, 9], SEED + 1) * warp).astype(np.float32)
    wx, wy = fx + nxw, fy + nyw

    def samp(field, coords_x, coords_y, order):
        return ndimage.map_coordinates(field, [coords_y.ravel(), coords_x.ravel()], order=order, mode="nearest", output=np.float32).reshape(ny, nx)

    Z = samp(elev, fx, fy, 3)
    Z = np.maximum(Z, -20)
    rgb = np.stack([samp(rgb1[..., c], wx, wy, 1) for c in range(3)], axis=-1)
    # a slight blur of the 1 km land/lake cells first, so shores traced from them are rounded, not stair-stepped
    land_c = samp(ndimage.gaussian_filter(land1, 0.65), wx, wy, 1)
    lake_c = samp(ndimage.gaussian_filter(lake1, 0.55), wx, wy, 1)
    # lake shapes: a bicubic interpolation of the 1 km water cells, wobbled by the same noise, gives rounded shores
    # instead of 1 km stair steps while keeping one-cell lakes
    # lake shapes from a signed distance field: the 1 km water cells (nearest, wobbled) → distance to the shore on
    # each side → blurred over ~1 km → zero crossing. Shores come out as smooth curves at any zoom, small lakes as
    # rounded ponds of about the same area, instead of 1 km stair steps.
    lk = samp(ndimage.gaussian_filter(lake1, 0.55), wx, wy, 1) > 0.42  # the v0.2 lake extent
    sdf = (ndimage.distance_transform_edt(~lk) - ndimage.distance_transform_edt(lk)).astype(np.float32)
    lake_s = ndimage.gaussian_filter(sdf, 2.0)
    del lk, sdf
    cover = {k_: np.clip(samp(ndimage.gaussian_filter(v_, 0.6), wx, wy, 1), 0, 1).astype(np.float32) for k_, v_ in cover1.items()}
    del cover1
    nord = samp(nordic, fx, fy, 1)
    cc = samp(ccode, fx, fy, 0)
    valid = samp(present, fx, fy, 1)
    del mx, my, px, py, fx, fy, nxw, nyw, wx, wy
    del rgb1

    # --- coast: polygons for Norway and Denmark (finer than 1 km), CORINE elsewhere -----------------------------
    munis = read_json(WEB_DATA / "munis.json")
    ss = 2  # supersampling
    img = Image.new("L", (nx * ss, ny * ss), 0)
    dr = ImageDraw.Draw(img)
    for f in munis["features"]:
        if not f["id"].startswith(("NO-", "DK-")):
            continue
        rings = list(_decode_rings(f, munis["scale"]))
        for k, a in enumerate(rings):
            pts = [(float(x / RES * ss), float(y / RES * ss)) for x, y in a]
            if len(pts) >= 3:
                dr.polygon(pts, fill=255)
    poly = np.asarray(img.resize((nx, ny), Image.BOX), np.float32) / 255
    del img, dr
    zone = ndimage.binary_dilation(poly > 0.5, iterations=int(3 / RES))
    smooth_land = np.clip((land_c - 0.40) / 0.16, 0, 1)
    near_sea = ndimage.binary_dilation((land_c < 0.5) & (lake_c < 0.5), iterations=int(2 / RES))
    use_poly = ((cc == 1) | (cc == 3) | (cc == 0)) & zone & near_sea
    alpha_land = np.where(use_poly, poly, np.maximum(poly, smooth_land))
    # no 1 km data beyond the EU/EFTA grid (Russia, Belarus): leave those to the hex art, with a 3 km margin
    nod = Image.new("L", (nx, ny), 0)
    dn = ImageDraw.Draw(nod)
    from shapely.geometry import shape
    ne = read_json(RAW / "natural_earth" / "ne_10m_admin_0_countries.geojson")
    for f in ne["features"]:
        if f["properties"].get("ISO_A2") not in ("RU", "BY", "UA"):
            continue
        g = shape(f["geometry"])
        for poly_ in (g.geoms if hasattr(g, "geoms") else [g]):
            lo, la = np.asarray(poly_.exterior.coords).T
            x_, y_ = frame.from_ll(lo, la)
            pts = list(zip((x_ / RES).tolist(), (y_ / RES).tolist()))
            if len(pts) >= 3:
                dn.polygon(pts, fill=255)
    nodata = ndimage.binary_dilation(np.asarray(nod) > 0, iterations=int(3 / RES))
    alpha_land *= ~nodata
    lake_a = np.clip(0.5 - (lake_s - 0.25) / 0.6, 0, 1) * (alpha_land > 0.5)  # biased so narrow lakes survive
    del lake_s
    lab1, n1 = ndimage.label(lake1 > 0.5)
    lab2, n2 = ndimage.label(lake_a > 0.5)
    old_a = np.clip((lake_c - 0.42) / 0.2, 0, 1) * (alpha_land > 0.5)
    lab3, n3 = ndimage.label(old_a > 0.5)
    print(f"    lakes painted on land: {lake_a.sum() * RES * RES:,.0f} km² in {n2} shapes (v0.2 method {old_a.sum() * RES * RES:,.0f} km² in {n3})")
    del old_a, lab3
    del lab1, lab2

    # --- hillshade -----------------------------------------------------------------------------------------------
    Zs = ndimage.gaussian_filter(Z, 0.6) * Z_EXAG
    dzdx = np.gradient(Zs, axis=1) / (RES * 1000)
    dzdy = np.gradient(Zs, axis=0) / (RES * 1000)
    slope = np.arctan(np.hypot(dzdx, dzdy))
    aspect = np.arctan2(-dzdx, dzdy)
    shade = np.zeros_like(Zs)
    for az, alt, wgt in ((315, 45, 0.55), (270, 40, 0.2), (0, 40, 0.15), (225, 50, 0.1)):
        a, h = math.radians(az), math.radians(alt)
        s_ = math.sin(h) * np.cos(slope) + math.cos(h) * np.sin(slope) * np.cos(a - aspect - math.pi / 2)
        shade += wgt * np.clip(s_, 0, 1)
    flat = math.sin(math.radians(45))  # shade of flat ground
    rel = (shade - flat * 0.98).astype(np.float32)  # <0 shadow, >0 lit
    del shade, slope, aspect, dzdx, dzdy, Zs
    # high-alpine tint, snowline falling from ~1500 m at 60°N to ~800 m at 70°N
    lat = _lat_raster(frame, nx, ny)
    snowline = 1500 - 70 * np.clip(lat - 60, 0, 12)
    alp = np.clip((Z - snowline) / 450, 0, 1) * (Z > 300)
    # snow gathers on the crests of the high ground, not evenly over plateaus (the ridge term is computed below,
    # so a local one here)
    crest = np.clip(np.tanh((Z - ndimage.gaussian_filter(Z, 5)) / 90), 0, 1)
    alp = alp * (0.55 + 0.45 * crest)
    del crest
    rgb = rgb * (1 - 0.6 * alp[..., None]) + np.float32([236, 240, 246]) * 0.6 * alp[..., None]
    # farmland: a slow patchwork of crop tones (ripe, green, ploughed) so agricultural plains read as farmed land
    # from mid zoom; the tones are illustrative, not observed crops
    fv = _noise((ny, nx), [7, 3], SEED + 11)
    farm_k = np.clip(cover["farm"] * 1.2, 0, 1)[..., None]
    tone = np.where((fv > 0.25)[..., None], np.float32([214, 188, 104]), np.where((fv < -0.25)[..., None], np.float32([150, 172, 88]), np.float32([196, 166, 106])))
    rgb = rgb * (1 - 0.35 * farm_k) + tone * 0.35 * farm_k
    del fv, farm_k, tone
    # canopy and field texture (deterministic, sub-km)
    tex = _noise((ny, nx), [3, 1.4], SEED + 2)
    rgb *= (1 + 0.05 * tex)[..., None]
    # World style (NC-V06): ranges as connected masses. Crests (above the 3 km mean surface) are lifted and valleys
    # deepened where the local relief is large, so a range reads as one sculpted body rather than scattered peaks.
    Zb = ndimage.gaussian_filter(Z, 6)
    amp = ndimage.maximum_filter(Zb, size=17) - ndimage.minimum_filter(Zb, size=17)
    mnt = np.clip((amp - 120) / 600, 0, 1)
    ridge = np.tanh((Z - Zb) / 110) * mnt
    # form shading at the scale of ranges (2 km smoothing, stronger exaggeration) added to the detail shading, so
    # mountains read as sculpted masses and the fine 1 km mottling recedes
    Zm = ndimage.gaussian_filter(Z, 4) * Z_EXAG * 1.6
    mx_, my_ = np.gradient(Zm, axis=1) / (RES * 1000), np.gradient(Zm, axis=0) / (RES * 1000)
    sl_, as_ = np.arctan(np.hypot(mx_, my_)), np.arctan2(-mx_, my_)
    a0, h0 = math.radians(315), math.radians(42)
    macro = np.clip(math.sin(h0) * np.cos(sl_) + math.cos(h0) * np.sin(sl_) * np.cos(a0 - as_ - math.pi / 2), 0, 1) - math.sin(h0)
    del mx_, my_, sl_, as_, Zm
    rel_w = (0.75 * macro + 0.6 * rel + 0.08 * ridge).astype(np.float32)
    del macro
    # painterly light: one sun in the north-west (as the map's buildings), warm light and blue-violet shadow
    lit = np.clip(rel_w, 0, None)[..., None]
    shd = np.clip(-rel_w, 0, None)[..., None]
    k_sh = np.clip(1.9 * shd, 0, 0.78)
    rgb = rgb * (1 - k_sh) + (rgb * 0.30 + np.float32([22, 30, 62])) * k_sh
    rgb = rgb * (1 + 1.05 * lit) + np.float32([255, 228, 176]) * 0.14 * lit
    # colour grade: slightly richer greens and warmer fields in the three countries, cooler high ground
    g_ = np.clip(nord, 0, 1)[..., None]
    rgb = rgb * (1 - 0.08 * g_) + (rgb * np.array([0.96, 1.05, 0.93])) * 0.08 * g_
    # lakes painted in, darker toward the middle
    depth = ndimage.gaussian_filter(lake_a, 2)
    lake_rgb = LAKE_RGB * (1.06 - 0.22 * depth[..., None]) + (tex * 3)[..., None]
    rim = np.clip(lake_a * (1 - lake_a) * 4, 0, 1)[..., None]  # a pale shore line where land meets lake water
    lake_rgb = lake_rgb * (1 - 0.35 * rim) + np.float32([170, 200, 205]) * 0.35 * rim
    rgb = rgb * (1 - lake_a[..., None]) + lake_rgb * lake_a[..., None]
    lum = rgb.mean(axis=-1, keepdims=True)
    boost = 1 + 0.10 * np.clip(nord, 0, 1)[..., None] * (1 - lake_a[..., None])
    rgb = lum + (rgb - lum) * boost
    rgb = np.clip(rgb, 0, 255).astype(np.uint8)
    alpha = np.clip(alpha_land * 255, 0, 255).astype(np.uint8)

    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("**/*.webp"):
        old.unlink()
    rgba = np.dstack([rgb, alpha])
    manifest = {"crs": "map km, y down (world.json)", "levels": [], "note": __doc__.split("\n\n")[0].strip(),
                "sources": ["gisco_grids (CORINE 2018, EU-DEM, Copernicus TCD 1 km)", "boundaries (Kartverket, DAGI)"]}
    # L1 tiles
    tiles = []
    for ty in range(0, ny, TILE):
        for tx in range(0, nx, TILE):
            a = alpha[ty:ty + TILE, tx:tx + TILE]
            if a.max() == 0:
                continue
            p = OUT / "L1" / f"{tx // TILE}_{ty // TILE}.webp"
            p.parent.mkdir(exist_ok=True)
            Image.fromarray(rgba[ty:ty + TILE, tx:tx + TILE], "RGBA").save(p, "WEBP", quality=82, alpha_quality=90, method=6)
            tiles.append([tx // TILE, ty // TILE])
    manifest["levels"].append({"id": "L1", "km_per_px": RES, "tile_px": TILE, "tiles": tiles, "path": "relief/L1/{x}_{y}.webp"})
    # land-cover masks at 1 km (the data's resolution), 16 levels, packed three to an image, in 512 px tiles:
    # A = conifer, broadleaf, farmland; B = rock, mire, heath; C = built-up. Loaded only at close zoom, for the
    # visible tiles.
    dry = (alpha_land * (1 - lake_a)).astype(np.float32)
    packs = {"A": ("conifer", "broadleaf", "farm"), "B": ("rock", "wet", "heath"), "C": ("urban", None, None)}
    packs_out = {k_: [n or "" for n in v_] for k_, v_ in packs.items()}
    n2y, n2x = ny // 2, nx // 2
    dry2 = dry[: n2y * 2, : n2x * 2].reshape(n2y, 2, n2x, 2).max(axis=(1, 3))
    cov_tiles = [[tx // TILE, ty // TILE] for ty in range(0, n2y, TILE) for tx in range(0, n2x, TILE)
                 if dry2[ty:ty + TILE, tx:tx + TILE].max() > 0]  # every pack is written for every tile with land
    for key, names in packs.items():
        arr = np.dstack([(cover[n] * dry)[: n2y * 2, : n2x * 2].reshape(n2y, 2, n2x, 2).mean(axis=(1, 3)) if n else
                         np.zeros((n2y, n2x), np.float32) for n in names])
        arr = (np.round(np.clip(arr, 0, 1) * 15) * 17).astype(np.uint8)
        for tx, ty in cov_tiles:
            blk = arr[ty * TILE:(ty + 1) * TILE, tx * TILE:(tx + 1) * TILE]
            q = OUT / "cover" / f"{key}_{tx}_{ty}.webp"
            q.parent.mkdir(exist_ok=True)
            Image.fromarray(np.ascontiguousarray(blk), "RGB").save(q, "WEBP", lossless=True, quality=100, method=6)
    manifest["cover"] = {"packs": packs_out, "km_per_px": RES * 2, "tile_px": TILE, "tiles": cov_tiles,
                         "path": "relief/cover/{k}_{x}_{y}.webp", "levels": 16,
                         "note": "CORINE 2018 class masks at 1 km (forest weighted by Copernicus tree cover density) for "
                                 "the illustration layer; patterns drawn through them are illustrative, not positions"}
    # L0 whole image at 1 km
    im0 = Image.fromarray(rgba, "RGBA").resize((nx // 2, ny // 2), Image.BOX)
    im0.save(OUT / "L0.webp", "WEBP", quality=84, alpha_quality=90, method=6)
    manifest["levels"].insert(0, {"id": "L0", "km_per_px": RES * 2, "size": [nx // 2, ny // 2], "path": "relief/L0.webp"})
    # gray hillshade for analyze mode (multiplied over lens colours; flat ground ≈ white); lakes cut out
    gval = np.clip(238 + 150 * rel, 0, 255)
    gray = np.dstack([gval, gval, gval, alpha_land * (1 - lake_a) * 255]).clip(0, 255).astype(np.uint8)
    Image.fromarray(gray, "RGBA").resize((nx // 2, ny // 2), Image.BOX).save(OUT / "gray.webp", "WEBP", quality=80, alpha_quality=90, method=6)
    manifest["gray"] = {"km_per_px": RES * 2, "size": [nx // 2, ny // 2], "path": "relief/gray.webp"}
    # sea: Natural Earth depth bands (200/1000/2000/3000 m) as one continuous image, so the water shows no hex steps
    _sea(frame, nx // 2, ny // 2, RES * 2, alpha_land[::2, ::2][: ny // 2, : nx // 2])
    manifest["sea"] = {"km_per_px": RES * 2, "size": [nx // 2, ny // 2], "path": "relief/sea.webp",
                       "note": "Natural Earth bathymetry depth bands, blurred; shallow tint within a few km of land is a "
                               "cartographic convention, not measured depth"}
    # land hexes the image does not cover (no 1 km data, e.g. Russia): the map draws those as hex tiles
    gw = world["grid"]
    del rgb, rgba, cover
    st = 2  # every other pixel (1 km) is plenty to measure each 6 km hex's coverage, at a quarter of the memory
    hx = geo.cell_at(((np.arange(0, nx, st) + 0.5) * RES)[None, :].repeat(len(range(0, ny, st)), 0).ravel(),
                     ((np.arange(0, ny, st) + 0.5) * RES)[:, None].repeat(len(range(0, nx, st)), 1).ravel(), gw["radius"], gw["cols"], gw["rows"])
    ok = hx >= 0
    cov = np.bincount(hx[ok], weights=(~nodata[::st, ::st]).ravel()[ok].astype(float), minlength=gw["cols"] * gw["rows"])
    cnt = np.bincount(hx[ok], minlength=gw["cols"] * gw["rows"])
    frac = cov / np.maximum(cnt, 1)
    water = world["water"]
    manifest["hex_fallback"] = [int(i) for i in range(len(frac)) if not water[i] and frac[i] < 0.5]
    h = hashlib.sha256()
    for p in sorted(OUT.glob("**/*.webp")):
        h.update(p.read_bytes())
    manifest["sha256"] = h.hexdigest()
    manifest["bytes"] = sum(p.stat().st_size for p in OUT.glob("**/*.webp"))
    write_json(OUT / "index.json", manifest)

    # --- coastline vectors (crisp stroke at close zoom), traced from the same land alpha -------------------------
    from skimage import measure
    a_sea = alpha_land.copy()
    a_sea[lake_a > 0.5] = 0
    lines = []
    for c in measure.find_contours(a_sea, 0.5):
        if len(c) < 6:
            continue
        xy = np.column_stack([(c[:, 1] + 0.5) * RES, (c[:, 0] + 0.5) * RES])
        from shapely.geometry import LineString
        ls = LineString(xy).simplify(0.12)
        pts = np.asarray(ls.coords)
        if ls.length < 1.5:
            continue
        q = np.round(pts / 0.02).astype(np.int64)
        d = np.vstack([q[:1], np.diff(q, axis=0)]).ravel().tolist()
        lines.append(d)
    write_json(WEB_DATA / "coast.json", {"scale": 0.02, "note": "shore lines (sea and lake) traced from the relief "
                                         "raster's land mask at 0.5 km; for drawing only", "lines": lines})
    print(f"    relief: {len(tiles)} L1 tiles, {manifest['bytes'] / 1e6:.1f} MB; {len(lines)} shore lines")


def _sea(frame, nx, ny, res, land):
    """Sea colour by depth band (Natural Earth 10 m bathymetry polygons), blurred across band edges, with a light
    tint near land and a faint texture. Saved as relief/sea.webp (opaque)."""
    from shapely.geometry import shape
    depth = np.zeros((ny, nx), np.uint8)
    for k, name in enumerate(("K_200", "J_1000", "I_2000", "H_3000"), 1):
        fs = read_json(RAW / "natural_earth" / f"ne_10m_bathymetry_{name}.geojson")["features"]
        img = Image.new("L", (nx, ny), 0)
        dr = ImageDraw.Draw(img)
        for f in fs:
            g = shape(f["geometry"])
            for poly_ in (g.geoms if hasattr(g, "geoms") else [g]):
                def pts(ring):
                    lo, la = np.asarray(ring.coords).T
                    x_, y_ = frame.from_ll(lo, la)
                    return list(zip((x_ / res).tolist(), (y_ / res).tolist()))
                e = pts(poly_.exterior)
                if len(e) >= 3:
                    dr.polygon(e, fill=255)
                for hole in poly_.interiors:
                    h_ = pts(hole)
                    if len(h_) >= 3:
                        dr.polygon(h_, fill=0)
        depth = np.where(np.asarray(img) > 127, k, depth)
    cols = np.array([[48, 106, 148], [32, 82, 124], [24, 66, 104], [18, 52, 86], [14, 44, 74]], np.float32)
    rgb = cols[depth]
    rgb = np.stack([ndimage.gaussian_filter(rgb[..., c], 2.2) for c in range(3)], axis=-1)
    # a soft shadow of the land on the water to the south-east (same sun as the relief): the land sits on the sea
    sh = ndimage.gaussian_filter(np.roll(np.roll((land > 0.5).astype(np.float32), int(round(2.5 / res)), 0), int(round(2.5 / res)), 1), 3.0 / res)
    rgb *= (1 - 0.28 * sh)[..., None]
    dist = ndimage.distance_transform_edt(land < 0.5) * res
    near = np.exp(-dist / 3.5)[..., None]
    rgb = rgb * (1 - 0.35 * near) + np.array([96, 160, 186], np.float32) * 0.35 * near
    rgb *= (1 + 0.035 * _noise((ny, nx), [10, 3], SEED + 7))[..., None]
    # fade to transparent over the outer 60 km so the image meets the map's deep-ocean background without an edge
    yy, xx = np.mgrid[0:ny, 0:nx]
    edge = np.minimum(np.minimum(xx, nx - 1 - xx), np.minimum(yy, ny - 1 - yy)) * res
    a = np.clip(edge / 60.0, 0, 1) * 255
    Image.fromarray(np.dstack([np.clip(rgb, 0, 255), a]).astype(np.uint8), "RGBA").save(OUT / "sea.webp", "WEBP", quality=80, alpha_quality=60, method=6)


def _countries_on_grid(codes, xmin, ymin, shp):
    """1 where a 1 km EPSG:3035 grid cell (lower-left xmin+i, ymin+j km) lies in one of the Natural Earth countries."""
    from shapely.geometry import shape
    to = Transformer.from_crs("EPSG:4326", "EPSG:3035", always_xy=True)
    img = Image.new("L", (shp[1], shp[0]), 0)
    dr = ImageDraw.Draw(img)
    ne = read_json(RAW / "natural_earth" / "ne_10m_admin_0_countries.geojson")
    for f in ne["features"]:
        if (f["properties"].get("ISO_A2_EH") or f["properties"].get("ISO_A2")) not in codes:  # Norway has ISO_A2 = -99
            continue
        g = shape(f["geometry"])
        for poly_ in (g.geoms if hasattr(g, "geoms") else [g]):
            lo, la = np.asarray(poly_.exterior.coords).T
            x_, y_ = to.transform(lo, la)
            pts = list(zip((x_ / 1000 - xmin).tolist(), (y_ / 1000 - ymin).tolist()))
            if len(pts) >= 3:
                dr.polygon(pts, fill=255)
    return (np.asarray(img) > 127).astype(np.float32)


def _lat_raster(frame, nx, ny):
    """Latitude of each pixel (computed on a coarse grid and interpolated)."""
    step = 16
    jj, ii = np.mgrid[0:ny:step, 0:nx:step]
    lon, lat = frame.to_ll((ii + 0.5) * RES, (jj + 0.5) * RES)
    z = ndimage.zoom(lat.astype(np.float32), (ny / lat.shape[0], nx / lat.shape[1]), order=1)[:ny, :nx]
    return np.pad(z, ((0, ny - z.shape[0]), (0, nx - z.shape[1])), mode="edge")
