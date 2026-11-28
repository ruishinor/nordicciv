"""NVE selected flood and glacier polygons from the official ArcGIS REST services."""
from __future__ import annotations
import json
from urllib.parse import urlencode
from ..core.source import Source, SourceInfo, File
from ..core import fetch

ROOT_URL = "https://kart.nve.no/enterprise/rest/services/"
# Historical product code is documented in the service renderer; the newer inventory is 2018–2019.
# Flood: only published current/updated 200-year inundation polygons, not low points or permanent water.
GROUPS = {
    "flood200": ("Flomsoner2/MapServer/17", "Flomsone_200arsflom",
                 "gjentaksinterval=200 AND statuskartlegging IN (1,5) AND symbolflom=1",
                 "objectid,flomsoneid,gjentaksinterval,statuskartlegging,symbolflom"),

}
BATCH = 80


def request(group, query=None):
    base = ROOT_URL + GROUPS[group][0]
    return base + ("/query?" + urlencode(query) if query is not None else "?f=json")


class NveEnvironment(Source):
    info = SourceInfo(id="nve_environment", title="NVE flood zones",
        publisher="Norwegian Water Resources and Energy Directorate (NVE)",
        homepage="https://www.nve.no/kart/",
        license="NLOD 1.0 (Norwegian Licence for Open Government Data)",
        description="Published current and updated flood polygons for the 200-year modelled event.",
        used_for=["optional flood extent layer"], country="NO")

    def initial(self, group):
        return [File(f"{group}/metadata.json", request(group)),
                File(f"{group}/ids.json", request(group, {"where": GROUPS[group][2], "returnIdsOnly": "true", "f": "json"}))]

    def ids(self, group):
        payload = json.loads(self.path(f"{group}/ids.json").read_text(encoding="utf-8"))
        ids = payload.get("objectIds")
        if not ids or any(type(i) is not int for i in ids) or len(ids) != len(set(ids)):
            raise ValueError(f"{group}: empty or invalid object ID response: {str(payload)[:300]}")
        return sorted(ids)

    def pages(self, group):
        ids = self.ids(group)
        for start in range(0,len(ids),BATCH):
            chunk = ids[start:start+BATCH]
            yield File(f"{group}/features-{start:05}.geojson", request(group, {
                "objectIds": ",".join(map(str,chunk)), "where": GROUPS[group][2],
                "outFields": GROUPS[group][3], "returnGeometry": "true", "outSR": "4326", "f": "geojson"})), chunk

    def files(self):
        return [f for g in GROUPS for f in self.initial(g)+[f for f,_ in self.pages(g)]]

    def fetch(self, force=False):
        for group in GROUPS:
            for f in self.initial(group):
                fetch.download(self.id,f.url,f.rel_path,force=force,relay=False)
            print(f"{group}: {len(self.ids(group))} objects", flush=True)
            for f,_ in self.pages(group):
                fetch.download(self.id,f.url,f.rel_path,force=force,relay=False)
        return []

    def process(self):
        for f in self.files():
            ok, why = fetch.verify(self.id,f.rel_path,url=f.url,method=f.method,body=f.body)
            if not ok:
                raise ValueError(f"{self.id}/{f.rel_path}: {why}")
        results = {}
        for group, (_,name,_,fields) in GROUPS.items():
            meta = json.loads(self.path(f"{group}/metadata.json").read_text(encoding="utf-8"))
            if meta.get("name") != name or meta.get("geometryType") != "esriGeometryPolygon" or not set(fields.split(",")) <= {x["name"].lower() for x in meta.get("fields",[])}:
                raise ValueError(f"{group}: unexpected source schema")
            features = []
            for f, expected in self.pages(group):
                packet = json.loads(self.path(f.rel_path).read_text(encoding="utf-8"))
                if packet.get("type") != "FeatureCollection" or packet.get("exceededTransferLimit"):
                    raise ValueError(f"{group}: incomplete GeoJSON response")
                rows = []
                for row in packet.get("features",[]):
                    props = {k.lower():v for k,v in row["properties"].items()}
                    if group == "flood200" and (props.get("gjentaksinterval") != 200 or props.get("statuskartlegging") not in (1,5) or props.get("symbolflom") != 1):
                        raise ValueError("Unexpected flood classification")
                    if row.get("geometry",{}).get("type") not in ("Polygon","MultiPolygon"):
                        raise ValueError(f"{group}: unexpected geometry")
                    rows.append({"properties":props,"geometry":row["geometry"]})
                if sorted(r["properties"]["objectid"] for r in rows) != expected:
                    raise ValueError(f"{group}: returned IDs do not equal requested IDs")
                features.extend(rows)
            results[group] = features
        return results
