"""Aggregate the official Swedish civil-defence shelter register by published municipal code.
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
    reader=shapefile.Reader(dbf=io.BytesIO(z.read(name)),encoding=encoding)
    fields=[f[0] for f in reader.fields[1:]]
    print(f"Register fields: {fields}; rows: {len(reader)}",flush=True)
    code=select(fields,{"kommunkod","kommunkodn","komkod","kommun","kommunkod1","komnr","kommunknr","kommunnr","kommunkod_"},"municipality code")
    cap=select(fields,{"antalplats","antalplatse","antalplatser","antalpl","platser","antalplatsr","skyddsplat","skyddsplatser","kapacitet"},"registered places")
    ident=select(fields,{"skyddsrums","skyddsrumsn","skyddsrumsnr","skyddsrumsnummer","skyddsrumn","skyddsrumnr","skyddsrumsid","skyddsrum","srnr","srnummer","srnum","skyddsrumid","skyddsrumnu","skyddsrum_n","skyddsrum_nr"},"shelter number")
    cities=json.loads((ROOT/"web/data/cities.json").read_text(encoding="utf-8"))
    ids={c["id"] for c in cities if c["country"]=="SE"}
    if len(ids)!=290: raise ValueError("Unexpected Swedish geography")
    counts={i:[0,0,0] for i in sorted(ids)}
    seen=set()
    for record in reader.iterRecords():
        row=record.as_dict()
        key=str(row[ident]).strip()
        if not key or key in seen: raise ValueError("Missing or duplicate shelter identifier")
        seen.add(key)
        k=str(row[code]).strip()
        if not k.isdigit(): raise ValueError(f"Unexpected municipality code format in {code}")
        k="SE-"+k.zfill(4)
        if k not in ids: raise ValueError(f"Unknown municipality {k}")
        value=row[cap]
        counts[k][0]+=1
        if value is None or value=="":
            counts[k][2]+=1
        else:
            n=float(value)
            if not n.is_integer() or n<0: raise ValueError("Invalid capacity")
            counts[k][1]+=int(n)
    totals=[sum(v[i] for v in counts.values()) for i in range(3)]
    if not 60000<=totals[0]<=70000 or not 6000000<=totals[1]<=8000000:
        raise ValueError(f"Register totals outside published approximate national range: {totals}")
    data=json.loads(TARGET.read_text(encoding="utf-8").removeprefix(PREFIX).strip().removesuffix(";"))
    data["SE"].update(municipalities=counts,totals=totals,register_url=url,sha256=hashlib.sha256(raw).hexdigest(),
                      bytes=len(raw),retrieved=datetime.now(timezone.utc).isoformat(),fields={"municipality":code,"capacity":cap,"identity":ident},
                      terms="Attribution: Myndigheten för civilt försvar (MCF); derived municipal totals, no individual records",
                      metadata="https://geodirekt.sokigohosting.com/dataset/skyddsrum1-kopia")
    TARGET.write_text(PREFIX+json.dumps(data,ensure_ascii=False,indent=2)+";\n",encoding="utf-8")
    print(f"Sweden: {len(counts)} municipalities; {totals[0]} shelters; {totals[1]} known places; {totals[2]} missing capacities",flush=True)

if __name__=="__main__":
    main()
