"""Real GIS/PyGMT integration using explicitly synthetic labelled products."""
import json
from pathlib import Path
import numpy as np
import pytest
import rasterio
from rasterio.enums import ColorInterp
from rasterio.transform import from_origin, from_bounds, array_bounds
from rasterio.warp import transform_bounds
from pyproj import Transformer
from afiw.core.types import WorkflowSpec, RunSpec, RegionSpec
from afiw.core.provenance import write_json
from afiw.processing.raster import profile
from afiw.processing.texture import rgb_texture
from afiw.plotting.primary import export_composite, require_pygmt, PALETTE
from afiw.workflows.maps import train_from_manifest, render_from_manifest, check_classifier
from afiw.classify.svm import SegmentClassifier
from afiw.products.bulletin import BulletinBuilder


@pytest.fixture
def product(tmp_path):
    directory = tmp_path / 'source'
    directory.mkdir()
    x, y = Transformer.from_crs(4326, 3031, always_xy=True).transform(77.9689, -68.5762)
    grid = dict(crs='EPSG:3031', transform=from_origin(x-6400,y+6400,200,200), width=64,height=64)
    bounds = array_bounds(64,64,grid['transform'])
    bbox = transform_bounds(3031,4326,*bounds,densify_pts=21)
    seg_grid = dict(crs='EPSG:3031', transform=from_bounds(*bounds,32,32),width=32,height=32)
    texture = np.full((3,64,64), -0.3, np.float32)
    texture[:,32:] = 0.8
    texture[:,:2] = np.nan
    with rasterio.open(directory/'texture.tif','w',**profile(grid,count=3)) as dst:
        dst.write(texture)
    rgb, valid = rgb_texture(texture[:,::2,::2])
    labels = np.ones((32,32),np.uint32)
    labels[16:] = 2
    labels[~valid] = 0
    validity = valid.astype('uint8')
    validity[:,-2:] = 2
    labels[:,-2:] = 0
    np.save(directory/'rgb.npy',rgb)
    for values,name in [(labels,'segments.tif'),(validity,'validity.tif')]:
        with rasterio.open(directory/name,'w',**profile(seg_grid,dtype=str(values.dtype),nodata=None)) as dst:
            dst.write(values,1)
    # Native CRS polygon for land/shelf exclusion, independent of out-of-swath.
    left,bottom,right,top = bounds
    coast = directory/'coast.geojson'
    write_json(coast, {'type':'FeatureCollection','crs':{'type':'name','properties':{'name':'EPSG:3031'}},'features':[
        {'type':'Feature','properties':{'surface':'land'},'geometry':{'type':'Polygon','coordinates':[[[right-800,bottom],[right,bottom],[right,top],[right-800,top],[right-800,bottom]]]}}]})
    config=WorkflowSpec(run=RunSpec(region=RegionSpec(bbox=bbox)),coastline=str(coast)).as_dict()
    record=dict(region='Davis',synthetic=True,config=config,resource_hashes={},
        first_time='2021-10-02T14:39:59Z',second_time='2021-10-14T14:39:59Z',baseline_days=12,
        status='segmentation_only',mask_provided=True,metrics={},limitations=['Not validated for operational use'],
        segmentation_pixel_size_m=[400,400],valid_texture_fraction=float(valid.mean()),
        outputs={'texture':'texture.tif','segments':'segments.tif','rgb':'rgb.npy','validity':'validity.tif'})
    manifest=write_json(directory/'manifest.json',record)
    manual=np.zeros((32,32),np.uint8)
    manual[16:]=2
    manual[validity!=1]=255
    manual_path=tmp_path/'manual.tif'
    with rasterio.open(manual_path,'w',**profile(seg_grid,dtype='uint8',nodata=255)) as dst:
        dst.write(manual,1)
    return manifest, manual_path, grid, seg_grid, record


def test_composite_preserves_full_grid_and_black_valid_pixels(tmp_path):
    grid=dict(crs='EPSG:3031',transform=from_origin(0,0,40,40),width=8,height=8)
    texture=np.full((3,8,8),-.5,np.float32)
    texture[:,0]=np.nan
    source=tmp_path/'texture.tif'
    with rasterio.open(source,'w',**profile(grid,count=3)) as dst:dst.write(texture)
    path=export_composite(source,tmp_path/'composite.tif')
    with rasterio.open(path) as src:
        assert src.shape==(8,8) and src.transform==grid['transform'] and src.crs.to_epsg()==3031
        assert src.colorinterp[-1]==ColorInterp.alpha
        assert (src.read(4)[0]==0).all()
        assert (src.read(4)[1:]==255).all()  # Valid black != missing.
        assert (src.read(1)==0).all()


