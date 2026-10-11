import logging
from afiw.core.logging import logged_step

from pathlib import Path
import math,json
from contextlib import ExitStack
import numpy as np
import rasterio
from rasterio.windows import Window
from rasterio.transform import from_origin,from_bounds
from rasterio.warp import transform_bounds,Resampling
from rasterio.vrt import WarpedVRT
from rasterio.features import rasterize
from pyproj import Transformer
from shapely.geometry import shape,mapping
from shapely.ops import transform as geom_transform
from .texture import normprod_smovar

logger = logging.getLogger(__name__)


@logged_step
def grid_for_region(region,processing):
    b=transform_bounds('EPSG:4326',processing.crs,*region.bbox,densify_pts=41)
    r=processing.resolution_m;left=math.floor(b[0]/r)*r;top=math.ceil(b[3]/r)*r
    width=math.ceil((b[2]-left)/r);height=math.ceil((top-b[1])/r)
    return dict(crs=processing.crs,transform=from_origin(left,top,r,r),width=width,height=height)

def profile(grid,count=1,dtype='float32',nodata=np.nan):
    return dict(driver='GTiff',**grid,count=count,dtype=dtype,nodata=nodata,compress='deflate',tiled=True,blockxsize=256,blockysize=256,BIGTIFF='IF_SAFER')

def tiles(width,height,size):
    for y in range(0,height,size):
        for x in range(0,width,size):yield Window(x,y,min(size,width-x),min(size,height-y))

@logged_step
def align_raster(source,destination,grid,tile_size=512,input_units='db'):
    logger.info('Aligning raster: %s -> %s; CRS=%s shape=%sx%s input units=%s', source, destination, grid['crs'], grid['height'], grid['width'], input_units)
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    temp=destination.with_suffix('.partial.tif')
    with rasterio.open(source) as src:
        if src.crs is None:raise ValueError('Raster CRS is missing')
        if src.count!=1:raise ValueError('Select a single co-polar backscatter band first')
        with WarpedVRT(src,**grid,dtype='float32',nodata=np.nan,resampling=Resampling.bilinear) as vrt,rasterio.open(temp,'w',**profile(grid)) as dst:
            for index, win in enumerate(tiles(grid['width'],grid['height'],tile_size), 1):
                if index == 1 or index % 25 == 0:
                    logger.info('Alignment tile %s/%s', index, math.ceil(grid['width'] / tile_size) * math.ceil(grid['height'] / tile_size))
                logger.debug('Alignment tile window=%s', win)
                a=vrt.read(1,window=win,masked=True).filled(np.nan)
                if input_units=='linear_power':
                    a=np.where(a>0,a,np.nan)
                    with np.errstate(invalid='ignore'):a=10*np.log10(a)
                dst.write(a.astype('float32'),1,window=win)
            dst.set_band_description(1,'co-polar backscatter dB')
    temp.replace(destination);return destination

@logged_step
def load_exclusions(path,target_crs):
    """Require CRS-bearing ADD-style GeoJSON; exclude land AND floating shelf."""
    if not path: return []
    d=json.loads(Path(path).read_text());crs=d.get('crs',{}).get('properties',{}).get('name','EPSG:4326')
    tr=Transformer.from_crs(crs,target_crs,always_xy=True)
    shapes=[]
    for f in d['features']:
        surface=f.get('properties',{}).get('surface')
        if surface not in ('land','ice shelf','ice tongue','rumple'):continue
        g=shape(f['geometry']);g=geom_transform(tr.transform,g)
        if not g.is_valid:raise ValueError('Invalid coastline geometry; repair/review source first')
        shapes.append((mapping(g),1))
    if not shapes:raise ValueError('No ADD surface polygons found in coastline file')
    return shapes

def exclusion_mask(shapes,grid,window=None):
    if window is None:height,width=grid['height'],grid['width'];transform=grid['transform']
    else:
        height,width=int(window.height),int(window.width);transform=rasterio.windows.transform(window,grid['transform'])
    if not shapes:return np.zeros((height,width),bool)
    return rasterize(shapes,out_shape=(height,width),transform=transform,fill=0,dtype='uint8').astype(bool)

@logged_step
def texture_raster(first,second,destination,processing,coastline=None):
    logger.info('Texture: %s and %s -> %s; windows=%s tile size=%s min valid fraction=%s coastline=%s', first, second, destination, processing.windows, processing.tile_size, processing.min_valid_fraction, coastline)
    destination=Path(destination);temp=destination.with_suffix('.partial.tif')
    with ExitStack() as ctx:
        a=ctx.enter_context(rasterio.open(first));b=ctx.enter_context(rasterio.open(second))
        if (a.crs,a.transform,a.shape)!=(b.crs,b.transform,b.shape):raise ValueError('Pair must have identical grids')
        grid={k:getattr(a,k) for k in ['crs','transform','width','height']}
        shapes=load_exclusions(coastline,a.crs)
        dst=ctx.enter_context(rasterio.open(temp,'w',**profile(grid,count=3)))
        halo=2*(max(processing.windows)//2)
        for index, win in enumerate(tiles(a.width,a.height,processing.tile_size), 1):
            if index == 1 or index % 25 == 0:
                logger.info('Texture tile %s/%s', index, math.ceil(a.width / processing.tile_size) * math.ceil(a.height / processing.tile_size))
            logger.debug('Texture tile window=%s halo=%s', win, halo)
            x,y=int(win.col_off),int(win.row_off);x0=max(0,x-halo);y0=max(0,y-halo)
            x1=min(a.width,x+int(win.width)+halo);y1=min(a.height,y+int(win.height)+halo)
            expanded=Window(x0,y0,x1-x0,y1-y0)
            aa=a.read(1,window=expanded,masked=True).filled(np.nan);bb=b.read(1,window=expanded,masked=True).filled(np.nan)
            excluded=exclusion_mask(shapes,grid,expanded);aa[excluded]=np.nan;bb[excluded]=np.nan
            ys=slice(y-y0,y-y0+int(win.height));xs=slice(x-x0,x-x0+int(win.width))
            for band,width in enumerate(processing.windows,1):
                value=normprod_smovar(aa,bb,width,processing.min_valid_fraction)
                dst.write(value[ys,xs],band,window=win)
                dst.set_band_description(band,f'NormProd_SmoVar window={width}')
        dst.update_tags(method='boxcar_normprod_smovar',mask_policy='local_valid_weighting',coastline=str(coastline or 'NOT PROVIDED'))
    temp.replace(destination);return destination
