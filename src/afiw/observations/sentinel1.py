"""Public ASF discovery; authenticated downloads run only when requested locally."""
import logging
from afiw.core.logging import logged_step

from dataclasses import dataclass
from datetime import datetime,timezone
from pathlib import Path
import json,os,zipfile
import netrc
from itertools import combinations
from shapely.geometry import shape,box
from shapely.ops import transform
from pyproj import Transformer
from afiw.core.provenance import write_json

logger = logging.getLogger(__name__)

def utc(value):
    t = datetime.fromisoformat(value.replace('Z','+00:00'))
    return t.replace(tzinfo=timezone.utc) if t.tzinfo is None else t.astimezone(timezone.utc)

@logged_step
def compatible_pairs(catalog,run,acquisition):
    import hashlib
    features = catalog.get('features',[])
    tr       = Transformer.from_crs(4326,3031, always_xy = True)
    aoi      = transform(tr.transform, box(*run.region.bbox))
    pairs    = []
    for f, g in combinations(features, 2):
        p, q = f['properties'], g['properties']
        if utc(p['startTime']) > utc(q['startTime']):
            f, g = g, f
            p, q = q, p
        days = (utc(q['startTime']) - utc(p['startTime'])).total_seconds() / 86400
        if not acquisition.min_pair_days <= days <= acquisition.max_pair_days:
            continue
        # pathNumber is ASF's Sentinel-1 relative orbit, NOT absolute orbit.
        keys = ['pathNumber', 'flightDirection', 'beamModeType', 'polarization']
        if any(p.get(k) is None or q.get(k) is None or p[k] != q[k] for k in keys):
            continue
        if acquisition.polarization not in p['polarization'].split('+'):
            continue
        fp = transform(tr.transform,shape(f['geometry']))
        gp = transform(tr.transform,shape(g['geometry']))
        if not fp.is_valid or not gp.is_valid:
            continue
        overlap = fp.intersection(gp).intersection(aoi).area / aoi.area
        if overlap<acquisition.min_aoi_overlap:
            continue
        # IDs include times, orbit and a stable scene suffix: same-date pairs never collide.
        fid    = p.get('fileID',p['fileName'])
        gid     = q.get('fileID',q['fileName'])
        digest  = hashlib.sha256(f'{fid}|{gid}'.encode()).hexdigest()[:8]
        pair_id = f"{utc(p['startTime']):%Y%m%dT%H%M%S}_{utc(q['startTime']):%Y%m%dT%H%M%S}_{digest}"
        pairs.append({'pair_id'             : pair_id,
                      'first'               : f,
                      'second'              : g,
                      'baseline_days'       : days,
                      'common_aoi_fraction' : overlap})
    logger.info('Pairing: %s scenes -> %s compatible pairs; baseline=%s..%s days; min overlap=%s', len(features), len(pairs), acquisition.min_pair_days, acquisition.max_pair_days, acquisition.min_aoi_overlap)
    return sorted(pairs, key = lambda p:(p['second']['properties']['startTime'], p['baseline_days']))

def earthdata_session(token_env = 'EARTHDATA_TOKEN'):
    """Authenticate locally: explicit token first, otherwise Earthdata .netrc entry."""
    import asf_search as asf
    token = os.environ.get(token_env)
    if token:
        try:
            return asf.ASFSession().auth_with_token(token)
        except Exception:
            raise RuntimeError(f'Earthdata token authentication failed; review {token_env} locally') from None
    try:
        # Default netrc() enforces private ownership/permissions on POSIX.
        credentials = netrc.netrc().hosts.get('urs.earthdata.nasa.gov')
    except (OSError, netrc.NetrcParseError):
        # Parser errors can include file contents; never expose the original exception.
        raise RuntimeError('Cannot read ~/.netrc; check its syntax and run chmod 600 ~/.netrc, or set an Earthdata token locally') from None
    if not credentials or not credentials[0] or not credentials[2]:
        raise RuntimeError(f'Provide the urs.earthdata.nasa.gov entry in ~/.netrc or set {token_env} locally')
    try:
        return asf.ASFSession().auth_with_creds(credentials[0], credentials[2])
    except Exception:
        raise RuntimeError('Earthdata .netrc authentication failed; check the Earthdata login/password and ASF application authorization locally') from None


@dataclass
class Sentinel1Client:
    run_cfg         : object
    acquisition_cfg : object
    paths           : object

    @logged_step
    def search(self):
        import asf_search as asf
        logger.info('ASF search: region=%s bbox=%s dates=%s..%s', self.run_cfg.region.name, self.run_cfg.region.bbox, self.run_cfg.start_date, self.run_cfg.end_date)
        cfg=self.acquisition_cfg
        results = asf.geo_search(platform        = asf.PLATFORM.SENTINEL1,
                                 intersectsWith  = box(*self.run_cfg.region.bbox).wkt,
                                 start           = self.run_cfg.start_date,
                                 end             = self.run_cfg.end_date+'T23:59:59Z',
                                 beamMode        = list(cfg.beam_modes),
                                 processingLevel = list(cfg.processing_levels),
                                 maxResults      = cfg.max_results)
        catalog         = results.geojson()
        catalog['afiw'] = {'region'             : self.run_cfg.region.name,
                           'bbox'               : self.run_cfg.region.bbox,
                           'query_start'        : self.run_cfg.start_date,
                           'query_end'          : self.run_cfg.end_date,
                           'possibly_truncated' : len(results)>=cfg.max_results}
        self.paths.ensure()
        write_json(self.paths.catalog / 'scenes.geojson', catalog)
        write_json(self.paths.catalog / 'pairs.json', compatible_pairs(catalog,self.run_cfg, cfg))
        logger.info('ASF search returned %s scenes; catalog directory: %s; possibly truncated=%s', len(results), self.paths.catalog, catalog['afiw']['possibly_truncated'])
        return catalog

    @logged_step
    def download_pair(self, pair, token_env = 'EARTHDATA_TOKEN'):
        import asf_search as asf
        session = None
        out     = []
        for f in [pair['first'], pair['second']]:
            p    = f['properties']
            name = Path(p['url'].split('?')[0]).name
            if not name.endswith('.zip') or '/' in name:
                raise ValueError('Expected an ASF SAFE ZIP URL')
            dst = self.paths.downloads/name
            if dst.exists() and valid_safe_zip(dst):
                logger.info('Reusing validated SAFE ZIP: %s', dst)
                out.append(dst)
                continue
            if session is None:
                session = earthdata_session(token_env)
            staging = self.paths.downloads / '.partial'
            staging.mkdir(parents = True, exist_ok = True)
            logger.info('Downloading SAFE ZIP: %s -> %s', name, staging)
            asf.download_urls([p['url']], path = str(staging), session = session)
            src = staging/name
            if not valid_safe_zip(src):
                raise RuntimeError('Incomplete or invalid SAFE ZIP; retained in .partial')
            src.replace(dst)
            logger.info('Validated SAFE ZIP: %s (%s bytes)', dst, dst.stat().st_size)
            out.append(dst)
        return out

def valid_safe_zip(path):
    try:
        with zipfile.ZipFile(path) as z:
            return any(n.endswith('/manifest.safe') for n in z.namelist())
    except (OSError,zipfile.BadZipFile):
        return False
