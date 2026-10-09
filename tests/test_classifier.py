import numpy as np
import pytest
from afiw.classify.svm import SegmentClassifier

def test_model_roundtrip_and_unknowns(tmp_path):
    rgb=np.zeros((20,20,3),np.uint8);rgb[:10]=30;rgb[10:]=220
    segments=np.ones((20,20),np.uint32);segments[10:]=2
    classes=np.zeros((20,20),np.uint8);classes[10:]=2
    clf=SegmentClassifier.train(rgb,segments,classes,{'region':'Davis','synthetic':True})
    loaded=SegmentClassifier.load(clf.save(tmp_path/'model.joblib'))
    valid=np.ones((20,20),bool);valid[0]=False;mask=np.zeros((20,20),bool);mask[:,0]=True
    result=loaded.predict(rgb,segments,valid,mask)
    assert (result[5,1:]==0).all();assert (result[15,1:]==2).all();assert (result[0,1:]==255).all();assert (result[:,0]==1).all()
    assert not loaded.metadata['validated']
    with pytest.raises(ValueError):SegmentClassifier.train(rgb,segments,np.zeros_like(classes))
