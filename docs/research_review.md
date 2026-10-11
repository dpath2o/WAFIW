# Research review and adoption decisions

This review used the supplied research review archive, the actual annotation arrays, the newer `posthonours/Fastice_Mapping` notebooks/scripts, the standalone `normalized_product` package and WAFIW's completed Davis manifest. The audit hashes and training results are in `reports/`; the external arrays/checkpoints are not redistributed in this repository.

## Finding: shared training is supported; station performance remains an assessment question

The supplied `SAM-SVM.ipynb` trains one default scikit-learn SVC from five Prydz and five Thwaites scene pairs. Its features are the three RGB channel means within each annotated segment. It fits the SVM in the notebook before prediction; it is not a provided, universally assessed Davis model. SAM supplies pretrained object segmentation, not physical fast-ice classes.

WAFIW's earlier region-equality restriction and documentation implying mandatory new Davis training were too restrictive. The revision supports shared annotation training and explicit candidate transfer, while recording source sites, model provenance and preprocessing differences. **No new per-station annotation is required to run the candidate product.** Whether additional labels or a station-specific model are needed must follow independent station assessment.

The existing Davis manifest has no classifier and no classification output; the missing PNG/TIF is explained directly by those fields. Logging now makes that decision visible, and the complete-product command refuses incomplete classification rather than returning only a composite.

Research attribution: the supplied `normalized_product` module credits initial development to A. P. Doulgeris, G. Burke and A. Fraser, and packaging to J. Lohse. The review retains that provenance; WAFIW does not assert a new licence over their research material.

## Adopted numerical/scientific workflow

| Supplied component | WAFIW adoption / deliberate difference |
| --- | --- |
| Boxcar difference and local standard deviation | Retained three scales, default 11/21/33. The method is boxcar smoothing, not Gaussian despite stale names/comments in some research scripts. |
| NormProd divided by smoothed mean-SD variance | Retained interior fully valid formula; vectorized weighted filtering and tile halos replace slow `generic_filter`. Missing data use local valid weights instead of scene-wide mean filling. |
| New standalone `normalized_product` package | Reviewed for packaging, mask/RGB/resampling improvements. Existing WAFIW components already cover the numerical core and geospatial orchestration; no additional GDAL/loguru processing stack is imported. |
| RGB encoding | Earlier notebooks cast an unbounded scaled float directly to uint8; newer `normprod_utils.stack_2_RGB` clips first. WAFIW clips and rounds to uint8. Truncation/rounding and order of resampling still differ. |
| Tenfold reduction | WAFIW uses nearest sampling of texture then RGB encoding and derives the exact segmentation transform from bounds. Research notebooks use bilinear `scipy.ndimage.zoom` after uint8 encoding, with zero-filled masked channels. These are not identical features. |
| SAM segmentation | Optional pretrained vit_b adapter, smaller-mask overlap priority, segment-0 gaps unknown. Sampling/IoU/stability/crop/NMS/minimum-area parameters are now explicit configurable fields. April 2026 notebook settings differ from earlier annotation settings. |
| SLIC | Retained only as an alternative/diagnostic backend. Using a SAM-trained SVM on SLIC objects is explicit unvalidated transfer, not reproduction of the original segmentation distribution. |
| SVM training | Existing segment-index annotation vectors imported correctly; HH-prefixed and legacy HH filenames supported. Default SVC and mean-RGB features retained. |
| Segment 0 and land class 1 | Background is not a coherent physical object; it is excluded from training and remains unknown in inference. Land/shelf is imposed by the reviewed mask, not learned by the ice SVM. Original loops admitted both if labelled. |
| Land/shelf exclusions | Native reviewed ADD land/shelf/tongue/rumple mask, separate from absent observations. No arbitrary 100-pixel mask erosion is copied. |
| Raster georeferencing | Native processing and segmentation grids preserved separately; PNG cartography uses PyGMT and native TIFFs remain GIS layers. Display reprojection does not modify analytical grids. |
| Validation notebook | Original area-scatter/correlation and manually inserted RMSE text do not establish pixelwise agreement or independent station transfer. New outline assessment reports spatial TP/FP/FN/TN areas and IoU on an explicit reviewed domain. |
| Publication | Composite and classification stay separate through processing; bulletin assembly alone creates the combined panel. |

Radiometric provenance, source scene grid size, registration quality, incidence-angle effects and annotation interpretation cannot be recovered from unreferenced RGB `.npy` arrays. WAFIW's SNAP gamma0/dB chain and masked texture processing cannot be asserted equivalent to external ISCE3 inputs from filenames alone. The imported model therefore has an incomplete source preprocessing contract and requires explicit candidate transfer review. Its use is not disguised as a locally matched, validated model.

