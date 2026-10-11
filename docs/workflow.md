# Consolidated primary-product workflow

The primary product is a pair of separate **composite and classified maps**, their native GeoTIFFs, and a provenance manifest. A bulletin assembles those two maps without repeating processing. All primary stages are accessible through `afiw-primary` or the equivalent `python scripts/run_primary.py`. Relative resource paths in YAML resolve from the YAML directory; command-line paths resolve from the working directory.

## 1. Reuse existing training annotations

**Already have the supplied model bundle?** Extract `fastice_HH_svm.npz` and
`fastice_HH_svm.training.json` into `afiw_data/models/` from the project root,
then go directly to section 2. Do not pass this model directory as
`--training-root`: that option requires the original scene folders containing
RGB, segment and annotation `.npy` arrays. Missing scene folders are now checked
before any import, with a message directing bundle users to `produce --classifier`.

The research method has two distinct learned components: a pretrained SAM segmentation checkpoint and a supervised SVM that assigns ice/ocean classes to segment-mean RGB features. The checkpoint alone does not provide fast-ice classification. Existing research annotations supply the SVM labels, so new labels for each station are **not automatically required**.

```bash
python scripts/run_primary.py train-research \
  --training-root /path/to/SVM_trainingdata \
  --output "afiw_data/models/fastice_HH_svm.npz" \
  --label-source "Research segment annotations, reviewed source and annotation history" \
  --log-station Davis
```

A supplied `WAFIW_HH_candidate.zip` contains the portable candidate and its report; extracting these into `afiw_data/models/` in the project directory can replace this import step. The feature table is fitted automatically in the local runtime when the classifier is loaded.

The default selection is the ten Prydz/Thwaites folders used in the supplied `SAM-SVM.ipynb`. The additional `prydz_20240708_20240720` folder is excluded: its imagery/segments duplicate Thwaites and its annotations conflict. Custom subsets use `--scenes scene_name ...`; duplicates then fail instead of being silently counted twice.

The importer reads `.npy` with `allow_pickle=False`, validates shapes/types/classes, resolves `HH_rgb_image_*` and reference `rgb_image_*` filenames, and indexes the annotation vector by segment ID. NaN labels, segment 0 and land/shelf class 1 are excluded. Unprefixed reference RGB is interpreted as HH. `--polarization HV` requires explicit HV files and an explicit compatible subset; it never substitutes HH. Current primary acquisition processing supports HH/VV, so an HV research model is for separate analysis, not an interchangeable primary classifier.

Training writes:

- A portable `.npz` feature/annotation table with model provenance, fitted as an SVC in the local runtime when loaded; or an executable `.joblib` estimator when that output suffix is selected.
- A neighbouring `.training.json` with per-scene file hashes, accepted segments, class counts, source sites, exclusions, acquisition-group/site assessments, and model checksum.

The SVM uses the supplied mean-three-channel uint8 feature definition and default `SVC`. Existing labels are numerical training input; an LLM does not train itself on imagery. Portable `.npz` loading uses `allow_pickle=False` and fits the same default SVC in the receiving runtime, avoiding cross-version estimator-pickle assumptions. Joblib loads executable pickle machinery: use only artifacts you trust and matching scikit-learn environments. Keep model/report together, and retain the source arrays externally. Neither training nor this report sets `validated=true`.

Training over every Sentinel-1 acquisition since launch is unnecessary. Start with representative labelled scenes, assess transfer at a target station across seasons and acquisition conditions, and add/revise labels only if that assessment shows a need. Historical archive processing belongs to retrospective production and seasonal analysis after the method is accepted.

## 2. Complete an already processed pair

The supplied Davis manifest says `classifier: null`, `status: segmentation_only`, and `classification_available: false`. That explains the missing classified PNG/TIF: rendering had no classifier or previous class raster to apply. Segment IDs cannot fill that role.

```bash
DAVIS_PAIR=20211002T143959_20211014T143959_45c821c8
python scripts/run_primary.py produce \
  --manifest "afiw_data/davis/products/$DAVIS_PAIR/manifest.json" \
  --classifier "afiw_data/models/fastice_HH_svm.npz" \
  --allow-model-transfer \
  --output "afiw_data/davis/products/${DAVIS_PAIR}_classified_v2" \
  --bulletin-output "bulletins/davis_20211015" --as-of 2021-10-15
```

