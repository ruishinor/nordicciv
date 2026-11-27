"""Sector-weighted allocation of regional economic output to municipalities (NC-T07).

The regional total published by each agency (Norway: county GVA at basic prices; Sweden: GRDP at market prices;
Denmark: GDP by landsdel) is kept exactly. What changes is the *key* used to share it between the municipalities of
the region. Instead of total jobs (which assumes the same output per job in every industry), each municipality's key
is the region's value added in each industry, shared by the municipality's jobs in that industry:

    key(m) = Σ_s GVA(region, s) × jobs(m, s) / jobs(region, s)   +   GVA(region, L) × residents(m) / residents(region)
             + unallocated GVA(region) × jobs(m) / jobs(region)

so a municipality of oil-service engineers and one of shop assistants with the same number of jobs no longer get the
same output. Real estate (L, which includes the imputed rent of owner-occupied dwellings) follows residents. Value added
the agency suppresses for a region-industry is shared by total jobs. The method still assumes equal output per job
*within* an industry and region; the result is an estimate and is always labelled as such.

Industry value added: SSB table 11713 (2023, 2020–2023 counties) and Eurostat nama_10r_3gva (2023, NUTS 3) for
Sweden and Denmark.
"""
from __future__ import annotations

import json
from collections import defaultdict

from ..core import jsonstat
from ..core.paths import RAW
from ..sources.stats import estat_records

YEAR = "2023"
# sector bucket -> harmonised job groups (None = residents)
BUCKETS = {
    "A": ["A"], "B-E": ["BC", "DE"], "F": ["F"], "G-I": ["G", "H", "I"], "J": ["J"], "K": ["K"],
    "L": None, "M_N": ["LMN"], "O-Q": ["O", "P", "Q"], "R-U": ["RS"],
}
NO_CODES = {
    "A": ["pub2X01_02", "pub2X03"], "B-E": ["pub2X05", "nr2X06_09", "nr23ind", "pub2X35", "pub2X36_39"],
    "F": ["pub2X41_43"], "G-I": ["pub2X45_47", "pub2X49B", "pub2X50A", "pub2X49A_52", "pub2X53", "pub2X55_56"],
    "J": ["pub2X58_63"], "K": ["pub2X64_66"], "L": ["pub2X68A", "pub2X68B"], "M_N": ["pub2X69_75", "pub2X77_82"],
    "O-Q": ["pub2X84", "pub2X85", "pub2X86_88"], "R-U": ["pub2X90_97"],
}
SE_NUTS3 = {"01": "SE110", "03": "SE121", "04": "SE122", "05": "SE123", "18": "SE124", "19": "SE125", "06": "SE211",
            "07": "SE212", "08": "SE213", "09": "SE214", "10": "SE221", "12": "SE224", "13": "SE231", "14": "SE232",
            "17": "SE311", "20": "SE312", "21": "SE313", "22": "SE321", "23": "SE322", "24": "SE331", "25": "SE332"}
DK_NUTS3 = {"01": "DK011", "02": "DK012", "03": "DK013", "04": "DK014", "05": "DK021", "06": "DK022", "07": "DK031",
            "08": "DK032", "09": "DK041", "10": "DK042", "11": "DK050"}
SOURCES = "SSB 11713 (2023); Eurostat nama_10r_3gva (2023)"


def sector_gva() -> dict:
    """{gdp region id: {"total": x, bucket: x or None}} in any currency (only shares are used)."""
    out = {}
    p = RAW / "regional_accounts" / "ssb_11713_gva_industry.json"
    if p.exists():
        js = jsonstat.load(p)
        t = defaultdict(dict)
        for d, v, _ in jsonstat.records(js):
            t[d["Region"]][d["NACE"]] = v
        for reg, vals in t.items():
            if len(reg) != 2 or reg in ("21", "23"):
                continue
            rec = {"total": vals.get("nr23_6")}
            for b, codes in NO_CODES.items():
                parts = [vals.get(c) for c in codes]
                rec[b] = sum(x for x in parts if x is not None) if any(x is not None for x in parts) else None
            out[f"NO-{reg}"] = rec
    p = RAW / "regional_accounts" / "nama_10r_3gva.json"
    if p.exists():
        recs = [r for r in estat_records(json.loads(p.read_text())) if r["time"] == YEAR]
        by = defaultdict(dict)
        for r in recs:
            by[r["geo"]][r["nace_r2"]] = r["value"]
        for cc, table in (("SE", SE_NUTS3), ("DK", DK_NUTS3)):
            for code, nuts in table.items():
                v = by.get(nuts)
                if not v:
                    continue
                rec = {"total": v.get("TOTAL")}
                for b in BUCKETS:
                    rec[b] = v.get(b)
                out[f"{cc}-{code}"] = rec
    return out


def keys(munis_in_region: list[dict], gva: dict) -> dict | None:
    """{muni id: allocation key} for one region (None if no industry data)."""
    if not gva or not gva.get("total"):
        return None
    jobs_r = defaultdict(float)
    pop_r = sum(m["pop"] or 0 for m in munis_in_region)
    jt_r = sum(m["jobs_total"] or 0 for m in munis_in_region)
    for m in munis_in_region:
        for g, v in m["jobs"].items():
            jobs_r[g] += v or 0
    allocated = sum(v for b, v in gva.items() if b != "total" and v is not None)
    unalloc = max(0.0, gva["total"] - allocated)
    out = {}
    for m in munis_in_region:
        k = 0.0
        for b, groups in BUCKETS.items():
            v = gva.get(b)
            if v is None:
                continue
            if groups is None:
                k += v * (m["pop"] or 0) / pop_r if pop_r else 0
            else:
                den = sum(jobs_r[g] for g in groups)
                k += v * sum(m["jobs"].get(g, 0) for g in groups) / den if den else 0
        k += unalloc * (m["jobs_total"] or 0) / jt_r if jt_r else 0
        out[m["id"]] = k
    return out
