"""2024 Swedish and Danish domestic commuting, kept separate from the SSB packet."""
from __future__ import annotations
import csv
import io
import json
from collections import Counter
from ..core import fetch, jsonstat
from ..core.paths import WEB_DATA
from ..core.source import File, Source, SourceInfo
from .commuting import YEAR, MIN_COMMUTERS, observation
from .stats import SCB, DST, _q

SCB_TABLE = SCB + "/TAB1830"
DST_TABLE = "https://api.statbank.dk/v1/tableinfo/PEND100?lang=en&format=JSON"

def municipality_codes(country):
    cities = json.loads((WEB_DATA / "cities.json").read_text(encoding="utf-8"))
    codes = sorted(c["id"][3:] for c in cities if c["country"] == country)
    count, length = {"SE": (290, 4), "DK": (98, 3)}[country]
    if len(codes) != count or len(set(codes)) != count or any(not c.isdigit() or len(c) != length for c in codes):
        raise ValueError(f"Unexpected {country} municipality geography")
    return codes

def classify(country, pairs):
    flows, audit = [], Counter()
    for (origin, destination), value in pairs.items():
        if value is None:
            audit["missing"] += 1
        elif origin == destination:
            audit["within_municipality"] += 1
        elif value < MIN_COMMUTERS:
            audit["below_threshold"] += 1
        else:
            audit["published"] += 1
            flows.append([country + "-" + origin, country + "-" + destination, value])
    return sorted(flows), dict(audit)

def parse_scb(packet, origins, destinations):
    expected = {"Bostadskommun", "Arbetsstallekommun", "Kon", "ContentsCode", "Tid"}
    if set(packet["id"]) != expected:
        raise ValueError("Unexpected SCB commuting dimensions")
    pairs = {}
    for d, value, status in jsonstat.records(packet):
        a, b = d["Bostadskommun"], d["Arbetsstallekommun"]
        if a not in origins or b not in destinations or (a,b) in pairs or d["Tid"] != YEAR or d["Kon"] != "1+2" or d["ContentsCode"] != "000000QT":
            raise ValueError(f"Unexpected SCB cell: {d}")
        pairs[a,b] = observation(value)
    if len(pairs) != len(origins) * len(destinations):
        raise ValueError("Incomplete SCB commuting matrix")
    return pairs

def parse_dst(text, origins, destinations):
    by_pair = {}
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    if not {"BOPKOM","ARBEJDSSTED","KØN","TID","INDHOLD"}.issubset(reader.fieldnames or []):
        raise ValueError(f"Unexpected DST CSV columns: {reader.fieldnames}")
    for row in reader:
        a,b,sex = row["BOPKOM"],row["ARBEJDSSTED"],row["KØN"]
        if a not in origins or b not in destinations or sex not in ("M","K") or row["TID"] != YEAR:
            raise ValueError(f"Unexpected DST cell: {row}")
        p = by_pair.setdefault((a,b), {})
        if sex in p:
            raise ValueError("Duplicate DST cell")
        v = observation(row["INDHOLD"])
        # PEND100 metadata defines 0 as its suppressed data value.
        # A zero could also be a genuine zero; omit that pair rather than claim an exact total.
        p[sex] = v if v and v > 0 else None
    if len(by_pair) != len(origins)*len(destinations) or any(set(p) != {"M","K"} for p in by_pair.values()):
        raise ValueError("Incomplete DST commuting matrix")
    return {pair: None if None in p.values() else p["M"]+p["K"] for pair,p in by_pair.items()}

