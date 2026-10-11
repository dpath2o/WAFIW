"""Import reviewed segment annotations, without loading executable pickle arrays.

Segment 0 is SAM's unassigned background, not a physical ocean object. Class 1
is provided by the land/shelf mask, not learned by the ice classifier.
"""
from pathlib import Path
from datetime import datetime
import logging
import re
import json
import numpy as np
from sklearn.svm import SVC
from sklearn.metrics import confusion_matrix, balanced_accuracy_score
from afiw.core.logging import logged_workflow, logged_step
from afiw.core.provenance import sha256, write_json, runtime
from .svm import SegmentClassifier
from .segmentation import segment_features

logger = logging.getLogger(__name__)
REFERENCE_SCENES = (
    'prydz_20210129_20210210', 'prydz_20210330_20210411',
    'prydz_20210728_20210809', 'prydz_20210821_20210902',
    'prydz_20211020_20211101', 'thwaites_20240708_20240720',
    'thwaites_20240813_20240825', 'thwaites_20241012_20241024',
    'thwaites_20241024_20241105', 'thwaites_20241105_20241117')


@logged_step
def read_scene(directory, polarization):
    directory = Path(directory).resolve()
    match = re.fullmatch(r'([a-zA-Z0-9-]+)_(\d{8})_(\d{8})', directory.name)
    if not match:
        raise ValueError(f'Invalid annotated scene name: {directory.name}')
    region, first, second = match.groups()
    if datetime.strptime(first, '%Y%m%d') >= datetime.strptime(second, '%Y%m%d'):
        raise ValueError('Annotated acquisition dates must be ordered')
    dates = f'{first}_{second}'
    # The reference notebook uses unprefixed HH files; the supplied newer
    # Thwaites arrays use explicit HH_/HV_ names. Never substitute HH for HV.
    explicit = directory / f'{polarization}_rgb_image_{dates}.npy'
    generic  = directory / f'rgb_image_{dates}.npy'
    rgb_path = explicit if explicit.is_file() else generic if polarization == 'HH' else explicit
    if explicit.is_file() and generic.is_file() and sha256(explicit) != sha256(generic):
        raise ValueError(f'Ambiguous RGB inputs: {directory}')
    paths = {'rgb' : rgb_path,
             'segments' : directory / f'label_map_{dates}.npy',
             'annotations' : directory / f'labelled_array_{dates}.npy'}
    hashes = {key : sha256(path) for key, path in paths.items()}
    rgb, segments, annotations = (np.load(paths[key], allow_pickle = False)
                                  for key in ('rgb', 'segments', 'annotations'))
    if rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[-1] != 3:
        raise ValueError(f'RGB must be H,W,3 uint8: {rgb_path}')
    if segments.shape != rgb.shape[:2] or not np.issubdtype(segments.dtype, np.integer) or np.any(segments < 0):
        raise ValueError(f'Segment grid must match RGB and use nonnegative integer IDs: {directory}')
    if annotations.ndim != 1 or not np.issubdtype(annotations.dtype, np.number):
        raise ValueError('Annotations must be a numeric vector indexed by segment ID')
    if np.any(np.isinf(annotations)) or not np.isin(annotations[np.isfinite(annotations)], [0,1,2,3]).all():
        raise ValueError('Annotations must use NaN or the research class IDs 0,1,2,3')
    ids = np.unique(segments)
    if ids.max() >= len(annotations):
        raise ValueError('Annotation vector does not cover all segment IDs')
    accepted = ids[(ids > 0) & np.isin(annotations[ids], [0,2,3])]
    feature_ids, all_features = segment_features(rgb, segments)
    features = all_features[np.isin(feature_ids, accepted)]
    labels   = annotations[accepted].astype(np.uint8)
    unused   = np.flatnonzero(np.isfinite(annotations) & ~np.isin(np.arange(len(annotations)), ids))
    report = {'scene' : directory.name, 'region' : region.lower(), 'dates' : [first, second],
              'shape' : list(segments.shape), 'files' : {key : directory.name + '/' + path.name for key,path in paths.items()},
              'sha256' : hashes, 'segment_ids' : accepted.tolist(),
              'class_counts' : {str(int(c)) : int(n) for c,n in zip(*np.unique(labels, return_counts = True))},
              'ignored_unassigned_label' : None if not np.isfinite(annotations[0]) else int(annotations[0]),
              'unused_annotation_ids' : unused.tolist()}
    logger.info('Annotations %s: usable=%s classes=%s; segment 0 label=%s excluded', directory.name, len(labels), report['class_counts'], report['ignored_unassigned_label'])
    return features, labels, report


def acquisition_groups(reports):
    """Keep pairs sharing an acquisition at the same site in the same fold."""
    groups = list(range(len(reports)))
    for i,a in enumerate(reports):
        for j,b in enumerate(reports[:i]):
            if a['region'] == b['region'] and set(a['dates']) & set(b['dates']):
                old, new = groups[i], groups[j]
                groups = [new if value == old else value for value in groups]
    return groups


