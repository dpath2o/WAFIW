"""Create a blank georeferenced label template for manual annotation in QGIS."""
import logging
from afiw.core.logging import add_logging_arguments, setup_from_args, logged_step
import argparse
from pathlib import Path
import numpy as np
import rasterio
from afiw.processing.raster import profile
from afiw.workflows.maps import inputs_from_manifest

@logged_step
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--output', required=True)
    add_logging_arguments(parser)
    args = parser.parse_args()
    setup_from_args(args, 'prepare_training_labels')
    destination = Path(args.output)
    if destination.exists():
        raise FileExistsError('Label template already exists; do not overwrite annotations')
    _, _, _, segments, _, grid = inputs_from_manifest(args.manifest)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(destination, 'w', **profile(grid, dtype='uint8', nodata=255)) as dst:
        dst.write(np.full(segments.shape, 255, np.uint8), 1)
        dst.update_tags(purpose='manual_training_labels', class_codes='0=other ocean/pack;2=candidate fast ice;3=legacy melt-affected fast ice (review required);255=unlabelled')
    logging.getLogger('afiw.scripts.prepare_training_labels').info('Blank label template: %s; grid=%s; unlabelled code=255', destination, grid)
    print(destination)


if __name__ == '__main__':
    main()
