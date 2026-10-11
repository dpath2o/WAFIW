"""Train an unvalidated region-specific SVM from reviewed manual label raster."""
from afiw.core.logging import add_logging_arguments, setup_from_args, logged_step
import argparse
from afiw.workflows.maps import train_from_manifest

@logged_step
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--labels', required=True, help='Single-band labels matching segments.tif: 0,2,3; unlabelled=255')
    parser.add_argument('--output', required=True, help='New .joblib model path')
    parser.add_argument('--label-source', required=True, help='Human reviewer and evidence used for labels')
    add_logging_arguments(parser)
    args = parser.parse_args()
    setup_from_args(args, 'train_classifier')
    print(train_from_manifest(args.manifest, args.labels, args.output, args.label_source))


if __name__ == '__main__':
    main()
