"""Annotation semantics, transfer controls, and leakage-resistant assessment."""
import json
import numpy as np
import pytest
from afiw.classify.research import read_scene, train_research, acquisition_groups
from afiw.classify.segmentation import segment_features
from afiw.classify.svm import SegmentClassifier
from afiw.core.types import WorkflowSpec
from afiw.workflows.maps import check_classifier, render_from_manifest
from afiw.workflows.primary import PrimaryWorkflow


def scene(root, name, prefix = 'HH_', labels = None):
    directory = root / name
    directory.mkdir()
    dates = '_'.join(name.split('_')[-2:])
    rgb = np.zeros((6,6,3), np.uint8)
    rgb[2:4] = 120
    rgb[4:] = 220
    segments = np.repeat(np.arange(3, dtype = np.uint16), 2)[:,None] * np.ones((1,6), np.uint16)
    np.save(directory / f'{prefix}rgb_image_{dates}.npy', rgb)
    np.save(directory / f'label_map_{dates}.npy', segments)
    np.save(directory / f'labelled_array_{dates}.npy', np.asarray(labels or [0,0,2,np.nan]))
    return directory


def test_scene_annotation_ids_background_and_polarization(tmp_path):
    directory = scene(tmp_path, 'prydz_20210101_20210113', prefix = '')
    x, y, report = read_scene(directory, 'HH')
    assert y.tolist() == [0,2] and report['segment_ids'] == [1,2]
    assert report['ignored_unassigned_label'] == 0
    np.testing.assert_array_equal(x, [[120]*3,[220]*3])
    with pytest.raises(FileNotFoundError): read_scene(directory, 'HV')
    np.save(directory / 'labelled_array_20210101_20210113.npy', [0,2])
    with pytest.raises(ValueError, match = 'cover'): read_scene(directory, 'HH')


def test_duplicate_sources_fail_even_with_different_labels(tmp_path):
    names = ['prydz_20210101_20210113', 'thwaites_20210101_20210113']
    for name in names: scene(tmp_path, name)
    with pytest.raises(ValueError, match = 'Duplicate imagery'):
        train_research(tmp_path, tmp_path / 'model.joblib', 'fixture', scenes = names)
    assert not (tmp_path / 'model.joblib').exists()


def test_training_provenance_assessment_and_transfer(tmp_path):
    name = 'prydz_20210101_20210113'
    scene(tmp_path, name)
    path = train_research(tmp_path, tmp_path / 'model.joblib', 'reviewed fixture', scenes = [name])
    classifier = SegmentClassifier.load(path)
    report = json.loads(path.with_suffix('.training.json').read_text())
    assert report['training_segments'] == 2
    assert report['assessment']['independent_validation'] is False
    assert report['assessment']['folds']['site'][0]['status'] == 'insufficient_training_classes'
    record = {'region' : 'Davis', 'synthetic' : False, 'config' : WorkflowSpec().as_dict()}
    with pytest.raises(ValueError, match = 'allow_model_transfer'):
        check_classifier(classifier, record)
    record['config']['allow_model_transfer'] = True
    assert check_classifier(classifier, record)['accepted_transfer']
    record['config']['acquisition']['polarization'] = 'VV'
    with pytest.raises(ValueError, match = 'polarization'):
        check_classifier(classifier, record)
    with pytest.raises(FileExistsError):
        train_research(tmp_path, path, 'fixture', scenes = [name])


def test_shared_acquisition_transitive_groups():
    reports = [{'region':'thwaites','dates':dates} for dates in (['a','b'],['b','c'],['d','e'],['c','d'])]
    reports.append({'region':'prydz','dates':['a','b']})
    groups = acquisition_groups(reports)
    assert len(set(groups[:4])) == 1 and groups[4] != groups[0]


def test_sparse_segment_means_match_reference():
    rgb = np.arange(27, dtype = np.uint8).reshape(3,3,3)
    labels = np.array([[0,2,2],[99,99,2],[0,99,99]], dtype = np.uint32)
    ids, features = segment_features(rgb, labels)
    assert ids.tolist() == [2,99]
    np.testing.assert_array_equal(features, [rgb[labels == i].mean(0) for i in ids])


def test_complete_workflow_fails_before_processing():
    workflow = PrimaryWorkflow(WorkflowSpec(require_classification = True))
    with pytest.raises(ValueError, match = 'requires an existing classifier'):
        workflow.from_rasters('absent.tif','absent2.tif','2021-01-01','2021-01-13')


def test_portable_model_refit_matches_estimator(tmp_path):
    name = 'prydz_20210101_20210113'
    scene(tmp_path, name)
    portable = train_research(tmp_path, tmp_path/'portable.npz','fixture',scenes=[name])
    native = train_research(tmp_path,tmp_path/'native.joblib','fixture',scenes=[name])
    a,b = SegmentClassifier.load(portable),SegmentClassifier.load(native)
    X = np.array([[20]*3,[120]*3,[220]*3])
    np.testing.assert_array_equal(a.model.predict(X),b.model.predict(X))
    assert a.metadata['training_scenes'] == b.metadata['training_scenes']
    malformed = tmp_path / 'malformed.npz'
    np.savez(malformed,features=[[999,0,0],[0,0,0]],labels=[0,2],metadata='{}')
    with pytest.raises(ValueError, match='Invalid portable'):SegmentClassifier.load(malformed)


def test_reference_date_conflicts_and_invalid_geometry(tmp_path):
    from afiw.workflows.validation import reviewed_polygons
    with pytest.raises(ValueError, match='dates conflict'):
        reviewed_polygons(tmp_path/'outline_20240720_20210801.shp', 'EPSG:3031', ['2024-10-12','2024-10-24'])
    path = tmp_path / 'reference.geojson'
    path.write_text(json.dumps({'type':'FeatureCollection','features':[]}))
    with pytest.raises(ValueError, match='nonempty'):
        reviewed_polygons(path,'EPSG:3031')
    path.write_text(json.dumps({'type':'FeatureCollection','features':[
        {'type':'Feature','properties':{},'geometry':{'type':'Polygon','coordinates':[
        [[0,0],[1,1],[1,0],[0,1],[0,0]]]}}]}))
    with pytest.raises(ValueError, match='Invalid'):
        reviewed_polygons(path,'EPSG:3031')
