"""Shared console/file logging for command-line and notebook workflows."""
from contextvars import ContextVar
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
import inspect
import json
import logging
import os
import re
import sys
import time

LOGGER         = logging.getLogger('afiw')
WORKFLOW_DEPTH = ContextVar('afiw_workflow_depth', default = 0)
AUTOMATIC      = False


def configure_logging(station = 'general', workflow = 'workflow', log_dir = None, level = 'INFO', *, _automatic = False):
    """Replace only AFIW handlers; retain host application logging settings."""
    global AUTOMATIC
    station = str(station).lower()
    if not re.fullmatch(r'[a-z0-9_-]+', station):
        raise ValueError('Unsafe logging station name')
    directory = Path(log_dir).expanduser() if log_dir else Path.home() / 'afiw_data' / station / 'logs'
    directory.mkdir(parents = True, exist_ok = True)
    name = re.sub(r'[^a-zA-Z0-9_-]', '_', workflow)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    path = directory / f'{stamp}_{name}_{os.getpid()}.log'
    formatter = logging.Formatter('%(asctime)sZ | %(levelname)-8s | %(name)s | %(message)s', '%Y-%m-%dT%H:%M:%S')
    formatter.converter = time.gmtime
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(level)
    console.setFormatter(formatter)
    file = logging.FileHandler(path, encoding = 'utf-8')
    file.setLevel(logging.DEBUG)
    file.setFormatter(formatter)
    for handler in list(LOGGER.handlers):
        LOGGER.removeHandler(handler)
        handler.close()
    LOGGER.setLevel(logging.DEBUG)
    LOGGER.propagate = False
    LOGGER.addHandler(console)
    LOGGER.addHandler(file)
    AUTOMATIC = _automatic
    LOGGER.info('Workflow=%s station=%s; log file: %s', workflow, station, path)
    return path


def add_logging_arguments(parser):
    parser.add_argument('--log-dir', help='Override ~/afiw_data/[station]/logs')
    parser.add_argument('--log-level', choices = ['DEBUG', 'INFO', 'WARNING', 'ERROR'], default = 'INFO',
                        help='Console verbosity; file always includes DEBUG')
    parser.add_argument('--log-station', help='Station for workflows without config/manifest; otherwise inferred')


def station_from_inputs(manifest = None, config = None, region = None, pairs = None):
    if region:
        return getattr(region, 'name', region)
    if manifest:
        return json.loads(Path(manifest).expanduser().read_text())['region']
    if config:
        import yaml
        return yaml.safe_load(Path(config).expanduser().read_text())['run']['region']['name']
    if pairs:
        path = Path(pairs).expanduser().resolve()
        if path.parent.name == 'catalog':
            return path.parent.parent.name
    return 'general'


def setup_from_args(args, workflow):
    try:
        station = getattr(args, 'log_station', None) or getattr(args, 'station', None) or station_from_inputs(
            manifest = getattr(args, 'manifest', None),
            config   = getattr(args, 'config', None),
            region   = getattr(args, 'region', None) or ('Davis' if getattr(args, 'command', None) == 'demo' else None),
            pairs    = getattr(args, 'pairs', None))
    except Exception:
        configure_logging('general', workflow, args.log_dir, args.log_level)
        LOGGER.exception('Cannot determine logging station from config/manifest')
        raise
    return configure_logging(station, workflow, args.log_dir, args.log_level)


def logged_step(function):
    """Report stage duration and full tracebacks without dumping inputs/secrets."""
    @wraps(function)
    def wrapped(*args, **kwargs):
        module = function.__module__ if function.__module__.startswith('afiw.') else 'afiw.scripts.' + Path(function.__code__.co_filename).stem
        logger = logging.getLogger(module)
        name   = function.__qualname__
        start  = time.monotonic()
        logger.info('Starting %s', name)
        try:
            result = function(*args, **kwargs)
        except Exception:
            logger.exception('Failed %s after %.2f s', name, time.monotonic() - start)
            raise
        logger.info('Completed %s in %.2f s', name, time.monotonic() - start)
        if isinstance(result, (Path, str)):
            logger.info('%s output: %s', name, result)
        return result
    return wrapped


def logged_workflow(function):
    """Enable default logging for direct Python/notebook workflow calls too."""
    step = logged_step(function)
    @wraps(function)
    def wrapped(*args, **kwargs):
        depth = WORKFLOW_DEPTH.get()
        if depth == 0 and (not LOGGER.handlers or AUTOMATIC):
            values = inspect.signature(function).bind(*args, **kwargs).arguments
            owner  = values.get('self')
            spec   = getattr(owner, 'spec', None)
            run    = getattr(spec, 'run', None) or getattr(owner, 'run_cfg', None)
            region = getattr(run, 'region', None) or getattr(owner, 'region', None)
            if function.__name__ == 'run_demo':
                region = 'Davis'
            try:
                station = station_from_inputs(values.get('manifest'), values.get('config'), region)
            except Exception:
                configure_logging(workflow = function.__name__, _automatic = True)
                LOGGER.exception('Cannot determine logging station')
                raise
            configure_logging(station, function.__name__, _automatic = True)
        token = WORKFLOW_DEPTH.set(depth + 1)
        try:
            return step(*args, **kwargs)
        finally:
            WORKFLOW_DEPTH.reset(token)
    return wrapped


def monitor_process_log(path, logger, label):
    """Mirror a subprocess log while retaining subprocess.run timeout semantics."""
    from contextlib import contextmanager
    from threading import Event, Thread

    @contextmanager
    def monitor():
        stop = Event()
        def follow():
            with Path(path).open(encoding = 'utf-8', errors = 'replace') as stream:
                while True:
                    line = stream.readline()
                    if line:
                        logger.info('%s | %s', label, line.rstrip())
                    elif stop.is_set():
                        break
                    else:
                        stop.wait(0.25)
        thread = Thread(target = follow, name = 'afiw_process_log', daemon = True)
        thread.start()
        try:
            yield
        finally:
            stop.set()
            thread.join()
    return monitor()
