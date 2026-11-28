"""Recover only the files missing in the 2026-11-28 local source check.

Run in an isolated checkout, never over an existing source cache. Report exact
matches separately from fresh upstream snapshots. This is not a rebuild.
"""
from __future__ import annotations
import json
from pathlib import Path
from pipeline.core import fetch
from pipeline.core.paths import RAW, WEB_DATA
from pipeline.sources import registry

MISSING = {
    "natural_earth": None, "boundaries": None, "euronym": None, "ourairports": None, "powerplants": None,
    "ssb": {"07459_pop_county2024.json","klass131_changes_2008_2026.json"},
    "eurostat": None,
    "regional_accounts": {"ssb_11713_gva_industry.json","nama_10r_3gva.json"},
    "wikidata": None, "sodir": None, "sgu": None, "links": None, "dsb_shelters": None,
}


def main():
    if any(RAW.glob("*/manifest.json")):
        raise RuntimeError("Use an isolated checkout with an empty raw cache")
    catalogue = json.loads((WEB_DATA/"sources.json").read_text(encoding="utf-8"))
    published = {(s["id"],f["file"]): f.get("sha256") for s in catalogue for f in s.get("files",[])}
    sources = registry()
    selected = [(sources[sid], f) for sid, names in MISSING.items() for f in sources[sid].files()
                if names is None or f.rel_path in names]
    if len(selected) != 56:
        raise RuntimeError(f"Expected exactly 56 missing declarations; got {len(selected)}")
    fetch.TIMEOUT=25
    fetch.RETRIES=1
    report=[]
    for source,f in selected:
        item={"source":source.id,"file":f.rel_path,"url":f.url,"expected_sha256":published.get((source.id,f.rel_path))}
        try:
            # A failed request must not prevent unrelated declarations from being attempted.
            fetch._REFUSED.clear()
            fetch.download(source.id,f.url,f.rel_path,method=f.method,body=f.body,headers=f.headers,relay=False)
            entry=fetch.read_manifest(source.id)["files"][f.rel_path]
            item["actual_sha256"]=entry["sha256"]
            item["bytes"]=entry["bytes"]
            item["status"]="exact" if entry["sha256"]==item["expected_sha256"] else "changed" if item["expected_sha256"] else "no_original_hash"
        except Exception as error:
            item["status"]="unavailable"
            item["error"]=str(error)
        report.append(item)
        print(f"{item['status']:16s} {source.id}/{f.rel_path}",flush=True)
    counts={status:sum(x["status"]==status for x in report) for status in ("exact","changed","no_original_hash","unavailable")}
    Path("recovery-report.json").write_text(json.dumps({"counts":counts,"files":report},indent=2,ensure_ascii=False),encoding="utf-8")
    print("RECOVERY SUMMARY",json.dumps(counts),flush=True)


if __name__=="__main__":
    main()