def test_manual_training_grid_contract_and_synthetic_guard(product,tmp_path):
    manifest, manual, _, seg_grid, record=product
    wrong=tmp_path/'wrong.tif'
    with rasterio.open(wrong,'w',**profile({**seg_grid,'transform':from_origin(0,0,400,400)},dtype='uint8',nodata=255)) as dst:
        dst.write(np.zeros((32,32),np.uint8),1)
    with pytest.raises(ValueError,match='match segments'):
        train_from_manifest(manifest,wrong,tmp_path/'bad.joblib','dummy reviewer')
    model=train_from_manifest(manifest,manual,tmp_path/'model.joblib','synthetic fixture labels')
    classifier=SegmentClassifier.load(model)
    assert not classifier.metadata['validated']
    with pytest.raises(ValueError,match='Synthetic classifier'):
        check_classifier(classifier,{**record,'synthetic':False})
    altered=json.loads(json.dumps(record))
    altered['config']['processing']['windows']=[5,9,13]
    with pytest.raises(ValueError,match='contract differs'):
        check_classifier(classifier,altered)


def test_pygmt_classification_exports_and_bulletin_only_assembly(product,tmp_path):
    require_pygmt()
    manifest,manual,full_grid,seg_grid,_=product
    model=train_from_manifest(manifest,manual,tmp_path/'model.joblib','synthetic fixture labels')
    original=manifest.read_bytes()
    derived=render_from_manifest(manifest,tmp_path/'derived',model)
    assert manifest.read_bytes()==original
    record=json.loads(derived.read_text())
    outputs=record['outputs']
    assert record['plotting_backend']=='pygmt'
    assert record['status']=='candidate_classification'
    assert 'quicklook' not in outputs and not (derived.parent/'primary.png').exists()
    with rasterio.open(derived.parent/outputs['composite_tif']) as src:
        assert src.shape==(64,64) and src.transform==full_grid['transform'] and src.count==4
    with rasterio.open(derived.parent/outputs['classification']) as src:
        assert src.shape==(32,32) and src.transform==seg_grid['transform'] and src.nodata==255
        classes=src.read(1)
        assert set(np.unique(classes))=={0,1,2,255}
        assert (classes[5,:-2]==0).all() and (classes[20,:-2]==2).all()
        assert (classes[:,-2:]==1).all() and (classes[0,:-2]==255).all()
    with rasterio.open(derived.parent/outputs['classification_rgb_tif']) as src:
        assert src.crs.to_epsg()==3031
        assert (src.read()[:3,20,4]==PALETTE[2]).all()
    for key in ('composite_png','classification_png'):
        assert (derived.parent/outputs[key]).stat().st_size>10000
    pdf=BulletinBuilder(derived.parent).build('2021-10-15',tmp_path/'bulletin')
    assert pdf.is_file() and (pdf.parent/'primary.png').exists()
    info=json.loads((pdf.parent/'bulletin.json').read_text())
    assert len(info['panel_sources'])==2 and info['panel_assembly']=='bulletin_only'
    assert not (derived.parent/'primary.png').exists()
    with pytest.raises(FileExistsError):render_from_manifest(manifest,derived.parent,model)


def test_unclassified_product_does_not_invent_classes(product,tmp_path):
    manifest,_,_,_,_=product
    derived=render_from_manifest(manifest,tmp_path/'unclassified')
    record=json.loads(derived.read_text())
    assert record['classification_available'] is False
    assert 'classification' not in record['outputs']
    assert not (derived.parent/'classification.png').exists()
    assert not (derived.parent/'classification.tif').exists()
    assert not (derived.parent/'primary.png').exists()
    assert record['metrics']=={}


def test_rerender_preserves_existing_classification(product, tmp_path):
    manifest, manual, _, _, _ = product
    model   = train_from_manifest(manifest, manual, tmp_path / 'model.joblib', 'synthetic fixture labels')
    first   = render_from_manifest(manifest, tmp_path / 'classified', model)
    second  = render_from_manifest(first, tmp_path / 'rerendered')
    record  = json.loads(second.read_text())
    assert record['classification_available']
    assert record['outputs']['classification_tif'] == record['outputs']['classification']
    for name in ('classification', 'classification_png', 'classification_rgb_tif'):
        assert (second.parent / record['outputs'][name]).is_file()
    with rasterio.open(first.parent / 'classification.tif') as a, rasterio.open(second.parent / 'classification.tif') as b:
        np.testing.assert_array_equal(a.read(1), b.read(1))
        assert (a.crs, a.transform, a.shape) == (b.crs, b.transform, b.shape)


