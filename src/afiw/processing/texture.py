"""Research boxcar NormProd_SmoVar, with explicit masks and numerical guards.

On fully valid data, the interior formula follows process_image_pairs.py:
mean[(I1-mean(I1))*(I2-mean(I2))] /
mean[((std(I1)+std(I2))/2)**2].
Missing pixels use local weighted means instead of scene-wide mean filling.
RGB rendering clips [-0.5,1] instead of wrapping uint8 values.
"""
import numpy as np
from scipy.ndimage import uniform_filter

def masked_mean(a, width, *, mode='nearest', min_fraction=.8):
    valid=np.isfinite(a); a=np.where(valid,a,0).astype(np.float64)
    count=uniform_filter(valid.astype(float),size=width,mode=mode,cval=0)
    total=uniform_filter(a,size=width,mode=mode,cval=0)
    out=np.full(a.shape,np.nan)
    np.divide(total,count,out=out,where=(count>=min_fraction)&(count>0))
    return out

def normprod_smovar(a,b,width,min_fraction=.8):
    a=np.asarray(a,dtype=float);b=np.asarray(b,dtype=float)
    if a.ndim!=2 or a.shape!=b.shape: raise ValueError('Require equal 2D arrays')
    if width<3 or width%2==0: raise ValueError('Odd window >=3 required')
    ma=masked_mean(a,width,min_fraction=min_fraction);mb=masked_mean(b,width,min_fraction=min_fraction)
    va=np.maximum(masked_mean(a*a,width,min_fraction=min_fraction)-ma*ma,0)
    vb=np.maximum(masked_mean(b*b,width,min_fraction=min_fraction)-mb*mb,0)
    stdmean=(np.sqrt(va)+np.sqrt(vb))/2
    num=masked_mean((a-ma)*(b-mb),width,mode='constant',min_fraction=min_fraction)
    den=masked_mean(stdmean**2,width,min_fraction=min_fraction)
    out=np.full(a.shape,np.nan,dtype=np.float32)
    np.divide(num,den,out=out,where=np.isfinite(num)&np.isfinite(den)&(den>1e-12))
    out[~np.isfinite(a)|~np.isfinite(b)]=np.nan
    return out

def rgb_texture(stack):
    stack=np.asarray(stack)
    if stack.ndim!=3 or stack.shape[0]!=3:raise ValueError('Expected 3,H,W texture stack')
    valid=np.all(np.isfinite(stack),axis=0)
    clipped=np.clip((np.nan_to_num(stack,nan=-.5)+.5)/1.5,0,1)
    rgb=np.moveaxis(np.rint(clipped*255).astype(np.uint8),0,-1)
    rgb[~valid]=0
    return rgb,valid
