import numpy as np
from afiw.metrics.change import change_metrics

def test_missing_swath_is_not_retreat():
    old=np.array([[2,2,0,2],[0,1,3,255]],np.uint8);new=np.array([[255,0,2,2],[0,1,2,2]],np.uint8)
    change,m=change_metrics(old,new,np.ones(old.shape))
    assert m['gain_km2']==1;assert m['loss_km2']==1;assert m['persistent_km2']==2;assert m['common_ocean_km2']==5
    assert change[0,0]==255;assert change[1,1]==255;assert change[1,3]==255
