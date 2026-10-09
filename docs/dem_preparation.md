# DEM download, storage and preparation

A terrain DEM supplies the **reflecting surface elevation** for SNAP terrain flattening/correction. ADD coastline polygons supply the land/ice-shelf exclusion mask; they cannot replace a raster DEM. Bed elevation and seabed bathymetry must not be used as the SAR surface.

## Download REMA for a station

Use the [Reference Elevation Model of Antarctica (REMA), PGC](https://www.pgc.umn.edu/data/rema/). For the initial 40 m SAR workflow, a **32 m mosaic subset** is a practical starting point. This is a processing choice to test, not a guarantee of radiometric or registration accuracy.

Two download routes:

1. [OpenTopography REMA](https://portal.opentopography.org/datasetMetadata?otCollectionID=OT.082023.3031.1): select a station region, choose the available 32 m mosaic and request a GeoTIFF subset. Review the site's current access/download requirements.
2. [PGC mosaic HTTP directory](https://data.pgc.umn.edu/elev/dem/setsm/REMA/mosaic/latest/): use `32m/` and the PGC tile discovery/index tools to identify tiles intersecting the region. Download and unpack the necessary archives; multiple tiles may need mosaicking. Retain the resolved release/version because `latest` can change.

Use the region bbox in `configs/davis.yaml`, `mawson.yaml` or `casey.yaml` as a starting point. For Davis it is `[75.5, -69.2, 80.5, -67.3]` in W,S,E,N order. Download a margin beyond the processing AOI. The coastline script's 0.2-degree margin is not a proven sufficient DEM margin: terrain flattening and the SNAP graph may need more coverage. Inspect selected scene footprints and the processing graph before deciding final DEM coverage.

Store source files outside the repository:

```bash
mkdir -p ../../data/DEMS
```

Keep source archives, download metadata, release, acquisition/mosaic information, requested bounds, resolution, horizontal CRS, vertical datum, licence/attribution and a checksum. Do not confuse the REMA elevation raster with error, count or date companion rasters.

## Current Davis checkpoint

The Davis source is an OpenTopography subset of **REMA mosaics v2, 32 m**, downloaded on 9 October 2026. The retained download metadata identifies **WGS84 ellipsoidal heights in metres** (vertical reference EPSG:4979). The raster tags alone do not declare that datum.

| Check | Observed result |
| --- | --- |
| Source file | `../../data/DEMS/Davis.tif`, about 638 MB |
| Horizontal CRS | EPSG:3031 |
| Projected bounds W,S,E,N | 2084640, 141824, 2600960, 1003072 m |
| Pixel spacing | 32 × 32 m |
| Shape, bands | 26914 rows × 16135 columns, one band |
| Type, NoData | float32, -9999 |
| Geographic enclosing bounds | 64.3044, -70.9400, 86.8789, -64.7437 degrees |
| Whole-rectangle sampled valid fraction | 49.09% |
| Valid sampled elevation min / 1% / median / 99% / max | 15.30 / 15.49 / 552.57 / 1739.48 / 1862.63 m |
| Within Davis AOI, ADD land/shelf sample | 280208 samples; 0 missing |
| Within Davis AOI, ocean outside ADD sample | 744640 samples; 528591 missing (70.99%) |

These are recorded local observations, **not a full-resolution certification**. The geographic enclosing rectangle is not the actual projected raster footprint. The historical coverage test sampled a 1200 × 1200 projected bounding window and selected pixels inside the densified geographic AOI. The reusable verifier below uses a geographic sample grid and conservative `all_touched` ADD masking, so its sample counts will differ.

The coastline file is `../../data/coastlines/davis_ADD_v7p9_exclusions.geojson`. It was clipped to `[75.3, -69.4, 80.7, -67.1]`, with 1536 land, 7 ice-shelf and 3 ice-tongue polygons, all valid. Its polygon envelope is **not** the mask's clip coverage: ocean contains no polygons.

Use separate source and prepared files:

```text
AAD_placement/data/DEMS/
  Davis.tif                         # downloaded elevation source; unchanged
  Davis_download_metadata.pdf       # retain the original download metadata
  us_nga_egm96_15.tif                # additional public geoid grid
  us_nga_egm96_15.download.json       # generated URL/checksum/metadata record
  davis_dem_verification.json        # generated inspection report
  davis_snap_wgs84.tif               # future prepared elevation raster
  davis_snap_wgs84.provenance.json   # generated preparation record
```

Mawson and Casey can use the same workflow with their own configs and source DEMs. Their DEMs have not been downloaded or validated here.

## Verify a downloaded elevation raster

From the repository root, with the WAFIW environment active and the project installed (`python -m pip install -e .`):

```bash
python scripts/verify_dem.py \
  --config configs/davis.yaml \
  --source ../../data/DEMS/Davis.tif \
  --report ../../data/DEMS/davis_dem_verification.json
```

The script prints CRS, bounds, spacing, shape, NoData, tags, SHA256, sampled elevation percentiles and separate ADD land/shelf versus ocean coverage. It requires a single elevation band and a prepared ADD polygon mask configured in `coastline`. It refuses to overwrite an existing report. Consult the source download metadata for vertical datum and units; neither a filename nor EPSG:3031 proves them.

## Download the additional EGM96 grid

The [PROJ grid catalogue](https://cdn.proj.org/) supplies the public NGA EGM96 15-arc-minute geoid grid. This is a **geoid undulation grid, not a terrain DEM**. Its values are N in the relationship `h = H + N`: approximating mean sea level by orthometric height H=0 gives ellipsoidal ocean height h=N. The grid is approximately +17.8 m near Davis.

```bash
python scripts/download_geoid.py \
  --output ../../data/DEMS/us_nga_egm96_15.tif
```

The script downloads `https://cdn.proj.org/us_nga_egm96_15.tif`, checks the expected geoid band/metadata and saves a SHA256 download record. It refuses to overwrite an existing grid or record. If you already downloaded the grid with `curl`, retain it and use that file; preparation records its checksum too. The SHA256 records the exact file used; it is not an independent publisher checksum verification.

## Prepare a verified ellipsoidal REMA source

The scripts do not download REMA automatically: select the area/release through OpenTopography or PGC and retain its metadata first. Preparation requires explicit confirmation that the source heights are WGS84 ellipsoidal metres. Orthometric products need a separately reviewed vertical conversion.

For the inspected Davis source and existing ADD mask:

```bash
python scripts/prepare_dem.py \
  --config configs/davis.yaml \
  --source ../../data/DEMS/Davis.tif \
  --geoid ../../data/DEMS/us_nga_egm96_15.tif \
  --output ../../data/DEMS/davis_snap_wgs84.tif \
  --confirm-ellipsoidal \
  --resolution-deg 0.0008 0.0003 \
  --mask-bounds 75.3 -69.4 80.7 -67.1
```

This is the **next local preparation command, not a completed Davis run**. At Davis latitude the trial spacing is roughly 33 m east–west and 33 m north–south, comparable to the 32 m source and finer than the 40 m SAR output. Spacing is expressed in longitude/latitude degrees, not metres; choose it again for a substantially different latitude. Pixel spacing is adjusted slightly to fit the requested outer bounds exactly.

The output defaults to the config's region bbox. This is an initial AOI preparation, not proof of sufficient coverage for SNAP terrain flattening; enlarge the source DEM and ADD mask before requesting a wider output when scene testing requires it. `--bounds W S E N` allows a larger output, but it must fit inside `--mask-bounds`. That argument is an explicit declaration of the geographic bounds used when clipping the ADD mask; the script cannot infer ocean coverage from the polygon envelope. Never declare coverage beyond the actual mask preparation extent. For additional stations, run `prepare_coastline.py` first and use its recorded clip bounds.

Preparation reads/writes in blocks, horizontally resamples REMA to EPSG:4326 with bilinear interpolation, and preserves its vertical datum. It retains REMA values inside conservatively rasterized (`all_touched`) ADD land/shelf/tongue/rumple polygons. **Every ocean pixel outside ADD is replaced with bilinearly sampled EGM96 undulation**, including pixels where REMA has a value. This avoids mixing two ocean-surface treatments. It stops on missing land/shelf elevations on the target grid, missing ocean geoid values or nonfinite output. It never fills missing land with sea heights, extrapolates terrain, repairs polygons, changes configs or overwrites sources/existing products.

A successful run checks every output pixel and writes source/geoid/coastline/config checksums, bounds, spacing, counts and the height policy to the provenance JSON. This validates the prepared grid, not every original source pixel or SNAP radiometry. Coastline dating/misregistration can still misclassify coast pixels. The geoid surface approximates mean sea level and does not resolve tides, dynamic ocean topography or sea-ice freeboard.

If preparation stops on a coastal land gap, inspect its cause and source/mask alignment before changing anything; do not turn it into ocean silently.

## Prepare only after inspection

1. Confirm this is surface elevation in metres, identify its vertical datum, and confirm the coverage/resolution.
2. Mosaic/crop tiles as needed with sufficient processing margin. Preserve valid land/shelf elevations and distinguish ocean gaps from missing land/shelf data.
3. Reproject horizontal coordinates to geographic WGS84 (`EPSG:4326`) for the current WAFIW external-DEM adapter. Choose angular pixel spacing deliberately; degrees are not metres and east-west scale varies with latitude. Horizontal reprojection alone does **not** transform vertical heights.
4. Supply consistent ocean surface heights and verify NoData behaviour. Native REMA often has no ocean elevations. Do not fill every gap with zero, and do not use bed/bathymetry to fill sea pixels. Zero ellipsoidal height is not generally mean sea level. Decide and document a geoid-consistent sea-surface approximation and test coastal output coverage.
5. Check datum handling in both Terrain-Flattening and Terrain-Correction, inspect a one-scene result and verify land/sea registration before treating the pair as usable.

PGC REMA downloads use WGS84 **ellipsoidal** elevations. PGC notes that Esri services instead supply EGM08 orthometric heights. Check the actual downloaded product. For verified ellipsoidal heights the current `dem_apply_egm: false` avoids an additional EGM conversion. Bedmap2 surface elevations use a different reference and are much coarser; do not assume SNAP's EGM switch implements an arbitrary source-geoid conversion. Bedmap2 **surface** is a potential coarse fallback, not the preferred Davis coastal DEM.

The Davis command above is based on the inspected source and confirmed download metadata. It is not a universal warp/fill recipe for other elevation products.

## Connect the prepared DEM to WAFIW

After preparing and validating the separate GeoTIFF, edit the existing `snap` section of `configs/davis.yaml`:

```yaml
snap:
  executable: "/Applications/snap/bin/gpt"
  dem_path: "../../../data/DEMS/davis_snap_wgs84.tif"
  dem_nodata: -9999        # must match the actual prepared file
  dem_apply_egm: false    # only for verified ellipsoidal heights
  memory: 4G
  threads: 2
  timeout_seconds: 7200
```

The example filename remains a future local output until preparation succeeds. Relative paths are resolved from `configs/`. Keep `dem_path: null` until the output exists and has been checked. Adapt the path/datum settings separately for each station.

```bash
python scripts/run_primary.py --config configs/davis.yaml doctor
```

`DEM: present` is only a file-presence check. It does not validate CRS, datum, coverage, ocean values or radiometry. Once resource checks and local Earthdata credentials are ready ([token or `.netrc`](installation.md#earthdata-download-authentication)), test one pair:

```bash
python scripts/run_primary.py --config configs/davis.yaml run-catalog \
  --pair-index 0 --max-pairs 1 --download
```

The current Davis pair 0 is 2–14 October 2021. This command downloads full scenes before preprocessing. Inspect preprocessing logs, valid swath coverage, coast alignment, and the segmentation quicklook. A model-free product remains segmentation only.

## References

- [PGC REMA overview, resolutions, download routes and datum](https://www.pgc.umn.edu/data/rema/)
- [PGC DEM product guide](https://www.pgc.umn.edu/guides/stereo-derived-elevation-models/pgc-dem-products-arcticdem-rema-and-earthdem/)
- [SNAP Terrain-Flattening parameters](https://step.esa.int/main/wp-content/help/versions/10.0.0/snap-toolboxes/eu.esa.microwavetbx.sar.op.sar.processing.ui/operators/TerrainFlatteningOp.html)
- [BAS Bedmap2 gridding products](https://doi.org/10.5285/fa5d606c-dc95-47ee-9016-7a82e446f2f2)

- [PROJ EGM96 grid catalogue](https://cdn.proj.org/)
- [PROJ vertical grid shift semantics](https://proj.org/en/stable/operations/transformations/vgridshift.html)
