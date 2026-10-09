import numpy as np
import pytest
from scipy.ndimage import uniform_filter,generic_filter
from afiw.processing.texture import normprod_smovar,rgb_texture

def test_legacy_interior_formula():
    rng=np.random.default_rng(3);a=rng.normal(size=(63,71));b=.8*a+.2*rng.normal(size=a.shape);w=5
    ma=uniform_filter(a,w,mode='nearest');mb=uniform_filter(b,w,mode='nearest')
    sa=np.sqrt(np.maximum(uniform_filter(a*a,w,mode='nearest')-ma*ma,0));sb=np.sqrt(np.maximum(uniform_filter(b*b,w,mode='nearest')-mb*mb,0))
    # Independent, slow reference follows the original notebook product averaging.
    numerator=generic_filter((a-ma)*(b-mb),np.nanmean,size=w,mode='constant',cval=np.nan)
    denominator=uniform_filter(((sa+sb)/2)**2,w,mode='nearest')
    actual=normprod_smovar(a,b,w)
    np.testing.assert_allclose(actual[10:-10,10:-10],(numerator/denominator)[10:-10,10:-10],rtol=1e-6,atol=1e-6)

def test_missing_and_constant_data_are_unknown():
    a=np.ones((30,30));assert np.isnan(normprod_smovar(a,a,5)).all()
    rng=np.random.default_rng(2);a=rng.normal(size=(30,30));a[10:20,10:20]=np.nan
    out=normprod_smovar(a,a,5);assert np.isnan(out[10:20,10:20]).all();assert np.isfinite(out[3,3])

def test_rgb_clips_instead_of_wrapping():
    stack=np.array([[[-1,2,np.nan]]]*3)
    rgb,valid=rgb_texture(stack);assert (rgb[0,0]==0).all();assert (rgb[0,1]==255).all();assert not valid[0,2]
