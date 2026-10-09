"""Deterministic presentation rendering. Inputs: original supplied TIFF and RGB NPY.
Run: python render_fastice.py INPUT_DIRECTORY OUTPUT_DIRECTORY
"""
import sys
from pathlib import Path
import numpy as np
import rasterio
from rasterio.transform import from_bounds
from rasterio.warp import reproject, Resampling
from pyproj import CRS, Transformer
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import patheffects

srcdir, outdir=map(Path,sys.argv[1:]); outdir.mkdir(parents=True,exist_ok=True)
rgb=np.load(srcdir/'rgb_image_20211010_20211022.npy')
with rasterio.open(srcdir/'predicted_map_20211010_20211022.tif') as src:
    cls=src.read(1,out_shape=rgb.shape[:2],resampling=Resampling.nearest)
    bounds=src.bounds; crs=src.crs
h,w=cls.shape
st=from_bounds(*bounds,w,h)
local=CRS.from_proj4('+proj=stere +lat_0=-90 +lat_ts=-71 +lon_0=173.51759 +datum=WGS84 +units=m +no_defs')
tr=Transformer.from_crs(crs,local,always_xy=True)
xs,ys=tr.transform([bounds.left,bounds.right,bounds.right,bounds.left],[bounds.bottom,bounds.bottom,bounds.top,bounds.top])
# Slight trim of the western boundary only: 12 km. Keep full southern extent.
left,right=min(xs)+12000,max(xs); bottom,top=min(ys),max(ys)
W=int(np.ceil((right-left)/400)); H=int(np.ceil((top-bottom)/400))
dt=from_bounds(left,bottom,right,top,W,H)
def warp(arr,fill,method):
    dst=np.full((H,W),fill,dtype=arr.dtype)
    reproject(arr,dst,src_transform=st,src_crs=crs,dst_transform=dt,dst_crs=local,dst_nodata=fill,resampling=method)
    return dst
c=warp(cls,254,Resampling.nearest)
r=np.stack([warp(rgb[:,:,i],0,Resampling.bilinear) for i in range(3)],axis=-1)
# Grey is a masked category, not a verified coastline: the source includes land
# and out-of-swath masking in class 1. Reprojection padding is white.
r[c==1]=[88,94,99]; r[c==254]=255
palette=np.zeros((256,3),dtype=np.uint8); palette[0]=[15,35,48]; palette[1]=[88,94,99]; palette[2]=[68,218,100]; palette[3]=[245,160,50]; palette[254:]=255
b=palette[c]
np.save(outdir/'display_classes.npy',c)
# Positions in this local projection are set using named geographic locations.
geog=Transformer.from_crs('EPSG:4326',local,always_xy=True)
def coord(lon,lat):return geog.transform(lon,lat)
# SCAR ADD v7.12 contextual land outlines; these do not change ice classes.
import json
from shapely.geometry import shape, box
from shapely.ops import transform as geom_transform
coast=json.loads((outdir/'ADD_coastline_subset_EPSG3031.geojson').read_text())
ct=Transformer.from_crs('EPSG:3031',local,always_xy=True)
source_box=box(*bounds)
lines=[]
for f in coast['features']:
    if f['properties']['surface']!='land': continue
    # Omit artificial edges introduced by clipping to the raster rectangle.
    boundary=shape(f['geometry']).boundary.difference(source_box.boundary.buffer(150))
    lines.append(geom_transform(ct.transform,boundary))
def draw_lines(ax,g):
    if g.geom_type=='LineString':
        x,y=g.xy; ax.plot(x,y,color='white',lw=.6,alpha=.7)
    elif hasattr(g,'geoms'):
        for child in g.geoms: draw_lines(ax,child)
fig,axes=plt.subplots(1,2,figsize=(12,6.35))
for ax,im,title in zip(axes,[r,b],['a) composite SAR','b) classification']):
    ax.imshow(im,extent=(left,right,bottom,top)); ax.set_xlim(left,right); ax.set_ylim(bottom,top); ax.axis('off'); ax.set_title(title,loc='left',fontsize=13,pad=7)
    for text,lon,lat in [('Ross Sea',177,-76.0),('Ross Ice Shelf',176,-78.6)]:
        x,y=coord(lon,lat); ax.text(x,y,text,color='white',fontsize=12,ha=('left' if text=='Victoria Land' else 'center'),rotation=0,path_effects=[patheffects.withStroke(linewidth=2,foreground='#26333a')])
    for g in lines: draw_lines(ax,g)
    for name,lon,lat,tlon,tlat in [('Minna Bluff',166.41667,-78.51667,171,-78.7),('Ross Island',167.5,-77.5,173,-77.7)]:
        px,py=coord(lon,lat); tx,ty=coord(tlon,tlat)
        ax.plot(px,py,'o',color='white',ms=2)
        ax.annotate(name,xy=(px,py),xytext=(tx,ty),color='white',fontsize=10,ha='center',va='center',path_effects=[patheffects.withStroke(linewidth=2,foreground='#26333a')],arrowprops=dict(arrowstyle='-',color='white',lw=.65,alpha=.7))
    # Grid north equals true north on the central meridian.
    x=0;y=top-85000
    ax.annotate('',xy=(x,y+40000),xytext=(x,y),arrowprops={'arrowstyle':'-|>','color':'white','lw':1.8})
    ax.text(x,y+47000,'N',ha='center',color='white',fontsize=11,path_effects=[patheffects.withStroke(linewidth=2,foreground='#26333a')])
# Attach callout to a northern component using the actual class-2 pixels.
from scipy.ndimage import label
labs,n=label(c==2); groups=[]
for k in range(1,n+1):
    yy,xx=np.where(labs==k)
    if len(xx)>150: groups.append((yy.mean(),xx.mean(),len(xx)))
groups.sort()
yy,xx,size=groups[0]
target=(left+(xx+.5)*(right-left)/W,top-(yy+.5)*(top-bottom)/H)
x,y=coord(177,-77.05)
axes[1].annotate('candidate landfast\nsea ice (green)',xy=target,xytext=(x,y),ha='center',va='center',fontsize=10,color='white',bbox=dict(boxstyle='round,pad=.45',facecolor='#183446',edgecolor='white',alpha=.96),arrowprops=dict(arrowstyle='->',color='white',lw=1.7,connectionstyle='arc3,rad=.15'))
fig.subplots_adjust(left=.01,right=.99,top=.92,bottom=.09,wspace=.035)
fig.text(.5,.038,'10–22 October 2021  |  North aligned at centre (173.52°E)  |  Grey: masked land / out-of-swath areas',ha='center',fontsize=9)
fig.text(.5,.014,'Faint lines: grounded-land outlines — SCAR Antarctic Digital Database, 2026 (contextual reference)',ha='center',fontsize=8)
fig.savefig(outdir/'fastice_texture_and_segmentation_20211010_20211022.png',dpi=220,facecolor='white')
for im,name in [(r,'composite_SAR_20211010_20211022'),(b,'classification_20211010_20211022')]:
    from PIL import Image
    Image.fromarray(im).save(outdir/(name+'.png'))
print('Output:',W,H,'northern component:',target,'classes:',np.unique(c))
