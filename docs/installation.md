# Installation and coastline setup

This guide captures the macOS WAFIW setup through the first Davis catalogue and coastline tests. Run commands from the repository root unless stated otherwise. Python 3.12 and the `WAFIW` conda environment are used. SNAP is a separate application; the DEM is covered in [DEM preparation](dem_preparation.md).

## Local layout

Keep the large source datasets outside Git. The supplied configs assume this layout:

```text
AAD_placement/
  src/WAFIW/
    environment.yml
    configs/davis.yaml
    configs/mawson.yaml
    configs/casey.yaml
  data/
    coastlines/
      add_coastline_high_res_polygon_v7_9.shp
      add_coastline_high_res_polygon_v7_9.shx
      add_coastline_high_res_polygon_v7_9.dbf
      add_coastline_high_res_polygon_v7_9.prj
      add_coastline_high_res_polygon_v7_9.cpg
      davis_ADD_v7p9_exclusions.geojson
    DEMS/
      Davis.tif
```

On the current Mac the project is under `~/Defence/AAD_placement/src/WAFIW`; its resolved path is in iCloud Drive. Keep input files fully downloaded locally while processing. Relative YAML paths resolve from the **config file's directory**, not the shell directory. Thus `../../../data/coastlines/...` from `src/WAFIW/configs/` reaches `AAD_placement/data/coastlines/`.

## Create or update conda

For a fresh checkout:

```bash
git clone https://github.com/dpath2o/WAFIW.git
cd WAFIW
conda env create -f environment.yml
conda activate WAFIW
python -m ipykernel install --user --name WAFIW --display-name "Python (WAFIW)"
```

For the existing environment after pulling these changes:

```bash
conda activate WAFIW
conda env update -n WAFIW -f environment.yml
```

The environment includes GeoPandas and Pyogrio for coastline preparation. These were initially added with `conda install -c conda-forge geopandas pyogrio`; the updated YAML makes them reproducible. For a pip-managed environment, the equivalent optional tools are `python -m pip install -e ".[test,coastline]"`. SAM/PyTorch are optional and are not needed for SLIC testing.

```bash
python -m pytest tests -q
python scripts/run_primary.py --config configs/davis.yaml doctor
```

The original macOS run passed 12 tests with 11 warnings in 126 seconds. That is component-test evidence, not validation of real Davis classification or raw SAFE processing. Review warnings when they occur.

## Install and identify SNAP

