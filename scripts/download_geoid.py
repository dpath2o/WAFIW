"""Download the public PROJ EGM96 grid without overwriting an existing file."""
import argparse
import json
import os
from pathlib import Path
import tempfile
from urllib.request import urlopen
import rasterio
from dem_utils import checksum

URL = 'https://cdn.proj.org/us_nga_egm96_15.tif'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    record = output.with_suffix('.download.json')
    if output.exists() or record.exists():
        raise FileExistsError('Existing geoid/report retained; choose a new output if needed')
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(suffix='.tif', dir=output.parent)
    try:
        with os.fdopen(fd, 'wb') as dst, urlopen(URL, timeout=60) as response:
            while chunk := response.read(1024 * 1024):
                dst.write(chunk)
        with rasterio.open(temporary) as src:
            if src.count != 1 or src.descriptions[0] != 'geoid_undulation' or src.tags().get('target_crs_epsg_code') != '5773':
                raise ValueError('Downloaded raster is not the expected EGM96 grid')
            metadata = dict(url=URL, sha256=checksum(temporary), tags=src.tags(),
                            crs=str(src.crs), description=src.descriptions[0])
        record.write_text(json.dumps(metadata, indent=2) + '\n')
        os.replace(temporary, output)
        print('Saved:', output)
        print('SHA256:', metadata['sha256'])
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


if __name__ == '__main__':
    main()
