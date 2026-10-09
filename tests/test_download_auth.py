"""Local authentication selection; mocked SDK, no network or real credentials."""
from types import SimpleNamespace
import netrc
import pytest
import asf_search as asf
from afiw.observations import sentinel1


def fake_session(monkeypatch):
    calls = []
    session = SimpleNamespace()
    def token(value):
        calls.append(('token', value))
        return session
    def creds(login, password):
        calls.append(('creds', login, password))
        return session
    session.auth_with_token = token
    session.auth_with_creds = creds
    monkeypatch.setattr(asf, 'ASFSession', lambda: session)
    return session, calls


def test_explicit_token_takes_precedence(monkeypatch):
    session, calls = fake_session(monkeypatch)
    monkeypatch.setenv('EARTHDATA_TOKEN', 'dummy-token')
    monkeypatch.setattr(sentinel1.netrc, 'netrc', lambda: pytest.fail('must not read netrc'))
    assert sentinel1.earthdata_session() is session
    assert calls == [('token', 'dummy-token')]


def test_netrc_selects_only_earthdata(monkeypatch):
    session, calls = fake_session(monkeypatch)
    monkeypatch.delenv('EARTHDATA_TOKEN', raising=False)
    entries = {'urs.earthdata.nasa.gov': ('dummy-login', '', 'dummy-password'),
               'other.example': ('unrelated-login', '', 'unrelated-password')}
    monkeypatch.setattr(sentinel1.netrc, 'netrc', lambda: SimpleNamespace(hosts=entries))
    assert sentinel1.earthdata_session() is session
    assert calls == [('creds', 'dummy-login', 'dummy-password')]


def test_parser_failure_is_sanitized(monkeypatch):
    monkeypatch.delenv('EARTHDATA_TOKEN', raising=False)
    def malformed():
        raise netrc.NetrcParseError('dummy-sensitive-text')
    monkeypatch.setattr(sentinel1.netrc, 'netrc', malformed)
    with pytest.raises(RuntimeError) as error:
        sentinel1.earthdata_session()
    assert 'dummy-sensitive-text' not in str(error.value)
    assert error.value.__suppress_context__


def test_auth_failure_is_sanitized(monkeypatch):
    session, _ = fake_session(monkeypatch)
    monkeypatch.setenv('EARTHDATA_TOKEN', 'dummy-token')
    def failure(value):
        raise ValueError('dummy-sensitive-text')
    session.auth_with_token = failure
    with pytest.raises(RuntimeError) as error:
        sentinel1.earthdata_session()
    assert 'dummy-sensitive-text' not in str(error.value)


def test_cached_pair_does_not_authenticate(tmp_path, monkeypatch):
    import zipfile
    from afiw.observations.sentinel1 import Sentinel1Client
    for name in ('first.zip', 'second.zip'):
        with zipfile.ZipFile(tmp_path / name, 'w') as archive:
            archive.writestr('scene.SAFE/manifest.safe', '<manifest/>')
    monkeypatch.setattr(sentinel1, 'earthdata_session', lambda *_: pytest.fail('cached pair should not authenticate'))
    pair = {key: {'properties': {'url': 'https://example.invalid/'+name}}
            for key, name in [('first', 'first.zip'), ('second', 'second.zip')]}
    client = Sentinel1Client(None, None, SimpleNamespace(downloads=tmp_path))
    assert len(client.download_pair(pair)) == 2


def test_default_netrc_entry_is_not_used(monkeypatch):
    monkeypatch.delenv('EARTHDATA_TOKEN', raising=False)
    monkeypatch.setattr(sentinel1.netrc, 'netrc', lambda: SimpleNamespace(
        hosts={'default': ('dummy-login', '', 'dummy-password')}))
    with pytest.raises(RuntimeError, match='urs.earthdata.nasa.gov'):
        sentinel1.earthdata_session()
