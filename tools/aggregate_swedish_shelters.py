"""Aggregate the official Swedish civil-defence shelter register by spatial intersection with the existing municipal boundaries.
Do not publish individual shelter coordinates, identifiers, addresses or technical fields.
The full download is used only for the aggregate; fail if the schema or coverage is ambiguous.
"""
import hashlib
import io
import json
import re
import unicodedata
import urllib.request
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import shapefile
from pyproj import CRS, Transformer
from shapely.geometry import Point, shape
from shapely.ops import transform, unary_union
from shapely import STRtree

ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/"web/js/ext/shelters/overview-data.js"
URLS=["https://inspire.mcf.se/nedladdning/filer/shape/Skyddsrum.zip",
      "https://inspire.msb.se/nedladdning/filer/shape/Skyddsrum.zip"]
PREFIX="export const OVERVIEW = "


def normal(s):
    return re.sub(r"[^a-z0-9]","",unicodedata.normalize("NFKD",str(s)).encode("ascii","ignore").decode().lower())


def select(fields, names, purpose):
    matches=[f for f in fields if normal(f) in names]
    if len(matches)!=1:
        raise ValueError(f"Cannot identify {purpose} unambiguously: {fields}")
    return matches[0]


def main():
    errors=[]
    for url in URLS:
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"NordicCiv aggregate shelter statistics"}),timeout=90) as response:
                raw=response.read(100_000_001)
            if len(raw)>100_000_000: raise ValueError("Archive exceeds size budget")
            z=zipfile.ZipFile(io.BytesIO(raw))
            break
        except Exception as e:
            errors.append(f"{url}: {e}")
    else:
        raise RuntimeError("; ".join(errors))
    dbfs=[n for n in z.namelist() if n.lower().endswith(".dbf") and not n.startswith("__MACOSX")]
    if len(dbfs)!=1: raise ValueError(f"Expected one shelter attribute table: {dbfs}")
    name=dbfs[0]
    encoding="cp1252"
    cpg=next((n for n in z.namelist() if n.lower()==name[:-4].lower()+".cpg"),None)
    if cpg:
        code=z.read(cpg).decode("ascii").strip()
        encoding={"65001":"utf-8","1252":"cp1252"}.get(code,code)
    members={n.lower():n for n in z.namelist()}
    stem=name[:-4].lower()
    reader=shapefile.Reader(shp=io.BytesIO(z.read(members[stem+".shp"])),dbf=io.BytesIO(z.read(name)),encoding=encoding)
    crs=CRS.from_wkt(z.read(members[stem+".prj"]).decode("utf-8"))
    fields=[f[0] for f in reader.fields[1:]]
    print(f"Register fields: {fields}; rows: {len(reader)}; CRS: {crs.to_string()}",flush=True)
    if not {"InspireID","numberOfOc"} <= set(fields):
        raise ValueError("Unexpected INSPIRE schema")
    cities=json.loads((ROOT/"web/data/cities.json").read_text(encoding="utf-8"))
    ids={c["id"] for c in cities if c["country"]=="SE"}
    if len(ids)!=290: raise ValueError("Unexpected Swedish geography")
    sources=json.loads((ROOT/"web/data/sources.json").read_text(encoding="utf-8"))
    boundary=next(f for s in sources if s["id"]=="boundaries" for f in s["files"] if f["file"]=="se_kommuner.geojson")
    with urllib.request.urlopen(boundary["url"],timeout=60) as response:
        boundary_bytes=response.read()
    if hashlib.sha256(boundary_bytes).hexdigest()!=boundary["sha256"]:
        raise ValueError("Boundary snapshot differs from the published map")
    to_metric=Transformer.from_crs("EPSG:4326","EPSG:3006",always_xy=True).transform
    shelter_to_metric=Transformer.from_crs(crs,"EPSG:3006",always_xy=True).transform
    by_id=defaultdict(list)
    for feature in json.loads(boundary_bytes)["features"]:
        key="SE-"+str(feature["properties"]["id"]).zfill(4)
        by_id[key].append(transform(to_metric,shape(feature["geometry"]).buffer(0)))
    if set(by_id)!=ids: raise ValueError("Municipality boundaries do not match map IDs")
    keys=sorted(by_id)
    polys=[unary_union(by_id[k]) for k in keys]
    tree=STRtree(polys)
    counts={i:[0,0,0] for i in keys}
    seen=set()
    unassigned=[0,0,0]
    nearest=0
    ambiguous=0
    for item in reader.iterShapeRecords():
        row=item.record.as_dict()
        key=str(row["InspireID"]).strip()
        if not key or key in seen: raise ValueError("Missing or duplicate INSPIRE identifier")
        seen.add(key)
        if len(item.shape.points)!=1: raise ValueError("Unexpected shelter point geometry")
        x,y=shelter_to_metric(*item.shape.points[0][:2])
        pt=Point(x,y)
        hits=tree.query(pt,predicate="intersects")
        if len(hits)==1:
            target=counts[keys[int(hits[0])]]
        elif len(hits)>1:
            ambiguous+=1
            target=unassigned
        else:
            j=int(tree.nearest(pt))
            if pt.distance(polys[j])<=1500:
                target=counts[keys[j]]
                nearest+=1
            else:
                target=unassigned
        target[0]+=1
        value=row["numberOfOc"]
        if value is None or value=="":
            target[2]+=1
        else:
            n=float(value)
            if not n.is_integer() or n<0: raise ValueError("Invalid capacity")
            target[1]+=int(n)
    totals=[sum(v[i] for v in counts.values())+unassigned[i] for i in range(3)]
    if not 60000<=totals[0]<=70000 or not 6000000<=totals[1]<=8000000:
        raise ValueError(f"Register totals outside published approximate national range: {totals}")
    if unassigned[0]>0.005*totals[0]:
        raise ValueError(f"Too many unassigned records: {unassigned[0]}")
    print(f"Assigned by nearest outline: {nearest}; unassigned: {unassigned}; ambiguous: {ambiguous}",flush=True)
    data=json.loads(TARGET.read_text(encoding="utf-8").removeprefix(PREFIX).strip().removesuffix(";"))
    data["SE"].update(municipalities=counts,totals=totals,register_url=url,sha256=hashlib.sha256(raw).hexdigest(),
                      bytes=len(raw),retrieved=datetime.now(timezone.utc).isoformat(),fields={"capacity":"numberOfOc","identity":"InspireID"},boundary_sha256=boundary["sha256"],
                      boundary_url=boundary["url"],nearest=nearest,unassigned=unassigned,assignment="Point in municipality; nearest outline within 1500 m; ambiguous or distant points excluded from municipal totals",
                      terms="Attribution: Myndigheten för civilt försvar (MCF); derived municipal totals, no individual records",
                      metadata="https://geodirekt.sokigohosting.com/dataset/skyddsrum1-kopia")
    TARGET.write_text(PREFIX+json.dumps(data,ensure_ascii=False,indent=2)+";\n",encoding="utf-8")
    print(f"Sweden: {len(counts)} municipalities; {totals[0]} shelters; {totals[1]} known places; {totals[2]} missing capacities",flush=True)

if __name__=="__main__":
    main()
