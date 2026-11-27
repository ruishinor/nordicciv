"""The administrative backbone: one harmonised list of municipalities and regions for Norway, Sweden and Denmark.

Ids: municipality "NO-0301", "SE-0180", "DK-101"; region "NO-03" (fylke), "SE-01" (län), "DK-084" (region).
Every statistical value attached here comes from the national statistical agency at municipal level.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache

from shapely.geometry import shape
from shapely.ops import unary_union

from ..core.paths import INTERIM, RAW

COUNTRIES = {"NO": "Norway", "SE": "Sweden", "DK": "Denmark"}
CURRENCY = {"NO": "NOK", "SE": "SEK", "DK": "DKK"}
CAPITALS = {"NO-0301", "SE-0180", "DK-101"}

# Harmonised industry groups (NACE Rev. 2 sections, grouped to the finest level all three agencies publish).
GROUPS = [
    ("A", "Agriculture, forestry & fishing"),
    ("BC", "Mining, quarrying & manufacturing"),
    ("DE", "Energy, water & waste"),
    ("F", "Construction"),
    ("G", "Wholesale & retail trade"),
    ("H", "Transport & storage"),
    ("I", "Accommodation & food"),
    ("J", "Information & communication"),
    ("K", "Finance & insurance"),
    ("LMN", "Real estate, professional, scientific, technical & business services"),
    ("O", "Public administration & defence"),
    ("P", "Education"),
    ("Q", "Health & social work"),
    ("RS", "Culture, recreation & other services"),
    ("X", "Unknown industry"),
]
GROUP_KEYS = [g for g, _ in GROUPS]
# Finer detail some countries publish (kept separately for specialisation where available).
DETAIL = {"B": "Mining & quarrying incl. oil & gas extraction", "C": "Manufacturing", "M72": "Scientific R&D"}

# national code -> harmonised group (and optional detail key)
MAP_NO = {"01-03": "A", "05-09": ("BC", "B"), "10-33": ("BC", "C"), "35-39": "DE", "41-43": "F", "45-47": "G",
          "49-53": "H", "55-56": "I", "58-63": "J", "64-66": "K", "68-75": "LMN", "77-82": "LMN", "84": "O",
          "85": "P", "86-88": "Q", "90-99": "RS", "00": "X"}
MAP_SE = {"A": "A", "B+C": "BC", "D+E": "DE", "F": "F", "G": "G", "H": "H", "I": "I", "J": "J", "K": "K", "L": "LMN",
          "M+N": "LMN", "O": "O", "P": "P", "Q": "Q", "R+S+T+U": "RS", "US": "X"}
# Denmark publishes DB25 (NACE Rev. 2.1); sections are re-lettered in 2.1, mapped back to Rev. 2 groups here.
MAP_DK = {"A": "A", "B": ("BC", "B"), "D": "DE", "E": "DE", "F": "F", "G": "G", "H": "H", "I": "I", "J": "J",
          "K61": "J", "K62-K63": "J", "L": "K", "M": "LMN", "N69-N71": "LMN", "N72": ("LMN", "M72"), "N73-N75": "LMN",
          "O": "LMN", "P": "O", "Q": "P", "R86": "Q", "R87-R88": "Q", "S": "RS", "TUV": "RS", "0000": "X"}


def _dk_group(code):
    if code.startswith("C"):
        return ("BC", "C")
    return MAP_DK.get(code)


def _load(name):
    return json.loads((INTERIM / f"{name}.json").read_text())


def _harmonise(jobs: dict, mapping, func=None):
    """Sum national industry codes into the harmonised groups. A group with a suppressed component is a lower
    bound and is listed in `partial`."""
    out = {g: 0 for g in GROUP_KEYS}
    detail = {}
    partial = set()
    for code, v in jobs.items():
        m = func(code) if func else mapping.get(code)
        if m is None:
            continue
        g, d = (m if isinstance(m, tuple) else (m, None))
        if v is None:
            partial.add(g)
            if d:
                detail[d] = None
            continue
        out[g] += v
        if d:
            detail[d] = (detail.get(d) or 0) + v
    return out, detail, sorted(partial)


@lru_cache(maxsize=1)
def municipalities() -> list[dict]:
    ssb, scb, dst = _load("ssb"), _load("scb"), _load("dst")
    out = []
    # --- Norway
    fylker = {f["properties"]["fylkesnummer"]: f["properties"]["fylkesnavn"]
              for f in json.loads((RAW / "boundaries" / "no_fylker_2024.geojson").read_text())["features"]}
    for code, r in sorted(ssb["municipalities"].items()):
        jobs, detail, partial = _harmonise(r.get("jobs", {}), MAP_NO)
        fy = code[:2]
        out.append(dict(id=f"NO-{code}", code=code, country="NO", name=_name(r.get("name")), official_name=r.get("name"), region=f"NO-{fy}",
                        region_name=_name(fylker.get(fy, fy)), gdp_region=_no_gdp_region(fy),
                        pop=_years(r["pop"]), age=r.get("age"), land_km2=r.get("land_km2"),
                        fresh_km2=r.get("fresh_km2"), jobs=jobs, jobs_detail=detail, jobs_partial=partial,
                        jobs_total=r.get("jobs_total"), employed_res=r.get("employed_res"), income=r.get("income")))
    # --- Sweden
    lan_names = {k: v.get("name") for k, v in scb["lan"].items()}
    for code, r in sorted(scb["municipalities"].items()):
        jobs, detail, partial = _harmonise(r.get("jobs", {}), MAP_SE)
        lan = code[:2]
        out.append(dict(id=f"SE-{code}", code=code, country="SE", name=r.get("name"), region=f"SE-{lan}",
                        region_name=_lan(lan_names.get(lan, lan)), gdp_region=f"SE-{lan}",
                        pop=_years(r["pop"]), age=r.get("age"), land_km2=r.get("land_km2"), jobs=jobs,
                        jobs_detail=detail, jobs_partial=partial, jobs_total=r.get("jobs_total"),
                        employed_res=r.get("employed_res"), income=r.get("income")))
    # --- Denmark: region (5) and landsdel (11 = NUTS 3) from the order of DST's workplace classification
    meta = json.loads((RAW / "dst" / "RAS501_meta.json").read_text())
    region_of, landsdel_of, region_names = {}, {}, {}
    reg = ld = None
    for v in next(x for x in meta["variables"] if x["id"] == "ARBKOM")["values"]:
        if v["id"].startswith("08") and len(v["id"]) == 3:
            reg = v["id"]
            region_names[reg] = v["text"]
        elif len(v["id"]) == 2:
            ld = v["id"]
        elif len(v["id"]) == 3 and v["id"] != "000":
            region_of[v["id"]], landsdel_of[v["id"]] = reg, ld
    for code, r in sorted(dst["municipalities"].items()):
        jobs, detail, partial = _harmonise(r.get("jobs", {}), None, _dk_group)
        out.append(dict(id=f"DK-{code}", code=code, country="DK", name=r.get("name"), region=f"DK-{region_of[code]}",
                        region_name=region_names[region_of[code]], gdp_region=f"DK-{landsdel_of[code]}",
                        pop=_years(r["pop"]), age=r.get("age"), land_km2=r.get("land_km2"), jobs=jobs,
                        jobs_detail=detail, jobs_partial=partial, jobs_total=r.get("jobs_total"),
                        employed_res=None, income=r.get("income")))
    _dk_income(out)
    polys = polygons()
    return [m for m in out if m["id"] in polys]


def _dk_income(munis):
    import csv
    import io
    p = RAW / "regional_accounts" / "dst_INDKP101.csv"
    if not p.exists():
        return
    vals = {r["OMRÅDE"]: float(r["INDHOLD"]) for r in csv.DictReader(io.StringIO(p.read_text(encoding="utf-8-sig")), delimiter=";")
            if r["INDHOLD"] not in ("", "..")}
    for m in munis:
        if m["country"] == "DK":
            m["income"] = vals.get(m["code"])
    munis_country_income["DK"] = vals.get("000")


munis_country_income: dict = {}


def country_income() -> dict:
    ssb, scb = _load("ssb"), _load("scb")
    municipalities()
    return {"NO": ssb["country"].get("income"), "SE": (scb["country"].get("income")), "DK": munis_country_income.get("DK")}


def _years(d):
    return {int(k): int(v) for k, v in d.items() if v is not None}


def _name(s):
    if not s:
        return s
    return s.split(" - ")[0].strip()


def _lan(s):
    return re.sub(r"\s+county$", "", s or "").strip()


def _no_gdp_region(fy):
    # SSB regional accounts 2023 are published on the 2020-2023 counties.
    return {"31": "NO-30", "32": "NO-30", "33": "NO-30", "39": "NO-38", "40": "NO-38", "55": "NO-54", "56": "NO-54"}.get(fy, f"NO-{fy}")


@lru_cache(maxsize=1)
def polygons() -> dict:
    """{municipality id: shapely geometry (lon/lat)} from the simplified boundary files."""
    out = {}
    for f in json.loads((RAW / "boundaries" / "no_kommuner_2024.geojson").read_text())["features"]:
        out.setdefault(f"NO-{f['properties']['kommunenummer']}", []).append(shape(f["geometry"]))
    for f in json.loads((RAW / "boundaries" / "se_kommuner.geojson").read_text())["features"]:
        out.setdefault(f"SE-{f['properties']['id']}", []).append(shape(f["geometry"]))
    for f in json.loads((RAW / "boundaries" / "dk_kommuner.geojson").read_text())["features"]:
        code = f["properties"]["KOMKODE"].lstrip("0")
        out.setdefault(f"DK-{code}", []).append(shape(f["geometry"]))
    return {k: unary_union([g.buffer(0) for g in v]) for k, v in out.items()}


def regions(munis: list[dict]) -> list[dict]:
    seen = {}
    for m in munis:
        if m["region"] not in seen:
            seen[m["region"]] = {"id": m["region"], "country": m["country"], "name": m["region_name"]}
    order = {"NO": 0, "SE": 1, "DK": 2}
    return sorted(seen.values(), key=lambda r: (order[r["country"]], r["id"]))