def test_complete_produce_requires_classifier_before_creating_output(product, tmp_path):
    manifest, _, _, _, _ = product
    output = tmp_path / 'missing-model'
    with pytest.raises(ValueError, match = 'requires a classifier'):
        render_from_manifest(manifest, output, require_classification = True)
    assert not output.exists()


def test_outline_validation_matches_only_reviewed_observed_domain(product, tmp_path):
    from afiw.workflows.validation import validate_outline
    manifest, manual, _, grid, _ = product
    model = train_from_manifest(manifest, manual, tmp_path / 'model.joblib', 'synthetic fixture')
    derived = render_from_manifest(manifest, tmp_path / 'classified', model)
    from rasterio.transform import array_bounds
    left, bottom, right, top = array_bounds(grid['height'],grid['width'],grid['transform'])
    def polygon(path, ytop):
        return write_json(path, {'type':'FeatureCollection', 'crs':{'type':'name','properties':{'name':'EPSG:3031'}},
           'features':[{'type':'Feature','properties':{},'geometry':{'type':'Polygon','coordinates':[
               [[left,bottom],[right,bottom],[right,ytop],[left,ytop],[left,bottom]]]}}]})
    reference = polygon(tmp_path / 'outline_20211002_20211014.geojson', (top+bottom)/2)
    domain = polygon(tmp_path / 'domain.geojson', top)
    output = validate_outline(derived, reference, domain, tmp_path / 'assessment.json',
                              '2021-10-02','2021-10-14','synthetic independent outline fixture')
    assessment = json.loads(output.read_text())
    assert assessment['iou'] == 1 and assessment['precision'] == 1 and assessment['recall'] == 1
    assert assessment['area_km2']['unassessed_ocean'] > 0
    assert assessment['model_validation_updated'] is False
    with pytest.raises(ValueError, match = 'exactly match'):
        validate_outline(derived,reference,domain,tmp_path/'wrong.json','2021-10-01','2021-10-14','fixture')


def test_classified_raster_workflow_is_complete_and_reusable(product, tmp_path):
    from afiw.core.types import ProcessingSpec, SegmentationSpec
    from afiw.workflows.primary import PrimaryWorkflow
    manifest, _, grid, _, record = product
    rng = np.random.default_rng(42)
    first = rng.normal(-15,2,(64,64)).astype('float32')
    second = first.copy()
    second[:,32:] = rng.normal(-15,2,(64,32))
    first[:2] = np.nan
    paths = []
    for name,values in [('first.tif',first),('second.tif',second)]:
        path = tmp_path/name
        with rasterio.open(path,'w',**profile(grid)) as dst:dst.write(values,1)
        paths.append(path)
    rgb = np.full((8,8,3),30,np.uint8);rgb[4:] = 220
    segments = np.ones((8,8),np.uint32);segments[4:] = 2
    labels = np.zeros((8,8),np.uint8);labels[4:] = 2
    model = SegmentClassifier.train(rgb,segments,labels,{'region':'Davis','synthetic':True}).save(tmp_path/'fixture.joblib')
    spec = WorkflowSpec(run=RunSpec(region=RegionSpec(**record['config']['run']['region'])),
                        root=str(tmp_path/'new_primary'),coastline=record['config']['coastline'],classifier=str(model),
                        processing=ProcessingSpec(resolution_m=200,windows=(5,9,13),tile_size=64),
                        segmentation=SegmentationSpec(downsample=2,n_segments=16),
                        require_classification=True,allow_model_transfer=True)
    workflow = PrimaryWorkflow(spec)
    arguments = dict(first_time='2021-10-02T14:39:59Z',second_time='2021-10-14T14:39:59Z',synthetic=True,grid_override=grid)
    result = workflow.from_rasters(*paths,**arguments)
    completed = json.loads(result.manifest.read_text())
    assert completed['classification_available'] and completed['classifier_review']['accepted_transfer']
    assert completed['synthetic'] and completed['status'] == 'candidate_classification'
    for key in ('composite_png','composite_tif','classification','classification_png','classification_rgb_tif'):
        assert (result.directory/completed['outputs'][key]).is_file()
    with rasterio.open(result.classification) as src:
        assert src.shape == (32,32) and src.nodata == 255
        assert set(np.unique(src.read(1))) <= {0,1,2,255}
    original = result.manifest.read_bytes()
    assert workflow.from_rasters(*paths,**arguments).manifest == result.manifest
    assert result.manifest.read_bytes() == original
