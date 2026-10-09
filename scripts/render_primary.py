"""Render separate PyGMT maps from a completed product; optionally classify it."""
import argparse
from afiw.workflows.maps import render_from_manifest

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--output', required=True, help='New empty derived-product directory')
    parser.add_argument('--classifier', help='Trusted local region-specific joblib model')
    args = parser.parse_args()
    print(render_from_manifest(args.manifest, args.output, args.classifier))
