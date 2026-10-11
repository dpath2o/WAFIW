# SNAP installation and Sentinel-1 orbit preparation

SNAP is an OS/runtime prerequisite for WAFIW raw Sentinel-1 SAFE processing. Conda installs the Python workflow; it does not install ESA SNAP or its Java toolboxes. WAFIW invokes the external `gpt` executable, so the SNAP Python bridge (`esa_snappy`) is not required.

## Checkpoint and diagnosed failure

On 9 October 2026, the Davis pair download stage completed and SNAP reached `Apply-Orbit-File`. The installed SNAP 8.0 tried `scihub.copernicus.eu/gnss/search` and failed with `No valid orbit file found`. This is an orbit acquisition failure, before calibration, DEM use and primary figure generation. The accompanying GDAL message said SNAP selected its bundled GDAL; it was not the fatal error.

The SNAP log reported version 14.0.0 available; ESA's download page also listed 14.0.0 when checked. Prefer a current, reviewed SNAP installation with the Microwave Toolbox. Keep the installed version and toolbox versions recorded in the runtime build specification. Updating alone is not proof that the WAFIW graph works: validate the selected version on a real scene.

## Install and configure SNAP

1. Download the appropriate installer from [ESA STEP](https://step.esa.int/main/download/snap-download/). The current page offers Windows, Mac ARM, Mac Intel and Linux builds. For Apple Silicon select Mac ARM; for Azure Linux select the compatible Linux build and VM architecture. Compare the installer checksum with ESA's published checksum. Review ESA's current upgrade instructions before replacing an older installation.
2. Include the **Microwave Toolbox**, which supplies Sentinel-1 readers and SAR operators. Open SNAP once to check installed modules and apply reviewed updates. For a headless server, complete installation/module provisioning as part of the image build; do not depend on a GUI during scheduled acquisition.
3. Find `gpt` under the SNAP installation's `bin` directory. On the tested Mac it was `/Applications/snap/bin/gpt`; `/usr/sbin/gpt` is the macOS partition utility and must not be used. Set `snap.executable` in the station YAML to the actual ESA executable. Linux and Windows paths depend on the installation location.
4. Use the runtime supplied/supported by the selected installer. Python/conda Java settings do not establish SNAP's Java runtime. Verify the executable under the actual job account, then record the SNAP/toolbox versions from its startup output.

```bash
/Applications/snap/bin/gpt -h
/Applications/snap/bin/gpt Apply-Orbit-File -h
/Applications/snap/bin/gpt Terrain-Flattening -h
/Applications/snap/bin/gpt Terrain-Correction -h
python scripts/run_primary.py --config configs/davis.yaml doctor
```

Replace the executable path for Linux/Windows. Check the graph's other operators too: `Read`, `Remove-GRD-Border-Noise`, `ThermalNoiseRemoval`, `Subset`, `Calibration`, `LinearToFromdB` and `Write`. A missing operator usually means missing/incompatible modules. `doctor` checks configured files, not Java execution, toolbox compatibility, orbit coverage or network authentication.

The existing Davis settings use `snap.memory: 4G`, `snap.threads: 2` and a processing timeout. GPT's `-c` controls its tile cache; it is not the total JVM heap or a VM RAM sizing guarantee. Configure the JVM heap using the selected SNAP release's launcher guidance and leave RAM for Python, Java overhead and the OS. Provision writable download, processing, product and auxiliary-data storage; measure peak RAM, disk use and elapsed time on a representative scene before choosing Azure VM capacity.

## Prepare precise orbit files

WAFIW now provides `afiw.observations.orbits` and `scripts/prepare_orbits.py`. They retrieve precise (`AUX_POEORB`) files from the public [ESA STEP orbit mirror](https://step.esa.int/auxdata/orbits/Sentinel-1/POEORB/). This endpoint needs no Earthdata or Copernicus token. ESA can distribute EOF files inside ZIP archives; the script reads and validates them without extracting archive paths.

Selection uses the scene spacecraft and start/stop timestamps from `pairs.json`, requiring an extra 60 seconds at each end. It uses the **validity interval**, not the orbit filename's creation timestamp, searches neighbouring months for boundary cases and chooses the newest matching creation timestamp among published candidates. It checks XML spacecraft/type/validity and finite, ordered orbit state vectors spanning the required interval. It writes an uncompressed EOF atomically and a neighbouring `.download.json` with source URL, SHA-256, validity and preparation time. This is structural/coverage validation, not an independent orbit accuracy assessment.

For the October Davis demonstration:

```bash
python scripts/prepare_orbits.py \
  --pairs examples/davis_catalog_202110/pairs.json \
  --pair-index 0 --max-pairs 1

python scripts/prepare_orbits.py \
  --pairs examples/davis_catalog_202110/pairs.json \
  --pair-index 0 --max-pairs 1 --check-only
```

The default cache root is `~/.snap/auxdata/Orbits/Sentinel-1`. For this pair the files are installed under:

```text
~/.snap/auxdata/Orbits/Sentinel-1/POEORB/S1A/2021/10/*.EOF
```

Run orbit preparation as the **same OS account that runs SNAP**. The log's destination is the authoritative check for a custom SNAP installation. `--cache-root` changes where Python stores files; it does not configure Java/SNAP to look there. If using a custom root, configure SNAP separately and confirm the paths agree. Preserve the auxiliary cache across jobs/containers and give the worker permission to read it. A valid local file is reused without a network request. Invalid matching files are not overwritten; review/quarantine them before retrying. `--check-only` performs an offline cache check and fails if coverage is missing.

The script is station independent: provide any compatible catalogue pair file. Use `--max-pairs` to cover more pairs; repeated scene/orbit needs reuse the local cache. It intentionally prepares precise orbits only. For recent acquisitions, a precise product may not yet be published: wait/retry under an explicit scheduling policy. WAFIW does not silently substitute restituted orbits or skip orbit correction. A later near-real-time product would need a separately reviewed restituted-orbit policy and provenance.

## Resume processing and automate the prerequisite

With the scenes already cached, rerun without `--download` or an interactive token:

```bash
python scripts/run_primary.py --config configs/davis.yaml run-catalog \
  --pairs examples/davis_catalog_202110/pairs.json \
  --pair-index 0 --max-pairs 1 --prepare-orbits
```

This performs orbit preparation before processing the selected pair. For a fresh local download, combine `--prepare-orbits --download` with the token launcher documented in [installation](installation.md#earthdata-download-authentication). For scheduled Azure execution, supply the Earthdata secret through the deployment launcher and invoke `run_primary.py` directly with both flags. Separate orbit preparation followed by `--check-only` is useful when acquisition and processing run in different network zones.

The graph retains `Sentinel Precise (Auto Download)` and `continueOnFail=false`. With a matching local orbit, SNAP should use its cache. Cache preparation does not change SNAP's fallback network configuration if SNAP rejects or cannot find a file. Inspect the processing log to confirm use of the intended precise orbit and successful completion. Do not bypass this failure by enabling `continueOnFail`.

Each processed scene has a `.snap.xml` graph and `.snap.log` beside its target TIFF. WAFIW now points to that log when GPT fails. Reprocessing remains explicit; incomplete outputs are not accepted as completed products.

## Azure network and runtime acceptance

Include orbit acquisition in the OS/platform build requirements alongside [Earthdata access](azure_earthdata_setup.md):

| Destination/resource | Purpose and requirement |
| --- | --- |
| `step.esa.int:443` | Public HTTPS orbit directory listings and EOF/ZIP downloads; approve the worker's outbound route, DNS and TLS trust. |
| `download.esa.int:443` or ESA's selected installer mirror | Installation/image build, according to the selected download link. |
| NASA/ASF destinations | Separate catalogue, scene and authentication routes listed in the Earthdata setup guide. |
| SNAP auxiliary cache | Persistent, writable during preparation and readable by the Java job account; paths must agree. |

The Python orbit downloader honours Requests proxy/CA environment settings, supplies no site credential and rejects HTTP redirects to unreviewed destinations. If ESA changes its download layout or redirects, review the source and update the provider deliberately. Java/SNAP proxy and certificate trust need their own configuration: Python's `REQUESTS_CA_BUNDLE` does not configure Java trust. Scheduled jobs need DNS, a correct system clock, trusted certificates and a controlled outbound policy; do not disable certificate verification.

A fully offline processing worker can use a prepopulated orbit cache, but test the entire graph for other auxiliary-data requirements. Do not assume orbit caching makes every SNAP operator offline. Pin/record the reviewed installation and preserve the cache independently of ephemeral container storage.

Acceptance gates:

- `gpt -h` and the required operator help succeed under the job identity.
- Prepared DEM and coastline settings pass local checks; see [DEM preparation](dem_preparation.md).
- Every selected scene passes the offline orbit coverage check in the cache used by SNAP.
- A genuine SAFE pair completes GPT and produces the expected georeferenced gamma0 dB TIFFs.
- The primary figure and manifest are inspected, with the orbit cache provenance and scene logs retained for review.

At this documentation checkpoint, the user's Mac failed before orbit correction. The Python downloader was exercised against the public ESA mirror for both pair-0 scenes and its offline cache check passed. The files selected were `S1A_OPER_AUX_POEORB_OPOD_20211022T122524_V20211001T225942_20211003T005942.EOF` and `S1A_OPER_AUX_POEORB_OPOD_20211103T122525_V20211013T225942_20211015T005942.EOF`. Successful SNAP 8/14 processing and Azure execution must still be demonstrated. Without a classifier the Davis figure remains segmentation only, not a validated fast-ice extent product.

## References

- [ESA SNAP installers and checksums](https://step.esa.int/main/download/snap-download/)
- [SNAP GPT command-line help](https://step.esa.int/main/wp-content/help/versions/9.0.0/snap/org.esa.snap.snap.gpf.ui/gpf/GraphProcessingTool.html)
- [Public precise-orbit mirror](https://step.esa.int/auxdata/orbits/Sentinel-1/POEORB/)
- [Copernicus Sentinel-1 auxiliary/orbit products](https://documentation.dataspace.copernicus.eu/Data/SentinelMissions/Sentinel1.html)

## After SNAP completion

See [separate PyGMT maps and classification](workflow.md) for the updated map runtime and output contract. Successful SNAP preprocessing supplies the backscatter inputs; it does not supply an ice classifier. Completed products can be regenerated into separate maps without repeating SNAP.
