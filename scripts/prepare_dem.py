"""Prepare a verified ellipsoidal REMA DEM with EGM96 ocean heights for SNAP."""
import logging
from afiw.core.logging import add_logging_arguments, setup_from_args, logged_step
import argparse
import json
import os
from pathlib import Path
import tempfile
import numpy as np
import rasterio
from rasterio.vrt import WarpedVRT
from rasterio.warp import Resampling
from dem_utils import checksum, combine, exclusions, grid, land_mask

logger = logging.getLogger('afiw.scripts.prepare_dem')


@logged_step
def prepare(source, geoid, config, output, resolution, mask_bounds, bounds=None):
    logger.info('DEM preparation: source=%s geoid=%s config=%s output=%s resolution=%s mask bounds=%s', source, geoid, config, output, resolution, mask_bounds)
    source, geoid, config, output = [Path(p).resolve() for p in (source, geoid, config, output)]
    record = output.with_suffix('.provenance.json')
    if output in (source, geoid) or output.exists() or record.exists():
        raise FileExistsError('Choose a new output; sources and existing products are never overwritten')
    spec, shapes = exclusions(config)
    bounds = list(bounds or spec.run.region.bbox)
    target = grid(bounds, resolution)
    grid(mask_bounds, resolution)  # validate the declared ADD coverage too
    if not (mask_bounds[0] <= bounds[0] < bounds[2] <= mask_bounds[2]
            and mask_bounds[1] <= bounds[1] < bounds[3] <= mask_bounds[3]):
        raise ValueError('Prepared DEM bounds extend beyond declared ADD mask coverage')
    if target['width'] * target['height'] > 200_000_000:
        raise ValueError('Output exceeds 200 million pixels; review spacing/bounds')
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=output.stem+'-', suffix='.tif', dir=output.parent)
    os.close(fd)
    totals = dict(land_shelf_pixels=0, ocean_pixels=0)
    try:
        with rasterio.open(source) as src, rasterio.open(geoid) as geo:
            if not src.crs or src.count != 1:
                raise ValueError('Source must have one elevation band and declared CRS')
            if geo.count != 1 or geo.descriptions[0] != 'geoid_undulation' or geo.tags().get('target_crs_epsg_code') != '5773':
                raise ValueError('Expected PROJ us_nga_egm96_15.tif geoid undulation grid')
            with WarpedVRT(src, **target, resampling=Resampling.bilinear, nodata=-9999) as terrain, \
                 WarpedVRT(geo, **target, resampling=Resampling.bilinear, nodata=-9999) as sea, \
                 rasterio.open(temporary, 'w', driver='GTiff', **target, count=1,
                               dtype='float32', nodata=-9999, tiled=True, blockxsize=512,
                               blockysize=512, compress='deflate', predictor=3, BIGTIFF='IF_SAFER') as dst:
                for index, (_, window) in enumerate(dst.block_windows(1), 1):
                    if index == 1 or index % 25 == 0:
                        logger.info('DEM block %s; window=%s counts=%s', index, window, totals)
                    land = land_mask(shapes, (int(window.height), int(window.width)), dst.window_transform(window))
                    values = combine(terrain.read(1, window=window, masked=True),
                                     sea.read(1, window=window, masked=True), land)
                    dst.write(values, 1, window=window)
                    totals['land_shelf_pixels'] += int(land.sum())
                    totals['ocean_pixels'] += int((~land).sum())
                dst.update_tags(vertical_datum='WGS84 ellipsoid', vertical_units='metres',
                                ocean_model='EGM96 geoid undulation; approximate mean sea level',
                                land_model='REMA; horizontally resampled, heights unchanged')
        logger.info('Validating every written DEM block')
        # Reopen and check all written blocks, not a sample.
        with rasterio.open(temporary) as dst:
            for _, window in dst.block_windows(1):
                values = dst.read(1, window=window, masked=True)
                if np.ma.getmaskarray(values).any() or not np.isfinite(values.data).all():
                    raise ValueError('Prepared DEM contains invalid pixels')
        provenance = dict(source=str(source), source_sha256=checksum(source),
                          geoid=str(geoid), geoid_sha256=checksum(geoid),
                          coastline=str(spec.coastline), coastline_sha256=checksum(spec.coastline),
                          config=str(config), config_sha256=checksum(config), bounds=bounds,
                          declared_mask_bounds=list(mask_bounds), requested_resolution_degrees=list(resolution),
                          actual_resolution_degrees=[target['transform'].a, -target['transform'].e],
                          output_shape=[target['height'], target['width']],
                          output_sha256=checksum(temporary), counts=totals,
                          vertical_datum='WGS84 ellipsoid (source datum explicitly confirmed by user)',
                          resampling='bilinear', mask_rule='all_touched ADD polygons',
                          ocean_rule='replace ALL pixels outside ADD with EGM96 undulation',
                          validation='all output pixels finite; no missing land/shelf pixels on target grid',
                          snap_validated=False)
        record.write_text(json.dumps(provenance, indent=2) + '\n')
        os.replace(temporary, output)
        logger.info('%s', json.dumps(dict(output=str(output), provenance=str(record), **totals), indent=2))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@logged_step
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'geoid', 'config', 'output'):
        parser.add_argument('--'+name, required=True, type=Path)
    parser.add_argument('--confirm-ellipsoidal', required=True, action='store_true', help='Confirm source metadata says WGS84 ellipsoidal heights in metres')
    parser.add_argument('--resolution-deg', nargs=2, required=True, type=float, metavar=('LON', 'LAT'))
    parser.add_argument('--mask-bounds', nargs=4, required=True, type=float, metavar=('W', 'S', 'E', 'N'), help='Geographic clip bounds used to prepare the ADD mask, NOT polygon envelope')
    parser.add_argument('--bounds', nargs=4, type=float, help='Output W,S,E,N; defaults to configured region bbox')
    add_logging_arguments(parser)
    args = parser.parse_args()
    setup_from_args(args, 'prepare_dem')
    prepare(args.source, args.geoid, args.config, args.output,
            args.resolution_deg, args.mask_bounds, args.bounds)


if __name__ == '__main__':
    main()
