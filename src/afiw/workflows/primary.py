from dataclasses import dataclass
from pathlib import Path
import hashlib,json,math
import numpy as np
import rasterio
from rasterio.warp import Resampling
from rasterio.transform import from_bounds
from afiw.core.paths import AFIWPaths
from afiw.core.types import PairResult
from afiw.core.provenance import write_json,sha256,runtime,implementation_hash
from afiw.processing.raster import grid_for_region,align_raster,texture_raster,profile,load_exclusions,exclusion_mask
from afiw.processing.texture import rgb_texture
from afiw.classify.segmentation import Segmenter
from afiw.classify.svm import SegmentClassifier
from afiw.plotting.primary import export_composite, export_classification, render_maps, require_pygmt
from afiw.metrics.change import extent_metrics,cell_areas_km2
from afiw.observations.sentinel1 import Sentinel1Client,utc
from afiw.processing.snap import SnapPreprocessor

@dataclass
class PrimaryWorkflow:
    spec: object
    @property
    def paths(self):return AFIWPaths(self.spec.root,self.spec.run).ensure()
    def search(self):return Sentinel1Client(self.spec.run,self.spec.acquisition,self.paths).search()
    def from_safe_pair(self,pair,download=True):
        require_pygmt()
        if self.spec.processing.input_units!='db':raise ValueError('The SNAP adapter outputs dB; set processing.input_units=db')
        client=Sentinel1Client(self.spec.run,self.spec.acquisition,self.paths)
        if download:sources=client.download_pair(pair)
        else:sources=[self.paths.downloads/Path(f['properties']['url'].split('?')[0]).name for f in [pair['first'],pair['second']]]
        pre=SnapPreprocessor(self.spec.snap,self.spec.processing,self.spec.run.region,self.spec.acquisition.polarization)
        processed=[]
        for source in sources:
            if not source.is_file():raise FileNotFoundError(source)
            output=self.paths.processed/(source.stem+'_gamma0_db.tif')
            # Raw processing is explicit; do not silently reuse stale preprocessing.
            processed.append(pre.run(source,output))
        return self.from_rasters(*processed,first_time=pair['first']['properties']['startTime'],second_time=pair['second']['properties']['startTime'],pair_id=pair['pair_id'],catalog_metadata=pair)
    def from_rasters(self,first,second,first_time,second_time,pair_id=None,synthetic=False,catalog_metadata=None,grid_override=None):
        require_pygmt()
        if utc(second_time)<=utc(first_time):raise ValueError('Acquisitions must be ordered and distinct')
        baseline=(utc(second_time)-utc(first_time)).total_seconds()/86400
        if not self.spec.acquisition.min_pair_days<=baseline<=self.spec.acquisition.max_pair_days:raise ValueError('Pair temporal baseline is outside configured limits')
        code_hash=implementation_hash()
        hashes=[sha256(first),sha256(second)]
        resources={name:sha256(value) for name,value in [('coastline',self.spec.coastline),('classifier',self.spec.classifier),('sam_checkpoint',self.spec.segmentation.checkpoint)] if value}
        hashes_for_fingerprint=hashes+[code_hash,json.dumps(resources,sort_keys=True)]
        ident=hashlib.sha256((''.join(hashes_for_fingerprint)+json.dumps(self.spec.as_dict(),sort_keys=True)).encode()).hexdigest()[:10]
        pair_id=pair_id or f'{utc(first_time):%Y%m%dT%H%M%S}_{utc(second_time):%Y%m%dT%H%M%S}_{ident}'
        directory=self.paths.pair(pair_id);directory.mkdir(parents=True,exist_ok=True)
        manifest=directory/'manifest.json'
        fingerprint=hashlib.sha256((''.join(hashes_for_fingerprint)+json.dumps(self.spec.as_dict(),sort_keys=True)).encode()).hexdigest()
        if manifest.exists():
            old=json.loads(manifest.read_text())
            if old.get('fingerprint')==fingerprint and old.get('synthetic')==synthetic and all((directory/v).is_file() for v in old['outputs'].values()):
                o=old['outputs'];return PairResult(directory,manifest,directory/o['texture'],directory/o['segments'],directory/o.get('composite_png',o.get('quicklook')),directory/o['classification'] if 'classification'in o else None)
            raise FileExistsError(f'Existing pair product differs or is incomplete: {directory}; choose a new pair ID/output root')
        grid=grid_override or grid_for_region(self.spec.run.region,self.spec.processing)
        first_aligned=align_raster(first,directory/'first_db.tif',grid,self.spec.processing.tile_size,self.spec.processing.input_units)
        second_aligned=align_raster(second,directory/'second_db.tif',grid,self.spec.processing.tile_size,self.spec.processing.input_units)
        texture=texture_raster(first_aligned,second_aligned,directory/'texture.tif',self.spec.processing,self.spec.coastline)
        with rasterio.open(texture) as src:
            factor=self.spec.segmentation.downsample;h=math.ceil(src.height/factor);w=math.ceil(src.width/factor)
            if h*w>self.spec.segmentation.max_pixels:raise MemoryError('Segmentation grid too large; increase downsample')
            # Nearest preserves finite/invalid texture semantics at selected cells.
            stack=src.read(out_shape=(3,h,w),resampling=Resampling.nearest)
            transform=from_bounds(*src.bounds,w,h);crs=src.crs
            seg_grid=dict(crs=crs,transform=transform,width=w,height=h)
        rgb,valid=rgb_texture(stack);labels=Segmenter(self.spec.segmentation).segment(rgb,valid)
        segments=directory/'segments.tif'
        with rasterio.open(segments,'w',**profile(seg_grid,dtype='uint32',nodata=0)) as dst:dst.write(labels,1)
        np.save(directory/'rgb.npy',rgb);np.save(directory/'segments.npy',labels)
        mask=exclusion_mask(load_exclusions(self.spec.coastline,crs),seg_grid)
        with rasterio.open(directory/'validity.tif','w',**profile(seg_grid,dtype='uint8',nodata=None)) as dst:
            validity=np.zeros(valid.shape,np.uint8);validity[valid]=1;validity[mask]=2;dst.write(validity,1)
        classes=None;classification=None;metrics={}
        if self.spec.classifier:
            if not self.spec.coastline:raise ValueError('Classification requires an explicit reviewed land/ice-shelf exclusion mask')
            classifier=SegmentClassifier.load(self.spec.classifier)
            from .maps import check_classifier
            check_classifier(classifier,{'region':self.spec.run.region.name,'synthetic':synthetic,'config':self.spec.as_dict()})
            model_region=classifier.metadata.get('region')
            if model_region!=self.spec.run.region.name:raise ValueError('Classifier must declare the matching region; cross-region transfer needs a reviewed model')
            if classifier.metadata.get('synthetic',False) and not synthetic:raise ValueError('Synthetic classifier cannot classify real scenes')
            classes=classifier.predict(rgb,labels,valid,mask);classification=directory/'classification.tif'
            export_classification(classes,seg_grid,classification)
            metrics=extent_metrics(classes,cell_areas_km2(classes.shape,transform,crs))
        composite=export_composite(texture,directory/'composite.tif',self.spec.coastline)
        outputs={'texture':texture.name,'segments':segments.name,'rgb':'rgb.npy','validity':'validity.tif'}
        outputs.update(render_maps(composite,classification,directory,self.spec.run.region,first_time,second_time,synthetic,self.spec.processing.windows))
        quicklook=directory/outputs['composite_png']
        record={**runtime(),'schema_version':2,'plotting_backend':'pygmt','classification_available':classification is not None,'implementation_hash':code_hash,'resource_hashes':resources,'fingerprint':fingerprint,'region':self.spec.run.region.name,'first_time':first_time,'second_time':second_time,'baseline_days':baseline,'synthetic':synthetic,'status':'candidate_classification' if classification else 'segmentation_only','config':self.spec.as_dict(),'source_files':[{'path':str(first),'sha256':hashes[0]},{'path':str(second),'sha256':hashes[1]}],'catalog_pair':catalog_metadata,'outputs':outputs,'segment_count':int(len(np.unique(labels[labels>0]))),'valid_texture_fraction':float(valid.mean()),'segmentation_pixel_size_m':[abs(transform.a),abs(transform.e)],'mask_provided':bool(self.spec.coastline),'metrics':metrics,'registration_qc':'not assessed; common grid does not prove subpixel registration','limitations':['Not validated for operational use','SLIC differs from the supplied SAM research workflow'] if self.spec.segmentation.backend=='slic' else ['Not validated for operational use']}
        write_json(manifest,record)
        return PairResult(directory,manifest,texture,segments,quicklook,classification)