class NordicCommuting(Source):
    def __init__(self,country):
        self.country = country
        self.info = {
            "SE": SourceInfo(id="commuting_se",title="Swedish municipality commuting, 2024",
                publisher="Statistics Sweden (SCB)",homepage="https://www.statistikdatabasen.scb.se/",
                license="CC0 1.0",country="SE",
                description="Annual register, employed people aged 15–74 by municipality of residence and workplace. Published totals for both sexes; statistical disclosure protection applies.",
                used_for=["Municipality commuting partners"]),
            "DK": SourceInfo(id="commuting_dk",title="Danish municipality commuting, 2024",
                publisher="Statistics Denmark (DST)",homepage="https://www.statbank.dk/PEND100",
                license="CC BY 4.0",country="DK",
                description="Employed people at end November by municipality of residence and workplace. Both sex counts must be published and nonzero; zero is also the suppression value, so pairs with a zero are omitted.",
                used_for=["Municipality commuting partners"]),
        }[country]

    def batches(self):
        codes = municipality_codes(self.country)
        for start in range(0,len(codes),30):
            origins = codes[start:start+30]
            for end in range(0,len(codes),100):
                destinations = codes[end:end+100]
                if self.country == "SE":
                    params = {"valueCodes[Bostadskommun]":",".join(origins),
                        "valueCodes[Arbetsstallekommun]":",".join(destinations),
                        "valueCodes[Kon]":"1+2","valueCodes[ContentsCode]":"000000QT","valueCodes[Tid]":YEAR}
                    path = f"scb-{start:03}-{end:03}.json"
                    url = SCB_TABLE+"/data?lang=en&outputFormat=json-stat2&"+_q(params)
                else:
                    params = {"BOPKOM":",".join(origins),"ARBEJDSSTED":",".join(destinations),"KØN":"M,K","Tid":YEAR}
                    path = f"dst-{start:03}-{end:03}.csv"
                    url = DST+"/PEND100/CSV?lang=en&delimiter=Semicolon&valuePresentation=Code&"+_q(params)
                yield File(path,url),set(origins),set(destinations)

    def files(self):
        meta = SCB_TABLE+"/metadata?lang=en" if self.country=="SE" else DST_TABLE
        return [File("metadata.json",meta)]+[f for f,_,_ in self.batches()]

    def fetch(self,force=False):
        for f in self.files():
            fetch.download(self.id,f.url,f.rel_path,force=force,relay=False)
            print(f"Acquired {self.id}/{f.rel_path}",flush=True)
        return []

    def process(self):
        for f in self.files():
            ok,why = fetch.verify(self.id,f.rel_path,url=f.url,method=f.method,body=f.body)
            if not ok:
                raise ValueError(f"{self.id}/{f.rel_path}: {why}")
        meta = jsonstat.load(self.path("metadata.json"))
        codes = set(municipality_codes(self.country))
        if self.country == "SE":
            for dim in ("Bostadskommun","Arbetsstallekommun"):
                if not codes.issubset(meta["dimension"][dim]["category"]["index"]):
                    raise ValueError(f"SCB municipality codes changed: {dim}")
        else:
            variables = {v["id"]:{x["id"] for x in v["values"]} for v in meta["variables"]}
            if meta.get("suppressedDataValue") != "0" or any(not codes.issubset(variables[d]) for d in ("BOPKOM","ARBEJDSSTED")) or variables["KØN"] != {"M","K"}:
                raise ValueError("DST geography or suppression contract changed")
        pairs, updated = {}, set()
        for f,origins,destinations in self.batches():
            if self.country=="SE":
                packet=jsonstat.load(self.path(f.rel_path))
                part=parse_scb(packet,origins,destinations)
                if packet.get("updated"):
                    updated.add(packet["updated"])
            else:
                part=parse_dst(self.path(f.rel_path).read_text(encoding="utf-8-sig"),origins,destinations)
            if pairs.keys() & part.keys():
                raise ValueError("Duplicate pair across batches")
            pairs.update(part)
        if len(updated)>1 or len(pairs)!=len(codes)**2:
            raise ValueError("Source changed or matrix incomplete")
        flows,audit=classify(self.country,pairs)
        if not flows:
            raise ValueError("No qualifying commuting pairs")
        manifest=fetch.read_manifest(self.id)["files"]
        return {"schema":1,"country":self.country,"period":"2024 annual register" if self.country=="SE" else "2024 end November",
                "unit":"employed people","minimum":MIN_COMMUTERS,"municipality_count":len(codes),
                "source":{"table":"TAB1830" if self.country=="SE" else "PEND100","url":self.info.homepage,
                          "publisher":self.info.publisher,"license":self.info.license,"updated":next(iter(updated),meta.get("updated")),
                          "note":self.info.description,
                          "files":[{"file":f.rel_path,"sha256":manifest[f.rel_path]["sha256"],"url":f.url,"retrieved":manifest[f.rel_path]["retrieved"]} for f in self.files()]},
                "audit":audit,"flows":flows}
