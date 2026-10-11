"""Render separate PyGMT maps from a completed product; optionally classify it."""
from afiw.core.logging import add_logging_arguments, setup_from_args, logged_step
import argparse
from afiw.workflows.maps import render_from_manifest

@logged_step
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--output', required=True, help='New empty derived-product directory')
    parser.add_argument('--classifier', help='Trusted local region-specific joblib model')
    add_logging_arguments(parser)
    args = parser.parse_args()
    setup_from_args(args, 'render_primary')
    print(render_from_manifest(args.manifest, args.output, args.classifier))


if __name__ == '__main__':
    main()
