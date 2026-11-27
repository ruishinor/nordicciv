"""Bounded 2024 origin/destination observations, using the ordinary cache/relay contract.

Municipality codes come from the shipped 2024 geography, never name matching. Queries
contain one year only. The transport selection contains identifiable two-endpoint ferry
routes and named domestic Danish airports; country totals and multi-stop routes are excluded.
"""
from __future__ import annotations

import csv
import io
import json
import math
from collections import Counter

from ..core import jsonstat
from ..core.paths import WEB_DATA
from ..core.source import File, Source, SourceInfo
from .stats import _q

YEAR = "2024"
MIN_COMMUTERS = 25
AIRPORTS = {"10015": "EKCH", "10020": "EKBI", "10025": "EKAH", "10030": "EKYT",
            "10035": "EKKA", "10040": "EKEB", "10045": "EKRN", "10050": "EKSB",
            "10055": "EKRK", "10060": "EKTS"}
# (existing port IDs, explicitly identified municipalities). The original port layer
# places Oslo in a neighbouring hex municipality; do not inherit that coarse association.
FERRIES = {
    "10240": ("DK_0DKHLS", "SE_1SEHEL", "DK-217", "SE-1283"),
    "10245": ("DK_0DKRNN", "SE_1SEYST", "DK-400", "SE-1286"),
    "10255": ("DK_0DKFDH", "SE_2SEGOT", "DK-813", "SE-1480"),
    "10270": ("DK_0DKCPH", "NO_0NOOSL", "DK-101", "NO-0301"),
    "10275": ("DK_0DKFDH", "NO_0NOOSL", "DK-813", "NO-0301"),
}
SOURCES = {
    "ssb-03321": {"publisher": "Statistics Norway", "table": "03321", "url": "https://www.ssb.no/en/statbank/table/03321/",
        "license": "NLOD 2.0 / CC BY 4.0", "period": "2024 Q4", "unit": "people", "country": "NO",
        "meaning": "Employed people aged 15–74, from registered home municipality to workplace municipality. This does not measure daily journeys or travel frequency."},
    "scb-TAB1830": {"publisher": "Statistics Sweden", "table": "TAB1830", "url": "https://www.statistikdatabasen.scb.se/pxweb/en/ssd/START__AM__AM0210__AM0210F/ArRegPend2/",
        "license": "CC0 1.0", "period": "2024 annual register", "unit": "people", "country": "SE",
        "meaning": "Employed people aged 15–74, from registered home municipality to workplace municipality. Disclosure protection means components may not sum to published totals. Missing workplaces are assigned to the home municipality."},
    "dst-PEND100": {"publisher": "Statistics Denmark", "table": "PEND100", "url": "https://www.statbank.dk/PEND100",
        "license": "CC BY 4.0", "period": "2024 end November", "unit": "people", "country": "DK",
        "meaning": "Employed people from home municipality to workplace municipality, men and women combined by the publisher. This measures registered employment relationships, not daily trips. The source uses 0 for suppressed observations."},
    "dst-SKIB32": {"publisher": "Statistics Denmark / Danish ferry operators", "table": "SKIB32", "url": "https://www.statbank.dk/SKIB32",
        "license": "CC BY 4.0", "period": "2024", "country": "DK",
        "meaning": "Annual passenger movements or freight tonnes on selected international ferry routes, both directions combined. Published in thousands; converted to people or tonnes. These are route totals, not unique travellers or individual consignments."},
    "dst-FLYV33": {"publisher": "Statistics Denmark / Danish Transport Authority", "table": "FLYV33", "url": "https://www.statbank.dk/FLYV33",
        "license": "CC BY 4.0", "period": "2024", "unit": "passenger movements", "country": "DK",
        "meaning": "Annual passenger journeys on the same flight number from embarking to disembarking Danish airport. Published in thousands and converted to passenger movements. Greenland, Faroe Islands and unnamed other airports are excluded; these are not unique travellers."},
}


def cities():
    return json.loads((WEB_DATA / "cities.json").read_text(encoding="utf-8"))


