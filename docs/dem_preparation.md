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

The user has downloaded and unpacked `../../data/DEMS/Davis.tif` (about 638 MB). Its CRS, datum, resolution, bounds and NoData **have not yet been inspected here**. The filename alone does not establish these. Do not point SNAP at it merely because it exists.

Use separate source and prepared files, for example:

```text
AAD_placement/data/DEMS/
  Davis.tif                  # downloaded source; retain unchanged
  Davis_download_metadata.txt
  davis_snap_wgs84.tif        # create only after inspection/preparation
```

Mawson and Casey can follow the same storage convention; their DEMs have not been downloaded or prepared in this workflow.

## Inspect the downloaded raster

From the repository root, with WAFIW active:

```bash
python - <<'PY'
from pathlib import Path
import hashlib
import rasterio
from rasterio.warp import transform_bounds

path = Path('../../data/DEMS/Davis.tif').resolve()
digest = hashlib.sha256()
with path.open('rb') as stream:
    for chunk in iter(lambda: stream.read(1024*1024), b''):
        digest.update(chunk)
print('File:', path)
print('SHA256:', digest.hexdigest())
with rasterio.open(path) as src:
    print('CRS:', src.crs)
    print('Bounds:', src.bounds)
    print('Resolution:', src.res)
    print('Shape/bands:', src.shape, src.count)
    print('Dtype/NoData:', src.dtypes, src.nodatavals)
    print('Dataset tags:', src.tags())
    print('Band 1 tags:', src.tags(1))
    if src.crs:
        print('Geographic bounds:', transform_bounds(
            src.crs, 'EPSG:4326', *src.bounds, densify_pts=41))
PY
```

Raster tags may not declare the vertical datum. Consult the download metadata too. These checks do not yet assess every pixel, coastal gaps or SNAP compatibility.

## Prepare only after inspection

1. Confirm this is surface elevation in metres, identify its vertical datum, and confirm the coverage/resolution.
2. Mosaic/crop tiles as needed with sufficient processing margin. Preserve valid land/shelf elevations and distinguish ocean gaps from missing land/shelf data.
3. Reproject horizontal coordinates to geographic WGS84 (`EPSG:4326`) for the current WAFIW external-DEM adapter. Choose angular pixel spacing deliberately; degrees are not metres and east-west scale varies with latitude. Horizontal reprojection alone does **not** transform vertical heights.
4. Supply consistent ocean surface heights and verify NoData behaviour. Native REMA often has no ocean elevations. Do not fill every gap with zero, and do not use bed/bathymetry to fill sea pixels. Zero ellipsoidal height is not generally mean sea level. Decide and document a geoid-consistent sea-surface approximation and test coastal output coverage.
5. Check datum handling in both Terrain-Flattening and Terrain-Correction, inspect a one-scene result and verify land/sea registration before treating the pair as usable.

PGC REMA downloads use WGS84 **ellipsoidal** elevations. PGC notes that Esri services instead supply EGM08 orthometric heights. Check the actual downloaded product. For verified ellipsoidal heights the current `dem_apply_egm: false` avoids an additional EGM conversion. Bedmap2 surface elevations use a different reference and are much coarser; do not assume SNAP's EGM switch implements an arbitrary source-geoid conversion. Bedmap2 **surface** is a potential coarse fallback, not the preferred Davis coastal DEM.

No universal warp/fill command is prescribed before inspecting `Davis.tif`: choosing resolution, datum conversion and ocean gap handling from the filename would be unreliable.

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

The example filename is a future prepared output, not a file already created. Relative paths are resolved from `configs/`. Keep `dem_path: null` until the output exists and has been checked. Adapt the path/datum settings separately for each station.

```bash
python scripts/run_primary.py --config configs/davis.yaml doctor
```

`DEM: present` is only a file-presence check. It does not validate CRS, datum, coverage, ocean values or radiometry. Once resource checks and local Earthdata credentials are ready, test one pair:

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
