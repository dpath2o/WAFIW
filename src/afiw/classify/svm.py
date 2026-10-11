"""Mean-RGB SVM matching the supplied notebook's feature definition.
Training data and a scientifically assessed model must be supplied externally.
"""
from dataclasses import dataclass
from pathlib import Path
import numpy as np
from sklearn.svm import SVC
import joblib
from .segmentation import segment_features

@dataclass
class SegmentClassifier:
    model   : object
    metadata: dict

    @classmethod
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
        model = SVC().fit(np.asarray(rows), np.asarray(y))
        return cls(model, {'features'          : 'mean_RGB_uint8',
                           'training_segments' : len(y),
                           'validated'         : False, **(metadata or {})})

    def save(self, path):
        joblib.dump({'model'    : self.model,
                     'metadata' : self.metadata}, path)
        return Path(path)

    @classmethod
    def load(cls, path):
        # Load only trusted local artifacts: joblib/pickle can execute code.
        d = joblib.load(path)
        if d['metadata'].get('features') != 'mean_RGB_uint8':
            raise ValueError('Unsupported classifier features')
        return cls(d['model'], d['metadata'])

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
        return out