Install ESA SNAP with the Sentinel-1/microwave toolbox from [ESA STEP](https://step.esa.int/main/download/). On the current Mac the verified executable is `/Applications/snap/bin/gpt`, already set in Davis, Mawson and Casey configs. Change it for other installations/platforms.

```bash
/Applications/snap/bin/gpt -h
```

Do not use `/usr/sbin/gpt`: on macOS that is the disk partition utility. The current installation reports SNAP 8.0; compatibility of the entire processing graph still needs a real-scene test. `doctor` checks executable/file presence, not operator compatibility or DEM suitability.

## Obtain ADD high-resolution polygons

Use the **polygon** dataset from the [SCAR ADD catalogue](https://data.bas.ac.uk/items/e74543c0-4c4e-4b41-aa33-5bb2f67df389/). Previous releases are linked there; this workflow has used v7.9. Preserve the exact downloaded version and its attribution/metadata. The catalogue's latest release can differ from v7.9.

Download and unpack the polygon archive into `../../data/coastlines` from the repository root. If copying an existing archive from another machine, perform that transfer yourself. Keep `.shp`, `.shx`, `.dbf`, `.prj` and `.cpg` together with the same basename. The `.qmd` and original ZIP may be retained as metadata/archive. Check ZIP contents before extracting; nested folders may need moving into the layout above.

```bash
mkdir -p ../../data/coastlines
unzip -l ../../data/coastlines/add_coastline_high_res_polygon_v7_9.shp.zip
unzip ../../data/coastlines/add_coastline_high_res_polygon_v7_9.shp.zip -d ../../data/coastlines
```

WAFIW consumes the **prepared GeoJSON**, not the original shapefile or coastline NetCDF. It excludes ADD `surface` classes `land`, `ice shelf`, `ice tongue` and `rumple`. Do not substitute monthly sea-ice extent polygons: they could exclude the sea ice being analysed. Review shelf fronts against the observation dates.

## Prepare a station mask

The canned selections load their corresponding workflow configs. These provide station coordinates, provisional AOIs, October 2021 discovery dates, EW/HH acquisition settings, 40 m processing, SLIC/CPU defaults and expected mask paths. Catalogue coverage, AOI boundaries and scientific settings need review at each station. Mawson and Casey settings have not been tested with real scenes.

```bash
python scripts/prepare_coastline.py --station davis --update-config
python scripts/prepare_coastline.py --station mawson --update-config
python scripts/prepare_coastline.py --station casey --update-config
```

Run only the station(s) you need. The default source is the v7.9 shapefile in `AAD_placement/data/coastlines/`. Default output is `<station>_ADD_v7p9_exclusions.geojson` beside it, plus a `.provenance.json` record. The latter records component checksums, counts, source CRS, region and clipping settings. If using another ADD version, supply an explicit version-appropriate `--output` filename and keep its release metadata.

For **Davis already prepared**, regeneration is optional. To replace the existing GeoJSON deliberately:

```bash
python scripts/prepare_coastline.py --station davis --update-config --overwrite
```

The script adds a 0.2-degree margin, densifies the AOI boundary, clips valid polygons in their **source CRS**, then reprojects to EPSG:4326. Clipping first avoids the self-intersection created when the whole Antarctic polygon is reprojected across the dateline. Invalid source polygons fail rather than being silently repaired. The script changes only the top-level `coastline` config setting when `--update-config` is supplied.

The completed local Davis preparation reported 1,536 land, 7 shelf and 3 tongue polygons, all valid. Their combined bounds were approximately `[75.570816, -69.400000, 80.7, -67.899119]`. Polygon bounds describe excluded surfaces, not the complete ocean AOI; they need not fill the requested rectangle. Geometry validity is not a substitute for visual coastal review.

## Another location or custom paths

Copy a station YAML and explicitly provide `run.region.name`, `bbox` in `[west, south, east, north]` longitude/latitude degrees, and `station_lon`/`station_lat`. Set dates and resource paths for that location. The preparer requires a regional bbox away from the poles/dateline and a safe region name; the full workflow also needs station coordinates.

```bash
python scripts/prepare_coastline.py \
  --config configs/my_location.yaml \
  --source /path/to/add_polygon.shp \
  --output /path/to/my_location_exclusions.geojson \
  --margin-deg 0.2 --update-config
```

CLI paths resolve from the shell directory. Built-in station configs and the default source resolve from the script/repository location. The config update stores the output path relative to the config directory. Custom configs override the need for a canned selection; do not pass both `--station` and `--config`.

Station-coordinate references: [Mawson](https://www.antarctica.gov.au/antarctic-operations/stations-and-field-locations/mawson/) and [Casey](https://www.antarctica.gov.au/antarctic-operations/stations-and-field-locations/casey/). Their rectangular AOIs are provisional workflow choices, not published operational boundaries.

## Verify and resume

```bash
python scripts/run_primary.py --config configs/davis.yaml doctor
python scripts/run_primary.py --config configs/davis.yaml search
```

The first Davis search found 12 compatible October 2021 pairs. `search` retrieves public catalogue metadata only. Raw-scene download requires local Earthdata authentication through a token or the Earthdata entry in `~/.netrc`. Never commit credentials. Raw SAFE processing requires a prepared DEM; classification also needs a trusted, region-specific model. Without a model the product remains segmentation only.

The current pause point has a valid Davis coastline and a downloaded `../../data/DEMS/Davis.tif`. The source metadata and sampled land/ocean coverage have now been inspected; ocean gaps remain to be prepared. Leave `snap.dem_path: null` until a separate prepared DEM passes verification. Continue with [DEM preparation](dem_preparation.md).


## Earthdata download authentication

For the successful token/EULA checkpoint, credential precedence and the mandatory Azure outbound-access requirements, see [Earthdata and Azure setup](azure_earthdata_setup.md). This is part of the OS/runtime build specification, not just Python installation.

WAFIW supports two local methods for ASF Sentinel-1 downloads:

1. If `EARTHDATA_TOKEN` is set and nonempty, authenticate with that token. Invalid explicit tokens fail; they do not silently fall back to another account.
2. Otherwise read **only the Earthdata account** from the standard `~/.netrc` file and authenticate through ASF's `auth_with_creds` method. The account must have a login and password under `machine urs.earthdata.nasa.gov`. Other machine entries are not passed to this authentication call.

For an interactive token-only run, use the launcher below. It prompts for the token and supplies `EARTHDATA_TOKEN` and `NETRC=os.devnull` to the primary CLI child process, including the scene downloads. Proxy and CA environment settings are preserved; the parent shell and existing `.netrc` are unchanged. A token entered in an earlier diagnostic does not persist into a later command.

```bash
python scripts/run_with_earthdata_token.py --visible-token \
  --config configs/davis.yaml run-catalog \
  --pairs examples/davis_catalog_202110/pairs.json \
  --pair-index 0 --max-pairs 1 --download
```

Omit `--visible-token` for hidden input. Paste only the raw token at the prompt. The launcher delegates to `run_primary.py`; it downloads missing scenes and then proceeds to SNAP processing and primary figures. It returns the primary command's exit status. Scheduled Azure jobs should use secret injection rather than this interactive launcher.

Keep the file private:

```bash
chmod 600 ~/.netrc
```

Edit the file locally with your usual editor. Do not print or paste its contents into chat, notebook output, logs or Git. WAFIW does not write credentials into configuration, manifests or provenance. Parsing/authentication failures give a generic message rather than reproducing credentials or parser contents. Authentication is deferred until a scene needs downloading; a pair with two valid cached ZIPs needs no login.

After setting up the Earthdata entry, run the normal command:

```bash
python scripts/run_primary.py --config configs/davis.yaml run-catalog \
  --pairs examples/davis_catalog_202110/pairs.json \
  --pair-index 0 --max-pairs 1 --download
```

If an old `EARTHDATA_TOKEN` is set and you intend to use `.netrc`, run `unset EARTHDATA_TOKEN` in this shell first. If authentication still fails, verify your Earthdata account and ASF authorization in your own browser; WAFIW does not manage accounts. The `doctor` command checks local resources, not login validity.

Reference: [ASF session authentication](https://docs.asf.alaska.edu/asf_search/ASFSession/).
