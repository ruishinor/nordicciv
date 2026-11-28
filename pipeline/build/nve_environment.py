"""Compile NVE polygon snapshots into the existing map frame; no runtime source requests."""
from __future__ import annotations
import argparse
import json
import math
import numpy as np
import shapely
from shapely.geometry import shape
from ..sources.nve_environment import NveEnvironment, GROUPS
from ..core import geo, fetch
from ..core.paths import WEB_DATA
from ..core.store import read_json, write_json
from .catalog import update_source

PATH = WEB_DATA / "nve_environment.json"
TOLERANCE_KM = 0.025
# Display only the southeast pilot area to keep the initial layer compact.
DISPLAY_BOUNDS = (9.0, 58.8, 12.8, 61.5)


def polygons(g):
    if g.geom_type == "Polygon":
        yield g
    elif hasattr(g, "geoms"):
        for part in g.geoms:
            yield from polygons(part)


def encode_feature(row, frame):
    original = shape(row["geometry"])
    if original.is_empty or not all(math.isfinite(x) for x in original.bounds):
        raise ValueError("Empty or invalid NVE geometry")
    lon0,lat0,lon1,lat1 = original.bounds
    if not (3 <= lon0 <= lon1 <= 33 and 56 <= lat0 <= lat1 <= 72):
        raise ValueError("NVE geometry is outside mainland Norway's coordinate envelope")
    def project(coords):
        x,y = frame.from_ll(coords[:,0],coords[:,1])
        return np.column_stack((x,y))
    projected = shapely.transform(original,project)
    if not projected.is_valid:
        projected = shapely.make_valid(projected)
    parts = list(polygons(projected))
    if not parts:
        raise ValueError("NVE feature has no polygon area")
    rings = []
    for p in parts:
        q = p.simplify(TOLERANCE_KM,preserve_topology=True)
        if q.is_empty:
            raise ValueError("NVE simplification removed a polygon")
        for ring in [q.exterior,*q.interiors]:
            points = [[round(float(x),5),round(float(y),5)] for x,y in ring.coords]
            if len({tuple(p) for p in points}) < 3:
                raise ValueError("NVE ring collapsed")
            rings.append(points)
    props = row["properties"]
    return {"id":props["objectid"], "name":props.get("flomsoneid") or props.get("brenavn") or props.get("hovedbrenavn"),
            "bbox":[round(float(v),5) for v in projected.bounds], "rings":rings}


def build(write=True):
    source = NveEnvironment()
    data = source.process()
    world = read_json(WEB_DATA / "world.json")
    proj = world["projection"]
    frame = geo.Frame(proj["x0_km"],proj["y1_km"])
    manifest = fetch.read_manifest(source.id)["files"]
    files = [{ "file":f.rel_path, "url":f.url, "sha256":manifest[f.rel_path]["sha256"],
              "bytes":manifest[f.rel_path]["bytes"], "retrieved":manifest[f.rel_path]["retrieved"]} for f in source.files()]
    packet = {"source":{"publisher":"NVE","license":source.info.license,"files":files},
              "simplification_km":TOLERANCE_KM, "groups":{}}
    for group, rows in data.items():
        selected = [row for row in rows if
                    (lambda b: b[0] >= DISPLAY_BOUNDS[0] and b[1] >= DISPLAY_BOUNDS[1]
                     and b[2] <= DISPLAY_BOUNDS[2] and b[3] <= DISPLAY_BOUNDS[3])(shape(row["geometry"]).bounds)]
        features = [encode_feature(row,frame) for row in sorted(selected,key=lambda r:r["properties"]["objectid"])]
        if not features:
            raise ValueError("No flood polygons in the display selection")
        packet["groups"][group] = {"source_count":len(rows),"display_count":len(features),
                                   "display_bounds_lonlat":list(DISPLAY_BOUNDS),"features":features}
        print(f"{group}: {len(features)} displayed of {len(rows)} source polygons",flush=True)
    if len(json.dumps(packet,separators=(",",":")).encode()) > 3_000_000:
        raise ValueError("NVE map packet exceeds 3 MB budget")
    if write:
        write_json(PATH,packet)
        update_source(source)
    return packet


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch",action="store_true")
    if parser.parse_args().fetch:
        NveEnvironment().fetch()
    build()
