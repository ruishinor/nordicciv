"""2024 home-to-work municipality observations from SSB table 03321.

The recovered connections draft established the table, period and municipality codes.
This first delivery deliberately excludes international, within-municipality, rail,
ferry and aviation movements. Counts are employed people, not journey counts.
"""
from __future__ import annotations
import json
import math
from collections import Counter
from ..core import fetch, jsonstat
from ..core.paths import WEB_DATA
from ..core.source import File, Source, SourceInfo
from .stats import _q

YEAR = "2024"
MIN_COMMUTERS = 25
BATCH = 50
BASE = "https://data.ssb.no/api/pxwebapi/v2/tables/03321"
SOURCE = "https://www.ssb.no/en/statbank/table/03321/"


def municipality_codes():
    cities = json.loads((WEB_DATA / "cities.json").read_text(encoding="utf-8"))
    codes = sorted(c["id"][3:] for c in cities if c["country"] == "NO")
    if len(codes) != 357 or len(set(codes)) != len(codes) or any(len(c) != 4 or not c.isdigit() for c in codes):
        raise ValueError("Unexpected Norwegian municipality geography")
    return codes


def observation(value):
    if value is None or str(value).strip() in ("", "..", ":", "-", "..."):
        return None
    number = float(value)
    if not math.isfinite(number) or number < 0 or not number.is_integer():
        raise ValueError(f"Invalid employed-person count: {value!r}")
    return int(number)


def parse_batch(packet, origins, destinations):
    if set(packet["id"]) != {"ArbstedKomm", "Bokommuen", "ContentsCode", "Tid"}:
        raise ValueError("Unexpected SSB commuting dimensions")
    seen = set()
    flows, audit = [], Counter()
    for d, value, status in jsonstat.records(packet):
        origin, destination = d["Bokommuen"], d["ArbstedKomm"]
        pair = origin, destination
        if (origin not in origins or destination not in destinations or pair in seen
                or d["Tid"] != YEAR or d["ContentsCode"] != "Sysselsatte"):
            raise ValueError(f"Unexpected SSB commuting cell: {d}")
        seen.add(pair)
        v = observation(value)
        if v is None:
            audit["missing"] += 1
        elif origin == destination:
            audit["within_municipality"] += 1
        elif v < MIN_COMMUTERS:
            audit["below_threshold"] += 1
        else:
            audit["published"] += 1
            flows.append(["NO-"+origin, "NO-"+destination, v])
        if status:
            audit["source_status_cells"] += 1
    if len(seen) != len(origins)*len(destinations):
        raise ValueError("Incomplete SSB commuting matrix")
    return flows, audit


class Commuting(Source):
    info = SourceInfo(id="commuting", title="Norwegian municipality commuting, 2024",
        publisher="Statistics Norway (SSB)", homepage=SOURCE,
        license="NLOD 2.0 / CC BY 4.0", country="NO",
        description="Employed people aged 15–74 by municipality of residence and workplace, fourth quarter 2024. Only domestic intermunicipal pairs with at least 25 published employed people are shown. Not counts of trips, routes or travel modes.",
        used_for=["Municipality commuting partners and schematic map connections"])

    def batches(self):
        codes = municipality_codes()
        for start in range(0,len(codes),BATCH):
            origins = codes[start:start+BATCH]
            dims = {"valueCodes[ArbstedKomm]": ",".join(codes),
                    "valueCodes[Bokommuen]": ",".join(origins),
                    "valueCodes[ContentsCode]": "Sysselsatte",
                    "valueCodes[Tid]": YEAR}
            yield File(f"ssb-{start:03}.json", BASE+"/data?lang=en&outputFormat=json-stat2&"+_q(dims)), origins, codes

    def files(self):
        return [File("metadata.json",BASE+"/metadata?lang=en")]+[f for f,_,_ in self.batches()]

    def fetch(self, force=False):
        import urllib.error
        for f in self.files():
            try:
                fetch.download(self.id,f.url,f.rel_path,force=force,relay=False)
            except urllib.error.HTTPError as err:
                print(f"{f.rel_path}: HTTP {err.code} {err.read().decode('utf-8',errors='replace')[:3000]}",flush=True)
                raise
            if f.rel_path == "metadata.json":
                meta=jsonstat.load(self.path(f.rel_path))
                for dim in ("ArbstedKomm","Bokommuen"):
                    known=set(meta["dimension"][dim]["category"]["index"])
                    missing=set(municipality_codes())-known
                    if missing:
                        raise ValueError(f"Municipality codes unavailable in {dim}: {sorted(missing)}")
            print(f"Acquired {f.rel_path}",flush=True)
        return []

    def process(self):
        for f in self.files():
            ok, why = fetch.verify(self.id, f.rel_path, url=f.url, method=f.method, body=f.body)
            if not ok:
                raise ValueError(f"{f.rel_path}: {why}")
        flows, audit, updated = [], Counter(), set()
        for f, origins, destinations in self.batches():
            packet = jsonstat.load(self.path(f.rel_path))
            part, counts = parse_batch(packet, set(origins), set(destinations))
            flows.extend(part)
            audit.update(counts)
            if packet.get("updated"):
                updated.add(packet["updated"])
        if len(updated)>1:
            raise ValueError("SSB source changed during batched acquisition")
        manifest=fetch.read_manifest(self.id)["files"]
        return {"schema":1, "country":"NO", "period":"2024 Q4", "unit":"employed people",
                "minimum":MIN_COMMUTERS, "municipality_count":len(municipality_codes()),
                "source":{"table":"03321","url":SOURCE,"publisher":self.info.publisher,"license":self.info.license,
                          "updated":next(iter(updated),None),
                          "files":[{"file":f.rel_path,"sha256":manifest[f.rel_path]["sha256"],
                                    "url":f.url,"retrieved":manifest[f.rel_path]["retrieved"]} for f in self.files()]},
                "audit":dict(audit),"flows":sorted(flows)}
