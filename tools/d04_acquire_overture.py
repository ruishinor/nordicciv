"""Run bounded, release-pinned Overture water queries for Herning only.
ODbL fallback; do not combine with national-source databases.
"""
import argparse
import json
import os
from pathlib import Path
from datetime import datetime, timezone
import duckdb

from d04_water_prep import REGIONS, ROOT, overture_sql, clip, digest, save_json, MAX_BYTES

def run(out):
    region=REGIONS['herning']
    target=(out/'overture'/'herning').resolve()
    target.mkdir(parents=True,exist_ok=True)
    report={'region':'herning','source':'Overture Maps base water','release':'2026-11-18.0',
            'licence':'ODbL 1.0','attribution':'© OpenStreetMap contributors; Overture Maps Foundation',
            'sourceTerms':'https://docs.overturemaps.org/attribution/',
            'licenceUrl':'https://opendatacommons.org/licenses/odbl/1-0/',
            'retrievalUtc':datetime.now(timezone.utc).isoformat(),'coverage':'unverified',
            'outputs':{},'errors':[]}
    # Save original bounded queries and raw selected data separately from CC BY sources.
    queries=overture_sql(region,2000).splitlines()
    selected=[q for q in queries if q.startswith('COPY ') and '/type=water/' in q]
    if len(selected)!=2: raise ValueError('Expected two bounded water queries')
    (target/'queries.sql').write_text('\n'.join(queries[:3]+selected)+'\n',encoding='utf-8')
    cwd=Path.cwd()
    try:
        os.chdir(target)
        con=duckdb.connect()
        con.execute("SET memory_limit='1GB'; SET threads=2;")
        con.execute("INSTALL spatial; INSTALL httpfs;")
        for q in queries[:3]: con.execute(q)
        for role,query in zip(('water-area','water-line'),selected):
            try:
                con.execute(query)
                raw=target/('overture-herning-'+role+'.geojson')
                if raw.stat().st_size>MAX_BYTES: raise ValueError('Extract exceeds bounded processing budget')
                doc=json.loads(raw.read_text(encoding='utf-8'))
                fc,stats=clip(doc,'EPSG:4326',region,'Polygon' if role=='water-area' else 'LineString')
                path=target/(role+'.geojson')
                save_json(path,fc)
                report['outputs'][role]={'file':path.name,'bytes':path.stat().st_size,'sha256':digest(path),
                     'rawFile':raw.name,'rawBytes':raw.stat().st_size,'rawSha256':digest(raw),**stats}
            except Exception as e: report['errors'].append(role+': '+str(e))
    except Exception as e: report['errors'].append(str(e))
    finally: os.chdir(cwd)
    (target/'NOTICE.txt').write_text(
        'Overture Maps base water, release 2026-11-18.0. © OpenStreetMap contributors; Overture Maps Foundation.\n'
        'This database and modified subset are distributed under the Open Database License (ODbL) 1.0: '
        'https://opendatacommons.org/licenses/odbl/1-0/\n'
        'Attribution: https://docs.overturemaps.org/attribution/ and https://www.openstreetmap.org/copyright\n'
        'Changes: bounded selection, geometry intersection, reprojection and clipping, dissolution of water polygons; '
        'processed geometries have attributes removed. Original selected records and queries are included. '
        'Coverage is unverified. Do not combine with permissively licensed national-source layers.\n',encoding='utf-8')
    save_json(target/'acquisition.json',report)
    print(json.dumps(report,ensure_ascii=False))
    return bool(report['outputs'])

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,default=ROOT/'data/raw/d04-prep')
    a=p.parse_args()
    raise SystemExit(0 if run(a.out) else 1)
