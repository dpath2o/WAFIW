import logging
from .core.logging import add_logging_arguments, setup_from_args, logged_step
from pathlib import Path
import argparse,json
from .core.types import WorkflowSpec
from .workflows.primary import PrimaryWorkflow
from .workflows.demo import run_demo
from .products.bulletin import BulletinBuilder

logger = logging.getLogger(__name__)

@logged_step
def primary_main(argv=None):
    p=argparse.ArgumentParser(description='AFIW primary Sentinel-1 workflow')
    p.add_argument('--config',default='configs/davis.yaml');sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('doctor',help='Check local configuration and dependencies')
    sub.add_parser('search',help='Public catalogue search; no scene download')
    demo=sub.add_parser('demo');demo.add_argument('--output',default='demo_output')
    raw=sub.add_parser('process-raster');raw.add_argument('--first',required=True);raw.add_argument('--second',required=True);raw.add_argument('--first-time',required=True);raw.add_argument('--second-time',required=True)
    cat=sub.add_parser('run-catalog');cat.add_argument('--pairs');cat.add_argument('--pair-index',type=int,default=0);cat.add_argument('--max-pairs',type=int,default=1);cat.add_argument('--download',action='store_true')
    cat.add_argument('--prepare-orbits',action='store_true',help='Prepare validated precise orbits in the local SNAP cache before processing')
    cat.add_argument('--orbit-cache-root',help='Sentinel-1 cache root; must match the cache used by SNAP')
    pre=sub.add_parser('preprocess');pre.add_argument('--safe',required=True);pre.add_argument('--output',required=True);pre.add_argument('--dry-run',action='store_true')
    train = sub.add_parser('train-research', help='Reuse research segment annotations; save model and grouped assessment')
    train.add_argument('--training-root', required = True)
    train.add_argument('--output', required = True)
    train.add_argument('--label-source', required = True)
    train.add_argument('--polarization', choices = ['HH', 'HV'], default = 'HH')
    train.add_argument('--scenes', nargs = '+', help='Explicit reviewed subset; default is the ten reference scenes')
    manual = sub.add_parser('train-labels', help='Train from reviewed labels on a persisted WAFIW segment grid')
    manual.add_argument('--manifest', required = True)
    manual.add_argument('--labels', required = True)
    manual.add_argument('--output', required = True)
    manual.add_argument('--label-source', required = True)
    render = sub.add_parser('render', help='Re-render or classify a persisted product')
    produce = sub.add_parser('produce', help='Complete classified maps and optionally assemble a bulletin')
    for command in (render, produce):
        command.add_argument('--manifest', required = True)
        command.add_argument('--output', required = True)
        command.add_argument('--classifier')
        command.add_argument('--allow-model-transfer', action = 'store_true', help='Explicit candidate reuse across sites/preprocessing; recorded in manifest')
    render.add_argument('--require-classification', action = 'store_true')
    produce.add_argument('--bulletin-output', help='Optional bulletin output directory')
    produce.add_argument('--as-of', help='Bulletin date; default is second acquisition date')
    validate = sub.add_parser('validate', help='Assess classified fast-ice outline within a reviewed domain')
    for name in ('manifest', 'reference', 'domain', 'output', 'first-date', 'second-date', 'label-source'):
        validate.add_argument('--' + name, required = True)
    for command in (raw, cat):
        command.add_argument('--require-classification', action = 'store_true', help='Fail before processing if a complete classified product cannot be configured')
    add_logging_arguments(p)
    for command_parser in sub.choices.values():
        add_logging_arguments(command_parser, suppress_defaults = True)
    args=p.parse_args(argv)
    if args.command in ('train-research', 'train-labels', 'render', 'produce', 'validate', 'demo'):
        args.config = None
    setup_from_args(args, args.command)
    if args.command=='demo':print(run_demo(args.output).manifest);return
    if args.command == 'train-research':
        from .classify.research import train_research
        print(train_research(args.training_root, args.output, args.label_source, args.polarization, args.scenes))
        return
    if args.command == 'train-labels':
        from .workflows.maps import train_from_manifest
        print(train_from_manifest(args.manifest, args.labels, args.output, args.label_source))
        return
    if args.command == 'validate':
        from .workflows.validation import validate_outline
        print(validate_outline(args.manifest, args.reference, args.domain, args.output,
                               args.first_date, args.second_date, args.label_source))
        return
    if args.command in ('render', 'produce'):
        from .workflows.maps import render_from_manifest
        result = render_from_manifest(args.manifest, args.output, args.classifier,
                                      args.allow_model_transfer, args.command == 'produce' or getattr(args, 'require_classification', False))
        if args.command == 'produce' and args.bulletin_output:
            record = json.loads(result.read_text())
            as_of = args.as_of or record['second_time'][:10]
            print(BulletinBuilder(result.parent, record['region']).build(as_of, args.bulletin_output))
        print(result)
        return
    spec=WorkflowSpec.load(args.config)
    if getattr(args, 'require_classification', False):
        from dataclasses import replace
        spec = replace(spec, require_classification = True)
    workflow=PrimaryWorkflow(spec)
    if args.command=='doctor':
        import shutil,platform
        logger.info('Platform: %s', platform.platform());logger.info('Root: %s', workflow.paths.station)
        logger.info('SNAP executable: %s', shutil.which(spec.snap.executable) or ('configured file' if Path(spec.snap.executable).is_file() else 'MISSING (needed for raw SAFE)'))
        logger.info('DEM: %s', 'present' if spec.snap.dem_path and Path(spec.snap.dem_path).is_file() else 'MISSING (needed for raw SAFE)')
        logger.info('Coastline: %s', 'present' if spec.coastline and Path(spec.coastline).is_file() else 'not supplied')
        logger.info('Classifier: %s', 'present' if spec.classifier and Path(spec.classifier).is_file() else 'not supplied; segmentation only')
        logger.info('Segmentation: %s device: %s', spec.segmentation.backend, spec.segmentation.device)
        from .plotting.primary import require_pygmt
        try:
            pygmt=require_pygmt(); logger.info('Plotting: PyGMT %s', pygmt.__version__); pygmt.show_versions()
        except RuntimeError as error:logger.info('Plotting: %s', error)
    elif args.command=='search':
        catalog=workflow.search();pairs=json.loads((workflow.paths.catalog/'pairs.json').read_text());print(f"{len(catalog['features'])} scenes; {len(pairs)} compatible pairs. Catalog: {workflow.paths.catalog}")
    elif args.command=='process-raster':print(workflow.from_rasters(args.first,args.second,args.first_time,args.second_time).manifest)
    elif args.command=='preprocess':
        from .processing.snap import SnapPreprocessor
        print(SnapPreprocessor(spec.snap,spec.processing,spec.run.region,spec.acquisition.polarization).run(args.safe,args.output,args.dry_run))
    else:
        pairs=json.loads(Path(args.pairs or workflow.paths.catalog/'pairs.json').read_text())
        if args.pair_index<0 or args.max_pairs<1:raise ValueError('Invalid pair selection')
        selected=pairs[args.pair_index:args.pair_index+args.max_pairs]
        if not selected:raise ValueError('No pairs selected; run search and inspect pairs.json')
        for pair in selected:
            if args.prepare_orbits:
                from .observations.orbits import prepare_pair_orbits
                for path in prepare_pair_orbits(pair,args.orbit_cache_root):logger.info('Validated precise orbit: %s', path)
            print(workflow.from_safe_pair(pair,args.download).manifest)

@logged_step
def bulletin_main(argv=None):
    p=argparse.ArgumentParser(description='Independent AFIW bulletin workflow')
    sub=p.add_subparsers(dest='command',required=True)
    for name in ['build','season']:
        s=sub.add_parser(name);s.add_argument('--root',required=True);s.add_argument('--region',default='Davis');s.add_argument('--output',required=True)
        if name=='build':s.add_argument('--as-of',required=True);s.add_argument('--compile-latex',action='store_true')
        else:s.add_argument('--start-years',type=int,nargs='+',required=True);s.add_argument('--start-month',type=int,default=9);s.add_argument('--end-month',type=int,default=4)
    add_logging_arguments(p)
    for command_parser in sub.choices.values():
        add_logging_arguments(command_parser, suppress_defaults = True)
    args=p.parse_args(argv)
    setup_from_args(args, args.command)
    builder=BulletinBuilder(args.root,args.region)
    if args.command=='build':print(builder.build(args.as_of,args.output,args.compile_latex))
    else:
        for year in args.start_years:logger.info('%s %s', year, len(builder.season(year,Path(args.output)/f'{year}-{year+1}',args.start_month,args.end_month)))
