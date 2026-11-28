"""Add comparable CORINE land-cover changes without rebuilding the existing map."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from ..core import geo, fetch
from ..core.paths import ROOT, RAW, WEB_DATA
from ..core.store import read_json, write_json

INVENTORY = ROOT / "pipeline" / "catalogue" / "corine_history_tiles.json"
RAMP = ["#b2443a", "#e08a5a", "#f3e6b0", "#7fbf8f", "#2f8f6f"]
GROUPS = {"forest_change": (23, 25, "Forest cover change 1990–2018", "l-forest", "🌲"),
          "agriculture_change": (12, 22, "Agricultural land change 1990–2018", "l-farmland", "🌾")}


def aggregate(cells, before, after, size):
    """One dominant class per 1 km cell; only paired valid observations count."""
    cells, before, after = map(np.asarray, (cells, before, after))
    valid = (cells >= 0) & (cells < size) & (before >= 1) & (before <= 44) & (after >= 1) & (after <= 44)
    def count(mask):
        return np.bincount(cells[valid & mask], minlength=size)
    out = {"paired": count(np.ones(len(cells), dtype=bool))}
    for key, (lo, hi, *_rest) in GROUPS.items():
        old, new = (before >= lo) & (before <= hi), (after >= lo) & (after <= hi)
        out[key + "_gain"] = count(~old & new)
        out[key + "_loss"] = count(old & ~new)
    out["urban_gain"] = count((after <= 11) & (before > 11))
    return out


def verified_tiles(acquire=False):
    inventory = read_json(INVENTORY)
    records = []
    for f in inventory["files"]:
        path = RAW / "gisco_grids" / f["file"]
        if not path.exists() and acquire:
            # Use the existing pipeline request and cache identity; verify immutable Git blob below.
            url = "https://raw.githubusercontent.com/jgaffuri/tiledgrids/master/data/europe/" + f["file"]
            fetch.download("gisco_grids", url, f["file"], relay=False)
        data = path.read_bytes()
        blob = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
        if len(data) != f["bytes"] or blob != f["git_blob"]:
            raise ValueError(f"CORINE tile differs from pinned upstream revision: {f['file']}")
        records.append({**f, "sha256": hashlib.sha256(data).hexdigest()})
    return inventory, records


def build(acquire=False, write=True):
    import pyarrow.parquet as pq
    inventory, records = verified_tiles(acquire)
    world = read_json(WEB_DATA / "world.json")
    lenses = read_json(WEB_DATA / "lenses.json")
    if lenses.get("packed") != "owned":
        raise ValueError("Expected owned-hex lens packing")
    owner = np.asarray(world["owner"])
    owned = np.flatnonzero(owner >= 0)
    n = len(owner)
    grid, proj = world["grid"], world["projection"]
    frame = geo.Frame(proj["x0_km"], proj["y1_km"])
    accum = {}
    for record in records:
        path = RAW / "gisco_grids" / record["file"]
        if path.suffix != ".parquet":
            continue
        tx, ty = int(path.parent.name), int(path.stem)
        table = pq.read_table(path, columns=["x", "y", "y1990", "y2018"])
        x, y, old, new = (np.asarray(table[k].to_numpy(zero_copy_only=False), dtype=float)
                          for k in ("x", "y", "y1990", "y2018"))
        if not (np.all(np.isfinite(x)) and np.all(np.isfinite(y)) and
                np.all((x >= 0) & (x < 256) & (y >= 0) & (y < 256)) and
                len(np.unique(x * 256 + y)) == len(x)):
            raise ValueError(f"Invalid or duplicate CORINE cell coordinates: {record['file']}")
        mx, my = frame.from_3035((tx * 256 + x) * 1000 + 500, (ty * 256 + y) * 1000 + 500)
        cells = geo.cell_at(mx, my, grid["radius"], grid["cols"], grid["rows"])
        for key, values in aggregate(cells, old, new, n).items():
            accum[key] = accum.get(key, np.zeros(n, dtype=np.int64)) + values
    paired = accum["paired"][owned]
    if not np.any(paired):
        raise ValueError("No paired CORINE observations on the NordicCiv map")
    # Independently reproduce the original urban-gain lens before introducing new values.
    old_lens = next(l for l in lenses["lenses"] if l["id"] == "urban_growth")
    expected = accum["urban_gain"][owned]
    if len(old_lens["values"]) != len(owned) or not np.array_equal(np.asarray(old_lens["values"]), expected):
        raise ValueError("Recovered CORINE tiles do not reproduce the existing urban-growth lens")
    new_lenses = []
    for key, (lo, hi, title, icon, emoji) in GROUPS.items():
        gain, loss = accum[key + "_gain"][owned], accum[key + "_loss"][owned]
        values = [int(g-l) if p else None for g,l,p in zip(gain,loss,paired)]
        label = "forest" if key == "forest_change" else "agricultural land"
        new_lenses.append({"id": key, "group": "land", "name": title, "icon": icon, "emoji": emoji,
            "unit": "km² (1 km cells)", "format": "int", "scale": "linear", "domain": [-20,20], "ramp": RAMP,
            "higher_is": "neutral", "source": "gisco_grids", "resolution": "hex",
            "description": f"Net change in CORINE {label} classes: newly classified cells minus cells leaving those classes between 1990 and 2018.",
            "note": "Only cells with a class in both years are compared. Red is loss; green is gain. Zero means no net change, not no changes. A hex is not a municipal boundary.",
            "values": values})
    lenses["lenses"] = [l for l in lenses["lenses"] if l["id"] not in GROUPS] + new_lenses
    lenses["land_history"] = {"period": [1990,2018], "upstream": inventory["upstream"],
        "revision": inventory["revision"], "files": records, "paired_cells": [int(p) for p in paired],
        "groups": {key: {"gain": [int(x) for x in accum[key+"_gain"][owned]],
                         "loss": [int(x) for x in accum[key+"_loss"][owned]]} for key in GROUPS}}
    if write:
        write_json(WEB_DATA / "lenses.json", lenses)
    print(f"CORINE: {len(records)-1} tiles, {int(paired.sum()):,} paired cells, existing urban lens reproduced exactly")
    for key in GROUPS:
        print(f"{key}: gained {int(accum[key+'_gain'][owned].sum()):,}; lost {int(accum[key+'_loss'][owned].sum()):,} one-kilometre cells")
    return lenses


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch", action="store_true", help="Acquire only the pinned CORINE tiles if missing")
    build(parser.parse_args().fetch)
