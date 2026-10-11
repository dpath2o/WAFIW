# Weekly Antarctic Fast Ice Watch (WAFIW)

WAFIW (“WAFF-ee”) produces separate Sentinel-1 texture and candidate fast-ice maps, georeferenced rasters, provenance, and a weekly PDF/LaTeX bulletin. One primary CLI coordinates acquisition, processing, reusable supervised classification, assessment, and map export; the bulletin CLI can also publish already completed products independently.

The supplied research annotations can train a **shared research SVM**. New manual training at each station is not a software requirement. Applying it to Davis, Mawson or Casey is a candidate transfer that needs assessment of preprocessing and station performance. Training the SVM is a short numerical fit on existing labelled segment features; it does not require an LLM or processing the entire Sentinel-1 archive first.

Start with [the consolidated workflow](docs/workflow.md). The [research review](docs/research_review.md) explains the adopted method, data problems, training results, and what remains scientifically unestablished.

## Setup

```bash
conda env create -f environment.yml
conda activate WAFIW
python scripts/run_primary.py --config configs/davis.yaml doctor
python -m pytest tests -q
```

For an existing environment, use `conda env update -n WAFIW -f environment.yml`. PyGMT requires GMT and Ghostscript, supplied by the conda environment. SNAP and a prepared external DEM are needed for raw Sentinel-1 SAFE processing. SAM additionally needs the optional Python dependencies and a separately obtained checkpoint.

- [Installation and ADD masks](docs/installation.md)
- [DEM preparation](docs/dem_preparation.md)
- [SNAP and precise orbits](docs/snap_setup.md)
- [Earthdata authentication and Azure runtime/network setup](docs/azure_earthdata_setup.md)

## Resume the existing Davis product

If using the supplied `WAFIW_HH_candidate.zip`, extract its `.npz` and `.training.json` files into `afiw_data/models/` in the project directory and proceed directly to `produce`. Otherwise build the same candidate from the existing annotation directory (on the machine where it is accessible):

The current bundle uses `fastice_HH_svm.npz` and `fastice_HH_svm.training.json`.
Replace the earlier bundle with this version. `train-research --training-root
afiw_data/models` is not needed: that directory contains a model, not the original
per-scene `.npy` annotations. The importer now checks for missing scene directories
before reading any arrays and points model-bundle users to `produce --classifier`.

```bash
python scripts/run_primary.py train-research \
  --training-root /g/data/jk72/gb4219/useful_stuff/honours_data/SVM_trainingdata \
  --output "afiw_data/models/fastice_HH_svm.npz" \
  --label-source "Research segment annotations; canonical ten-scene SAM-SVM selection" \
  --log-station Davis
```

If importing annotations on the Mac, replace `--training-root` with the local copy of that directory, or transfer the trusted model **and its `.training.json` report** from Gadi. With either the supplied bundle or an imported model, generate the complete candidate product from the saved analytical files:

```bash
DAVIS_PAIR=20211002T143959_20211014T143959_45c821c8
python scripts/run_primary.py produce \
  --manifest "afiw_data/davis/products/$DAVIS_PAIR/manifest.json" \
  --classifier "afiw_data/models/fastice_HH_svm.npz" \
  --allow-model-transfer \
  --output "afiw_data/davis/products/${DAVIS_PAIR}_classified_v2" \
  --bulletin-output "bulletins/davis_20211015" --as-of 2021-10-15
```

This intentionally records transfer to the existing **SLIC** product as unvalidated; it does not make SLIC equivalent to research SAM. Use a new empty output directory. The saved inputs and reviewed mask must remain available. `produce` fails if classification is unavailable, rather than silently returning just a composite.

## Evidence and limits

The supplied HH arrays were imported and used to fit/assess an SVM. Duplicate/conflicting imagery was excluded, unassigned background was excluded, and acquisition/site holdouts were assessed. The pipeline tests exercise separate classified PNG/TIFF exports and bulletin assembly. These software checks do not establish real Davis accuracy, SAM inference, physical registration, or operational suitability; see the research review and current test report.

Console logging and DEBUG files are enabled by default under `~/afiw_data/[station]/logs/`. Commands also accept `--log-dir`, `--log-level` and `--log-station`. Synthetic demos and candidate research classifications are labelled accordingly.

`notebooks/primary_workflow.ipynb` uses the same public APIs. Superseded illustration workflows, duplicated legacy executables and old milestone reports have been removed. Their source checksums remain in [the historical inventory](docs/reference_inventory.json), and previous files remain in Git history. No new ownership licence is asserted over the supplied research material.

## Acknowledgements and credit

WAFIW builds on the fast-ice research and methods contributed by **Alex Fraser**,
**Gabby Burke** and **Tony (Anthony P.) Doulgeris**. Burke's supplied annotation
arrays, SAM/SVM notebooks, processing code and validation outlines informed the
consolidated workflow and shared classifier. The supplied normalized-product
package credits initial development to Doulgeris, Burke and Fraser, and packaging
to **J. Lohse**. Doulgeris's supplied FastIce24 code identifies him through its
contact header. These research contributions retain their original attribution.

We also acknowledge **Andrew Einhorn**, with particular recognition for the SWOT
work that will inform the planned SWOT extension. SWOT integration remains future
work; this acknowledgement does not imply that it is implemented or validated.

Active model and workflow filenames use neutral scientific names. Original
external filenames are retained only in historical inventories and source-audit
records so their checksums and provenance remain traceable.
