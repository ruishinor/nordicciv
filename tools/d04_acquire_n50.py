"""Acquire and stage N50 municipal water extracts, never national archives."""
import argparse
import json
import re
import time
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlparse
from datetime import datetime, timezone

from d04_water_prep import REGIONS, ROOT, plan, clip, digest, save_json
from pyproj import Transformer
from shapely.geometry import shape, mapping
from shapely.ops import transform
from shapely import force_2d
import fiona

UUID = 'ea192681-d039-42ec-b1bc-f3ce04c189ac'
BASE = 'https://nedlasting.geonorge.no'
MAX_FILE = 100 * 1024**2
MAX_TOTAL = 400 * 1024**2
MAX_EXPANDED = 600 * 1024**2
AREAS = {'havflate','innsjø','innsjøregulert','elv','elvbekk'}
LINES = {'elvbekk','elv','flomløp'}
def request(url, payload=None):
    if urlparse(url).scheme != 'https' or urlparse(url).hostname != 'nedlasting.geonorge.no':
        raise ValueError('Unexpected API host')
    req = Request(url, data=None if payload is None else json.dumps(payload).encode(),
                  headers={'Content-Type':'application/json','User-Agent':'NordicCiv-D04/1'})
    with urlopen(req,timeout=60) as res:
        data=res.read(16*1024**2+1)
        if len(data)>16*1024**2: raise ValueError('Oversized API response')
    return json.loads(data)

def link(doc, rel):
    return next(x['href'] for x in doc['_links'] if x['rel'].rstrip('/').endswith('/'+rel))

def codes(region):
    # Conservative bbox overlap on existing simplified municipal geometry; verify
    # source coverage independently. No inference of dry land from this selection.
    l,t,r,b=region['bounds']
    doc=json.loads((ROOT/'web/data/munis.json').read_text(encoding='utf-8'))
    selected=[]
    for f in doc['features']:
        if not re.fullmatch(r'NO-\d{4}',f['id']): continue
        x,y,xx,yy=f['bbox']
        if x<=r+2 and xx>=l-2 and y<=b+2 and yy>=t-2:
            selected.append(f['id'][3:])
    if not 0<len(selected)<=20: raise ValueError('Unexpected municipal selection')
    return sorted(selected)

def download(url,path,remaining):
    if urlparse(url).scheme!='https' or urlparse(url).hostname!='nedlasting.geonorge.no':
        raise ValueError('Unexpected download host')
    if path.exists():
        if path.stat().st_size>min(MAX_FILE,remaining): raise ValueError('Cache exceeds budget')
        return
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.part')
    try:
        with urlopen(Request(url,headers={'User-Agent':'NordicCiv-D04/1'}),timeout=90) as res, tmp.open('wb') as out:
            count=0
            while chunk:=res.read(1024**2):
                count+=len(chunk)
                if count>min(MAX_FILE,remaining): raise ValueError('Download budget exceeded')
                out.write(chunk)
        if not zipfile.is_zipfile(tmp): raise ValueError('Not a ZIP archive')
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)

def safe_extract(path,dest):
    with zipfile.ZipFile(path) as z:
        if sum(i.file_size for i in z.infolist())>MAX_EXPANDED: raise ValueError('Expanded archive too large')
        for i in z.infolist():
            target=(dest/i.filename).resolve()
            if not target.is_relative_to(dest.resolve()): raise ValueError('Unsafe ZIP member')
        z.extractall(dest)

def process_archive(path,region):
    dest=path.with_suffix('')
    safe_extract(path,dest)
    dbs=list(dest.rglob('*.gdb'))
    if not dbs: raise ValueError('No FileGDB in archive')
    records={'water-area':[],'water-line':[]}
    schema=[]
    from rasterio.warp import transform_bounds
    from d04_water_prep import CRS
    extent=plan(region,2000)['bufferedProjectedBounds']
    for db in dbs:
        for layer in fiona.listlayers(db):
            norm=re.sub(r'[^a-zæøå0-9]','',layer.casefold())
            with fiona.open(db,layer=layer) as src:
                fields=list(src.schema['properties'])
                clsfield=next((f for f in fields if f.casefold() in {'objtype','objekttype','featuretype'}),None)
                explicit=next((k for k in sorted(AREAS|LINES,key=len,reverse=True) if norm.endswith(k)),None)
                # Generic thematic layers require actual object-type field.
                if not explicit and not clsfield: continue
                if not src.crs: raise ValueError('Source layer has no CRS: '+layer)
                bb=transform_bounds(CRS,src.crs_wkt or src.crs,*extent,densify_pts=41)
                forward=Transformer.from_crs(src.crs_wkt or src.crs,'EPSG:4326',always_xy=True).transform
                counts={}
                for f in src.filter(bbox=bb):
                    cls=str(f['properties'].get(clsfield) if clsfield else explicit).casefold()
                    if cls not in AREAS|LINES or not f['geometry']: continue
                    g=force_2d(shape(f['geometry']))
                    typ=g.geom_type
                    role='water-area' if typ in {'Polygon','MultiPolygon'} and cls in AREAS else 'water-line' if typ in {'LineString','MultiLineString'} and cls in LINES else None
                    if not role: continue
                    records[role].append({'type':'Feature','geometry':mapping(transform(forward,g)),'properties':{}})
                    counts[cls]=counts.get(cls,0)+1
                if counts: schema.append({'layer':layer,'counts':counts,'geometry':src.schema['geometry']})
    return records,schema

