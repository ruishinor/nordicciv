"""Build only the three close-up terrain pilots; municipal data is never read or changed.

Install requirements-terrain.txt, then: python -m pipeline.terrain_pilot [--offline]
Source windows are cached under data/raw/terrain-pilot. --check verifies shipped assets
and shared edges without requiring Rasterio or network access.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from urllib.request import Request, urlopen

import numpy as np

from pipeline.core.geo import Frame

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web" / "terrain"
CACHE = ROOT / "data" / "raw" / "terrain-pilot"
SPAN = 3.84
CELL = 0.03
LEVELS = [(0, 16), (1, 4), (2, 1)]
REGIONS = [
    ("oslo-lillestrom", "Oslo–Lillestrøm", 10.94, 59.94, 8, 6),
    ("aurland", "Aurland mountains", 7.236, 60.909, 4, 4),
    ("herning", "Herning", 8.973, 56.139, 4, 4),
]
LICENSE_URL = "https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/DEM/resources/license/License-COPDEM-30.pdf"
ATTRIBUTION = "produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved"
LIABILITY = "The organisations in charge of the Copernicus programme by law or by delegation do not incur any liability for any use of the Copernicus WorldDEM-30."


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def source_window(lon, lat, south, west, offline):
    """Read a cropped native-resolution COG window, never a full national raster."""
    import rasterio
    from rasterio.windows import Window

    name = f"Copernicus_DSM_COG_10_N{south:02d}_00_E{west:03d}_00_DEM"
    url = f"https://copernicus-dem-30m.s3.amazonaws.com/{name}/{name}.tif"
    # The COG pixels are point samples. Record actual affine/window values, not guessed spacing.
    request_key = sha(np.array([lon.min(), lat.min(), lon.max(), lat.max()], dtype="<f8").tobytes())[:16]
    path = CACHE / f"{name}-{request_key}.npz"
    meta_path = path.with_suffix(".json")
    if path.exists() and meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if sha(path.read_bytes()) != meta["cropSha256"]:
            raise ValueError(f"Source crop checksum differs: {path.name}")
        with np.load(path) as d:
            return d["heights"], meta
    if offline:
        raise FileNotFoundError(f"Cached source window required: {path}")
    CACHE.mkdir(parents=True, exist_ok=True)
    # Confirm range support and record the immutable object identity before GDAL reads blocks.
    with urlopen(Request(url, headers={"Range": "bytes=0-15"}), timeout=45) as response:
        if response.status != 206 or len(response.read(17)) != 16:
            raise ValueError("Source does not honour bounded byte ranges")
        etag, modified, content_range = (response.headers.get(k) for k in ("ETag", "Last-Modified", "Content-Range"))
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
                      GDAL_HTTP_TIMEOUT="45", GDAL_HTTP_MAX_RETRY="2", GDAL_CACHEMAX=32 * 1024 * 1024):
        with rasterio.open(url) as src:
            cols = (lon - src.transform.c) / src.transform.a - 0.5
            rows = (lat - src.transform.f) / src.transform.e - 0.5
            c0, r0 = max(0, math.floor(cols.min()) - 2), max(0, math.floor(rows.min()) - 2)
            c1, r1 = min(src.width, math.ceil(cols.max()) + 3), min(src.height, math.ceil(rows.max()) + 3)
            window = Window(c0, r0, c1 - c0, r1 - r0)
            values = src.read(1, window=window, masked=True)
            if np.ma.getmaskarray(values).any() or not np.isfinite(values).all():
                raise ValueError(f"Missing elevation in {name}")
            values = np.asarray(values, dtype="<f4")
            np.savez_compressed(path, heights=values)
            meta = {"url": url, "etag": etag, "lastModified": modified, "rangeProbe": content_range,
                    "nativeShape": [src.height, src.width], "nativeSpacingDegrees": list(src.res),
                    "crs": str(src.crs), "transform": list(src.transform)[:6],
                    "window": [c0, r0, c1 - c0, r1 - r0], "cropFile": path.name,
                    "cropSha256": sha(path.read_bytes()), "cropBytes": path.stat().st_size}
    write_json(meta_path, meta)
    print(f"Source window {name}: {values.shape}, {path.stat().st_size:,} bytes cached", flush=True)
    return values, meta


def sample_region(frame, x, y, offline):
    from scipy.ndimage import map_coordinates

    lon, lat = frame.to_ll(x, y)
    result = np.full(x.shape, np.nan, dtype=np.float64)
    sources = []
    for south in range(math.floor(lat.min()), math.floor(lat.max()) + 1):
        for west in range(math.floor(lon.min()), math.floor(lon.max()) + 1):
            mask = (np.floor(lat) == south) & (np.floor(lon) == west)
            if not mask.any():
                continue
            values, meta = source_window(lon[mask], lat[mask], south, west, offline)
            a, _, c, _, e, f = meta["transform"]
            c0, r0, _, _ = meta["window"]
            col = (lon[mask] - c) / a - 0.5 - c0
            row = (lat[mask] - f) / e - 0.5 - r0
            result[mask] = map_coordinates(values, [row, col], order=1, mode="nearest", prefilter=False)
            sources.append(meta)
    if not np.isfinite(result).all() or result.min() < -200 or result.max() > 4000:
        raise ValueError("Pilot elevation coverage or range check failed")
    return np.rint(result * 4).astype("<i2"), sources


def build(offline=False):
    projection = json.loads((ROOT / "web/data/world.json").read_text(encoding="utf-8"))["projection"]
    frame = Frame(projection["x0_km"], projection["y1_km"])
    manifest = {"version": 1, "projection": projection, "tileSpanKm": SPAN, "heightUnitM": 0.25,
                "encoding": "Signed 16-bit little-endian, row-major, one-sample halo on all sides",
                "source": {"name": "Copernicus GLO-30 Public", "release": "2021 AWS COG distribution",
                           "type": "Surface model including vegetation and buildings", "verticalDatum": "EGM2008",
                           "nominalSpacingM": 30, "license": LICENSE_URL, "attribution": ATTRIBUTION,
                           "liability": LIABILITY,
                           "documentation": "https://copernicus-dem-30m.s3.amazonaws.com/readme.html"},
                "levels": [{"id": level, "stepKm": CELL * stride, "samples": 128 // stride + 3}
                           for level, stride in LEVELS], "regions": [], "tiles": []}
    provenance = {"source": manifest["source"], "processing": "Native-resolution HTTP-range windows; bilinear reprojection to the existing Nordic LAEA frame; quarter-metre quantisation; nested grids share samples. No statistical data is rebuilt.",
                  "regions": []}
    tiles_dir = OUT / "tiles"
    tiles_dir.mkdir(parents=True, exist_ok=True)
    for rid, name, lon, lat, nx, ny in REGIONS:
        cx, cy = frame.from_ll(lon, lat)
        tx, ty = math.floor(float(cx) / SPAN) - nx // 2, math.floor(float(cy) / SPAN) - ny // 2
        # The coarsest halo is 16 base samples, so every exported level has actual neighbours for its normals.
        xs = (np.arange(nx * 128 + 33) + tx * 128 - 16) * CELL
        ys = (np.arange(ny * 128 + 33) + ty * 128 - 16) * CELL
        x, y = np.meshgrid(xs, ys)
        heights, sources = sample_region(frame, x, y, offline)
        region = {"id": rid, "name": name, "bounds": [tx * SPAN, ty * SPAN, (tx + nx) * SPAN, (ty + ny) * SPAN],
                  "heightRangeM": [float(heights.min()) / 4, float(heights.max()) / 4],
                  "center": {"lon": lon, "lat": lat}}
        manifest["regions"].append(region)
        provenance["regions"].append({**region, "windows": sources})
        for level, stride in LEVELS:
            n = 128 // stride + 3
            for dy in range(ny):
                for dx in range(nx):
                    row, col = 16 + dy * 128 - stride, 16 + dx * 128 - stride
                    tile = heights[row:row + (n - 1) * stride + 1:stride, col:col + (n - 1) * stride + 1:stride]
                    assert tile.shape == (n, n)
                    data = tile.tobytes()
                    digest = sha(data)
                    key = f"{level}-{tx+dx}-{ty+dy}"
                    filename = f"tiles/{key}-{digest[:12]}.bin"
                    (OUT / filename).write_bytes(data)
                    manifest["tiles"].append({"key": key, "level": level, "x": tx + dx, "y": ty + dy,
                                              "path": filename, "sha256": digest, "bytes": len(data)})
        print(f"{name}: {nx * ny} tiles per level; heights {region['heightRangeM']}", flush=True)
    write_json(OUT / "provenance.json", provenance)
    write_json(OUT / "index.json", manifest)
    return check()


def check(root=OUT):
    """Verify files, coverage, level nesting and neighbouring edges from shipped assets."""
    doc = json.loads((root / "index.json").read_text(encoding="utf-8"))
    projection = json.loads((ROOT / "web/data/world.json").read_text(encoding="utf-8"))["projection"]
    assert doc["projection"] == projection, "Terrain must use the existing map frame"
    assert len(doc["regions"]) == 3
    levels = {d["id"]: d for d in doc["levels"]}
    arrays = {}
    for t in doc["tiles"]:
        path = root / t["path"]
        assert path.resolve().is_relative_to(root.resolve())
        data = path.read_bytes()
        assert len(data) == t["bytes"] and sha(data) == t["sha256"], t["key"]
        n = levels[t["level"]]["samples"]
        a = np.frombuffer(data, dtype="<i2").reshape(n, n)
        assert a.min() > -32768 and a.min() >= -800 and a.max() <= 16000
        arrays[t["key"]] = a
    seams = nesting = 0
    for t in doc["tiles"]:
        level, x, y = t["level"], t["x"], t["y"]
        a = arrays[t["key"]]
        right, bottom = arrays.get(f"{level}-{x+1}-{y}"), arrays.get(f"{level}-{x}-{y+1}")
        if right is not None:
            assert np.array_equal(a[:, -3:], right[:, :3]), f"East seam {t['key']}"
            seams += 1
        if bottom is not None:
            assert np.array_equal(a[-3:, :], bottom[:3, :]), f"South seam {t['key']}"
            seams += 1
        if level < 2:
            fine = arrays[f"2-{x}-{y}"]
            stride = round(levels[level]["stepKm"] / CELL)
            assert np.array_equal(a[1:-1, 1:-1], fine[1:-1:stride, 1:-1:stride]), f"Nested level {t['key']}"
            nesting += 1
    result = {"tiles": len(arrays), "bytes": sum(t["bytes"] for t in doc["tiles"]), "sharedEdges": seams, "nestedGrids": nesting}
    print(json.dumps(result), flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Use verified cached source windows only")
    parser.add_argument("--check", action="store_true", help="Check the shipped terrain without downloads")
    args = parser.parse_args()
    check() if args.check else build(args.offline)
