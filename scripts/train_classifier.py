"""Train an unvalidated region-specific SVM from reviewed manual label raster."""
import argparse
from afiw.workflows.maps import train_from_manifest

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--labels', required=True, help='Single-band labels matching segments.tif: 0,2,3; unlabelled=255')
    parser.add_argument('--output', required=True, help='New .joblib model path')
    parser.add_argument('--label-source', required=True, help='Human reviewer and evidence used for labels')
    args = parser.parse_args()
    print(train_from_manifest(args.manifest, args.labels, args.output, args.label_source))
