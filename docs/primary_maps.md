# Separate SAR composite and classification products with PyGMT

## Scope and checkpoint

The real Davis pair from 2–14 October 2021 has completed Sentinel-1 download, SNAP preprocessing, multi-scale texture calculation and SLIC segmentation on the user's Mac. Its manifest has `classifier: null` and `status: segmentation_only`. The previous `primary.png` combined a Matplotlib composite and segmentation boundaries; those boundaries were not ice classes.

Production maps now use **PyGMT**, with a polar stereographic map centred on the station AOI, annotated longitude/latitude frames, a graticule, station marker, dates and a legend. Rasterio handles GIS export/display reprojection; Pillow handles publication panel layout. Neither replaces PyGMT for map drawing. The legacy, supplied McMurdo illustration in `examples/research_example` remains a historical reference, not the new Davis processing workflow.

The analytical texture formula, SLIC/SAM implementation and mean-RGB SVM feature definition are unchanged. There is no automatic classification by texture threshold, land proximity or segment ID. A reviewed region-specific model or manual training labels must be supplied to produce candidate ice classes. Training alone does not establish scientific validation.

## Install the map runtime

For an existing Mac environment:

```bash
conda activate WAFIW
conda install -c conda-forge pygmt "gmt>=6.6" ghostscript
python -c "import pygmt; pygmt.show_versions()"
python scripts/run_primary.py --config configs/davis.yaml doctor
```

For a new runtime, `conda env create -f environment.yml` includes these dependencies. PyGMT is a Python wrapper around the GMT shared library; pip alone is insufficient. Ghostscript is needed to convert map output to PNG. Use a consistent conda-forge installation rather than combining unrelated Homebrew/conda libraries. Python package metadata declares PyGMT; the conda file supplies GMT and Ghostscript. The automated tests were exercised with PyGMT 0.19.0, GMT 6.6.0 and Ghostscript 10.08.0 on Linux; inspect the real maps on the Mac after updating.

`doctor` reports plotting availability and versions. A missing plotting runtime fails before a new raw-SAFE preprocessing attempt. On Azure, install/test this stack under the actual job account; do not rely on an interactive desktop or display server. These maps do not fetch GMT remote datasets. Later background imagery will require its own approved network routes.

## Output contract

| File | Meaning | Grid / missing data |
| --- | --- | --- |
| `texture.tif` | Three floating-point normalized-product texture scales | Full processing grid; NaN means unavailable. |
| `composite.tif` | Four-band RGBA composite SAR texture for GIS | Same CRS, bounds, transform and dimensions as `texture.tif`; 40 m in the Davis configuration. Alpha 0 is unavailable; reviewed land/shelf is grey with alpha 255. |
| `composite.png` | Separate framed PyGMT map of that composite | Geographic frame and station annotation; presentation image, not GIS data. |
| `segments.tif`, `rgb.npy`, `validity.tif` | Classifier features and segmentation/coverage diagnostics | Segmentation grid; about 400 m for current Davis settings. Segment IDs are not ice classes. |
| `classification.tif` | Single-band categorical candidate classes with colour table | Same segmentation CRS/transform/grid; uint8, NoData 255. Created only when classification is available. |
| `classification_rgb.tif` | Four-band RGBA display of the candidate classes | Same classification grid; unknown pixels transparent. Useful for overlays, without changing the class raster. |
| `classification.png` | Separate framed PyGMT map of candidate classes | Created only with an applied classifier or an existing classification raster. |
| `manifest.json` | Schema-2 provenance and output locations | Separate PNG/TIFF keys, `plotting_backend: pygmt`, classification availability and status. |

The GeoTIFFs are georeferenced raster layers, not pictures containing page margins, legends or axes. Those decorations belong to the PNGs. RGB conversion still clips texture values from `[-0.5,1]` into `[0,255]`; the three colour channels correspond to the configured texture windows. Valid black pixels remain observed, distinct from transparent NoData.

For plotting only, a bounded-size, nearest-neighbour geographic display copy is prepared for GMT. It is then plotted stereographically. This does not replace the native analytical/GIS rasters, and categorical values are never bilinearly interpolated. Grey distinguishes excluded land/shelf; light grey distinguishes no observation or unassigned pixels. No background land is invented where no reviewed exclusion mask exists.

Class IDs retain the existing convention:

| Code | Interpretation |
| --- | --- |
| 0 | Other observed ocean / pack, outside the candidate fast-ice classes |
| 1 | Reviewed excluded land / shelf / ice tongue / rumple |
| 2 | Candidate fast ice |
| 3 | Legacy melt-affected fast-ice class; requires reviewed labels and interpretation |
| 255 | Unknown, unobserved or unassigned |

