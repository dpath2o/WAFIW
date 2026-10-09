from pathlib import Path
import argparse,json
from .core.types import WorkflowSpec
from .workflows.primary import PrimaryWorkflow
from .workflows.demo import run_demo
from .products.bulletin import BulletinBuilder
from .products.example import generate_research_example

def primary_main(argv=None):
    p=argparse.ArgumentParser(description='AFIW primary Sentinel-1 workflow')
    p.add_argument('--config',default='configs/davis.yaml');sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('doctor',help='Check local configuration and dependencies')
    sub.add_parser('search',help='Public catalogue search; no scene download')
    demo=sub.add_parser('demo');demo.add_argument('--output',default='demo_output')
    raw=sub.add_parser('process-raster');raw.add_argument('--first',required=True);raw.add_argument('--second',required=True);raw.add_argument('--first-time',required=True);raw.add_argument('--second-time',required=True)
    cat=sub.add_parser('run-catalog');cat.add_argument('--pairs');cat.add_argument('--pair-index',type=int,default=0);cat.add_argument('--max-pairs',type=int,default=1);cat.add_argument('--download',action='store_true')
    pre=sub.add_parser('preprocess');pre.add_argument('--safe',required=True);pre.add_argument('--output',required=True);pre.add_argument('--dry-run',action='store_true')
    args=p.parse_args(argv)
    if args.command=='demo':print(run_demo(args.output).manifest);return
    spec=WorkflowSpec.load(args.config);workflow=PrimaryWorkflow(spec)
    if args.command=='doctor':
        import shutil,platform
        print('Platform:',platform.platform());print('Root:',workflow.paths.station)
        print('SNAP executable:',shutil.which(spec.snap.executable) or ('configured file' if Path(spec.snap.executable).is_file() else 'MISSING (needed for raw SAFE)'))
        print('DEM:', 'present' if spec.snap.dem_path and Path(spec.snap.dem_path).is_file() else 'MISSING (needed for raw SAFE)')
        print('Coastline:', 'present' if spec.coastline and Path(spec.coastline).is_file() else 'not supplied')
        print('Classifier:', 'present' if spec.classifier and Path(spec.classifier).is_file() else 'not supplied; segmentation only')
        print('Segmentation:',spec.segmentation.backend,'device:',spec.segmentation.device)
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
        for pair in selected:print(workflow.from_safe_pair(pair,args.download).manifest)

def bulletin_main(argv=None):
    p=argparse.ArgumentParser(description='Independent AFIW bulletin workflow')
    sub=p.add_subparsers(dest='command',required=True)
    for name in ['build','season']:
        s=sub.add_parser(name);s.add_argument('--root',required=True);s.add_argument('--region',default='Davis');s.add_argument('--output',required=True)
        if name=='build':s.add_argument('--as-of',required=True);s.add_argument('--compile-latex',action='store_true')
        else:s.add_argument('--start-years',type=int,nargs='+',required=True);s.add_argument('--start-month',type=int,default=9);s.add_argument('--end-month',type=int,default=4)
    ex=sub.add_parser('research-example');ex.add_argument('--template',default='examples/research_example');ex.add_argument('--output',required=True);ex.add_argument('--no-compile',action='store_true')
    args=p.parse_args(argv)
    if args.command=='research-example':print(generate_research_example(args.template,args.output,not args.no_compile));return
    builder=BulletinBuilder(args.root,args.region)
    if args.command=='build':print(builder.build(args.as_of,args.output,args.compile_latex))
    else:
        for year in args.start_years:print(year,len(builder.season(year,Path(args.output)/f'{year}-{year+1}',args.start_month,args.end_month)))
