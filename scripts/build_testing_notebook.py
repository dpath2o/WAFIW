from pathlib import Path
import nbformat as nbf
nb=nbf.v4.new_notebook();cells=[]
def md(s):cells.append(nbf.v4.new_markdown_cell(s))
def code(s):cells.append(nbf.v4.new_code_cell(s))
md('''# AFIW primary-product component testing
Laptop-first Davis development. Algorithms live in the module; this notebook tests them. Offline cells use clearly labelled synthetic data. Supplied McMurdo data remain a separate research example. Full Sentinel-1 downloads and SNAP/SAM are opt-in and require local setup.

Install first: `python -m pip install -e ".[test]"`. Launch Jupyter from the project directory in that environment.''')
code('''from pathlib import Path
import json,sys
import numpy as np
import matplotlib.pyplot as plt
import rasterio
from afiw import WorkflowSpec, PrimaryWorkflow, SegmentationSpec, AFIWPaths
from afiw.processing.texture import normprod_smovar, rgb_texture
from afiw.classify.segmentation import Segmenter, segment_features
from afiw.workflows.demo import run_demo
from afiw.products.bulletin import BulletinBuilder
from afiw.metrics.change import change_metrics
PROJECT=Path.cwd().resolve()
if PROJECT.name=='notebooks': PROJECT=PROJECT.parent
assert (PROJECT/'configs/davis.yaml').is_file()
SPEC=WorkflowSpec.load(PROJECT/'configs/davis.yaml')
WORK=PROJECT/'notebook_output';WORK.mkdir(exist_ok=True)
print('Python:',sys.version.split()[0],'AOI:',SPEC.run.region.bbox)''')
md('## Texture response and masks\nPersistent texture should score higher than independent texture. Missing pixels remain unknown.')
code('''rng=np.random.default_rng(42);a=rng.normal(-15,2,(192,192))
b_static=a+rng.normal(0,.1,a.shape);b_drift=rng.normal(-15,2,a.shape)
static=normprod_smovar(a,b_static,11);drift=normprod_smovar(a,b_drift,11)
assert np.nanmedian(static[20:-20,20:-20])>np.nanmedian(drift[20:-20,20:-20])+.5
a[70:90,70:90]=np.nan;masked=normprod_smovar(a,b_static,11)
assert np.isnan(masked[70:90,70:90]).all()
fig,ax=plt.subplots(1,3,figsize=(12,3))
for axis,img,title in zip(ax,[static,drift,masked],['Persistent texture','Independent texture','Missing data']):
    axis.imshow(img,vmin=-.5,vmax=1);axis.set_title(title);axis.axis('off')
plt.show()''')
md('## RGB and laptop segmentation\nSLIC is an alternate backend, not SAM-equivalent. Segment IDs are not ice classes.')
code('''stack=np.stack([normprod_smovar(a,b_static,w) for w in (5,9,13)])
rgb,valid=rgb_texture(stack)
segments=Segmenter(SegmentationSpec(n_segments=80)).segment(rgb,valid)
assert np.all(segments[~valid]==0)
ids,features=segment_features(rgb,segments);assert features.shape==(len(ids),3)
print('Segments:',len(ids),'features:',features.shape)
plt.figure(figsize=(5,4));plt.imshow(segments,cmap='tab20');plt.title('Region IDs');plt.axis('off');plt.show()''')
md('## Tiled workflow and separate bulletin\nSynthetic coordinates near Davis exercise georeferencing only. No real ice conditions are claimed.')
code('''result=run_demo(WORK/'synthetic_demo')
manifest=json.loads(result.manifest.read_text())
assert manifest['synthetic'] and manifest['status']=='segmentation_only'
assert result.classification is None
assert manifest['segmentation_pixel_size_m']==[200,200]
print(result.manifest)
bulletin=BulletinBuilder(WORK/'synthetic_demo').build('2021-10-24',WORK/'synthetic_bulletin')
print('PDF:',bulletin)
from IPython.display import Image,display
display(Image(filename=str(result.quicklook)))''')
md('## Common-coverage change metrics\nUnknown cells in the later map must not count as retreat. These arrays are test fixtures.')
code('''old=np.array([[2,2,0,2],[0,1,3,255]],np.uint8)
new=np.array([[255,0,2,2],[0,1,2,2]],np.uint8)
change,metrics=change_metrics(old,new,np.ones(old.shape))
assert metrics['gain_km2']==1 and metrics['loss_km2']==1
assert change[0,0]==255
print(metrics)''')
md('## Actual supplied McMurdo arrays\nExisting predictions are not independent training labels or validation truth.')
code('''example=PROJECT/'examples/supplied_mcmurdo'
source_rgb=np.load(example/'rgb_image_20211010_20211022.npy')
source_labels=np.load(example/'label_map_20211010_20211022.npy')
assert source_rgb.shape[:2]==source_labels.shape
with rasterio.open(example/'predicted_map_20211010_20211022.tif') as src:
    predicted=src.read(1,out_shape=source_labels.shape)
    print('CRS:',src.crs,'bounds:',src.bounds)
assert set(np.unique(predicted)).issubset({0,1,2,3,255})
print('RGB:',source_rgb.shape,'classes:',np.unique(predicted))''')
md('## Davis catalogue\nThe saved public October 2021 catalogue is included. Refreshing is opt-in and unauthenticated.')
code('''LIVE_SEARCH=False
workflow=PrimaryWorkflow(SPEC)
if LIVE_SEARCH:
    catalog=workflow.search();pair_path=workflow.paths.catalog/'pairs.json'
else:
    catalog=json.loads((PROJECT/'examples/davis_catalog_202110/scenes.geojson').read_text())
    pair_path=PROJECT/'examples/davis_catalog_202110/pairs.json'
pairs=json.loads(pair_path.read_text());assert pairs
print('Scenes:',len(catalog['features']),'pairs:',len(pairs))
print('Pair:',pairs[0]['pair_id'],'days:',pairs[0]['baseline_days'],'overlap:',pairs[0]['common_aoi_fraction'])''')
md('## Optional real Sentinel-1 run\nConfigure SNAP GPT and a reviewed Antarctic DEM first. Provide Earthdata credentials locally, never in notebook cells. Enabling this may download gigabytes and take substantial time. Start with one pair.')
code('''RUN_REAL_PAIR=False
if RUN_REAL_PAIR:
    real_result=workflow.from_safe_pair(pairs[0],download=True)
    print(real_result.manifest)
else:
    print('Real SAFE download and SNAP integration have not been executed.')''')
