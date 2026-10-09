"""Prepare ADD exclusion polygons; clip in source CRS before reprojection."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re

import geopandas as gpd
import pyogrio
from shapely.geometry import box
import yaml

REPO = Path(__file__).resolve().parents[1]
STATIONS = {name: REPO / 'configs' / f'{name}.yaml'
            for name in ('davis', 'mawson', 'casey')}
SURFACES = ('land', 'ice shelf', 'ice tongue', 'rumple')


def prepare(source, config, output, margin=0.2, update_config=False, overwrite=False):
    source, config, output = map(lambda p: Path(p).expanduser().resolve(),
                                 (source, config, output))
    if not math.isfinite(margin) or margin < 0:
        raise ValueError('Margin must be finite and nonnegative')
    document = yaml.safe_load(config.read_text())
    region = document['run']['region']
    name = region['name']
    if not re.fullmatch(r'[A-Za-z0-9_-]+', name):
        raise ValueError('Region name must contain only letters, digits, _ or -')
    west, south, east, north = map(float, region['bbox'])
    bounds = (west-margin, south-margin, east+margin, north+margin)
    w, s, e, n = bounds
    if not all(map(math.isfinite, bounds)) or not (-180 < w < e < 180 and -90 < s < n < 90):
        raise ValueError('Use a regional W,S,E,N bbox away from poles/dateline')
    record_path = output.with_suffix('.provenance.json')
    if not overwrite and (output.exists() or record_path.exists()):
        raise FileExistsError(f'{output}: use --overwrite after reviewing existing outputs')
    text = config.read_text()
    if update_config and len(re.findall(r'^coastline:.*$', text, re.MULTILINE)) != 1:
        raise ValueError('Config must have exactly one top-level coastline setting')
    info = pyogrio.read_info(source)
    if not info['crs']:
        raise ValueError('Source CRS is missing')
    # Densification preserves curved geographic edges in the projected CRS.
    aoi = gpd.GeoSeries([box(*bounds).segmentize(0.02)], crs='EPSG:4326').to_crs(info['crs'])
    data = gpd.read_file(source, engine='pyogrio', bbox=tuple(aoi.total_bounds))
    if 'surface' not in data:
        raise ValueError("ADD 'surface' attribute missing")
    source_counts = data.surface.value_counts().to_dict()
    data = data[data.surface.isin(SURFACES)].copy()
    if data.empty or data.geometry.isna().any() or not data.geometry.is_valid.all():
        raise ValueError('Missing polygons or invalid source geometry; inspect before repair')
    # The full continent is valid in EPSG:3031 but can self-intersect at the
    # dateline after reprojection. Never reproject it before regional clipping.
    data = gpd.clip(data, aoi, keep_geom_type=True)
    data = data[data.geometry.notna() & ~data.geometry.is_empty].copy()
    data = data.to_crs('EPSG:4326')
    if data.empty or not data.geometry.is_valid.all():
        raise ValueError('Clipped/reprojected geometry failed validation')
    if not data.geom_type.isin(['Polygon', 'MultiPolygon']).all():
        raise ValueError('Exclusions must be polygons, not coastline lines')
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.stem + '.partial.geojson')
    data[['surface', 'geometry']].to_file(temporary, driver='GeoJSON', index=False)
    temporary.replace(output)
    components = {}
    for suffix in ('.shp', '.shx', '.dbf', '.prj', '.cpg'):
        part = source.with_suffix(suffix)
        if part.exists():
            digest = hashlib.sha256()
            with part.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024*1024), b''):
                    digest.update(chunk)
            components[part.name] = digest.hexdigest()
    record = dict(region=name, config=str(config), source=str(source),
                  source_crs=info['crs'], component_sha256=components,
                  requested_bbox=list(region['bbox']), margin_degrees=margin,
                  clipping_bbox=list(bounds), output_crs='EPSG:4326',
                  output_bounds=data.total_bounds.tolist(),
                  source_surface_counts=source_counts,
                  output_surface_counts=data.surface.value_counts().to_dict(),
                  geometry_repair=False, method='source-CRS clip then reproject',
                  geopandas_version=gpd.__version__, pyogrio_version=pyogrio.__version__)
    record_path.write_text(json.dumps(record, indent=2) + '\n')
    if update_config:
        relative = Path(os.path.relpath(output, config.parent)).as_posix()
        text = re.sub(r'^coastline:.*$', lambda _: 'coastline: ' + json.dumps(relative),
                      text, flags=re.MULTILINE)
        config.write_text(text)
    print('Saved:', output)
    print('Bounds:', data.total_bounds)
    print('Surface counts:', record['output_surface_counts'])
    print('All geometries valid:', bool(data.geometry.is_valid.all()))
    print('Provenance:', record_path)
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument('--station', type=str.lower, choices=STATIONS)
    selection.add_argument('--config', type=Path, help='Custom workflow YAML with run.region.name and bbox')
    parser.add_argument('--source', type=Path, default=REPO.parent.parent / 'data/coastlines/add_coastline_high_res_polygon_v7_9.shp')
    parser.add_argument('--output', type=Path, help='Output GeoJSON; defaults beside source')
    parser.add_argument('--margin-deg', type=float, default=0.2)
    parser.add_argument('--update-config', action='store_true')
    parser.add_argument('--overwrite', action='store_true')
    args = parser.parse_args(argv)
    config = args.config or STATIONS[args.station]
    name = yaml.safe_load(config.read_text())['run']['region']['name']
    if not re.fullmatch(r'[A-Za-z0-9_-]+', name):
        parser.error('Unsafe region name')
    output = args.output or args.source.parent / f'{name.lower()}_ADD_v7p9_exclusions.geojson'
    prepare(args.source, config, output, args.margin_deg, args.update_config, args.overwrite)


if __name__ == '__main__':
    main()
