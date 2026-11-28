"""Verify acquired pilot files, repair export topology and stage isolated packages."""
import argparse
import gzip
import json
import shutil
from pathlib import Path
from shapely import make_valid, union_all
from shapely.geometry import shape, mapping, box
from shapely.ops import transform
from pyproj import Transformer
from d04_water_prep import REGIONS, CRS, bounds, parts, digest, save_json


def load_verified(path, meta, kind):
    if path.stat().st_size != meta['bytes'] or digest(path) != meta['sha256']:
        raise ValueError(f'Source checksum or size mismatch: {path}')
    doc = json.loads(path.read_text(encoding='utf-8'))
    if doc.get('type') != 'FeatureCollection' or len(doc['features']) != meta['outputFeatures']:
        raise ValueError(f'Unexpected feature collection: {path}')
    geoms, repairs = [], 0
    for feature in doc['features']:
        geom = shape(feature['geometry'])
        if not geom.is_valid:
            geom = make_valid(geom)
            repairs += 1
        for part in parts(geom, kind):
            if not part.is_valid or part.is_empty:
                raise ValueError(f'Invalid repaired geometry: {path}')
            geoms.append(part)
    if not geoms:
        raise ValueError(f'No usable geometries: {path}')
    return geoms, repairs


def write_layer(path, geoms):
    if not all(g.is_valid and not g.is_empty for g in geoms):
        raise ValueError('Invalid export geometry')
    doc = {'type':'FeatureCollection','features':[{'type':'Feature','geometry':mapping(g),'properties':{}} for g in geoms]}
    # Gzip is an offline interchange format, not a browser runtime contract.
    data = (json.dumps(doc,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8')
    path.write_bytes(gzip.compress(data,compresslevel=9,mtime=0))
    return {'file':path.name,'features':len(geoms),'bytes':path.stat().st_size,
            'uncompressedBytes':len(data),'sha256':digest(path)}


def finalize(source, dest, region_id):
    report = json.loads((source/'acquisition.json').read_text(encoding='utf-8'))
    if report['region'] != region_id or report.get('errors'):
        raise ValueError('Wrong pilot or unresolved acquisition errors')
    if set(report['outputs']) != {'water-area','water-line'}:
        raise ValueError('Expected both acquired water layers')
    region = REGIONS[region_id]
    forward = Transformer.from_crs('EPSG:4326',CRS,always_xy=True).transform
    backward = Transformer.from_crs(CRS,'EPSG:4326',always_xy=True).transform
    extent = box(*bounds(region))
    dest.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source/'acquisition.json',dest/'acquisition.json')
    areas, ar = load_verified(source/'water-area.geojson',report['outputs']['water-area'],'Polygon')
    lines, lr = load_verified(source/'water-line.geojson',report['outputs']['water-line'],'LineString')
    projected_areas = [make_valid(transform(forward,g)) for g in areas]
    projected_lines = [transform(forward,g) for g in lines]
    # A tiny tolerance permits floating-point round trips through geographic CRS.
    excess = max(max(extent.bounds[0]-g.bounds[0],extent.bounds[1]-g.bounds[1],g.bounds[2]-extent.bounds[2],g.bounds[3]-extent.bounds[3],0) for g in projected_areas+projected_lines)
    if excess > 0.1:
        raise ValueError(f'Geometry outside pilot by {excess:.3f} m')
    water = union_all(projected_areas)
    visible = []
    for line in projected_lines:
        for part in parts(line.difference(water),'LineString'):
            # Revalidate after the inverse transform, not only in projected CRS.
            visible.extend(parts(make_valid(transform(backward,part)),'LineString'))
    layers = {'water-area':write_layer(dest/'water-area.geojson.gz',areas),
              'water-line':write_layer(dest/'water-line.geojson.gz',lines),
              'water-line-visible':write_layer(dest/'water-line-visible.geojson.gz',visible)}
    if region_id == 'herning':
        # Keep the ODbL original bounded selected records and attribution separate.
        for role, meta in report['outputs'].items():
            raw=source/meta['rawFile']
            if raw.stat().st_size!=meta['rawBytes'] or digest(raw)!=meta['rawSha256']:
                raise ValueError(f'Raw ODbL file mismatch: {raw}')
            (dest/(raw.name+'.gz')).write_bytes(gzip.compress(raw.read_bytes(),compresslevel=9,mtime=0))
        for name in ('NOTICE.txt','queries.sql'):
            shutil.copyfile(source/name,dest/name)
    else:
        (dest/'NOTICE.txt').write_text('Kartverket, N50 Kartdata, CC BY 4.0. https://creativecommons.org/licenses/by/4.0/\nClipped, transformed, dissolved and export topology repaired. Water-line-visible excludes mapped water areas.\n',encoding='utf-8')
    result = {'region':region_id,'source':report.get('source','Kartverket N50 Kartdata'),
              'licence':report['licence'],'coverage':report['coverage'],
              'sourceInputBytes':sum(i['bytes'] for i in report.get('inputs',[])) or None,
              'sourceReportSha256':digest(dest/'acquisition.json'),'exportRepairs':{'area':ar,'line':lr},
              'waterAreaKm2':water.area/1e6,'polygonHoles':sum(len(g.interiors) for g in areas),
              'maxPilotBoundsExcessM':excess,'layers':layers,
              'note':'Water areas and lines are mapped features; no dry-land coverage claim. Visible lines are derived, original lines retained.'}
    save_json(dest/'finalization.json',result)
    print(json.dumps(result,ensure_ascii=False))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--dest',type=Path,required=True)
    p.add_argument('--region',choices=REGIONS,required=True)
    a=p.parse_args()
    finalize(a.source,a.dest,a.region)