`produce` requires classification. It can apply the supplied model, or re-render an existing classification raster without one. It uses saved `texture.tif`, `rgb.npy`, `segments.tif` and `validity.tif`, preserving their analytical grid. A reviewed exclusion mask is required when applying a model. The coastline checksum must match the source record; changed masks require analytical recomputation. Source files/manifest are preserved. Output must be a new empty directory.

`--allow-model-transfer` records explicit **candidate** reuse across sites or different/incompletely documented preprocessing. It is required for the imported research model, including its use on the old Davis SLIC segments. It cannot bypass synthetic-to-real protection, incompatible polarization, unsupported features, or missing masks. It does not certify scientific suitability. The new manifest includes model metadata and the reasons transfer was recorded.

For composite-only diagnostics, use `render` instead of `produce`. The older `scripts/render_primary.py` remains a compatibility entry point and supports `--require-classification` and `--allow-model-transfer`. There is no need to rerun SNAP just to classify the existing SLIC product, but reproducing SAM segmentation requires recomputing that analytical stage.

## 3. Configure subsequent classified processing

Retain existing station mask/DEM/resource paths, then update the station YAML deliberately:

```yaml
classifier: ../afiw_data/models/fastice_HH_svm.npz
require_classification: true
allow_model_transfer: true # candidate transfer; review scientific suitability
```

The checked-in station configs retain diagnostic SLIC defaults and no model path, so a fresh installation can run component tests. For the supplied April 2026 SAM notebook profile, install `python -m pip install -e ".[sam]"`, obtain the trusted `vit_b` checkpoint, and configure:

```yaml
segmentation:
  backend: sam
  downsample: 10
  checkpoint: ~/afiw_data/models/sam_vit_b_01ec64.pth
  sam_model: vit_b
  device: cpu # cuda on an available GPU; mps requires Mac verification
  points_per_side: 90
  pred_iou_thresh: 0.75
  stability_score_thresh: 0.65
  crop_n_layers: 2
  crop_overlap_ratio: 0.65
  box_nms_thresh: 0.3
  min_mask_region_area: 50
  max_pixels: 4000000
```

Other supplied annotations used different SAM settings; this is a **documented notebook profile**, not proof that every training array was produced with it. Dense SAM sampling/crops can be expensive on CPU. SLIC remains a diagnostic/alternative segmentation backend; changing it or texture settings changes the classifier's input domain. WAFIW does not silently substitute a backend when SAM is unavailable.

Review dates, AOI and acquisition constraints, then discover/select pairs:

```bash
python scripts/run_primary.py --config configs/davis.yaml doctor
python scripts/run_primary.py --config configs/davis.yaml search
python scripts/run_primary.py --config configs/davis.yaml run-catalog \
  --pair-index 0 --max-pairs 1 --download --prepare-orbits \
  --require-classification
```

`--download` requires local Earthdata authentication only for missing scenes. `--prepare-orbits` prepares/checks precise orbit resources in the cache used by SNAP. Without `--download`, the selected SAFE ZIPs must already be cached. The SNAP graph produces single-band gamma0 dB; see the setup guides for DEM datum/coverage and runtime details. Complete-product mode checks for a model/mask before raw processing.

For existing compatible single-band backscatter rasters:

```bash
python scripts/run_primary.py --config configs/davis.yaml process-raster \
  --first /path/first_gamma0_db.tif --second /path/second_gamma0_db.tif \
  --first-time 2021-10-02T14:39:59Z --second-time 2021-10-14T14:39:59Z \
  --require-classification
```

Use actual acquisition metadata. `input_units: linear_power` explicitly converts positive power to dB; all subsequent texture computation is on dB. Common-grid resampling does not prove physical subpixel registration. Acquisition/radiometry compatibility must be reviewed for externally prepared TIFFs.

Products fingerprint source files, configuration, implementation and resources. A completed mismatched product is not overwritten. For changed analytical settings, use a new output root; for new render/classification settings, use a new derived directory. A derived manifest points back to analytical inputs: do not remove those inputs while it is in use.

## 4. Assess station transfer

Station validation is needed to decide whether additional training is necessary. Supplied outlines do not all have usable geometry or consistent names/dates, and no matching reference imagery/classified products were included for a complete independent assessment.

After reviewing a reference outline and its date, supply a **separate evaluation-domain polygon** within which the outline is considered complete. Outside the outline is reference ocean only inside this domain. Do not assume the whole AOI has been labelled.

