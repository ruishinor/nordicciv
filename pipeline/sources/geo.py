"""Geographic foundation sources (all downloadable from GitHub-hosted mirrors of the publishers' data)."""
from __future__ import annotations

import csv
import io
import json
import subprocess

import numpy as np

from ..core.source import File, Source, SourceInfo
from ..core.paths import INTERIM

GH = "https://raw.githubusercontent.com"

# EPSG:3035 bounding box of the area modelled (km): Scandinavia + a margin of neighbouring land.
BBOX_KM = (3500, 3250, 5700, 5600)  # x0, y0, x1, y1


def _tiles(dataset: str, tile_cells: int, ext: str, listing: list[str] | None = None) -> list[tuple[int, int]]:
    x0, y0, x1, y1 = BBOX_KM
    out = []
    for tx in range(x0 // tile_cells, x1 // tile_cells + 1):
        for ty in range(y0 // tile_cells, y1 // tile_cells + 1):
            out.append((tx, ty))
    return out


class GiscoGrids(Source):
    """Eurostat/GISCO 1 km grids, tiled for the web by Julien Gaffuri (Eurostat) on GitHub."""

    info = SourceInfo(
        id="gisco_grids",
        title="European 1 km grids: EU-DEM elevation, CORINE Land Cover, Tree Cover Density, GEOSTAT population, "
              "DEGURBA, service accessibility, road transport performance",
        publisher="Eurostat GISCO / Copernicus Land Monitoring Service / JRC (tiled by J. Gaffuri, github.com/jgaffuri/tiledgrids)",
        homepage="https://github.com/jgaffuri/tiledgrids",
        license="Eurostat/GISCO reuse policy (free reuse with attribution: © EuroGeographics for administrative "
                "boundaries; Copernicus data: free, full and open, attribution required)",
        description="1 km cells in ETRS89-LAEA (EPSG:3035). Elevation = EU-DEM v1.1; land cover = CORINE Land Cover "
                    "(1990–2018, class of the 1 km cell); tree cover density = Copernicus HRL TCD (2012–2018); "
                    "population = GEOSTAT grids 2006/2011/2018 (+2021); DEGURBA grid classes; average time to the "
                    "nearest primary school and hospital; population reachable by road in 90 min.",
        used_for=["terrain", "land cover", "elevation", "hex population weights", "urban classes", "accessibility lenses"],
    )
    DATASETS = {  # name: (tile cells, extension)
        "population2": (128, "csv"),
        "clc_": (256, "parquet"),
        "elevation_": (256, "parquet"),
        "forest_": (256, "parquet"),
        "degurba": (128, "csv"),
        "accessibility": (128, "csv"),
        "road_transp_perf": (128, "csv"),
    }

    def files(self):
        # The repository only holds tiles that contain data; the listing is part of the cache.
        out = []
        listing = self._listing()
        for ds, (tc, ext) in self.DATASETS.items():
            out.append(File(f"{ds}/1000m/info.json", f"{GH}/jgaffuri/tiledgrids/master/data/europe/{ds}/1000m/info.json"))
            for tx, ty in _tiles(ds, tc, ext):
                rel = f"{ds}/1000m/{tx}/{ty}.{ext}"
                if rel in listing:
                    out.append(File(rel, f"{GH}/jgaffuri/tiledgrids/master/data/europe/{rel}"))
        return out

    def _listing(self) -> set[str]:
        p = self.raw_dir / "listing.txt"
        if not p.exists():
            raise FileNotFoundError("gisco_grids: listing.txt missing (run tools/list_tiledgrids.sh)")
        return set(p.read_text().split())

    def process(self) -> dict:
        import pyarrow.parquet as pq

        cells: dict[tuple[int, int], dict] = {}

        def put(X, Y, **kv):
            c = cells.get((X, Y))
            if c is None:
                c = cells[(X, Y)] = {}
            c.update(kv)

        for ds, (tc, ext) in self.DATASETS.items():
            base = self.raw_dir / ds / "1000m"
            for f in sorted(base.glob(f"*/*.{ext}")):
                tx, ty = int(f.parent.name), int(f.stem)
                if ext == "csv":
                    rows = csv.DictReader(io.StringIO(f.read_text()))
                else:
                    rows = pq.read_table(f).to_pylist()
                for r in rows:
                    X, Y = tx * tc + int(r["x"]), ty * tc + int(r["y"])
                    if ds == "population2":
                        put(X, Y, cntr=r["CNTR_ID"], **{f"pop{y}": _num(r.get(f"TOT_P_{y}")) for y in (2006, 2011, 2018, 2021)})
                    elif ds == "clc_":
                        put(X, Y, clc1990=r.get("y1990"), clc2000=r.get("y2000"), clc2018=r.get("y2018"))
                    elif ds == "elevation_":
                        put(X, Y, elev=r.get("elevation"))
                    elif ds == "forest_":
                        put(X, Y, tcd2018=r.get("tcd2018"), tcd2012=r.get("tcd2012"))
                    elif ds == "degurba":
                        # dominant DEGURBA settlement class of the 1 km cell (GHS-SMOD style classes)
                        best = max(("uc", "du", "sdu", "sbu", "sub", "r", "lr", "vlr"), key=lambda k: _num(r.get(k)) or 0)
                        put(X, Y, cntr2=r["CNTR_ID"], degurba=best if (_num(r.get(best)) or 0) > 0 else None)
                    elif ds == "accessibility":
                        put(X, Y, acc_school=_num(r.get("avg_time_nearest_ep")), acc_hospital=_num(r.get("avg_time_nearest_h")))
                    elif ds == "road_transp_perf":
                        put(X, Y, road_reach=_num(r.get("ra")), road_near=_num(r.get("pp")), road_perf=_num(r.get("rp")))
        keys = sorted(cells)
        X = np.array([k[0] for k in keys], dtype=np.int32)
        Y = np.array([k[1] for k in keys], dtype=np.int32)

        def col(name, dtype=np.float32, fill=np.nan):
            return np.array([cells[k].get(name) if cells[k].get(name) is not None else fill for k in keys], dtype=dtype)

        cntr = [cells[k].get("cntr") or cells[k].get("cntr2") or "" for k in keys]
        arrays = dict(
            X=X, Y=Y, cntr=np.array(cntr),
            pop2006=col("pop2006"), pop2011=col("pop2011"), pop2018=col("pop2018"), pop2021=col("pop2021"),
            clc1990=col("clc1990", np.int16, -1), clc2000=col("clc2000", np.int16, -1), clc2018=col("clc2018", np.int16, -1),
            elev=col("elev"), tcd2018=col("tcd2018"), tcd2012=col("tcd2012"),
            degurba=np.array([cells[k].get("degurba") or "" for k in keys]),
            acc_school=col("acc_school"), acc_hospital=col("acc_hospital"),
            road_reach=col("road_reach"), road_near=col("road_near"), road_perf=col("road_perf"),
        )
        INTERIM.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(INTERIM / "gisco_grids.npz", **arrays)
        return {"cells": len(keys), "file": "gisco_grids.npz",
                "countries": {c: int(sum(1 for x in cntr if x == c)) for c in ("NO", "SE", "DK", "FI", "DE")}}


def _num(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


class NaturalEarth(Source):
    info = SourceInfo(
        id="natural_earth",
        title="Natural Earth 1:10m cultural and physical vectors",
        publisher="Natural Earth (naturalearthdata.com), via github.com/nvkelso/natural-earth-vector",
        homepage="https://www.naturalearthdata.com/",
        license="Public domain",
        description="Lakes (incl. the European supplement), rivers (incl. the European supplement), glaciated areas, "
                    "roads with ferry routes, railroads, ports, populated places, 200 m bathymetry, sea names.",
        used_for=["rivers", "lakes", "glaciers", "roads", "railroads", "ferries", "ports", "sea labels", "shelf/coast"],
    )
    LAYERS = ["lakes", "lakes_europe", "rivers_lake_centerlines", "rivers_europe", "glaciated_areas", "roads",
              "railroads", "ports", "populated_places", "bathymetry_K_200", "bathymetry_J_1000", "bathymetry_I_2000", "bathymetry_H_3000", "geography_marine_polys",
              "geography_regions_polys", "admin_0_countries", "land", "minor_islands"]

    def files(self):
        return [File(f"ne_10m_{l}.geojson", f"{GH}/nvkelso/natural-earth-vector/master/geojson/ne_10m_{l}.geojson")
                for l in self.LAYERS]

    def process(self):
        return {"layers": self.LAYERS}


class Boundaries(Source):
    info = SourceInfo(
        id="boundaries",
        title="Municipal and regional boundaries (Norway 2024, Sweden, Denmark) and NUTS 2024",
        publisher="Kartverket (NO, via github.com/robhop/fylker-og-kommuner); Valmyndigheten (SE, via "
                  "github.com/okfse/sweden-geojson); Geodatastyrelsen DAGI (DK, via github.com/Neogeografen/dagi); "
                  "Eurostat GISCO NUTS 2024 (via github.com/eurostat/Nuts2json)",
        homepage="https://github.com/eurostat/Nuts2json",
        license="NO: CC BY 4.0 Kartverket; SE: public data, reuse permitted; DK: free data (Geodatastyrelsen terms); "
                "NUTS: © EuroGeographics for the administrative boundaries",
        description="Simplified polygons. Used only to assign 1 km grid cells and hexes to municipalities and NUTS 3 "
                    "regions; statistics always come from the statistical agencies at municipal level.",
        used_for=["municipality of each hex", "NUTS 3 region of each municipality", "borders"],
    )

    def files(self):
        return [
            File("no_kommuner_2024.geojson", f"{GH}/robhop/fylker-og-kommuner/main/Kommuner-M.geojson"),
            File("no_fylker_2024.geojson", f"{GH}/robhop/fylker-og-kommuner/main/Fylker-M.geojson"),
            File("se_kommuner.geojson", f"{GH}/okfse/sweden-geojson/master/swedish_municipalities.geojson"),
            File("se_lan.geojson", f"{GH}/okfse/sweden-geojson/master/swedish_regions.geojson"),
            File("dk_kommuner.geojson", f"{GH}/Neogeografen/dagi/master/geojson/kommuner.geojson"),
            File("dk_regioner.geojson", f"{GH}/Neogeografen/dagi/master/geojson/regioner.geojson"),
            File("nuts2024_3035_03M_nutsrg_3.json", f"{GH}/eurostat/Nuts2json/master/pub/v2/2024/3035/03M/nutsrg_3.json"),
            File("nuts2024_3035_03M_nutsbn_3.json", f"{GH}/eurostat/Nuts2json/master/pub/v2/2024/3035/03M/nutsbn_3.json"),
            File("nuts2024_3035_03M_cntrg.json", f"{GH}/eurostat/Nuts2json/master/pub/v2/2024/3035/03M/cntrg.json"),
            File("nuts2024_3035_03M_cntbn.json", f"{GH}/eurostat/Nuts2json/master/pub/v2/2024/3035/03M/cntbn.json"),
        ]

    def process(self):
        return {}


class Euronym(Source):
    info = SourceInfo(
        id="euronym",
        title="Euronym place-name labels",
        publisher="Eurostat GISCO (from EuroGeographics EuroRegionalMap and the EC towns table)",
        homepage="https://github.com/eurostat/euronym",
        license="Eurostat reuse policy; © EuroGeographics",
        description="Settlement names with the map resolution above which each label is hidden (rs): a published, "
                    "evidence-based label prominence used for town names at close zoom.",
        used_for=["town labels"],
    )

    def files(self):
        return [File(f"{cc}.csv", f"{GH}/eurostat/euronym/main/pub/v3/UTF/50/{cc}.csv") for cc in ("NO", "SE", "DK")]

    def process(self):
        return {}


class OurAirports(Source):
    info = SourceInfo(
        id="ourairports",
        title="OurAirports airport database",
        publisher="OurAirports (David Megginson et al.)",
        homepage="https://ourairports.com/data/",
        license="Public domain",
        description="Airport locations, ICAO codes and size class; matched to Eurostat passenger counts by ICAO code.",
        used_for=["airport locations"],
    )

    def files(self):
        return [File("airports.csv", f"{GH}/davidmegginson/ourairports-data/main/airports.csv")]

    def process(self):
        return {}


class PowerPlants(Source):
    info = SourceInfo(
        id="powerplants",
        title="powerplantmatching: matched European power plant database",
        publisher="PyPSA / powerplantmatching (Gotzens, Hofmann et al.), combining ENTSO-E, OPSD, JRC, GEO, GPD",
        homepage="https://github.com/PyPSA/powerplantmatching",
        license="Data: CC BY 4.0 (aggregated from open sources; see project for per-source terms)",
        description="Power plants with fuel type, technology, installed capacity (MW) and coordinates.",
        used_for=["energy resources on the map (installed capacity, not generation)"],
    )

    def files(self):
        return [File("powerplants.csv", f"{GH}/PyPSA/powerplantmatching/master/powerplants.csv")]

    def process(self):
        return {}
