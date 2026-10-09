import json
from dataclasses import replace
from pathlib import Path
import numpy as np
import pytest
from afiw.workflows.demo import run_demo
from afiw.products.bulletin import BulletinBuilder,escape_latex,available_manifests
from afiw.processing.snap import SnapPreprocessor
from afiw.core.types import SnapSpec,ProcessingSpec,RegionSpec,WorkflowSpec
from afiw.classify.segmentation import Segmenter
from afiw.core.types import SegmentationSpec

def test_demo_bulletin_never_claims_observed_ice(tmp_path):
    result=run_demo(tmp_path/'data');d=json.loads(result.manifest.read_text())
    assert d['synthetic'];assert d['status']=='segmentation_only';assert not d['metrics'];assert result.classification is None
    assert d['segmentation_pixel_size_m']==[200,200]
    output=BulletinBuilder(tmp_path/'data').build('2021-10-24',tmp_path/'bulletin')
    assert output.is_file();data=json.loads((output.parent/'bulletin.json').read_text());assert 'SYNTHETIC TEST DATA' in data['summary']
    assert not available_manifests(tmp_path/'data','Davis','2021-10-11')

def test_snap_graph_keeps_sea_and_requires_dem(tmp_path):
    cfg=SnapSpec();proc=ProcessingSpec();reg=RegionSpec()
    with pytest.raises(FileNotFoundError):SnapPreprocessor(cfg,proc,reg).graph('a.zip','b.tif')
    dem=tmp_path/'dem.tif';dem.touch();cfg=replace(cfg,dem_path=str(dem))
    xml=SnapPreprocessor(cfg,proc,reg).graph('space & name.zip','b.tif')
    import xml.etree.ElementTree as ET
    root=ET.fromstring(xml);assert root.find(".//nodataValueAtSea").text=='false'
    assert root.find(".//operator[.='Terrain-Flattening']") is not None
    assert '&amp;' in xml

def test_sam_without_checkpoint_fails():
    with pytest.raises(FileNotFoundError):Segmenter(SegmentationSpec(backend='sam')).segment(np.zeros((32,32,3),np.uint8),np.ones((32,32),bool))

def test_config_resolves_paths_relative_to_config(tmp_path):
    config=tmp_path/'settings.yaml';config.write_text('root: ../data\ncoastline: coast.geojson\n')
    cfg=WorkflowSpec.load(config);assert Path(cfg.root)==tmp_path.parent/'data';assert Path(cfg.coastline)==tmp_path/'coast.geojson'
    assert escape_latex('a_b & c%')==r'a\_b \& c\%'
