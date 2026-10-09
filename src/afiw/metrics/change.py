"""Common-coverage change metrics; unknown cells never count as ice retreat."""
import numpy as np
from pyproj import Proj,Transformer
from affine import Affine

def cell_areas_km2(shape,transform,crs):
    if not crs.is_projected:raise ValueError('Metrics require a projected CRS')
    yy,xx=np.indices(shape);x=transform.c+(xx+.5)*transform.a+(yy+.5)*transform.b;y=transform.f+(xx+.5)*transform.d+(yy+.5)*transform.e
    lon,lat=Transformer.from_crs(crs,4326,always_xy=True).transform(x,y)
    factors=Proj(crs).get_factors(lon,lat)
    projected=abs(transform.a*transform.e-transform.b*transform.d)/1e6
    return projected/np.asarray(factors.areal_scale) # centre-point projection-scale correction

def extent_metrics(classes,areas):
    valid=np.isin(classes,[0,2,3]);fast=np.isin(classes,[2,3])
    return {'candidate_fast_ice_km2':float(areas[fast].sum()),'observed_ocean_km2':float(areas[valid].sum()),'unknown_pixels':int((classes==255).sum()),'area_method':'pixel-centre projection scale correction','fast_classes':[2,3]}

def change_metrics(previous,current,areas):
    if previous.shape!=current.shape or previous.shape!=areas.shape:raise ValueError('Change maps require matching grids')
    common=np.isin(previous,[0,2,3])&np.isin(current,[0,2,3]);old=np.isin(previous,[2,3]);new=np.isin(current,[2,3])
    gain=common&~old&new;loss=common&old&~new;persist=common&old&new
    # 0 unchanged ocean;1 persistent ice;2 gain;3 loss;255 unavailable.
    change=np.full(current.shape,255,np.uint8);change[common]=0;change[persist]=1;change[gain]=2;change[loss]=3
    return change,{'common_ocean_km2':float(areas[common].sum()),'gain_km2':float(areas[gain].sum()),'loss_km2':float(areas[loss].sum()),'persistent_km2':float(areas[persist].sum()),'net_change_km2':float(areas[gain].sum()-areas[loss].sum())}