## Actual data audit

The upload contains eleven annotated scene folders, six nominal Prydz and five Thwaites. The default reference list has ten.

- `prydz_20240708_20240720/rgb_image_*.npy` is byte-identical to Thwaites's HH RGB, and its segment map is also byte-identical. Its annotation vector differs, including conflicting class assignments. It is absent from the reference notebook's training list and excluded by default. Custom duplicate selections fail for review.
- Thwaites has `HH_rgb_image_*` and `HV_rgb_image_*`, whereas the old main training notebook constructs unprefixed paths. The importer resolves the supplied naming convention explicitly and never silently swaps polarizations.
- Annotation vectors are indexed by segment ID, not per-pixel label rasters. Some vectors are longer than the populated segment-ID range; NaN/unpopulated entries are not training examples.
- Several scenes label unassigned segment 0 as ocean, and the duplicate folder labels it as land. Segment 0 is excluded consistently. Class 1 is likewise excluded from the ice classifier.
- The canonical HH selection has **68** usable labelled object segments: **27 class 0**, **40 class 2**, **one class 3**. This is much smaller than the pixel count/file size suggests. Class 3 cannot establish general melting-ice discrimination with that support.

No hyperparameter search or pixel-random split was used. Pairs sharing an acquisition at the same site are kept together, including the linked three-pair Thwaites October–November chain. Site holdouts provide a second transfer diagnostic.

| Assessment | Result on supplied HH annotations | Interpretation |
| --- | --- | --- |
| Acquisition-group holdouts | Eight folds; seven balanced accuracies 0.917–1.000; January Prydz fold 0.556 | That fold holds the only class-3 example, so its training set has never seen class 3. |
| Hold out Prydz | Balanced accuracy 0.648 across supported test classes; 6/6 class-0 and 17/18 class-2 segments correct; 0/1 class-3 correct | Melting example is absent from training. This is annotation-level cross-site assessment. |
| Hold out Thwaites | Balanced accuracy 0.976; 20/21 class-0 and 22/22 class-2 segments correct | Encouraging for these labelled segments; not a Davis accuracy estimate. |

The report records confusion matrices and unseen test classes so a single summary score does not conceal the support problem. These scores are segment-weighted, not pixel/area-weighted, and labels used in model development are not independent validation truth.

## Validation references require repair/review before use

Seventeen shapefile datasets were inspected. They all declare EPSG:3031, but that does not make all of them suitable reference truth:

- The McMurdo 2021-09-01/2021-09-13 outline is empty.
- The EPB October 2021 outline, the Thwaites 2024-09-06/2024-09-18 outline, and the file under the Thwaites 2024-10-12/2024-10-24 directory include invalid geometry.
- The latter directory contains an outline named with the conflicting dates 2024-07-20/2021-08-01, conflicting with its directory dates and with an expected 2024 acquisition sequence. Its correct identity cannot be guessed.
- Most attributes contain an empty `id`; some contain manually stored areas. They are outline geometries, not a fully coded multi-class raster or a declared exhaustive evaluation domain.

No source reference was silently repaired or renamed. The new validation command rejects empty/invalid geometry and conflicting declared/file dates, requires pair date matching, and requires a separate reviewed evaluation-domain polygon. Unknown/unobserved and excluded land cells remain outside the confusion matrix; unassessed ocean coverage is reported.

## Consolidation and remaining acceptance work

The primary CLI and public Python APIs now coordinate training, acquisition/processing, complete-product generation, rendering and outline assessment. Publication can follow immediately from `produce` or run independently against completed manifests. Thin historical script entry points remain for existing commands. The notebook uses these same APIs.

Overlapping milestone/source-audit/map/validation guides, historical illustration PDFs/data and duplicated legacy Python/notebook/MATLAB/SWOT executables were removed from the current tree. Historical hashes remain in `docs/reference_inventory.json`; originals remain in Git history and external source archives. Setup guides for masks, DEMs, SNAP, authentication and Azure remain relevant prerequisites. None of the supplied research cleanup scripts is invoked against user data.

Software and actual-array training checks are recorded in `reports/pytest.txt`, `reports/notebook_cells.json` and `reports/research_training_HH.json`. Real Davis analytical inputs were not supplied here, so no real Davis classification/performance result is claimed. SAM checkpoint inference, Mac/MPS verification, exact external radiometry/registration comparison, independently assessed station accuracy and class-3 support remain acceptance work. Visible imagery, long-term seasonal assessment and SWOT freeboard remain future extensions rather than implied completed stages.
