# Architecture and execution model

Configuration objects (`RunSpec`, `RegionSpec`, `AcquisitionSpec`, `ProcessingSpec`, `SegmentationSpec`, `SnapSpec`) hold scientific/runtime choices. `WorkflowSpec` composes them and resolves relative paths. `AFIWPaths` owns the station output layout. `PrimaryWorkflow` coordinates independent adapters and processors. `BulletinBuilder` consumes completion manifests, never triggers raw processing.

Every pair retains input paths/checksums, configuration, model/coastline/checkpoint hashes, acquisition times/baseline, output grid resolution, valid-data fraction and method limitations. SAM/SLIC segments are uint32 region IDs with 0 unassigned. Ice classification is an independent uint8 product with 255 unknown. Classification is optional and cannot silently fall back to texture thresholds.

Raw scenes, prepared backscatter, pair products and weekly bulletins occupy separate directories under one configurable root. No PBS/job-scheduler code is required. The default tile size is 512 with the full dependency halo for nested window operations. Segmentation operates on a smaller grid with a pixel-count guard. The two-panel plotting reprojection aligns north on the centre meridian only; classification/texture GeoTIFFs remain on their recorded analysis grid.

The current execution is serial and local. Azure can use the same package/CLI with a mounted data root; blob I/O, orchestration, managed identity and deployment are not implemented or validated in this milestone. Configure those as adapters without changing scientific calculations. Large multi-season archives need planned scene/pair scheduling and product-version governance rather than a single unbounded laptop command.

The standalone PDF engine needs no TeX; LaTeX output is generated separately and optionally compiled. The prior manually curated example is reproducible through its own function and template. SWOT sources are reference-only at this stage.
