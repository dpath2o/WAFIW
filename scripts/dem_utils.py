"""Shared DEM helpers. Raster reprojection changes horizontal coordinates only."""
from pathlib import Path
import hashlib
import math
import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.transform import from_origin
from afiw.core.types import WorkflowSpec
from afiw.processing.raster import load_exclusions


def checksum(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def grid(bounds, resolution):
    w, s, e, n = bounds
    dx, dy = resolution
    if not all(math.isfinite(v) for v in (*bounds, dx, dy)):
        raise ValueError('Bounds and spacing must be finite')
    if not (-180 < w < e < 180 and -90 < s < n < 90 and dx > 0 and dy > 0):
        raise ValueError('Invalid regional bounds or angular spacing')
    width, height = math.ceil((e-w)/dx), math.ceil((n-s)/dy)
    # Adjust spacing to preserve the requested outer bounds exactly.
    return dict(crs='EPSG:4326', width=width, height=height,
                transform=from_origin(w, n, (e-w)/width, (n-s)/height))


def exclusions(config):
    spec = WorkflowSpec.load(config)
    if not spec.coastline:
        raise ValueError('Config needs a prepared ADD polygon coastline')
    return spec, load_exclusions(spec.coastline, 'EPSG:4326')


def land_mask(shapes, shape, transform):
    return rasterize(shapes, out_shape=shape, transform=transform,
                     all_touched=True).astype(bool)


def combine(terrain, geoid, land):
    terrain_valid = ~np.ma.getmaskarray(terrain) & np.isfinite(terrain.data)
    geoid_valid = ~np.ma.getmaskarray(geoid) & np.isfinite(geoid.data)
    missing_land = int(np.count_nonzero(land & ~terrain_valid))
    if missing_land:
        raise ValueError(f'{missing_land} missing land/shelf pixels in output block; do not ocean-fill them')
    if np.any(~land & ~geoid_valid):
        raise ValueError('Geoid does not cover all ocean pixels')
    return np.where(land, terrain.data, geoid.data).astype('float32')