def run(region,out):
    started=datetime.now(timezone.utc).isoformat()
    selected=codes(region)
    target=out/'n50'/region['id']
    target.mkdir(parents=True,exist_ok=True)
    report={'region':region['id'],'candidateMunicipalities':selected,'startedUtc':started,
            'licence':'CC BY 4.0','attribution':'Kartverket, N50 Kartdata, CC BY 4.0; clipped and transformed',
            'inputs':[],'errors':[],'outputs':{},'coverage':'unverified; simplified municipal bbox selection'}
    try:
        caps=request(BASE+'/api/capabilities/'+UUID)
        areas=request(link(caps,'area'))
        order=[]
        for code in selected:
            a=next((a for a in areas if a['code']==code and a['type'].casefold()=='kommune'),None)
            if a is None: raise ValueError('Municipal code unavailable: '+code)
            choices=[(p,f) for p in a['projections'] for f in p['formats']
                     if p['code'] in ('25832','25833') and f['name'].casefold() in ('fgdb','filegdb','esri file geodatabase')]
            if not choices: raise ValueError('No municipal FileGDB format: '+code)
            p,f=choices[0]
            order.append({'metadataUuid':UUID,'areas':[{'code':a['code'],'name':a['name'],'type':a['type']}],
                          'projections':[{k:p[k] for k in ('code','name','codespace') if k in p}],
                          'formats':[{'name':f['name']}]})
        if caps.get('deliveryNotificationByEmail'): raise ValueError('Provider requires email; no invented identity')
        result=request(link(caps,'order'),{'orderLines':order})
        files=result.get('files',[])
        if not files: raise ValueError('Provider returned no files')
        # Only consume explicitly ready files; pending items remain in report.
        all_records={'water-area':[],'water-line':[]}
        spent=0
        for item in files:
            code=str(item.get('area',''))
            if code not in selected or item.get('metadataUuid')!=UUID:
                report['errors'].append('Unexpected area or dataset in order response'); continue
            if item.get('status')!='ReadyForDownload':
                report['errors'].append(code+': '+str(item.get('status'))); continue
            try:
                name=Path(item['name']).name
                if not name.lower().endswith('.zip'): raise ValueError('Unexpected file extension')
                path=out/'cache'/name
                download(item['downloadUrl'],path,MAX_TOTAL-spent)
                spent+=path.stat().st_size
                rec,schema=process_archive(path,region)
                report['inputs'].append({'municipality':code,'file':name,'bytes':path.stat().st_size,
                                         'sha256':digest(path),'layers':schema,'orderDate':result.get('orderDate')})
                for role in rec: all_records[role].extend(rec[role])
            except Exception as e: report['errors'].append(code+': '+str(e))
        for role,features in all_records.items():
            if not features: continue
            try:
                fc,stats=clip({'type':'FeatureCollection','features':features},'EPSG:4326',region,
                              'Polygon' if role=='water-area' else 'LineString')
                path=target/(role+'.geojson')
                save_json(path,fc)
                report['outputs'][role]={'file':path.name,'bytes':path.stat().st_size,'sha256':digest(path),**stats}
            except Exception as e: report['errors'].append(role+': '+str(e))
    except Exception as e: report['errors'].append(str(e))
    save_json(target/'acquisition.json',report)
    print(json.dumps(report,ensure_ascii=False))
    return bool(report['outputs'])

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--region',choices=['aurland','oslo-lillestrom'],required=True)
    p.add_argument('--out',type=Path,default=ROOT/'data/raw/d04-prep')
    a=p.parse_args()
    raise SystemExit(0 if run(REGIONS[a.region],a.out) else 1)
