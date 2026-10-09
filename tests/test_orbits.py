from io import BytesIO
import zipfile
import pytest
from afiw.observations import orbits

NAME = 'S1A_OPER_AUX_POEORB_OPOD_20211022T122524_V20211001T225942_20211003T005942.EOF'
FEATURE = {'properties': {'sceneName': 'S1A_EW_scene',
    'startTime': '2021-10-02T14:39:59Z', 'stopTime': '2021-10-02T14:41:03Z'}}


def xml(mission='Sentinel-1A', stop='2021-10-03T00:59:42', last='2021-10-03T00:59:42'):
    def osv(time):
        return '<OSV><UTC>UTC='+time+'</UTC>'+''.join('<'+k+'>1</'+k+'>' for k in ('X','Y','Z','VX','VY','VZ'))+'</OSV>'
    return ('<Earth_Explorer_File><Earth_Explorer_Header><Fixed_Header><Mission>'+mission+
        '</Mission><File_Type>AUX_POEORB</File_Type><Validity_Period><Validity_Start>UTC=2021-10-01T22:59:42</Validity_Start><Validity_Stop>UTC='+stop+
        '</Validity_Stop></Validity_Period></Fixed_Header></Earth_Explorer_Header><Data_Block><List_of_OSVs>'+osv('2021-10-01T22:59:42')+osv(last)+
        '</List_of_OSVs></Data_Block></Earth_Explorer_File>').encode()


def test_validity_and_spacecraft():
    mission, start, end, _ = orbits.scene_window(FEATURE)
    orbits.validate_eof(xml(), NAME, mission, start, end)
    with pytest.raises(ValueError, match='spacecraft'):
        orbits.validate_eof(xml(mission='Sentinel-1B'), NAME, mission, start, end)
    with pytest.raises(ValueError, match='validity'):
        orbits.validate_eof(xml(stop='2021-10-02T00:00:00'), NAME, mission, start, end)
    with pytest.raises(ValueError, match='state vectors do not cover'):
        orbits.validate_eof(xml(last='2021-10-02T14:41:03'), NAME, mission, start, end)


def test_download_duplicate_zip_and_cache(tmp_path, monkeypatch):
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr(NAME, xml())
        archive.writestr('var/www/auxdata/'+NAME, xml())
    def fetch(url, _session):
        if url.endswith('/'):
            return ('<a href="'+NAME+'.zip">orbit</a>').encode()
        return buffer.getvalue()
    monkeypatch.setattr(orbits, 'public_get', fetch)
    path = orbits.prepare_scene_orbit(FEATURE, tmp_path, session=object())
    assert path == tmp_path/'POEORB/S1A/2021/10'/NAME
    assert path.with_suffix('.download.json').exists()
    monkeypatch.setattr(orbits, 'public_get', lambda *_: pytest.fail('cached orbit must not download'))
    assert orbits.prepare_scene_orbit(FEATURE, tmp_path, check_only=True) == path
    assert not (tmp_path/'var').exists()


def test_check_only_never_networks(tmp_path, monkeypatch):
    monkeypatch.setattr(orbits, 'public_get', lambda *_: pytest.fail('offline check'))
    with pytest.raises(FileNotFoundError):
        orbits.prepare_scene_orbit(FEATURE, tmp_path, check_only=True)


def test_year_boundary_discovery(tmp_path, monkeypatch):
    feature = {'properties': {'sceneName': 'S1A_test', 'startTime': '2022-01-01T00:00:30Z', 'stopTime': '2022-01-01T00:01:30Z'}}
    calls = []
    monkeypatch.setattr(orbits, 'public_get', lambda url, session: calls.append(url) or b'')
    with pytest.raises(FileNotFoundError, match='No published'):
        orbits.prepare_scene_orbit(feature, tmp_path, session=object())
    assert any('/2021/12/' in url for url in calls)
    assert any('/2022/01/' in url for url in calls)


def test_corrupt_download_not_installed(tmp_path, monkeypatch):
    monkeypatch.setattr(orbits, 'public_get', lambda url, session:
        ('<a href="'+NAME+'">orbit</a>').encode() if url.endswith('/') else b'<html>error</html>')
    with pytest.raises(ValueError):
        orbits.prepare_scene_orbit(FEATURE, tmp_path, session=object())
    assert not list(tmp_path.rglob('*.EOF'))


def test_public_request_uses_no_site_auth_and_rejects_redirect():
    from types import SimpleNamespace
    calls = []
    class Response:
        status_code = 302
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass
    def get(url, **kwargs):
        calls.append(kwargs)
        return Response()
    with pytest.raises(RuntimeError, match='HTTP 302'):
        orbits.public_get(orbits.BASE_URL, SimpleNamespace(get=get))
    request = object()
    assert calls[0]['auth'](request) is request
    assert calls[0]['allow_redirects'] is False
