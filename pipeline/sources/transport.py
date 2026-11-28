"""Bounded published Danish aviation and ferry movements; never port/airport throughput."""
import csv
import io
import itertools
import json
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from ..core import fetch
from ..core.paths import WEB_DATA
from ..core.source import Source, SourceInfo, File

YEAR = "2024"
BASE = "https://api.statbank.dk/v1/"
AIRPORTS = dict(zip(["10015", "10020", "10025", "10030", "10035", "10040", "10045", "10050", "10055", "10060"],
                    ["EKCH", "EKBI", "EKAH", "EKYT", "EKKA", "EKEB", "EKRN", "EKSB", "EKRK", "EKTS"]))
# Reuse the mapped ports; the Læsø endpoint is explicitly a municipality centre.
FERRIES = {
    "SKIB32": {"10240": ("port:DK_0DKHLS", "port:SE_1SEHEL"), "10245": ("port:DK_0DKRNN", "port:SE_1SEYST"),
               "10255": ("port:DK_0DKFDH", "port:SE_2SEGOT"), "10270": ("port:DK_0DKCPH", "port:NO_0NOOSL"),
               "10275": ("port:DK_0DKFDH", "port:NO_0NOOSL")},
    "SKIB31": {"10028": ("port:DK_0DKKOG", "port:DK_0DKRNN"), "10170": ("port:DK_0DKFDH", "municipality:DK-825"),
               "10205": ("port:DK_0DKEBJ", "port:DK_0DKNDB")},
}
SELECTIONS = {
    "FLYV33": {"PÅSTIG1": ["F"+k for k in AIRPORTS], "AFSTIG1": ["T"+k for k in AIRPORTS], "Tid": [YEAR]},
    "FLYV34": {"LUFTHAVN": ["10015", "10020"], "DESTI": ["NO", "SE"], "RET": ["0003", "0005"], "Tid": [YEAR]},
    **{table: {"FÆRGE": list(routes), "ENHED": ["8005", "8065"], "Tid": [YEAR]} for table, routes in FERRIES.items()},
}
NOTES = {
    "FLYV33": "Passenger movements between ten named Danish airports on the same flight number, including any intermediate landing. Greenland, the Faroe Islands and unnamed airports are excluded.",
    "FLYV34": "Passenger movements between Copenhagen or Billund airport and all airports in Norway or Sweden. The foreign endpoint is a country, not a named airport; these observations are listed without map lines.",
    "SKIB31": "Three selected domestic ferry routes. Annual passenger movements and freight tonnes, both directions combined.",
    "SKIB32": "Five selected international ferry routes. Annual passenger movements and freight tonnes, both directions combined.",
}


def read_cells(text, selection):
    """Require exactly the requested matrix; preserve ambiguous zeros and missing cells."""
    dims = [d.upper() for d in selection]
    expected = set(itertools.product(*selection.values()))
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")), delimiter=";")
    if len(reader.fieldnames or []) != len(dims) + 1 or set(reader.fieldnames or []) != set(dims + ["INDHOLD"]):
        raise ValueError("Transport CSV dimensions changed")
    result = {}
    for row in reader:
        if None in row or any(v is None for v in row.values()):
            raise ValueError("Malformed transport CSV row")
        key = tuple(row[d] for d in dims)
        if key not in expected or key in result:
            raise ValueError("Unexpected or duplicate transport cell")
        raw = row["INDHOLD"].strip()
        if raw in ("", "..", "...", ":", "-"):
            result[key] = None
            continue
        try:
            value = Decimal(raw) * 1000
        except InvalidOperation as error:
            raise ValueError("Invalid transport count") from error
        if not value.is_finite() or value < 0 or value != value.to_integral_value():
            raise ValueError("Invalid transport count")
        result[key] = int(value) if value else None  # DST also uses 0 for suppression.
    if set(result) != expected:
        raise ValueError("Incomplete transport matrix")
    return result


