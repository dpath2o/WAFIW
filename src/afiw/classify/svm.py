"""Mean-RGB SVM matching the supplied notebook's feature definition.
Training data and a scientifically assessed model must be supplied externally.
"""
import logging
from afiw.core.logging import logged_step

from dataclasses import dataclass
from pathlib import Path
import numpy as np
from sklearn.svm import SVC
import joblib
import json
from .segmentation import segment_features

logger = logging.getLogger(__name__)

@dataclass
class SegmentClassifier:
    model   : object
    metadata: dict

    @classmethod
    @logged_step
    def train(cls, rgb, segments, training_classes, metadata = None):
        if training_classes.shape != segments.shape:
            raise ValueError('Training raster shape mismatch')
        ids, X = segment_features(rgb, segments)
        rows   = []
        y      = []
        for k, sid in enumerate(ids):
            values = training_classes[segments==sid]
            values = values[np.isin(values,[0,2,3])]
            if not len(values):
                continue
            classes, counts = np.unique(values, return_counts = True)
            if (counts.max() / len(values)) < .9:
                continue # mixed labels are excluded, not guessed
            rows.append(X[k])
            y.append(classes[counts.argmax()])
        if len(set(y)) < 2:
            raise ValueError('At least two manually labelled classes are required')
        logger.info('SVM training: eligible segments=%s accepted=%s class counts=%s', len(ids), len(y), dict(zip(*np.unique(y, return_counts = True))))
        model = SVC().fit(np.asarray(rows), np.asarray(y))
        return cls(model, {'features'          : 'mean_RGB_uint8',
                           'training_segments' : len(y),
                           'class_counts' : {str(int(c)) : int(n) for c,n in zip(*np.unique(y, return_counts = True))},
                           'validated'         : False, **(metadata or {})})

    @logged_step
    def save(self, path):
        joblib.dump({'model'    : self.model,
                     'metadata' : self.metadata}, path)
        return Path(path)

    @classmethod
    @logged_step
    def load(cls, path):
        # Load only trusted local artifacts: joblib/pickle can execute code.
        logger.info('Loading trusted local classifier: %s', path)
        if Path(path).suffix == '.npz':
            # Portable research feature tables are fitted using this runtime;
            # no executable pickle or cross-version estimator state is loaded.
            with np.load(path, allow_pickle = False) as source:
                X = source['features']
                y = source['labels']
                metadata = json.loads(str(source['metadata'].item()))
            if (X.ndim != 2 or X.shape[1] != 3 or y.shape != (len(X),) or
                not np.isfinite(X).all() or np.any((X < 0) | (X > 255)) or
                not np.isin(y, [0,2,3]).all() or len(np.unique(y)) < 2):
                raise ValueError('Invalid portable research feature table')
            d = {'model' : SVC().fit(X,y), 'metadata' : metadata}
            logger.info('Fitted portable research features using current scikit-learn runtime; segments=%s', len(y))
        else:
            d = joblib.load(path)
        if d['metadata'].get('features') != 'mean_RGB_uint8':
            raise ValueError('Unsupported classifier features')
        return cls(d['model'], d['metadata'])

    @logged_step
    def predict(self, rgb, segments, valid, excluded = None):
        ids, X = segment_features(rgb, segments)
        out    = np.full(segments.shape, 255, np.uint8)
        if len(ids):
            y = self.model.predict(X)
            if not np.isin(y,[0,2,3]).all():
                raise ValueError('Classifier returned unknown class IDs')
            for sid,c in zip(ids,y):
                out[segments==sid] = c
        out[~valid] = 255
        if excluded is not None:
            out[excluded] = 1
        logger.info('Predicted class counts: %s', dict(zip(*np.unique(out, return_counts = True))))
        return out
