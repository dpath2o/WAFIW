"""Prepare validated Sentinel-1 precise orbit files in SNAP's local cache.

Public ESA STEP downloads only; no Earthdata/CDSE credential is required.
"""
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
import re
import tempfile
import xml.etree.ElementTree as ET
import zipfile
import requests
from afiw.core.provenance import sha256, write_json

BASE_URL  = 'https://step.esa.int/auxdata/orbits/Sentinel-1/POEORB/'
NAME      = re.compile(r'(S1[ABCD])_OPER_AUX_POEORB_OPOD_(\d{8}T\d{6})_V(\d{8}T\d{6})_(\d{8}T\d{6})\.EOF(?:\.zip)?')
MAX_BYTES = 20 * 1024 * 1024

def timestamp(value):
    parsed = datetime.fromisoformat(value.removeprefix('UTC=').replace('Z', '+00:00'))
    return parsed.replace(tzinfo = timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)

def orbit_name(name):
    match = NAME.fullmatch(name)
    if not match:
        raise ValueError('Not a supported precise orbit filename')
    mission, creation, start, end = match.groups()
    return mission, timestamp(creation), timestamp(start), timestamp(end)

def scene_window(feature, margin_seconds = 60):
    props   = feature['properties']
    name    = props.get('sceneName') or Path(props['url'].split('?')[0]).name
    mission = name[:3]
    if mission not in ('S1A', 'S1B', 'S1C', 'S1D'):
        raise ValueError('Cannot determine Sentinel-1 spacecraft from scene name')
    start, end = timestamp(props['startTime']), timestamp(props['stopTime'])
    if end <= start:
        raise ValueError('Invalid scene time interval')
    margin = timedelta(seconds = margin_seconds)
    return mission, start - margin, end + margin, start

def validate_eof(data, name, mission, start, end):
    """Check type, spacecraft, validity, OSV times and finite state vectors."""
    nm, _, ns, ne = orbit_name(name)
    if nm != mission or not ns <= start <= end <= ne:
        raise ValueError('Orbit filename does not cover scene and margin')
    if len(data) > MAX_BYTES:
        raise ValueError('Orbit XML is too large')
    root = ET.fromstring(data)
    header = root.find('./Earth_Explorer_Header/Fixed_Header')
    if header is None or header.findtext('File_Type') != 'AUX_POEORB':
        raise ValueError('Expected an Earth Explorer precise orbit file')
    if header.findtext('Mission') != 'Sentinel-1' + mission[-1]:
        raise ValueError('Orbit XML spacecraft mismatch')
    vs = timestamp(header.findtext('Validity_Period/Validity_Start', ''))
    ve = timestamp(header.findtext('Validity_Period/Validity_Stop', ''))
    if vs != ns or ve != ne or not vs <= start <= end <= ve:
        raise ValueError('Orbit XML validity mismatch')
    import math
    vectors = root.findall('./Data_Block/List_of_OSVs/OSV')
    times = []
    for vector in vectors:
        times.append(timestamp(vector.findtext('UTC', '')))
        if not all(math.isfinite(float(vector.findtext(key, 'nan')))
                   for key in ('X', 'Y', 'Z', 'VX', 'VY', 'VZ')):
            raise ValueError('Invalid orbit state vector')
    if len(times) < 2 or any(a >= b for a, b in zip(times, times[1:])):
        raise ValueError('Missing or unordered orbit state vectors')
    if not times[0] <= start <= end <= times[-1]:
        raise ValueError('Orbit state vectors do not cover scene and margin')

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.names = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            href = dict(attrs).get('href', '')
            if NAME.fullmatch(href):
                self.names.append(href)

def public_get(url, session, limit = MAX_BYTES):
    # Explicit no-op auth prevents Requests consulting developer netrc entries.
    # Reject redirects: new destinations require a reviewed provider change.
    with session.get(url, auth = lambda request: request, allow_redirects = False, timeout = (15, 120), stream = True) as response:
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise RuntimeError(f'ESA orbit request returned HTTP {response.status_code}: {url}')
        data = bytearray()
        for chunk in response.iter_content(65536):
            data.extend(chunk)
            if len(data) > limit:
                raise ValueError('ESA orbit response exceeds size limit')
        return bytes(data)