```bash
python scripts/run_primary.py validate \
  --manifest /path/classified/manifest.json \
  --reference /path/reviewed_outline_20211002_20211014.shp \
  --domain /path/reviewed_evaluation_domain.geojson \
  --first-date 2021-10-02 --second-date 2021-10-14 \
  --label-source "Reviewer, independent evidence, completeness and annotation date" \
  --output /path/assessment/davis_20211002_20211014.json
```

The assessment requires matching pair dates, valid CRS-bearing polygon geometries, and a matching classification grid. Filename date conflicts fail. It reports projection-scale-corrected TP/FP/FN/TN areas, binary precision/recall/IoU, and unassessed ocean coverage. Land/shelf and unknown/unassigned cells do not become ocean or false retreat. It combines predicted classes 2+3 for binary fast ice; it does not separately validate melting class 3 or automatically mark a model validated.

Use temporally/spatially held-out station observations, independent labels, registration checks and reviewed preprocessing. Examine nearshore errors, summer/melt, different geometries and coverage. The existing annotation holdouts are useful diagnostics, not Davis validation. If errors reveal a station/domain gap, add targeted labels using `prepare_training_labels.py` and `train-labels`; per-station models are an available remedy rather than a mandatory architecture.

```bash
python scripts/prepare_training_labels.py --manifest /path/product/manifest.json --output /path/labels.tif
python scripts/run_primary.py train-labels --manifest /path/product/manifest.json \
  --labels /path/reviewed_labels.tif --output /path/local_model.joblib \
  --label-source "Reviewer and independent annotation evidence"
```

Labels must exactly match the saved segment grid: 0,2,3; unlabelled 255. The local trainer records a strict preprocessing contract; compatible reuse needs no transfer override. Mixed segments require at least 90% agreement among labelled pixels. No existing prediction raster is accepted as independent truth by inference.

## 5. Publish the bulletin

The optional `produce --bulletin-output` builds a one-page PDF/LaTeX bulletin. Independently publish any completed product without repeating SAR processing:

```bash
python scripts/generate_bulletin.py build \
  --root /path/to/classified_product --region Davis --as-of 2021-10-15 \
  --output /path/to/bulletin
```

The bulletin assembles the separate PNGs into its own `primary.png`; native maps remain separate. Its JSON records the source panels, observation age, limitations and change metrics. Change requires matching analytical grids and compatible model/mask/configuration hashes, and uses common observed ocean coverage only. Weekly season publication consumes already processed results; it does not train a model or download historical scenes.

## Output contract and logs

| Output | Meaning |
| --- | --- |
| `texture.tif` | Three float NormProd_SmoVar scales on the processing grid; NaN unknown. |
| `composite.tif` / `composite.png` | Native full-grid RGBA GIS raster / separate framed PyGMT map. |
| `segments.tif`, `rgb.npy`, `validity.tif` | Segment IDs, classifier RGB and coverage/exclusion mask at segmentation resolution. |
| `classification.tif` | uint8 classes: 0 pack/ocean, 1 excluded land/shelf, 2 candidate fast ice, 3 legacy melting fast ice, 255 unknown. |
| `classification_rgb.tif` / `classification.png` | Native RGBA classification layer / separate framed PyGMT map. |
| `manifest.json` | Provenance, exact output paths, grid spacing, model/transfer review, status and metrics. |
| Bulletin `bulletin.pdf`, `main.tex`, `primary.png`, `bulletin.json` | Publication assembled from completed primary maps. |

Classification remains at the segmentation resolution (about 400 m for the default 40 m / tenfold settings); the composite retains the processing grid. A finer display does not restore classification detail. Class 0 does not distinguish pack from open water. Class 3 is poorly supported in the supplied labels; combined candidate extent must retain that limitation.

Each command logs stage starts, durations, inputs/outputs, decisions, masks/grids, class counts and exceptions to the console and a DEBUG file under `~/afiw_data/[station]/logs/`. SNAP/LaTeX subprocess logs are mirrored. Override with `--log-dir`, `--log-level` or `--log-station`; cross-site training defaults to `general`. Direct Python/notebook workflows enable logging too. Final stdout remains the result path for scripting.

Visible-imagery underlays, independently validated operational ice products, archive-wide seasonal anomaly/persistence and SWOT freeboard remain separate development tasks. They are not implied by successful classification/export or bulletin generation.
