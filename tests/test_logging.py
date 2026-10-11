"""Logging defaults, diagnostics and unchanged failure semantics."""
import argparse
import json
import logging
from pathlib import Path
import pytest
from afiw.core.logging import (LOGGER, configure_logging, add_logging_arguments,
                               setup_from_args, logged_step, logged_workflow,
                               monitor_process_log)


@pytest.fixture(autouse = True)
def isolated_logger():
    handlers, level, propagate = LOGGER.handlers[:], LOGGER.level, LOGGER.propagate
    LOGGER.handlers = []
    yield
    for handler in LOGGER.handlers:
        handler.close()
    LOGGER.handlers, LOGGER.level, LOGGER.propagate = handlers, level, propagate


def test_default_station_directory_and_console(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    root_handlers = logging.getLogger().handlers[:]
    path = configure_logging('Davis', 'render_primary')
    logger = logging.getLogger('afiw.workflows.maps')
    logger.info('classification unavailable')
    logger.debug('tile window diagnostic')
    assert path.parent == tmp_path / 'afiw_data/davis/logs'
    assert 'classification unavailable' in capsys.readouterr().err
    assert 'tile window diagnostic' in path.read_text()
    assert logging.getLogger().handlers == root_handlers
    replacement = configure_logging('Davis', 'render_primary')
    assert replacement != path and len(LOGGER.handlers) == 2
    logger.info('only one copy')
    assert replacement.read_text().count('only one copy') == 1
    assert 'only one copy' not in path.read_text()


def test_manifest_inference_overrides_and_full_traceback(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({'region': 'Mawson'}))
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest')
    add_logging_arguments(parser)
    args = parser.parse_args(['--manifest', str(manifest)])
    path = setup_from_args(args, 'render_primary')
    assert path.parent == tmp_path / 'afiw_data/mawson/logs'
    @logged_step
    def fail():
        raise ValueError('grid mismatch diagnostic')
    with pytest.raises(ValueError, match = 'grid mismatch'):
        fail()
    assert 'Traceback' in path.read_text() and 'grid mismatch diagnostic' in path.read_text()
    args = parser.parse_args(['--manifest', str(manifest), '--log-dir', str(tmp_path / 'custom'), '--log-level', 'DEBUG'])
    assert setup_from_args(args, 'render_primary').parent == tmp_path / 'custom'


def test_bad_manifest_creates_fallback_error_log(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    args = argparse.Namespace(manifest = tmp_path / 'missing.json', log_station = None,
                              log_dir = None, log_level = 'INFO')
    with pytest.raises(FileNotFoundError):
        setup_from_args(args, 'render_primary')
    logs = list((tmp_path / 'afiw_data/general/logs').glob('*.log'))
    assert len(logs) == 1 and 'Cannot determine logging station' in logs[0].read_text()


def test_workflow_api_enables_logging(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({'region': 'Casey'}))
    @logged_workflow
    def workflow(manifest):
        return manifest
    assert workflow(manifest) == manifest
    log = next((tmp_path / 'afiw_data/casey/logs').glob('*.log'))
    assert 'Completed' in log.read_text()


def test_subprocess_log_mirrored_on_failure(tmp_path, capsys):
    log = configure_logging('Davis', 'snap', tmp_path)
    native = tmp_path / 'scene.snap.log'
    with pytest.raises(RuntimeError):
        with native.open('w') as stream, monitor_process_log(native, LOGGER, 'SNAP'):
            stream.write('Orbit processing failed\n')
            stream.flush()
            raise RuntimeError('test subprocess failed')
    assert 'SNAP | Orbit processing failed' in log.read_text()
    assert 'Orbit processing failed' in capsys.readouterr().err


def test_consecutive_notebook_workflows_use_their_own_station(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    @logged_workflow
    def workflow(manifest):
        return manifest
    for region in ('Davis', 'Casey'):
        manifest = tmp_path / f'{region}.json'
        manifest.write_text(json.dumps({'region': region}))
        workflow(manifest)
        assert len(list((tmp_path / 'afiw_data' / region.lower() / 'logs').glob('*.log'))) == 1