class Transport(Source):
    info = SourceInfo(id="transport", title="Danish aviation and selected ferry connections, 2024",
        publisher="Statistics Denmark", homepage="https://www.statbank.dk/FLYV33", license="CC BY 4.0", country="DK",
        description="FLYV33, FLYV34, SKIB31 and SKIB32. Passenger movements and freight tonnes remain separate. Rounded thousands converted to movements or tonnes; zero or suppressed cells are omitted.",
        used_for=["Transport connections", "Discover journeys"])

    def files(self):
        out = []
        for table, selection in SELECTIONS.items():
            out += [File(table+"_meta.json", BASE+"tableinfo/"+table+"?lang=en&format=JSON"),
                    File(table+".csv", BASE+"data/"+table+"/CSV?lang=en&delimiter=Semicolon&valuePresentation=Code&"+
                         urlencode({k: ",".join(v) for k, v in selection.items()}))]
        return out

    def process(self):
        for f in self.files():
            valid, why = fetch.verify(self.id, f.rel_path, url=f.url)
            if not valid:
                raise ValueError(f"{f.rel_path}: {why}")
        infra = json.loads((WEB_DATA/"infrastructure.json").read_text(encoding="utf-8"))
        cities = {c["id"]: c for c in json.loads((WEB_DATA/"cities.json").read_text(encoding="utf-8"))}
        nodes = {}
        # Correct coarse hex associations for named endpoints without changing the infrastructure layer.
        municipalities = {"EKCH": "DK-185", "EKBI": "DK-530", "NO_0NOOSL": "NO-0301", "DK_0DKNDB": "DK-563"}
        for kind, records in (("airport", infra["airports"]), ("port", infra["ports"])):
            for n in records:
                nodes[kind+":"+n["id"]] = {"name": n["name"], "kind": kind, "city": municipalities.get(n["id"], n.get("cbsa")),
                    "x": n["x"], "y": n["y"], "country": n["country"]}
        # The existing Nordby port position is inconsistent with Fanø. Keep the named
        # endpoint and municipality link, but do not draw a line from an unverified position.
        nodes["port:DK_0DKNDB"] = {"name": "Fanø (port position unavailable)", "kind": "port",
            "city": "DK-563", "country": "DK"}
        c = cities["DK-825"]
        nodes["municipality:DK-825"] = {"name": "Læsø (municipality centre)", "kind": "municipality", "city": c["id"], "x": c["x"], "y": c["y"], "country": "DK"}
        for code, name in (("NO", "Norway"), ("SE", "Sweden")):
            nodes["country:"+code] = {"name": name+" (all airports)", "kind": "country", "country": code}
        flows, tables, audit = [], {}, {}
        for table, selection in SELECTIONS.items():
            meta = json.loads(self.path(table+"_meta.json").read_text(encoding="utf-8"))
            variables = {v["id"]: {x["id"]: x["text"] for x in v["values"]} for v in meta["variables"]}
            if meta.get("suppressedDataValue") != "0" or any(not set(v) <= set(variables[k]) for k, v in selection.items()):
                raise ValueError(f"{table}: source codes or suppression contract changed")
            if table in FERRIES and not ("1000" in variables["ENHED"]["8005"] and "1000" in variables["ENHED"]["8065"]):
                raise ValueError("Ferry units changed")
            if table.startswith("FLYV") and not meta["unit"].startswith("1,000"):
                raise ValueError("Aviation units changed")
            tables[table] = {"url": "https://www.statbank.dk/"+table, "note": NOTES[table], "updated": meta["updated"], "unit_scale": 1000}
            cells = read_cells(self.path(table+".csv").read_text(encoding="utf-8-sig"), selection)
            audit[table] = {"requested": len(cells), "unavailable_or_zero": 0, "same_airport": 0, "published": 0}
            for key, value in cells.items():
                if value is None:
                    audit[table]["unavailable_or_zero"] += 1
                    continue
                unit, directed, category = "passenger movements", True, "aviation"
                if table == "FLYV33":
                    a, b = ["airport:"+AIRPORTS[x[1:]] for x in key[:2]]
                    if a == b:
                        audit[table]["same_airport"] += 1
                        continue
                elif table == "FLYV34":
                    a, b = "airport:"+AIRPORTS[key[0]], "country:"+key[1]
                    if key[2] == "0003": a, b = b, a
                else:
                    a, b = FERRIES[table][key[0]]
                    directed = False
                    unit = "passenger movements" if key[1] == "8005" else "tonnes"
                    category = "ferry" if key[1] == "8005" else "freight"
                audit[table]["published"] += 1
                flows.append({"id": table+":"+":".join(key), "origin": a, "destination": b, "value": value,
                              "unit": unit, "directed": directed, "category": category, "table": table})
        used = {n for f in flows for n in (f["origin"], f["destination"])}
        manifest = fetch.read_manifest(self.id)["files"]
        return {"schema": 1, "period": YEAR, "nodes": {k: nodes[k] for k in sorted(used)}, "flows": flows,
                "tables": tables, "audit": audit, "files": [{"file": f.rel_path, "url": f.url, "sha256": manifest[f.rel_path]["sha256"]} for f in self.files()]}