Extent/change metrics retain classes **2 and 3** as candidate fast ice. Class 0 alone does not distinguish open water from pack ice. Class 3 is not an automatically inferred uncertainty category. The observed-ocean denominator includes only codes 0,2,3; missing swath and land are excluded. The product remains an unvalidated research classification until independent assessment is supplied.

## Regenerate the completed Davis product without repeating SNAP

Keep the existing product intact and create a derived directory:

```bash
DAVIS_PAIR=20211002T143959_20211014T143959_45c821c8
python scripts/render_primary.py \
  --manifest "afiw_data/davis/products/$DAVIS_PAIR/manifest.json" \
  --output "afiw_data/davis/products/${DAVIS_PAIR}_pygmt"
```

This uses the saved texture, segment, RGB and validity files. It produces the full-grid composite GeoTIFF and separate PyGMT PNG without downloading scenes, authenticating or rerunning SNAP. It writes a new schema-2 manifest with the source manifest hash and pointers to the original analytical inputs. Do not delete/move those inputs: derived maps depend on them. The source coastline path must remain available for full-grid excluded-land rendering. Output must be a new empty directory; changed maps/models do not overwrite old completed products.

Because the supplied Davis manifest has no classifier, this command will **not** manufacture a classification PNG/TIFF. To apply an existing trusted Davis model, add `--classifier models/davis_svm.joblib`. If the source already contains a classified raster, the command can render it without reapplying a model.

For newly processed pairs, the main workflow produces the separate outputs automatically. Configure `classifier` in the station YAML for supervised classification. Relative model paths resolve from the YAML's directory. Existing pair IDs with changed code/configuration still refuse conflicting overwrites: use the regeneration command for completed data, or a new processing root for recomputation.

## Prepare and apply a classifier from reviewed manual labels

The scripts now expose the existing segment-mean SVM training API. No observed Davis labels/model are bundled.

1. Open `composite.tif` and `segments.tif` in QGIS. Use a clearly documented label source and the research interpretation agreed with the domain reviewer. Stable texture over two dates does not by itself establish landfast attachment or motionlessness.
2. Create a blank label template at the exact segment grid:

```bash
python scripts/prepare_training_labels.py \
  --manifest "afiw_data/davis/products/$DAVIS_PAIR/manifest.json" \
  --output training/davis_labels.tif
```

3. Annotate/rasterize reviewed training areas into that grid using codes 0,2,3, leaving unlabelled cells at 255. Keep the exact CRS, pixel origin, transform, dimensions and one-band layout of `segments.tif`; avoid QGIS defaults that shift the grid. Land and unavailable observations are excluded by the saved validity mask, rather than being training classes. Include at least two manually labelled classes. The trainer ignores mixed segments when one class does not account for at least 90% of their labelled pixels; it does not guess a class for them.
4. Train:

```bash
python scripts/train_classifier.py \
  --manifest "afiw_data/davis/products/$DAVIS_PAIR/manifest.json" \
  --labels training/davis_labels.tif \
  --output models/davis_svm.joblib \
  --label-source "Reviewer, reviewed evidence and annotation date"
```

The model and neighbouring `.training.json` record the region, synthetic/real origin, source-manifest and label hashes, feature encoding and processing/segmentation contract. `validated` remains false. Synthetic models are rejected for real products. New models require matching texture/segmentation settings when applied. Existing trusted legacy models still require matching region and feature metadata; their absent preprocessing contract is a limitation that must be reviewed. Joblib models must come from trusted sources because loading them executes pickle machinery.

5. Apply and produce both separate maps in a new directory:

```bash
python scripts/render_primary.py \
  --manifest "afiw_data/davis/products/$DAVIS_PAIR/manifest.json" \
  --output "afiw_data/davis/products/${DAVIS_PAIR}_classified" \
  --classifier models/davis_svm.joblib
```

This keeps classification at the segmentation resolution. Upsampling it onto the 40 m composite would not restore classification detail. Validate with independently reviewed, spatially/temporally held-out labels before interpreting candidate extent or change as assessed observations. No independence claim is made for predicting the same pair used for training.

## Assemble only when producing the bulletin

```bash
python scripts/generate_bulletin.py build \
  --root "afiw_data/davis/products/${DAVIS_PAIR}_classified" \
  --region Davis --as-of 2021-10-15 \
  --output bulletins/davis_20211015
```

The bulletin builder consumes the separate PNGs and assembles its own `primary.png`, which is embedded in the PDF and LaTeX. It does not replot or reprocess SAR. `bulletin.json` records the source panels. An unclassified product contributes only the composite and explicit text that classification/extent is unavailable; segmentation boundaries do not fill the classification slot. Schema-1 combined quicklooks remain readable for historical publications. Revised renderings of the same observation date are not treated as a new earlier observation for change assessment.

