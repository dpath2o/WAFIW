# Supplied-code audit and adoption map

The package follows shuga's dataclass specification + path-manager + reusable component + workflow conventions, rather than importing shuga's CICE/PBS/HPC dependencies. Root `core/types.py` and `core/paths.py` were inspected through the repository connector. The current package uses an installable src layout so notebooks need no sys.path editing.

| Supplied material | Adopted in this milestone | Status / difference |
|---|---|---|
| Gabby `process_image_pairs.py` | Boxcar differences, local SD, mean-SD variance normalization, multiscale texture | Interior valid-data formula checked independently. Vectorized masked averaging replaces slow generic_filter; missing-data handling differs intentionally. |
| Tony `process_image_pairs.py` | Same numerical source | The supplied Gabby and Tony files are AST-identical; byte differences are formatting, not a different formula. |
| Gabby `NormProd.ipynb` / Tony standalone notebooks | Common-overlap/georeferenced preparation concepts | Replaced GDAL full-scene/in-place operations with Rasterio common-grid streaming. Common georeferencing is not proof of physical subpixel registration. |
| Tony EW SAFE search notebook | Scene discovery and pairing intent | Public ASF search, scene footprints and matching acquisition metadata replace HPC path/search assumptions. |
| Gabby `SAM-SVM.ipynb` | Optional SAM adapter; mean-RGB segment features; SVC | Weights/manual training labels absent. SLIC is an alternate initial laptop backend. CPU default; MPS opt-in. SAM overlaps/gaps explicit. |
| Notebook RGB uint8 conversion | Fixed-range RGB display [-0.5,1] | Clip before uint8 cast to prevent value wraparound. No claim of bitwise agreement with wrapped legacy colours. |
| Notebook land masks | ADD surface exclusion API | Land AND floating shelves excluded; no 100-pixel mask erosion or inference that grey means land only. Preserve NoData as 255. |
| Notebook tenfold resize | Configurable downsampling | Effective segmentation resolution and transformed grid are preserved; no claim that nearest upsampling restores native detail. |
| Prior example LaTeX + annotated figures | Independent reproduction function / script | Frozen research example included, with corrected Ross Ice Shelf/Ross Island/Minna Bluff geography and contextual SCAR outlines. |
| Alex SWOT notebook / both SWOT source archives | Source preservation | Not integrated into the primary pipeline. Existing plot is an anomaly illustration, not validated freeboard. |
| MATLAB archive | Source preservation | Not translated automatically; external toolboxes/functions unresolved. |

64 code/reference files are retained from the five supplied archives and Alex's standalone notebook, excluding macOS resource-fork files. `legacy/INVENTORY.json` records original hashes and bundled hashes. Notebook outputs and execution counts were cleared. Credential-literal sanitization is applied to reference sources; credentials should be supplied through local environment handling when ports are implemented. Original supplied ZIPs are not redistributed within the package.

## Checks to review with Alex

- Authoritative current code repository and research attribution.
- Whether Davis should initially use EW/HH only or other acquisition groups.
- Priority AOI and station approach bounds.
- Match external preprocessing radiometry and compare SNAP gamma0 results against the source chain.
- Registration quality on stationary features, robust land/shelf masks and incidence-angle dependence.
- Window sizes and downsampling versus coastal-feature resolution.
- SAM weights/settings and manually labelled training scenes, including held-out Davis validation.
- Validate class 3's meaning before operational reporting.
- Required evidence before replacing RESEARCH DEMONSTRATION with OFFICIAL.

## Secondary-product stage

The two SWOT versions are deliberately kept distinct under legacy. Next: compare helpers and retrieval definitions; implement one provider adapter and common observation schema; separate SSH anomaly from sea/snow-surface freeboard; preserve corrections/quality flags/uncertainty; validate before thickness inference. This stage should follow a successful real Davis processing test rather than treating a synthetic run as scientific validation.
