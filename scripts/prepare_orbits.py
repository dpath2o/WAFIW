"""Populate SNAP's precise orbit cache for selected catalogue pairs."""
import argparse
import json
from pathlib import Path
from afiw.observations.orbits import prepare_pair_orbits


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pairs', required=True)
    parser.add_argument('--pair-index', type=int, default=0)
    parser.add_argument('--max-pairs', type=int, default=1)
    parser.add_argument('--cache-root', help='Sentinel-1 cache root, containing POEORB; default ~/.snap/auxdata/Orbits/Sentinel-1')
    parser.add_argument('--check-only', action='store_true', help='Validate local cache without network downloads')
    args = parser.parse_args()
    if args.pair_index < 0 or args.max_pairs < 1:
        parser.error('pair-index must be nonnegative and max-pairs positive')
    pairs = json.loads(Path(args.pairs).read_text())
    selected = pairs[args.pair_index:args.pair_index + args.max_pairs]
    if not selected:
        parser.error('No catalogue pairs selected')
    for pair in selected:
        print('Pair:', pair['pair_id'], flush=True)
        for path in prepare_pair_orbits(pair, args.cache_root, args.check_only):
            print('Validated precise orbit:', path, flush=True)


if __name__ == '__main__':
    main()