def prepare_scene_orbit(feature, cache_root=None, check_only=False, session=None):
    mission, start, end, acquisition = scene_window(feature)
    root = Path(cache_root).expanduser() if cache_root else Path.home() / '.snap/auxdata/Orbits/Sentinel-1'
    folder = root / 'POEORB' / mission / f'{acquisition:%Y/%m}'
    # SNAP searches the acquisition month. Store uncompressed EOF there.
    for path in sorted(folder.glob('*.EOF'), reverse=True):
        try:
            validate_eof(path.read_bytes(), path.name, mission, start, end)
        except (ValueError, ET.ParseError):
            continue
        return path
    if check_only:
        raise FileNotFoundError(f'No validated precise orbit covers the scene: {folder}')
    if session is None:
        with requests.Session() as owned:
            return prepare_scene_orbit(feature, root, session=owned)
    candidates = []
    # Validity can begin in the previous month, including across year boundaries.
    months = sorted({(start + timedelta(days=d)).strftime('%Y/%m') for d in (-2, 0, 2)})
    for month in months:
        url = BASE_URL + mission + '/' + month + '/'
        listing = public_get(url, session)
        if listing is None:
            continue
        parser = Links()
        parser.feed(listing.decode('utf-8'))
        for name in parser.names:
            nm, creation, ns, ne = orbit_name(name)
            if nm == mission and ns <= start <= end <= ne:
                candidates.append((creation, name, url + name))
    if not candidates:
        raise FileNotFoundError('No published ESA precise orbit covers this scene; recent scenes may need to wait for POEORB publication. No restituted fallback is applied.')
    _, name, url = max(candidates)
    data         = public_get(url, session)
    if data is None:
        raise FileNotFoundError('Listed orbit file disappeared; retry discovery')
    eof_name = name.removesuffix('.zip')
    if name.endswith('.zip'):
        with zipfile.ZipFile(BytesIO(data)) as archive:
            members = archive.infolist()
            # ESA archives may include a second copy under var/www/auxdata/...
            # Read bytes only; never extract those paths into the local filesystem.
            if not 1 <= len(members) <= 4 or any(
                    Path(member.filename).name != eof_name or member.file_size > MAX_BYTES
                    for member in members):
                raise ValueError('Unexpected orbit ZIP contents')
            data = archive.read(members[0])  # CRC checked; never extract archive paths.
            if any(archive.read(member) != data for member in members[1:]):
                raise ValueError('Conflicting copies in orbit ZIP')
    validate_eof(data, eof_name, mission, start, end)
    folder.mkdir(parents = True, exist_ok = True)
    destination = folder / eof_name
    if destination.exists():
        raise FileExistsError(f'Existing orbit failed validation; review rather than overwrite: {destination}')
    with tempfile.NamedTemporaryFile(dir = folder, suffix = '.partial', delete = False) as handle:
        temporary = Path(handle.name)
        handle.write(data)
    try:
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    write_json(destination.with_suffix('.download.json'), {'source_url'                : url,
                                                           'sha256'                    : sha256(destination),
                                                           'orbit_type'                : 'AUX_POEORB',
                                                           'spacecraft'                : mission,
                                                           'validity_start'            : orbit_name(eof_name)[2].isoformat(),
                                                           'validity_stop'             : orbit_name(eof_name)[3].isoformat(),
                                                           'prepared_at'               : datetime.now(timezone.utc).isoformat(),
                                                           'margin_seconds'            : 60,
                                                           'snap_processing_validated' : False})
    return destination

def prepare_pair_orbits(pair, cache_root=None, check_only=False):
    with requests.Session() as session:
        return [prepare_scene_orbit(pair[key], cache_root, check_only, session) for key in ('first', 'second')]