@logged_step
def assess(features, labels, reports, lengths):
    scene_indices = np.repeat(np.arange(len(reports)), lengths)
    results = {}
    for name, scene_groups in [('acquisition_group', acquisition_groups(reports)),
                               ('site', [r['region'] for r in reports])]:
        row_groups = np.asarray(scene_groups)[scene_indices]
        folds = []
        for group in sorted(set(scene_groups), key = str):
            test = row_groups == group
            train = ~test
            entry = {'held_out' : str(group), 'scenes' : [r['scene'] for r,g in zip(reports,scene_groups) if g == group],
                     'training_segments' : int(train.sum()), 'test_segments' : int(test.sum())}
            if not test.any() or len(np.unique(labels[train])) < 2:
                entry['status'] = 'insufficient_training_classes'
            else:
                prediction = SVC().fit(features[train], labels[train]).predict(features[test])
                entry.update(status = 'assessed', class_order = [0,2,3],
                             confusion_matrix = confusion_matrix(labels[test], prediction, labels = [0,2,3]).tolist(),
                             balanced_accuracy = float(balanced_accuracy_score(labels[test], prediction)),
                             unseen_test_classes = sorted(set(map(int, labels[test])) - set(map(int, labels[train]))))
            folds.append(entry)
        results[name] = folds
    return {'unit' : 'annotated segment (not pixel or area)', 'folds' : results,
            'independent_validation' : False,
            'limitations' : ['Training annotations are not independent validation polygons.',
                             'Scene/site holdouts do not establish transfer to Davis or other stations.',
                             'Class 3 support must be reviewed separately; a single labelled segment cannot establish performance.',
                             'Shared acquisitions are grouped; pixel-random splits are not used.']}


@logged_workflow
def train_research(root, output, label_source, polarization = 'HH', scenes = None):
    root, output = Path(root).resolve(), Path(output).resolve()
    report_path = output.with_suffix('.training.json')
    if output.suffix not in ('.joblib', '.npz'):
        raise ValueError('Research model output must end in .joblib or portable .npz')
    if output.exists() or report_path.exists():
        raise FileExistsError('Choose new model and training-report filenames')
    if polarization not in ('HH', 'HV') or not str(label_source).strip():
        raise ValueError('Select HH or HV and document the annotation source')
    names = list(REFERENCE_SCENES if scenes is None else scenes)
    if not names or len(set(names)) != len(names):
        raise ValueError('Select a nonempty list of unique scenes')
    rows, targets, reports, seen = [], [], [], {}
    for name in names:
        if Path(name).name != name:
            raise ValueError('Scene names must be direct subdirectories')
        x, y, report = read_scene(root / name, polarization)
        identity = (report['sha256']['rgb'], report['sha256']['segments'])
        if identity in seen:
            raise ValueError(f'Duplicate imagery/segments: {seen[identity]} and {name}; review conflicting annotations before combining')
        seen[identity] = name
        rows.append(x); targets.append(y); reports.append(report)
    features, labels = np.concatenate(rows), np.concatenate(targets)
    if len(np.unique(labels)) < 2:
        raise ValueError('At least two labelled ice/ocean classes are required')
    metadata = {'features' : 'mean_RGB_uint8', 'training_segments' : int(len(labels)),
                'training_regions' : sorted({r['region'] for r in reports}),
                'polarization' : polarization, 'synthetic' : False, 'validated' : False,
                'source_kind' : 'research_segment_annotations', 'label_source' : label_source,
                'preprocessing_contract' : None, 'requires_transfer_review' : True,
                'class_counts' : {str(int(c)) : int(n) for c,n in zip(*np.unique(labels, return_counts = True))},
                'training_scenes' : reports,
                'excluded_scenes' : ([{'scene' : 'prydz_20240708_20240720',
                                      'reason' : 'RGB and segments duplicate Thwaites 20240708/20240720 with conflicting annotations; absent from reference training list'}]
                                     if scenes is None and (root / 'prydz_20240708_20240720').exists() else []),
                'method_note' : 'Existing RGB arrays have incomplete radiometric/grid provenance; reuse is an explicit candidate transfer, not preprocessing equivalence.'}
    assessment = assess(features, labels, reports, [len(y) for y in targets])
    logger.warning('Research model is an unvalidated transfer candidate: class counts=%s; training sites=%s', metadata['class_counts'], metadata['training_regions'])
    output.parent.mkdir(parents = True, exist_ok = True)
    if output.suffix == '.npz':
        np.savez_compressed(output, features = features, labels = labels, metadata = json.dumps(metadata, allow_nan = False))
    else:
        SegmentClassifier(SVC().fit(features, labels), metadata).save(output)
    write_json(report_path, {**runtime(), **metadata, 'assessment' : assessment, 'model_sha256' : sha256(output)})
    return output
