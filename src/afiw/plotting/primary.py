from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from skimage.segmentation import mark_boundaries

PALETTE=np.full((256,3),255,dtype=np.uint8)
PALETTE[0]=[15,35,48];PALETTE[1]=[88,94,99];PALETTE[2]=[68,218,100];PALETTE[3]=[240,170,40]

def primary_figure(rgb,segments,path,title,classes=None,grid=None):
    note=''
    if grid is not None:
        from pyproj import Transformer,CRS
        from rasterio.warp import transform_bounds,reproject,Resampling
        from rasterio.transform import from_bounds,array_bounds
        x,y=grid['transform']*(grid['width']/2,grid['height']/2)
        lon,lat=Transformer.from_crs(grid['crs'],4326,always_xy=True).transform(x,y)
        local=CRS.from_proj4(f'+proj=stere +lat_0=-90 +lat_ts=-71 +lon_0={lon} +datum=WGS84 +units=m')
        b=transform_bounds(grid['crs'],local,*array_bounds(grid['height'],grid['width'],grid['transform']),densify_pts=21)
        res=abs(grid['transform'].a);w=int(np.ceil((b[2]-b[0])/res));h=int(np.ceil((b[3]-b[1])/res));dt=from_bounds(*b,w,h)
        def warp(a,fill):
            dst=np.full((h,w),fill,dtype=a.dtype)
            reproject(a,dst,src_transform=grid['transform'],src_crs=grid['crs'],dst_transform=dt,dst_crs=local,dst_nodata=fill,resampling=Resampling.nearest)
            return dst
        # Plotting-only reprojection: persisted georeferenced labels stay unchanged.
        padding=warp(np.ones(rgb.shape[:2],np.uint8),0)==0
        rgb=np.stack([warp(rgb[:,:,k],0) for k in range(3)],axis=-1);rgb[padding]=255
        segments=warp(segments,0)
        if classes is not None:classes=warp(classes,255)
        note=f'North aligned at centre ({lon:.2f}°E). '
    fig,ax=plt.subplots(1,2,figsize=(10,5.6))
    ax[0].imshow(rgb);ax[0].set_title('a) composite SAR',loc='left')
    if classes is None:
        ax[1].imshow(mark_boundaries(rgb,segments,color=(0,.9,.5),mode='thin'));ax[1].set_title('b) segmentation (not ice classes)',loc='left')
    else:
        ax[1].imshow(PALETTE[classes]);ax[1].set_title('b) candidate ice classification',loc='left')
    for a in ax:a.axis('off')
    fig.suptitle(title,fontsize=11)
    fig.text(.5,.03,note+'RESEARCH DEMONSTRATION | NOT FOR OPERATIONAL USE',ha='center',color='red',fontsize=9)
    fig.tight_layout(rect=(0,.055,1,.96));fig.savefig(path,dpi=180);plt.close(fig);return Path(path)
