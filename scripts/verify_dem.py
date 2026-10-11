"""Inspect DEM metadata and sample ADD land/shelf versus ocean coverage."""
import logging
from afiw.core.logging import add_logging_arguments, setup_from_args, logged_step
import argparse
import json
from pathlib import Path
import numpy as np
import rasterio
from rasterio.vrt import WarpedVRT
from rasterio.warp import Resampling, transform_bounds
from dem_utils import checksum, exclusions, grid, land_mask

logger = logging.getLogger('afiw.scripts.verify_dem')


@logged_step
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--samples', type=int, default=1200, help='Longest sample grid dimension')
    parser.add_argument('--report', type=Path, help='Optional JSON report')
    add_logging_arguments(parser)
    args = parser.parse_args()
    setup_from_args(args, 'verify_dem')
    if not 2 <= args.samples <= 10000:
        parser.error('--samples must be between 2 and 10000')
    spec, shapes = exclusions(args.config)
    bounds = spec.run.region.bbox
    spacing = max(bounds[2]-bounds[0], bounds[3]-bounds[1]) / args.samples
    target = grid(bounds, (spacing, spacing))
    with rasterio.open(args.source) as src:
        if not src.crs or src.count != 1:
            raise ValueError('Expected a single-band DEM with declared horizontal CRS')
        report = dict(source=str(args.source.resolve()), sha256=checksum(args.source),
                      crs=str(src.crs), bounds=list(src.bounds), resolution=list(src.res),
                      shape=list(src.shape), bands=src.count, dtype=src.dtypes[0],
                      nodata=src.nodata, tags=src.tags(), band_tags=src.tags(1),
                      geographic_bounds=list(transform_bounds(src.crs, 'EPSG:4326', *src.bounds, densify_pts=41)),
                      aoi_bounds=list(bounds), sample_shape=[target['height'], target['width']],
                      coverage_method='nearest-neighbour sample; not a full-resolution check')
        with WarpedVRT(src, **target, resampling=Resampling.nearest, nodata=-9999) as vrt:
            data = vrt.read(1, masked=True)
    land = land_mask(shapes, data.shape, target['transform'])
    valid = ~np.ma.getmaskarray(data) & np.isfinite(data.data)
    report['coverage'] = {}
    for label, mask in [('ADD land/shelf', land), ('Ocean outside ADD', ~land)]:
        total = int(mask.sum())
        missing = int((mask & ~valid).sum())
        report['coverage'][label] = dict(samples=total, missing=missing,
                                       missing_percent=100*missing/total if total else None)
    values = data.data[valid]
    report['elevation_percentiles_min_1_50_99_max'] = np.percentile(values, [0, 1, 50, 99, 100]).tolist() if values.size else []
    logger.info('%s', json.dumps(report, indent=2, allow_nan=False))
    if args.report:
        if args.report.exists():
            raise FileExistsError(args.report)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
