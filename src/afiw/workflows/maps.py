"""Re-render completed products and train/apply supplied manual labels."""
from copy import deepcopy
from pathlib import Path
import json
import numpy as np
import rasterio
from afiw.classify.svm import SegmentClassifier
from afiw.core.types import RegionSpec
from afiw.core.provenance import write_json, runtime, sha256, implementation_hash
from afiw.metrics.change import extent_metrics, cell_areas_km2
from afiw.plotting.primary import export_composite, export_classification, render_maps, require_pygmt

def inputs_from_manifest(manifest):
    manifest = Path(manifest).resolve()
    record   = json.loads(manifest.read_text())
    outputs  = record['outputs']
    rgb      = np.load(manifest.parent / outputs['rgb'], allow_pickle = False)
    with rasterio.open(manifest.parent / outputs['segments']) as src:
        segments = src.read(1)
        grid    = {key: getattr(src, key) for key in ('crs', 'transform', 'width', 'height')}
    with rasterio.open(manifest.parent / outputs['validity']) as src:
        if (src.crs, src.transform, src.shape) != (grid['crs'], grid['transform'], segments.shape):
            raise ValueError('Validity and segment grids differ')
        validity = src.read(1)
    if rgb.dtype != np.uint8 or rgb.shape != (*segments.shape, 3):
        raise ValueError('Persisted RGB/segment arrays differ or RGB is not uint8')
    return manifest, record, rgb, segments, validity, grid

def preprocessing_contract(record):
    config = record['config']
    return json.loads(json.dumps({'processing'   : config['processing'],
                                  'segmentation' : config['segmentation'],
                                  'features'     : 'mean_RGB_uint8',
                                  'rgb_encoding' : 'normprod_clipped_-0.5_1_uint8'}))

def check_classifier(classifier, record):
    if classifier.metadata.get('region') != record['region']:
        raise ValueError('Classifier must declare the matching region')
    if classifier.metadata.get('synthetic', False) and not record['synthetic']:
        raise ValueError('Synthetic classifier cannot classify real scenes')
    contract = classifier.metadata.get('preprocessing_contract')
    if contract is not None and contract != preprocessing_contract(record):
        raise ValueError('Classifier preprocessing contract differs (texture/segmentation settings)')

def train_from_manifest(manifest, labels, output, label_source):
    manifest, record, rgb, segments, validity, grid = inputs_from_manifest(manifest)
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError('Choose a new classifier filename; existing models are not overwritten')
    if not str(label_source).strip():
        raise ValueError('Document the manual label source')
    with rasterio.open(labels) as src:
        if src.count != 1 or (src.crs, src.transform, src.shape) != (grid['crs'], grid['transform'], segments.shape):
            raise ValueError('Training labels must match segments.tif exactly: CRS, transform, shape and one band')
        training = src.read(1, masked=True).filled(255)
    if not np.isin(training, [0, 2, 3, 255]).all():
        raise ValueError('Labels must use 0,2,3 and 255 for unlabelled cells; land/shelf is supplied by the mask')
    training[(validity != 1) | (segments == 0)] = 255
    classifier = SegmentClassifier.train(rgb, segments, training, {'region'                  : record['region'],
                                                                   'synthetic'               : record['synthetic'],
                                                                   'validated'               : False,
                                                                   'label_source'            : label_source,
                                                                   'training_manifest'       : str(manifest),
                                                                   'training_manifest_sha256': sha256(manifest),
                                                                   'labels_sha256'           : sha256(labels),
                                                                   'preprocessing_contract'  : preprocessing_contract(record)})
    output.parent.mkdir(parents = True, exist_ok = True)
    classifier.save(output)
    write_json(output.with_suffix('.training.json'), classifier.metadata)
    return output

def render_from_manifest(manifest, output, classifier_path=None):
    """New derived manifest; do not overwrite analytical inputs or old product."""
    require_pygmt()
    manifest, source, rgb, segments, validity, grid = inputs_from_manifest(manifest)
    output = Path(output).resolve()
    if output == manifest.parent or (output.exists() and any(output.iterdir())):
        raise FileExistsError('Use a new empty output directory to preserve the source product')
    coastline          = source['config'].get('coastline')
    expected_mask_hash = source.get('resource_hashes', {}).get('coastline')
    if coastline and expected_mask_hash and sha256(coastline) != expected_mask_hash:
        raise ValueError('Coastline changed since source processing; restore the reviewed source mask or recompute the product')
    output.mkdir(parents = True, exist_ok = True)
    record         = deepcopy(source)
    classification = None
    if classifier_path:
        if not source['mask_provided']:
            raise ValueError('Classification requires a reviewed land/shelf exclusion mask')
        classifier_path = Path(classifier_path).resolve()
        classifier      = SegmentClassifier.load(classifier_path)
        check_classifier(classifier, source)
        classes        = classifier.predict(rgb, segments, validity == 1, validity == 2)
        classification = export_classification(classes, grid, output / 'classification.tif')
        record['config']['classifier']          = str(classifier_path)
        record['resource_hashes']['classifier'] = sha256(classifier_path)
        record['metrics']                       = extent_metrics(classes, cell_areas_km2(classes.shape, grid['transform'], grid['crs']))
    elif source['outputs'].get('classification'):
        with rasterio.open(manifest.parent / source['outputs']['classification']) as src:
            if (src.crs, src.transform, src.shape) != (grid['crs'], grid['transform'], segments.shape):
                raise ValueError('Existing classification grid differs')
            classes = src.read(1)
        classification = export_classification(classes, grid, output / 'classification.tif')
    outputs   = {key: str((manifest.parent / source['outputs'][key]).resolve()) for key in ('texture', 'segments', 'rgb', 'validity')}
    composite = export_composite(outputs['texture'], output / 'composite.tif', coastline)
    region    = RegionSpec(**source['config']['run']['region'])
    outputs.update(render_maps(composite, classification, output, region, source['first_time'], source['second_time'], source['synthetic'], source['config']['processing']['windows']))
    record.update(runtime())
    record.update(schema_version           = 2,
                  plotting_backend         = 'pygmt',
                  outputs                  = outputs,
                  source_manifest          = str(manifest),
                  source_manifest_sha256   = sha256(manifest),
                  implementation_hash      = implementation_hash(),
                  classification_available = classification is not None,
                  status                   = 'candidate_classification' if classification else 'segmentation_only')
    # Derived outputs have a new identity; analytical inputs retain their own provenance.
    record['fingerprint']         = sha256(manifest) + ':' + record['implementation_hash'] + ':' + record['resource_hashes'].get('classifier', 'none')
    record['classification_note'] = ('Unvalidated candidate classes; training is not independent validation.' if classification else 'No classifier supplied; no classification raster or figure generated.')
    return write_json(output / 'manifest.json', record)
