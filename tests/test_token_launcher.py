"""Token handoff tests use dummy values and never connect to Earthdata."""
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace


spec = importlib.util.spec_from_file_location('token_launcher',
    Path(__file__).resolve().parents[1] / 'scripts/run_with_earthdata_token.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


def test_visible_token_child_environment(monkeypatch, capsys):
    monkeypatch.setenv('NETRC', '/dummy/old-netrc')
    monkeypatch.setenv('EARTHDATA_TOKEN', 'dummy-stale-token')
    monkeypatch.setenv('HTTPS_PROXY', 'https://proxy.example:443')
    monkeypatch.setenv('REQUESTS_CA_BUNDLE', '/dummy/ca.pem')
    monkeypatch.setattr('builtins.input', lambda _: ' dummy-new-token ')
    calls = []
    monkeypatch.setattr(launcher.subprocess, 'run',
        lambda command, env: calls.append((command, env)) or SimpleNamespace(returncode=7))
    args = ['--config', 'configs/davis.yaml', 'run-catalog', '--download']
    assert launcher.main(['--visible-token', *args]) == 7
    command, env = calls[0]
    assert command[2:] == args
    assert 'dummy-new-token' not in command
    assert env['EARTHDATA_TOKEN'] == 'dummy-new-token'
    assert env['NETRC'] == os.devnull
    assert env['HTTPS_PROXY'] == 'https://proxy.example:443'
    assert env['REQUESTS_CA_BUNDLE'] == '/dummy/ca.pem'
    assert os.environ['NETRC'] == '/dummy/old-netrc'
    assert os.environ['EARTHDATA_TOKEN'] == 'dummy-stale-token'
    assert 'dummy-new-token' not in capsys.readouterr().out


def test_hidden_prompt_and_empty_token(monkeypatch):
    monkeypatch.setattr(launcher.getpass, 'getpass', lambda _: ' ')
    monkeypatch.setattr(launcher.subprocess, 'run', lambda *_args, **_kw: (_ for _ in ()).throw(AssertionError('must not launch')))
    assert launcher.main(['--config', 'configs/davis.yaml', 'doctor']) == 2


def test_cancelled_prompt(monkeypatch):
    def cancelled(_):
        raise EOFError
    monkeypatch.setattr('builtins.input', cancelled)
    assert launcher.main(['--visible-token', 'doctor']) == 2
