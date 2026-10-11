"""Deterministic, explicitly synthetic local demonstration; never real Davis ice."""
import logging
from afiw.core.logging import logged_workflow

from pathlib import Path
from dataclasses import replace
import numpy as np
import rasterio
from rasterio.transform import from_origin
from pyproj import Transformer
from afiw.core.types import WorkflowSpec,RunSpec,RegionSpec,ProcessingSpec,SegmentationSpec
from afiw.processing.raster import profile
from .primary import PrimaryWorkflow

logger = logging.getLogger(__name__)

@logged_workflow
def run_demo(root):
    root=Path(root).resolve();raw=root/'synthetic_inputs';raw.mkdir(parents=True,exist_ok=True)
    x,y=Transformer.from_crs(4326,3031,always_xy=True).transform(77.9689,-68.5762)
    grid=dict(crs='EPSG:3031',transform=from_origin(x-12800,y+12800,100,100),width=256,height=256)
    rng=np.random.default_rng(20211010);a=rng.normal(-15,2,(256,256)).astype('float32');b=a.copy()
    b[:,128:]=rng.normal(-15,2,(256,128));a[:10]=np.nan;b[:10]=np.nan
    paths=[]
    for arr,name in [(a,'scene_20211010_db.tif'),(b,'scene_20211022_db.tif')]:
        p=raw/name
        with rasterio.open(p,'w',**profile(grid)) as dst:dst.write(arr,1)
        paths.append(p)
    # Frame the small synthetic raster rather than the full Davis AOI.
    from rasterio.warp import transform_bounds
    from rasterio.transform import array_bounds
    bounds=transform_bounds(grid['crs'],'EPSG:4326',*array_bounds(256,256,grid['transform']),densify_pts=21)
    region=RegionSpec(bbox=bounds)
    spec=WorkflowSpec(root=str(root),run=RunSpec(region=region),processing=ProcessingSpec(resolution_m=100,windows=(5,9,13),tile_size=64),segmentation=SegmentationSpec(downsample=2,n_segments=120))
    return PrimaryWorkflow(spec).from_rasters(*paths,first_time='2021-10-10T00:00:00Z',second_time='2021-10-22T00:00:00Z',synthetic=True,grid_override=grid)