## Verification and remaining work

Tests exercise real PyGMT drawing/GMT conversion, native-grid RGBA exports, categorical grids/colour tables, transparent missing pixels versus valid black, manual-label alignment, synthetic-model safeguards, separate PNGs and bulletin-only assembly. A synthetic labelled product was trained, classified and published through the full path. This verifies software behaviour, not Davis classification skill. The actual user-provided Davis TIFFs are local to the Mac, so its new maps need local review.

Visible imagery is **not implemented in this change**. A later adapter should record sensor/platform, processing level, actual acquisition time, cloud/quality screening, time difference from the second SAR scene, reprojection and spatial coverage. Terra is a platform carrying MODIS, rather than a separate visible sensor. A daily rendered mosaic must not be presented as one precisely timed overpass. VIIRS/MODIS true colour is useful summer context; a reflectance granule and its cloud/quality information provide stronger timing/quality control than an undifferentiated daily picture. Cloud-free daylight availability still needs checking.

For a robust fallback, the second Sentinel-1 backscatter raster is already contemporaneous with the SAR pair end and independent of solar illumination. A neutral ocean with the reviewed ADD land/shelf context is also clear when optical coverage is poor. Avoid a textured underlay that makes SAR colour interpretation harder; candidate class boundaries or controlled transparency may be preferable to opaque overlays. Optical choice and its network/authentication route will be assessed separately.

References: [PyGMT installation](https://www.pygmt.org/latest/install.html), [grdimage/image projection](https://www.pygmt.org/latest/api/generated/pygmt.Figure.grdimage.html), [NASA corrected reflectance imagery](https://forum.earthdata.nasa.gov/viewtopic.php?t=5203).

## Workflow logging

Operational CLI workflows now use Python `logging` with console output (stderr)
and a unique UTC timestamped log file. For Davis the default directory is
`~/afiw_data/davis/logs/`, independent of the configured analytical-data root.
Mawson and Casey use their corresponding station directories. Region is inferred
from the config/manifest, bulletin region, coastline station selection, or a
`[station]/catalog/pairs.json` path. Station-independent tasks such as downloading
a geoid use `~/afiw_data/general/logs/`; use `--log-station davis` if preferred.

The default console level is INFO; the file always records DEBUG diagnostics.
Stage start/completion, elapsed seconds, paths, grid and validity summaries,
segmentation/model decisions, output lists and exception tracebacks are recorded.
SNAP stdout/stderr is mirrored live into both destinations and also retained in
its per-scene `.snap.log`. Existing shell-friendly final output-path prints remain
on stdout. Arguments, environments and authentication credentials are not dumped.

All operational scripts accept `--log-dir`, `--log-level` and `--log-station`.
For the primary and bulletin CLIs place these global flags **before** the command:

```bash
python scripts/run_primary.py --config configs/davis.yaml --log-level DEBUG search
python scripts/render_primary.py --manifest "$MANIFEST" --output "$NEW_OUTPUT" --log-level DEBUG
```

Direct workflow calls in notebooks enable default logging as well. For explicit
control before running a workflow:

```python
from afiw.core.logging import configure_logging
configure_logging(station = 'davis', workflow = 'notebook', level = 'DEBUG')
```

## Why only the composite was produced

A manifest with `config.classifier: null`, `classification_available: false` and
`status: segmentation_only` has no ice classification to plot. `segments.tif`
contains object IDs, not fast-ice class labels. Re-rendering such a manifest without
`--classifier` produces `composite.png` and `composite.tif` and now emits an explicit
WARNING explaining why classification PNG/TIF outputs were skipped.

Apply a trusted local Davis classifier trained from reviewed manual labels, using
a **new** output directory (the earlier derived product is retained):

```bash
DAVIS_PAIR=20211002T143959_20211014T143959_45c821c8
python scripts/render_primary.py \
    --manifest "afiw_data/davis/products/$DAVIS_PAIR/manifest.json" \
    --output "afiw_data/davis/products/${DAVIS_PAIR}_pygmt_classified" \
    --classifier "/path/to/reviewed_davis_model.joblib"
```

See the manual-label/training workflow above if a suitable model is not yet
available. Successful classification produces `classification.png`, a single-band
GIS class raster `classification.tif`, and `classification_rgb.tif` for RGBA display.
The manifest exposes the GIS raster under both `classification` (existing consumer
key) and `classification_tif` (explicit TIFF alias). A source manifest that already
contains `outputs.classification` can be re-rendered without supplying the model
again; its classes, grid and metrics are retained. Training remains distinct from
independent validation.
