from dataclasses import replace
import numpy as np
import rasterio
from rasterio.transform import from_origin
from afiw.processing.raster import texture_raster,profile,align_raster
from afiw.processing.texture import normprod_smovar
from afiw.core.types import ProcessingSpec

def test_tiling_matches_full_array(tmp_path):
    rng=np.random.default_rng(9);a=rng.normal(size=(101,117)).astype('float32');b=(a*.8+rng.normal(size=a.shape)*.2).astype('float32')
    a[25:40,43:60]=np.nan;b[25:40,43:60]=np.nan
    g=dict(crs='EPSG:3031',transform=from_origin(2000000,1000000,40,40),width=117,height=101)
    files=[]
    for k,img in enumerate([a,b]):
        p=tmp_path/f'{k}.tif'
        with rasterio.open(p,'w',**profile(g)) as dst:dst.write(img,1)
        files.append(p)
    cfg=ProcessingSpec(windows=(5,9,13),tile_size=32)
    out=texture_raster(*files,tmp_path/'out.tif',cfg)
    with rasterio.open(out) as src:
        for i,w in enumerate(cfg.windows,1):np.testing.assert_allclose(src.read(i),normprod_smovar(a,b,w),atol=2e-6,rtol=2e-6,equal_nan=True)

def test_alignment_preserves_validity_and_converts_power(tmp_path):
    a=np.full((32,32),.01,np.float32);a[:5]=np.nan
    g=dict(crs='EPSG:3031',transform=from_origin(2000000,1000000,40,40),width=32,height=32)
    p=tmp_path/'src.tif'
    with rasterio.open(p,'w',**profile(g)) as dst:dst.write(a,1)
    out=align_raster(p,tmp_path/'out.tif',g,input_units='linear_power')
    with rasterio.open(out) as src:
        b=src.read(1);assert np.isnan(b[:5]).all();np.testing.assert_allclose(b[5:],-20,atol=1e-5)
