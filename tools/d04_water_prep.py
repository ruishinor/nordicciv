"""Bounded D04 GIS staging. Reuses D05 projection/grid; no runtime dependencies."""
import argparse
import json
from pathlib import Path

from pyproj import Transformer
from rasterio.warp import transform_bounds
from shapely import force_2d, make_valid, union_all
from shapely.geometry import box, mapping, shape
from shapely.ops import transform

from d05_landcover import CRS, REGIONS, ROOT, bounds, digest, save_json

MAX_BYTES = 64 * 1024 * 1024
MAX_FEATURES = 100000
MANIFEST = json.loads((ROOT / 'docs/d04-d05/sources.json').read_text(encoding='utf-8'))


def parts(geom, kind):
    if geom.is_empty:
        return
    if geom.geom_type == kind:
        yield geom
    elif hasattr(geom, 'geoms'):
        for child in geom.geoms:
            yield from parts(child, kind)


def plan(region, buffer_m):
    l, b, r, t = bounds(region)
    buffered = (l-buffer_m, b-buffer_m, r+buffer_m, t+buffer_m)
    return dict(region=region['id'], exactProjectedBounds=[l,b,r,t],
                bufferedProjectedBounds=buffered,
                bufferedLonLat=transform_bounds(CRS, 'EPSG:4326', *buffered, densify_pts=41),
                bufferedUTM32=transform_bounds(CRS, 'EPSG:25832', *buffered, densify_pts=41),
                bufferedUTM33=transform_bounds(CRS, 'EPSG:25833', *buffered, densify_pts=41),
                projection=CRS)


def clip(doc, input_crs, region, kind, tolerance=0, buffer_m=2000):
    if doc.get('type') != 'FeatureCollection' or not isinstance(doc.get('features'), list):
        raise ValueError('Expected a GeoJSON FeatureCollection')
    if len(doc['features']) > MAX_FEATURES:
        raise ValueError('Too many input features; prefilter to buffered pilot')
    forward = Transformer.from_crs(input_crs, CRS, always_xy=True).transform
    backward = Transformer.from_crs(CRS, 'EPSG:4326', always_xy=True).transform
    extent = box(*bounds(region))
    halo = extent.buffer(buffer_m, cap_style=3, join_style=2)
    geometries = []
    repaired = rejected = 0
    for feature in doc['features']:
        if not feature.get('geometry'):
            rejected += 1
            continue
        geom = transform(forward, force_2d(shape(feature['geometry'])))
        if not geom.is_valid:
            geom = make_valid(geom)
            repaired += 1
        selected = list(parts(geom.intersection(halo), kind))
        if not selected:
            rejected += 1
        geometries.extend(selected)
    if not geometries:
        raise ValueError('No selected geometry intersects the buffered pilot; coverage unknown')
    # One source and one explicitly selected role at a time. Dissolve polygon seams
    # before simplification; never use this for combining different source licences.
    groups = [union_all(geometries)] if kind == 'Polygon' else geometries
    output = []
    for geom in groups:
        if tolerance:
            geom = geom.simplify(tolerance, preserve_topology=True)
        for part in parts(make_valid(geom.intersection(extent)), kind):
            if not part.is_valid:
                raise ValueError('Invalid output geometry')
            output.append({'type':'Feature','geometry':mapping(transform(backward, part)),
                           'properties':{}})
    if not output:
        raise ValueError('No geometry intersects exact pilot; coverage not established')
    return {'type':'FeatureCollection','features':output}, dict(inputFeatures=len(doc['features']),
                repairedInputs=repaired, outsideOrWrongType=rejected, outputFeatures=len(output))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['plan','clip'])
    p.add_argument('--region', choices=REGIONS, required=True)
    p.add_argument('--buffer-m', type=int, choices=[2000,3000,5000], default=2000)
    p.add_argument('--source', choices=['n50','geodanmark','elvis','topografi50','overture','eu-hydro'])
    p.add_argument('--role', choices=['water-area','land-area','water-line'])
    p.add_argument('--input', type=Path)
    p.add_argument('--input-crs', default='EPSG:4326')
    p.add_argument('--revision', help='Actual extract date/version, not the current date')
    p.add_argument('--tolerance-m', type=float, default=0)
    p.add_argument('--out', type=Path, default=ROOT/'data/raw/d04-prep')
    a = p.parse_args()
    region = REGIONS[a.region]
    if a.action == 'plan':
        print(json.dumps(plan(region,a.buffer_m), indent=2))
        return
    if not all([a.source,a.role,a.input,a.revision]) or not 0 <= a.tolerance_m <= 15:
        p.error('clip requires source, role, input, revision and tolerance 0–15 m')
    if a.input.stat().st_size > MAX_BYTES:
        p.error('Prefilter input to buffered pilot; 64 MiB input cap')
    kind = 'LineString' if a.role == 'water-line' else 'Polygon'
    fc, stats = clip(json.loads(a.input.read_text(encoding='utf-8')), a.input_crs,
                     region, kind, a.tolerance_m, a.buffer_m)
    # Explicit per-source isolation; raw staging only, not public web assets.
    target = a.out/a.source/a.region/(a.role+'.geojson')
    save_json(target,fc)
    info = dict(source=a.source, sourceRevision=a.revision, role=a.role,
                inputFile=a.input.name, inputSha256=digest(a.input), inputCRS=a.input_crs,
                outputCRS='EPSG:4326', pilot=plan(region,a.buffer_m), toleranceM=a.tolerance_m,
                bytes=target.stat().st_size, sha256=digest(target), counts=stats,
                coverageStatus='not established by geometry clipping',
                publication='staging only; review source licence and coverage')
    save_json(target.with_suffix('.json'),info)
    print(json.dumps(info,indent=2))


if __name__ == '__main__':
    main()
