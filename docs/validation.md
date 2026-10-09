# Validation record — primary milestone

## Executed

- Installable package installed editable in a Linux Python 3.12 environment; dependency consistency check passed.
- 12 automated tests passed. See `reports/pytest.txt`.
- Legacy valid-data interior NormProd_SmoVar formula compared against an independent slow generic-filter reference.
- Tiled raster processing compared against full-array processing, including tile seams and missing-data holes.
- Linear-power to dB conversion and georeferenced raster validity preservation checked.
- Pair rejection checked for mismatched orbit/polarization, unsuitable time gap, missing metadata and insufficient overlap.
- Unknown cells cannot count as fast-ice retreat; land/shelf cells remain outside common ocean coverage.
- SVM save/load and explicit unknown/exclusion handling tested on synthetic manual labels only.
- Synthetic end-to-end workflow generated texture, SLIC segments, validity raster, figure and completion manifest. It generated no ice-classification output and no real extent claim.
- Standalone PDF and LaTeX-compiled PDF inspected visually as one-page products; no text clipping or overlap observed.
- Public Davis October 2021 discovery found 23 scenes and 12 compatible pairs, saved with the query parameters. No satellite scene bytes were downloaded.
- 10 offline testing-notebook code cells executed sequentially in a shared Python namespace and passed; actual supplied McMurdo RGB/labels/classification metadata inspected.
- Notebook JSON/structure validated. Actual Jupyter kernel launch failed because both TCP and IPC socket binding are prohibited in this execution environment. Jupyter kernel/UI execution on the Mac remains untested; sequential execution is not presented as that check.

## Not executed / not established

- macOS, Windows or Azure deployment.
- Authenticated Earthdata download or scene checksum verification.
- SNAP GPT on real Sentinel-1 SAFE data. The generated XML structure and sea-preservation setting were checked; operator/version compatibility remains a real-data integration check.
- External DEM coverage, ocean filling, vertical datum or terrain-flattening accuracy.
- Physical/subpixel registration quality on stationary reference features.
- SAM weights/inference or Mac MPS execution.
- Trained Davis model performance, independent labelled validation, operational skill or fast-ice ground truth.
- Real multi-season persistence/anomaly generation or route/access hazard wording.
- SWOT download, corrections, freeboard retrieval, validation or thickness inference.

`reports/tested_versions.json` records the tested dependency versions; it is not a platform-independent lockfile. Shapely reports deprecation warnings for the compatible `ops.transform` API; these did not affect test results. Exact terrain-flattened radiometry and legacy missing-data behaviour are not asserted to be identical.
