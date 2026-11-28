"""Offline-first D05 pilot preparation. No changes to web/ or existing datasets."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.transform import from_origin
from rasterio.warp import transform_bounds
from rasterio.windows import Window, from_bounds

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / 'docs/d05/sources.json').read_text(encoding='utf-8'))
PROJ = MANIFEST['projection']
CRS = PROJ['proj4'].replace('+units=km', '+units=m')
REGIONS = {r['id']: r for r in MANIFEST['regions']}
SOURCES = MANIFEST['sources']
NODATA = 255
MAX_FEATURES = 20000
MAX_RESPONSE = 32 * 1024 * 1024


def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def save_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def bounds(region):
    l, t, r, b = region['bounds']
    return ((l + PROJ['x0_km']) * 1000, (PROJ['y1_km'] - b) * 1000,
            (r + PROJ['x0_km']) * 1000, (PROJ['y1_km'] - t) * 1000)


def grid(region, spacing):
    l, b, r, t = bounds(region)
    w, h = round((r-l)/spacing), round((t-b)/spacing)
    if not (0 < w*h <= 8_000_000) or not (math.isclose(w*spacing, r-l, abs_tol=1e-5) and math.isclose(h*spacing, t-b, abs_tol=1e-5)):
        raise ValueError('Invalid or oversized pilot grid')
    return from_origin(l, t, spacing, spacing), (h, w)


def worldcover_urls(region):
    w, s, e, n = transform_bounds(CRS, 'EPSG:4326', *bounds(region), densify_pts=41)
    for lat in range(3*math.floor(s/3), 3*math.floor(n/3)+1, 3):
        for lon in range(3*math.floor(w/3), 3*math.floor(e/3)+1, 3):
            key = f'N{lat:02d}E{lon:03d}'
            yield SOURCES['worldcover']['urlTemplate'].format(tile=key)


def wfs_url(**params):
    return SOURCES['dk-marker']['endpoint'] + '?' + urlencode(dict(service='WFS', version='2.0.0', **params))


def field_params(region):
    bb = transform_bounds(CRS, 'EPSG:25832', *bounds(region), densify_pts=41)
    return dict(typeNames=SOURCES['dk-marker']['typeName'], bbox=','.join(map(str, bb)) + ',EPSG:25832', srsName='EPSG:25832')


def request_bytes(url, limit=MAX_RESPONSE):
    with urlopen(Request(url, headers={'User-Agent': 'NordicCiv-D05-prep/1.0'}), timeout=60) as response:
        data = response.read(limit+1)
        if len(data) > limit:
            raise ValueError('Response exceeds pilot byte limit')
        return data


def write_tif(path, data, transform, crs, nodata):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp.tif')
    with rasterio.open(tmp, 'w', driver='GTiff', width=data.shape[1], height=data.shape[0], count=1,
                       dtype='uint8', crs=crs, transform=transform, nodata=nodata,
                       compress='deflate', tiled=True, blockxsize=256, blockysize=256) as dst:
        dst.write(data, 1)
    tmp.replace(path)


def crop_worldcover(url, region, cache, local_dir=None, offline=False):
    name = url.rsplit('/', 1)[-1]
    path = cache / region['id'] / name
    meta_path = path.with_suffix('.json')
    if path.exists() and meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
        if digest(path) != meta['sha256'] or meta['url'] != url or meta['boundsMapKm'] != region['bounds']:
            raise ValueError(f'Cached source mismatch: {path}')
        return path, meta
    if offline:
        raise FileNotFoundError(f'Missing cached window: {path}')
    local = local_dir / name if local_dir else None
    headers = {}
    if local is None:
        with urlopen(Request(url, headers={'Range': 'bytes=0-15'}), timeout=45) as r:
            if r.status != 206 or len(r.read(17)) != 16 or not r.headers.get('Content-Range', '').startswith('bytes 0-15/'):
                raise ValueError('Source did not honour a bounded HTTP range')
            headers = {k: r.headers.get(k) for k in ('ETag', 'Last-Modified', 'Content-Range')}
    elif not local.is_file():
        raise FileNotFoundError(local)
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR', CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif',
                      GDAL_HTTP_TIMEOUT='45', GDAL_HTTP_MAX_RETRY='0', GDAL_CACHEMAX=32*1024*1024):
        with rasterio.open(str(local) if local else url) as src:
            if src.crs != rasterio.crs.CRS.from_epsg(4326) or src.count != 1 or src.dtypes[0] != 'uint8':
                raise ValueError('Unexpected WorldCover source format')
            bb = transform_bounds(CRS, src.crs, *bounds(region), densify_pts=41)
            win = from_bounds(*bb, transform=src.transform)
            c0, r0 = math.floor(win.col_off)-1, math.floor(win.row_off)-1
            c1, r1 = math.ceil(win.col_off+win.width)+1, math.ceil(win.row_off+win.height)+1
            win = Window(c0, r0, c1-c0, r1-r0).intersection(Window(0, 0, src.width, src.height))
            if win.width*win.height > 30_000_000:
                raise ValueError('Source window exceeds pilot pixel limit')
            data = src.read(1, window=win, masked=True).filled(0)
            write_tif(path, data, src.window_transform(win), src.crs, 0)
            meta = dict(url=url, boundsMapKm=region['bounds'], sourceResolutionDegrees=list(src.res),
                        window=list(win.flatten()), sourceCRS=str(src.crs), sourceHeaders=headers,
                        acquisition='local file' if local else 'HTTP range window', sha256=digest(path))
    save_json(meta_path, meta)
    return path, meta


def sample_native(src, region, spacing):
    # Transform pixel centres exactly. Warping adjacent tiles independently can create
    # overlapping output cells at a seam; explicit source-pixel ownership avoids this.
    dst_transform, shape = grid(region, spacing)
    a = np.full(shape, NODATA, np.uint8)
    if src.transform.b != 0 or src.transform.d != 0 or src.transform.a <= 0 or src.transform.e >= 0:
        raise ValueError('Expected a north-up source grid')
    bb = transform_bounds(CRS, src.crs, *bounds(region), densify_pts=41)
    win = from_bounds(*bb, transform=src.transform)
    c0 = max(0, math.floor(win.col_off)-2)
    r0 = max(0, math.floor(win.row_off)-2)
    c1 = min(src.width, math.ceil(win.col_off+win.width)+2)
    r1 = min(src.height, math.ceil(win.row_off+win.height)+2)
    if c1 <= c0 or r1 <= r0:
        return a
    if (c1-c0)*(r1-r0) > 30_000_000:
        raise ValueError('Source window exceeds pilot pixel limit')
    values = src.read(1, window=Window(c0,r0,c1-c0,r1-r0), masked=True).filled(NODATA)
    convert = Transformer.from_crs(CRS, src.crs, always_xy=True).transform
    xx = dst_transform.c + (np.arange(shape[1])+0.5)*spacing
    for start in range(0, shape[0], 128):
        stop = min(start+128, shape[0])
        yy = dst_transform.f - (np.arange(start,stop)+0.5)*spacing
        x,y = np.meshgrid(xx,yy)
        sx,sy = convert(x,y)
        cols = np.floor((sx-src.transform.c)/src.transform.a).astype(np.int64)-c0
        rows = np.floor((sy-src.transform.f)/src.transform.e).astype(np.int64)-r0
        inside = (cols >= 0) & (cols < c1-c0) & (rows >= 0) & (rows < r1-r0)
        a[start:stop][inside] = values[rows[inside],cols[inside]]
    return a


def raster_layer(paths, region, source_id, spacing, out, provenance):
    source = SOURCES[source_id]
    transform, shape = grid(region, spacing)
    result = np.full(shape, NODATA, np.uint8)
    valid = source['validCodes']
    unknown_codes = {}
    for path in paths:
        with rasterio.open(path) as src:
            if not src.crs or src.count != 1 or src.dtypes[0] != 'uint8':
                raise ValueError(f'Expected georeferenced single-band uint8 raster: {path}')
            if src.nodata in valid:
                raise ValueError(f'Source nodata overlaps a valid code: {path}')
            a = sample_native(src, region, spacing)
            for code, count in zip(*np.unique(a, return_counts=True)):
                if int(code) not in valid and code != NODATA:
                    unknown_codes[int(code)] = unknown_codes.get(int(code), 0) + int(count)
            a[~np.isin(a, valid)] = NODATA
            if np.any((result != NODATA) & (a != NODATA) & (result != a)):
                raise ValueError('Overlapping source rasters disagree; resolve the source revision first')
            result[a != NODATA] = a[a != NODATA]
    if not np.any(result != NODATA):
        raise ValueError('No valid source samples in pilot')
    target = out / region['id'] / f'{source_id}-{spacing}m.tif'
    write_tif(target, result, transform, CRS, NODATA)
    counts = {str(int(k)): int(v) for k, v in zip(*np.unique(result, return_counts=True))}
    info = dict(sourceId=source_id, source=source, region=region['id'], boundsMapKm=region['bounds'],
                projection=PROJ, gridSpacingM=spacing, shape=list(shape), nodata=NODATA, codeCounts=counts,
                unknownInputCodes=unknown_codes, resampling='nearest', bytes=target.stat().st_size,
                sha256=digest(target), inputs=provenance)
    save_json(target.with_suffix('.json'), info)
    return {'path': str(target), 'shape': list(shape), 'bytes': info['bytes'], 'codeCounts': counts}


def fields(doc, input_crs, region):
    from shapely import make_valid
    from shapely.geometry import shape, mapping, box, MultiPolygon
    from shapely.ops import transform
    if doc.get('type') != 'FeatureCollection' or len(doc.get('features', [])) > MAX_FEATURES:
        raise ValueError('Expected bounded GeoJSON FeatureCollection')
    forward = Transformer.from_crs(input_crs, CRS, always_xy=True).transform
    inverse = Transformer.from_crs(CRS, 'EPSG:4326', always_xy=True).transform
    clip = box(*bounds(region))
    out = []
    for f in doc['features']:
        if not f.get('geometry'):
            raise ValueError('Missing parcel geometry')
        geom = make_valid(transform(forward, shape(f['geometry']))).intersection(clip)
        parts = [geom] if geom.geom_type == 'Polygon' else [g for g in getattr(geom, 'geoms', []) if g.geom_type == 'Polygon']
        parts = [g for g in parts if not g.is_empty and g.area > 0]
        if parts:
            g = parts[0] if len(parts) == 1 else MultiPolygon(parts)
            out.append({'type': 'Feature', 'geometry': mapping(transform(inverse, g)), 'properties': {}})
    if not out:
        raise ValueError('No parcels intersect pilot; verify source CRS and coverage')
    return {'type': 'FeatureCollection', 'features': out}


def fetch_fields(region, geometry_field):
    params = field_params(region)
    hits = ElementTree.fromstring(request_bytes(wfs_url(request='GetFeature', resultType='hits', **params), 1_000_000))
    count = int(hits.attrib.get('numberMatched', '-1'))
    if not 0 < count <= MAX_FEATURES:
        raise ValueError('WFS hit count missing, empty or too large; no unbounded download')
    url = wfs_url(request='GetFeature', count=count, propertyName=geometry_field, outputFormat='application/json', **params)
    doc = json.loads(request_bytes(url))
    if len(doc.get('features', [])) != count:
        raise ValueError('Incomplete WFS response')
    if any(f.get('properties') for f in doc['features']):
        raise ValueError('Server did not honour geometry-only request; no attributes retained')
    if '25832' not in str(doc.get('crs', {})):
        raise ValueError('WFS response did not identify the requested projected CRS')
    return doc, url


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['plan', 'worldcover', 'raster', 'fields'])
    p.add_argument('--region', choices=REGIONS, required=True)
    p.add_argument('--out', type=Path, default=ROOT/'data/raw/d05-prep')
    p.add_argument('--spacing', type=int, choices=[10, 30], default=10)
    p.add_argument('--local-dir', type=Path)
    p.add_argument('--offline', action='store_true')
    p.add_argument('--source', choices=['clms-tcd', 'clms-dlt', 'clms-grassland'])
    p.add_argument('--year', type=int, help='Reference year confirmed from the downloaded source metadata')
    p.add_argument('--input', type=Path, nargs='+')
    p.add_argument('--input-crs', default='EPSG:4326')
    p.add_argument('--geometry-field', help='Exact geometry property from WFS DescribeFeatureType')
    a = p.parse_args()
    region = REGIONS[a.region]
    if a.action == 'plan':
        t, sh = grid(region, a.spacing)
        plan = dict(region=region, boundsLonLat=transform_bounds(CRS, 'EPSG:4326', *bounds(region), densify_pts=41),
                    shape=sh, rawBytesPerBand=sh[0]*sh[1], worldcoverUrls=list(worldcover_urls(region)))
        if a.region == 'herning':
            plan['fieldDescribe'] = wfs_url(request='DescribeFeatureType', typeNames=SOURCES['dk-marker']['typeName'])
            plan['fieldHits'] = wfs_url(request='GetFeature', resultType='hits', **field_params(region))
        print(json.dumps(plan, indent=2)); return
    if a.action == 'worldcover':
        items = [crop_worldcover(u, region, a.out/'cache', a.local_dir, a.offline) for u in worldcover_urls(region)]
        result = raster_layer([i[0] for i in items], region, 'worldcover', a.spacing, a.out, [i[1] for i in items])
    elif a.action == 'raster':
        if not a.source or not a.input or a.year != SOURCES[a.source]['year']:
            p.error('raster requires --source, --input and the manifest reference --year')
        result = raster_layer(a.input, region, a.source, a.spacing, a.out,
                              [{'file': f.name, 'sha256': digest(f)} for f in a.input])
    else:
        if a.region != 'herning':
            p.error('Marker is a Danish source; only the Herning pilot is supported')
        if a.input and len(a.input) == 1:
            if a.input[0].stat().st_size > MAX_RESPONSE:
                p.error('Input exceeds bounded parcel file limit')
            doc, provenance, crs = json.loads(a.input[0].read_text(encoding='utf-8')), {'file': a.input[0].name, 'sha256': digest(a.input[0])}, a.input_crs
        elif a.geometry_field and not a.offline and not a.input:
            doc, url = fetch_fields(region, a.geometry_field)
            provenance, crs = {'url': url}, 'EPSG:25832'
        else:
            p.error('fields requires one local --input or online --geometry-field')
        fc = fields(doc, crs, region)
        path = a.out/region['id']/'dk-marker-2024.geojson'
        save_json(path, fc)
        result = dict(path=str(path), count=len(fc['features']), sha256=digest(path), bytes=path.stat().st_size,
                      source=SOURCES['dk-marker'], input=provenance, boundsMapKm=region['bounds'],
                      outputCRS='EPSG:4326', publication='Hold pending direct official licence confirmation')
        save_json(path.with_suffix('.json'), result)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
