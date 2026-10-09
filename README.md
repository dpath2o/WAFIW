# Weekly Antarctic Fast Ice Watch (WAFIW) — primary-product milestone v0.1

**Pronunciation:** WAFIW is pronounced “WAFF-ee”

A laptop-first Python package for Davis Sentinel-1 acquisition, terrain-corrected backscatter preparation, multiscale normalized-product textures, segmentation, optional supervised classification, and independent weekly bulletin generation. The object-oriented API follows shuga's configuration-object/path-manager/workflow pattern. There are no PBS or Gadi dependencies.

**What has actually run:** public Davis catalogue discovery; numerical and geospatial component tests; a synthetic tiled texture → SLIC segmentation → PDF/LaTeX workflow; inspection of supplied McMurdo arrays; reconstruction of the supplied illustrative PDF.

**What has not run:** an authenticated scene download; raw SAFE processing in SNAP; SAM inference; a scientifically trained Davis classifier; a real Davis extent/change assessment; macOS execution; SWOT retrieval. These need local assets or credentials not present here. The SNAP adapter is an integration candidate, not a validated replacement for the original external preprocessing chain.

## Setup documentation

- [Installation, conda and ADD coastline preparation](docs/installation.md)
- [DEM download, storage and preparation](docs/dem_preparation.md)

## Start on your Mac

Use Python 3.11 or 3.12. Python handles processing; SNAP is a separate application needed only for raw SAFE files. The pure-Python/Rasterio workflow also accepts existing georeferenced single-band dB backscatter TIFFs.

Extract the ZIP to a working project directory, then in Terminal:

```bash
cd /path/to/afiw_project
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
python -m pytest tests -q
python scripts/run_primary.py --config configs/davis.yaml doctor
python scripts/run_primary.py demo --output demo_output
python scripts/generate_bulletin.py build --root demo_output --as-of 2021-10-24 --output demo_output/bulletin
```

The last command produces a **clearly synthetic** PDF and an editable LaTeX file. It requires no satellite credentials, SNAP, SAM weights or TeX installation. Do not interpret it as Davis observations.

To launch the testing notebook:

```bash
python -m pip install jupyterlab
python -m ipykernel install --user --name afiw --display-name "Python (AFIW)"
python -m jupyterlab notebooks/primary_components.ipynb
```

Select **Python (AFIW)**. Offline notebook cells are enabled; real downloads, live catalogue refresh and SAM are opt-in switches. Notebook code cells were checked sequentially in Python here; starting an actual Jupyter kernel was blocked by this execution environment's socket restrictions, so the Mac kernel run remains a local check.

On Windows activate `.venv\Scripts\Activate.ps1` instead. The workflow uses pathlib and subprocess argument lists, not shell-specific processing commands. macOS/Windows/Azure portability is designed for, but only Linux/Python component execution has been tested here.

## Discover Davis scenes

Review `configs/davis.yaml`: dates, provisional approaches AOI, beam mode and co-polar band. Relative file paths resolve from the configuration file, not the terminal working directory.

```bash
python scripts/run_primary.py --config configs/davis.yaml search
```

The actual October 2021 test found **23 scenes and 12 compatible pairs**. The saved public catalogue is in `examples/davis_catalog_202110/`; it is metadata only. Pair selection requires matching relative orbit, flight direction, beam mode and polarization, a configured temporal baseline, and common footprint coverage within the AOI. Missing metadata excludes a pair. Catalogue overlap is not a guarantee of usable raster coverage.

A four-day observation target is an aspiration, not a forced pairing rule. The default pair baseline is 3–24 days; longer baselines are recorded and reported. Do not interpret a 12-day pair as a four-day update.

## Process one real pair

