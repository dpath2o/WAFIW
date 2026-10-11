import logging
from afiw.core.logging import logged_step

from dataclasses import dataclass
from pathlib import Path
import numpy as np
from skimage.segmentation import slic

logger = logging.getLogger(__name__)

@dataclass
class Segmenter:
    spec: object
    @logged_step
    def segment(self, rgb, valid):
        logger.info('Segmenter: backend=%s device=%s RGB shape=%s valid pixels=%s/%s', self.spec.backend, self.spec.device, rgb.shape, np.count_nonzero(valid), valid.size)
        if rgb.shape[:2] != valid.shape or rgb.ndim != 3 or rgb.shape[-1] != 3:
            raise ValueError('RGB/mask shape mismatch')
        if valid.size > self.spec.max_pixels:
            raise MemoryError('Segmentation pixel limit exceeded; increase downsample or reduce AOI')
        if not valid.any():
            raise ValueError('No valid pixels for segmentation')
        if self.spec.backend == 'slic':
            # SLIC is a laptop testing alternative; it is NOT SAM-equivalent.
            return slic(rgb,
                        n_segments           = self.spec.n_segments,
                        compactness          = self.spec.compactness,
                        mask                 = valid,
                        start_label          = 1,
                        convert2lab          = False,
                        channel_axis         = -1,
                        enforce_connectivity = True).astype('uint32')
        if not self.spec.checkpoint or not Path(self.spec.checkpoint).is_file():
            raise FileNotFoundError('Provide a local SAM checkpoint')
        import torch
        from segment_anything import sam_model_registry, SamAutomaticMaskGenerator
        if self.spec.device=='mps' and not torch.backends.mps.is_available():
            raise RuntimeError('MPS not available; select CPU')
        if self.spec.device=='cuda' and not torch.cuda.is_available():
            raise RuntimeError('CUDA not available; select CPU')
        model     = sam_model_registry[self.spec.sam_model](checkpoint = self.spec.checkpoint).to(self.spec.device)
        generator = SamAutomaticMaskGenerator(model,
                                              points_per_side                = self.spec.points_per_side,
                                              pred_iou_thresh                = self.spec.pred_iou_thresh,
                                              stability_score_thresh         = self.spec.stability_score_thresh,
                                              crop_n_layers                  = self.spec.crop_n_layers,
                                              crop_n_points_downscale_factor = 2,
                                              crop_overlap_ratio             = self.spec.crop_overlap_ratio,
                                              box_nms_thresh                 = self.spec.box_nms_thresh,
                                              min_mask_region_area           = self.spec.min_mask_region_area,
                                              output_mode                    = 'binary_mask')
        with torch.inference_mode():
            masks = generator.generate(rgb)
        logger.info('SAM masks returned: %s', len(masks))
        labels    = np.zeros(valid.shape, dtype = np.uint32)
        # Assign smaller masks last. SAM overlap resolution is explicit and deterministic.
        for i,m in enumerate(sorted(masks, key = lambda x:x['area'], reverse = True), 1):
            labels[m['segmentation']&valid] = i
        # Preserve unassigned pixels as 0; never interpret SAM gaps as pack/ocean.
        return labels

@logged_step
def segment_features(rgb,labels):
    rgb, labels = np.asarray(rgb), np.asarray(labels)
    if rgb.dtype != np.uint8 or rgb.shape != (*labels.shape, 3):
        raise ValueError('Features require H,W,3 uint8 RGB matching the segment grid')
    if not np.issubdtype(labels.dtype, np.integer) or np.any(labels < 0):
        raise ValueError('Features require nonnegative integer segment IDs')
    ids, inverse, counts = np.unique(labels, return_inverse = True, return_counts = True)
    inverse = inverse.ravel()
    features = np.stack([np.bincount(inverse, weights = rgb[...,channel].ravel()) / counts
                         for channel in range(3)], axis = 1)
    selected = ids > 0
    return ids[selected], features[selected]