def finite_observation(value):
    """None and suppression markers stay missing; invalid numerics are rejected."""
    if value is None or str(value).strip() in ("", "..", ":", "-", "..."):
        return None
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"Invalid non-negative connection observation: {value!r}")
    return int(number) if number.is_integer() else number


def make_flow(source, origin, destination, value, category="commuting", *, directed=True,
              unit="people", status=None, label=None, classification="municipality"):
    value = finite_observation(value)
    if value is None:
        return None
    return {"id": f"{source}:{origin}:{destination}:{category}", "source": source,
            "origin": origin, "destination": destination, "value": value,
            "category": category, "unit": unit, "period": SOURCES[source]["period"],
            "directed": directed, "status": status or "published", "classification": classification,
            **({"label": label} if label else {})}


class Connections(Source):
    info = SourceInfo(id="connections", title="Commuting and passenger/freight connections, 2024",
        publisher="Statistics Norway; Statistics Sweden; Statistics Denmark",
        homepage="https://www.ssb.no/en/statbank/table/03321/",
        license="SSB: NLOD 2.0 / CC BY 4.0; SCB: CC0; DST: CC BY 4.0",
        description="Municipal commuting (SSB 03321, SCB TAB1830, DST PEND100), selected international ferry routes "
                    "(DST SKIB32), domestic Danish airport-to-airport passenger journeys (DST FLYV33). One year, 2024.",
        used_for=["Connections exploration", "municipality and regional connections", "connected discoveries"])

    def files(self):
        codes = {country: sorted(c["id"].split("-", 1)[1] for c in cities() if c["country"] == country)
                 for country in ("NO", "SE", "DK")}
        def px(name, base, table, dims):
            return [File(name+"_meta.json", f"{base}/{table}/metadata?lang=en"),
                    File(name+".json", f"{base}/{table}/data?lang=en&outputFormat=json-stat2&" + _q(dims))]
        def dst(table, dims):
            return [File(table+"_meta.json", f"https://api.statbank.dk/v1/tableinfo/{table}?lang=en&format=JSON"),
                    File(table+".csv", f"https://api.statbank.dk/v1/data/{table}/CSV?lang=en&delimiter=Semicolon&valuePresentation=Code&"+_q(dims))]
        return (px("ssb", "https://data.ssb.no/api/pxwebapi/v2/tables", "03321",
                   {"valueCodes[ArbstedKomm]": ",".join(codes["NO"]), "valueCodes[Bokommuen]": ",".join(codes["NO"]),
                    "valueCodes[ContentsCode]": "Sysselsatte", "valueCodes[Tid]": YEAR})
                + px("scb", "https://statistikdatabasen.scb.se/api/v2/tables", "TAB1830",
                   {"valueCodes[Kon]": "1+2", "valueCodes[Bostadskommun]": "*", "valueCodes[Arbetsstallekommun]": "*",
                    "valueCodes[ContentsCode]": "000000QT", "valueCodes[Tid]": YEAR})
                + dst("PEND100", {"BOPKOM": ",".join(codes["DK"]), "ARBEJDSSTED": ",".join(codes["DK"]), "Tid": YEAR})
                + dst("SKIB32", {"FÆRGE": ",".join(FERRIES), "ENHED": "8005,8065", "Tid": YEAR})
                + dst("FLYV33", {"PÅSTIG1": ",".join("F"+k for k in AIRPORTS),
                                 "AFSTIG1": ",".join("T"+k for k in AIRPORTS), "Tid": YEAR}))

    def process(self):
        allowed = {c["id"] for c in cities()}
        flows, observed, counts = [], [], Counter()
        sources = json.loads(json.dumps(SOURCES))
        seen = set()
        def add(f):
            if f is None:
                counts["missing"] += 1
                return
            if f["id"] in seen:
                raise ValueError(f"Duplicate connection {f['id']}")
            seen.add(f["id"])
            counts[f["source"]+":cells"] += 1
            if f["value"] == 0:
                counts[f["source"]+":zero_or_suppressed"] += 1
                return
            if f["origin"] == f["destination"]:
                counts[f["source"]+":within_place"] += 1
                return
            if f["category"] == "commuting" and f["value"] < MIN_COMMUTERS:
                counts[f["source"]+":below_display_threshold"] += 1
                return
            flows.append(f)
        for name, source, country, origin, dest in [
            ("ssb", "ssb-03321", "NO", "Bokommuen", "ArbstedKomm"),
            ("scb", "scb-TAB1830", "SE", "Bostadskommun", "Arbetsstallekommun")]:
            js = jsonstat.load(self.path(name+".json"))
            meta = jsonstat.load(self.path(name+"_meta.json"))
            sources[source].update(updated=js.get("updated"), notes=meta.get("note", []))
            for d, value, status in jsonstat.records(js):
                if d["Tid"] != YEAR:
                    raise ValueError("Unexpected source period")
                a, b = country+"-"+d[origin], country+"-"+d[dest]
                if a not in allowed or b not in allowed:
                    raise ValueError(f"Unmatched municipality {a} / {b}")
                add(make_flow(source, a, b, value, status=status))
        def rows(name):
            return csv.DictReader(io.StringIO(self.path(name+".csv").read_text(encoding="utf-8-sig")), delimiter=";")
        for table in ("PEND100", "SKIB32", "FLYV33"):
            meta = jsonstat.load(self.path(table+"_meta.json"))
            sources["dst-"+table].update(updated=meta["updated"], notes=[meta["footnote"]["text"]] if meta.get("footnote") else [],
                                        suppressedDataValue=meta.get("suppressedDataValue"))
        for d in rows("PEND100"):
            if d["TID"] != YEAR:
                raise ValueError("Unexpected source period")
            a, b = "DK-"+d["BOPKOM"], "DK-"+d["ARBEJDSSTED"]
            if a not in allowed or b not in allowed:
                raise ValueError("Unmatched Danish municipality")
            add(make_flow("dst-PEND100", a, b, d["INDHOLD"]))
        ferry_meta = jsonstat.load(self.path("SKIB32_meta.json"))
        labels = {v["id"]: v["text"] for v in next(v for v in ferry_meta["variables"] if v["id"] == "FÆRGE")["values"]}
        for d in rows("SKIB32"):
            if d["TID"] != YEAR or d["FÆRGE"] not in FERRIES or d["ENHED"] not in ("8005", "8065"):
                raise ValueError("Unexpected ferry selection")
            a,b,_,_ = FERRIES[d["FÆRGE"]]
            v=finite_observation(d["INDHOLD"])
            add(make_flow("dst-SKIB32", "port:"+a, "port:"+b, None if v is None else v*1000,
                          "ferry" if d["ENHED"] == "8005" else "freight", directed=False,
                          unit="passenger movements" if d["ENHED"] == "8005" else "tonnes",
                          label=labels[d["FÆRGE"]], classification="published ferry route"))
        for d in rows("FLYV33"):
            if d["TID"] != YEAR:
                raise ValueError("Unexpected aviation period")
            a,b = AIRPORTS[d["PÅSTIG1"][1:]], AIRPORTS[d["AFSTIG1"][1:]]
            v=finite_observation(d["INDHOLD"])
            add(make_flow("dst-FLYV33", "airport:"+a, "airport:"+b, None if v is None else v*1000,
                          "aviation", unit="passenger movements", classification="airport"))
        flows.sort(key=lambda f: f["id"])
        return {"schema":1, "sources":sources, "flows":flows, "audit":dict(counts),
                "coverage":{"commuting":"Norway, Sweden and Denmark: domestic municipal pairs with at least 25 published employed people in 2024. Within-municipality employment is not drawn. Unknown workplaces and overseas employment are outside this selection.",
                            "ferry":"Five selected Denmark–Sweden/Norway ferry routes, both directions combined, 2024.",
                            "freight":"Freight on the same five selected international ferry routes; not all maritime freight.",
                            "aviation":"Named Danish domestic airport pairs, 2024. No international aviation coverage.",
                            "cross_border":"Cross-border commuting is not included. Regional Øresund statistics use a different geographical definition.",
                            "rail":"Railway geometry is retained as infrastructure; no observed rail origin–destination data is included."},
                "minimum_commuters":MIN_COMMUTERS}