1. Install ESA SNAP with the microwave/Sentinel-1 toolbox. Set `snap.executable` to the absolute GPT executable path if `gpt` is not on PATH.
2. Supply a reviewed Antarctic DEM. SNAP's external DEM must have geographic WGS84 coordinates and elevations in metres. Resolve vertical datum explicitly: the config default disables EGM conversion only for ellipsoidal elevations. Ensure coverage of the AOI and geocoding margins, and geoid-consistent surface heights over ocean; DEM nodata must not silently erase sea ice. A projected REMA mosaic is not directly interchangeable with the required geographic external DEM.
3. Supply a locally managed Earthdata token using the `EARTHDATA_TOKEN` environment variable. Do not put it in YAML, notebook cells or source files. Use your normal local credential handling.
4. Run only one pair initially:

```bash
python scripts/run_primary.py --config configs/davis.yaml run-catalog --pair-index 0 --max-pairs 1 --download
```

Without `--download`, already-downloaded SAFE ZIPs must exist under `afiw_data/davis/raw/`. Download staging validates that the ZIP contains a SAFE manifest; it does not claim a full checksum audit. Full-scene downloads and SNAP may take much longer than the small offline tests.

The SNAP graph applies orbit correction, GRD border-noise removal, thermal-noise removal, AOI subset, beta0 calibration, terrain flattening to gamma0, terrain correction and conversion to dB. It explicitly keeps sea pixels (`nodataValueAtSea=false`). No extra speckle filter is silently introduced. Generated graph, run log, DEM reference and source checksum are retained.

**Scientific review needed:** match this chain to the radiometry/preprocessing used for Alex/Gabby/Tony's research. Putting both images on the same grid does not prove subpixel co-registration. Stationary rock/coastline registration checks, incidence-angle effects, exclusion-mask suitability and classification skill remain acceptance work.

## Use processed backscatter instead

```bash
python scripts/run_primary.py --config configs/davis.yaml process-raster \
  --first /path/first_gamma0_db.tif --second /path/second_gamma0_db.tif \
  --first-time 2021-10-10T11:01:00Z --second-time 2021-10-22T11:01:00Z
```

Use real acquisition times from metadata, not file modification dates. Single-band georeferenced TIFFs are required. Set `processing.input_units: linear_power` only for linear power input; conversion to dB is then explicit. The default is `db`, matching the provided research filenames. Pair scenes should already be compatible in acquisition geometry and radiometry; the TIFF command cannot recover missing orbit metadata.

The module aligns data to a common EPSG:3031 station grid and computes three texture scales in bounded-memory tiles. It keeps NoData separate from land/ice-shelf exclusions. Incomplete output runs can be retried before a completion manifest exists; completed products refuse conflicting overwrites. Inputs/configuration/resource hashes are retained. Use a new output root or pair ID for changed settings.

## Segmentation and classification

- **SLIC:** default laptop testing backend, using only valid texture pixels. It is not equivalent to SAM and does not identify ice classes.
- **SAM:** install `python -m pip install -e ".[sam]"`, supply a local checkpoint and select `backend: sam`. CPU is the default. `device: mps` is optional, checked for availability, and requires Mac testing. The lightweight vit_b defaults differ from the supplied vit_h/95-point/two-crop-layer settings. Reproduce the research settings explicitly when resources and weights permit.
- **SVM:** the module provides the supplied notebook's mean-RGB segment features and an SVC training/prediction API. Manual labels and a scientifically assessed Davis model were not supplied. Existing prediction TIFFs are not treated as training truth. The model must declare the matching region, and a synthetic model is rejected for real scenes. Load only trusted local joblib files.

A candidate extent requires `classifier` **and** reviewed ADD-style coastline/exclusion polygons. Provide a CRS-bearing GeoJSON with `surface` values (`land`, `ice shelf`, `ice tongue`, `rumple`). All four are excluded from sea-ice detection. No arbitrary mask erosion is applied. Without a classifier the output and bulletin explicitly say **segmentation only**.

Class IDs: 0 pack/ocean, 1 excluded land/shelf, 2 candidate fast ice, 3 legacy melt-affected fast-ice class, 255 unknown. Segment ID 0 denotes unassigned/invalid; other segment IDs are not classes. The default segmentation grid is about 400 m for 40 m input with 10× downsampling; the exact resulting spacing is recorded. Upsampling would not restore 40 m classification detail.

