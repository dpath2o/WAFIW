from dataclasses import dataclass
from pathlib import Path
import numpy as np
from scipy.ndimage import label as connected_components
from skimage.segmentation import slic

@dataclass
class Segmenter:
    spec: object
    def segment(self,rgb,valid):
        if rgb.shape[:2]!=valid.shape or rgb.ndim!=3 or rgb.shape[-1]!=3:raise ValueError('RGB/mask shape mismatch')
        if valid.size>self.spec.max_pixels:raise MemoryError('Segmentation pixel limit exceeded; increase downsample or reduce AOI')
        if not valid.any():raise ValueError('No valid pixels for segmentation')
        if self.spec.backend=='slic':
            # SLIC is a laptop testing alternative; it is NOT SAM-equivalent.
            return slic(rgb,n_segments=self.spec.n_segments,compactness=self.spec.compactness,mask=valid,
                        start_label=1,convert2lab=False,channel_axis=-1,enforce_connectivity=True).astype('uint32')
        if not self.spec.checkpoint or not Path(self.spec.checkpoint).is_file():raise FileNotFoundError('Provide a local SAM checkpoint')
        import torch
        from segment_anything import sam_model_registry,SamAutomaticMaskGenerator
        if self.spec.device=='mps' and not torch.backends.mps.is_available():raise RuntimeError('MPS not available; select CPU')
        if self.spec.device=='cuda' and not torch.cuda.is_available():raise RuntimeError('CUDA not available; select CPU')
        model=sam_model_registry[self.spec.sam_model](checkpoint=self.spec.checkpoint).to(self.spec.device)
        generator=SamAutomaticMaskGenerator(model,points_per_side=self.spec.points_per_side,pred_iou_thresh=.85,
            stability_score_thresh=.85,crop_n_layers=self.spec.crop_n_layers,crop_n_points_downscale_factor=2,
            crop_overlap_ratio=.5,box_nms_thresh=.3,min_mask_region_area=50,output_mode='binary_mask')
        masks=generator.generate(rgb);labels=np.zeros(valid.shape,dtype=np.uint32)
        # Assign smaller masks last. SAM overlap resolution is explicit and deterministic.
        for i,m in enumerate(sorted(masks,key=lambda x:x['area'],reverse=True),1):labels[m['segmentation']&valid]=i
        # Preserve unassigned pixels as 0; never interpret SAM gaps as pack/ocean.
        return labels


def segment_features(rgb,labels):
    ids=np.unique(labels);ids=ids[ids>0]
    features=np.array([rgb[labels==i].mean(axis=0) for i in ids],dtype=float).reshape(-1,3)
    return ids,features
