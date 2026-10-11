"""Area-weighted outline assessment on an explicitly reviewed evaluation domain."""
from pathlib import Path
import logging
import re
import numpy as np
import rasterio
from afiw.core.logging import logged_workflow
from afiw.core.provenance import sha256, write_json, runtime
from afiw.metrics.change import cell_areas_km2
from afiw.processing.raster import exclusion_mask
from .maps import inputs_from_manifest

logger = logging.getLogger(__name__)


def reviewed_polygons(path, target_crs, dates = None):
    import geopandas as gpd
    from shapely.geometry import mapping
    path = Path(path).resolve()
    if dates:
        expected = [date.replace('-','') for date in dates]
        for name in (path.stem, path.parent.name):
            declared = re.search(r'(\d{8})_(\d{8})', name)
            if declared and list(declared.groups()) != expected:
                raise ValueError(f'Reference filename/directory dates conflict with declared observation dates: {name}')
    polygons = gpd.read_file(path)
    if polygons.crs is None or polygons.empty:
        raise ValueError('Reference/domain polygons require a CRS and nonempty geometries')
    if polygons.geometry.isna().any() or polygons.geometry.is_empty.any() or not polygons.is_valid.all():
        raise ValueError('Invalid reference/domain geometry; review and repair externally with recorded provenance')
    if not polygons.geom_type.isin(['Polygon', 'MultiPolygon']).all():
        raise ValueError('Assessment requires polygon outlines, not coastline lines')
    return [(mapping(geometry), 1) for geometry in polygons.to_crs(target_crs).geometry]


def vector_hashes(path):
    path = Path(path).resolve()
    paths = [path]
    if path.suffix.lower() == '.shp':
        paths = [path.with_suffix(suffix) for suffix in ('.shp','.shx','.dbf','.prj','.cpg') if path.with_suffix(suffix).exists()]
    return {p.name : sha256(p) for p in paths}


@logged_workflow
def validate_outline(manifest, reference, domain, output, first_date, second_date, label_source):
    manifest, record, _, _, validity, grid = inputs_from_manifest(manifest)
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError('Choose a new validation-report filename')
    dates = [first_date, second_date]
    if dates != [record['first_time'][:10], record['second_time'][:10]]:
        raise ValueError('Reference observation dates must exactly match the classified pair')
    if not str(label_source).strip():
        raise ValueError('Document reviewer, reference interpretation, and independence from training')
    classification = record['outputs'].get('classification')
    if not classification:
        raise ValueError('Outline assessment requires a classification raster')
    with rasterio.open(manifest.parent / classification) as src:
        if (src.crs, src.transform, src.shape) != (grid['crs'],grid['transform'],validity.shape):
            raise ValueError('Classification grid differs from persisted analytical inputs')
        classes = src.read(1)
    if not np.isin(classes, [0,1,2,3,255]).all():
        raise ValueError('Unexpected classification codes')
    reference_mask = exclusion_mask(reviewed_polygons(reference, grid['crs'], dates), grid)
    domain_mask    = exclusion_mask(reviewed_polygons(domain, grid['crs']), grid)
    if not domain_mask.any():
        raise ValueError('Reviewed evaluation domain does not overlap the product grid')
    ocean   = domain_mask & (validity != 2) & (classes != 1)
    assessed = ocean & (validity == 1) & np.isin(classes, [0,2,3])
    areas    = cell_areas_km2(classes.shape, grid['transform'], grid['crs'])
    if not assessed.any():
        raise ValueError('No classified observed ocean cells in the evaluation domain')
    predicted = np.isin(classes, [2,3])
    tp = float(areas[assessed & predicted & reference_mask].sum())
    fp = float(areas[assessed & predicted & ~reference_mask].sum())
    fn = float(areas[assessed & ~predicted & reference_mask].sum())
    tn = float(areas[assessed & ~predicted & ~reference_mask].sum())
    ratio = lambda numerator, denominator: numerator / denominator if denominator else None
    report = {**runtime(), 'manifest' : str(manifest), 'manifest_sha256' : sha256(manifest),
              'reference_sha256' : vector_hashes(reference), 'domain_sha256' : vector_hashes(domain),
              'reference_dates' : dates, 'label_source' : label_source,
              'interpretation' : 'Binary fast ice: predicted classes 2+3 versus reviewed outline; outside outline is reference ocean only within the explicit evaluation domain.',
              'area_km2' : {'true_positive' : tp, 'false_positive' : fp, 'false_negative' : fn, 'true_negative' : tn,
                            'evaluation_ocean' : float(areas[ocean].sum()),
                            'unassessed_ocean' : float(areas[ocean & ~assessed].sum())},
              'precision' : ratio(tp, tp+fp), 'recall' : ratio(tp, tp+fn), 'iou' : ratio(tp,tp+fp+fn),
              'model_validation_updated' : False,
              'limitations' : ['Reference completeness and independence require scientific review.',
                               'Missing/unassigned cells are reported as unassessed, not counted as ocean.',
                               'Binary outline assessment does not validate melting-fast-ice class 3 separately.']}
    logger.info('Outline assessment: areas=%s precision=%s recall=%s IoU=%s', report['area_km2'], report['precision'], report['recall'], report['iou'])
    output.parent.mkdir(parents = True, exist_ok = True)
    return write_json(output, report)