## Generate products separately

```bash
python scripts/generate_bulletin.py build \
  --root afiw_data --region Davis --as-of 2021-10-31 --output bulletins/2021-10-31
```

This reads completed pair manifests without reprocessing SAR. Outputs are PDF, LaTeX, quicklook and a structured text/quality record. Add `--compile-latex` if MacTeX/TeX Live is installed; `main.pdf` will then be the compiled LaTeX version. The direct PDF uses ReportLab and needs no TeX. Both were inspected as one-page outputs.

Automatically selected text is currently conservative: observation dates/baseline, status, candidate area when classified, change only on common observed ocean cells, effective segmentation spacing, mask status, and stale-observation warnings. Missing swath pixels cannot count as retreat. Comparisons require identical grids and compatible processing/model/mask settings. Area uses pixel-centre projection-scale correction, not raw EPSG:3031 pixel area. This is not a navigation recommendation.

For weekly historical issue selection across processed seasons:

```bash
python scripts/generate_bulletin.py season --root afiw_data --region Davis \
  --start-years 2021 2022 2023 --start-month 9 --end-month 4 --output bulletins
```

This generates a Sep–Apr weekly series from **already processed** results. It does not download an entire historical archive. Dates with no earlier product are skipped; repeated/stale observations are labelled. Historical persistence, season-normalized anomaly text and station-specific hazard wording are later work; historical bulletin generation is the foundation, not a completed seasonal assessment system.

Reproduce the already-discussed illustrative McMurdo+SWOT PDF separately:

```bash
python scripts/generate_bulletin.py research-example \
  --template examples/research_example --output example_pdf
```

The example's SWOT figure remains a detrended sea-surface-height-anomaly illustration, not validated freeboard. The Davis pipeline leaves the secondary product explicitly unprocessed.

## Python API

```python
from afiw import WorkflowSpec, AFIWPaths, PrimaryWorkflow
from afiw.products.bulletin import BulletinBuilder

spec = WorkflowSpec.load("configs/davis.yaml")
paths = AFIWPaths(spec.root, spec.run)
workflow = PrimaryWorkflow(spec)
catalogue = workflow.search()
# result = workflow.from_rasters(first, second, first_time, second_time)
# BulletinBuilder(spec.root, "Davis").build("2021-10-31", "bulletins/2021-10-31")
```

## Layout

`src/afiw/core` holds specs, paths and provenance; `observations` holds acquisition adapters; `processing` holds SNAP/grid/texture components; `classify` holds segmentation and SVM; `metrics` holds extent/change calculations; `plotting` holds quicklooks; `products` holds PDF/LaTeX generation; `workflows` coordinates these components. `scripts` are thin CLI entry points, and `notebooks` tests public APIs.

`legacy/` retains the supplied Python/notebook/MATLAB source for traceability, with notebook outputs removed and source checksums recorded. These files are reference material, not automatically executed. The two SWOT versions remain distinct; MATLAB is retained, not automatically translated. No supplied HPC cleanup script is invoked. See `docs/source_audit.md` for adoption decisions and `docs/validation.md` for test evidence/limits.

No new open-source ownership licence is asserted over the supplied research code. Keep this working package internal pending the ownership/attribution discussion already underway.

## References

- shuga architecture: https://github.com/dpath2o/shuga (core specs and paths inspected).
- ASF search: https://docs.asf.alaska.edu/asf_search/searching/
- ASF downloads: https://docs.asf.alaska.edu/asf_search/downloading/
- SNAP downloads: https://step.esa.int/main/download/
- SNAP external DEM/terrain correction: https://step.esa.int/main/wp-content/help/versions/9.0.0/snap-toolboxes/org.esa.s1tbx.s1tbx.op.sar.processing.ui/operators/RangeDopplerGeocodingOp.html
- SCAR ADD reference outlines in the illustrative figure: doi:10.5285/13c4d2f1-8903-4d7f-8977-592121975554, CC BY 4.0.