md('## Optional SAM\nInstall `.[sam]`, supply a checkpoint and select CPU initially on Mac. MPS is opt-in. Lightweight vit_b settings differ from Gabby\'s vit_h, 95-point, two-crop-layer settings.')
code('''RUN_SAM=False
if RUN_SAM:
    from dataclasses import replace
    sam_spec=replace(SPEC.segmentation,backend='sam',checkpoint=str(PROJECT/'models/sam_vit_b_01ec64.pth'),device='cpu')
    sam_labels=Segmenter(sam_spec).segment(rgb,valid)
    print('SAM labelled pixels:',np.count_nonzero(sam_labels))''')
md('## Automated checks\nFormula agreement, tile seams, masks, pairing, classifier round-trip, common coverage, and bulletin semantics.')
code('''import subprocess
completed=subprocess.run([sys.executable,'-m','pytest','tests','-q'],cwd=PROJECT,text=True,capture_output=True)
print(completed.stdout)
assert completed.returncode==0,completed.stderr+completed.stdout''')
nb.cells=cells;nb.metadata={'kernelspec':{'display_name':'Python 3 (AFIW)','language':'python','name':'python3'},'language_info':{'name':'python','version':'3.11'}}
path=Path(__file__).resolve().parents[1]/'notebooks/primary_components.ipynb';nbf.write(nb,path);print(path)
