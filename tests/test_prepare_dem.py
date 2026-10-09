"""DEM tests use small synthetic rasters; no network or station datasets."""
from pathlib import Path
import sys
from types import SimpleNamespace
import json
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box, mapping

scripts = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(scripts))
from dem_utils import combine, grid
from prepare_dem import prepare
import prepare_dem


def test_ocean_replacement_and_land_gap_failure():
    land = np.array([[True, False]])
    terrain = np.ma.array([[123., 800.]], mask=False)
    sea = np.ma.array([[18., 19.]], mask=False)
    assert combine(terrain, sea, land).tolist() == [[123., 19.]]
    terrain.mask = [[True, False]]
    with pytest.raises(ValueError, match='missing land/shelf'):
        combine(terrain, sea, land)
    terrain.mask = False
    sea.mask = [[False, True]]
    with pytest.raises(ValueError, match='Geoid'):
        combine(terrain, sea, land)


def test_bounds_and_spacing():
    target = grid([0, 0, 2, 1], [0.3, 0.3])
    assert (target['width'], target['height']) == (7, 4)
    with pytest.raises(ValueError):
        grid([0, 0, 2, 1], [0, 1])


def test_prepare_raster_and_provenance(tmp_path, monkeypatch):
    config = tmp_path / 'test.yaml'
    coast = tmp_path / 'coast.geojson'
    config.write_text('test configuration')
    coast.write_text('{}')
    source, geoid, output = [tmp_path / name for name in ('source.tif', 'geoid.tif', 'prepared.tif')]
    for path, value in [(source, 100), (geoid, 18)]:
        with rasterio.open(path, 'w', driver='GTiff', width=20, height=20,
                           count=1, dtype='float32', crs='EPSG:4326',
                           transform=from_origin(0, 2, .1, .1), nodata=-9999) as dst:
            dst.write(np.full((20, 20), value, dtype='float32'), 1)
            if path == geoid:
                dst.set_band_description(1, 'geoid_undulation')
                dst.update_tags(target_crs_epsg_code='5773')
    spec = SimpleNamespace(coastline=coast, run=SimpleNamespace(region=SimpleNamespace(bbox=[.2, .2, 1.8, 1.8])))
    monkeypatch.setattr(prepare_dem, 'exclusions', lambda _: (spec, [(mapping(box(.2, .2, .8, 1.8)), 1)]))
    prepare(source, geoid, config, output, [.1, .1], [0, 0, 2, 2])
    with rasterio.open(output) as src:
        values = src.read(1, masked=True)
        assert not np.ma.getmaskarray(values).any()
        assert set(np.unique(values.data)) == {18., 100.}
        assert src.tags()['vertical_datum'] == 'WGS84 ellipsoid'
    report = json.loads(output.with_suffix('.provenance.json').read_text())
    assert report['snap_validated'] is False
    assert report['counts']['ocean_pixels'] > 0
    with pytest.raises(FileExistsError):
        prepare(source, geoid, config, output, [.1, .1], [0, 0, 2, 2])
    failed = tmp_path / 'failed.tif'
    with rasterio.open(source, 'r+') as src:
        src.write(np.full((20, 20), -9999, dtype='float32'), 1)
    with pytest.raises(ValueError, match='missing land/shelf'):
        prepare(source, geoid, config, failed, [.1, .1], [0, 0, 2, 2])
    assert not failed.exists()
    assert not failed.with_suffix('.provenance.json').exists()


def test_verifier_cli_reports_ocean_gaps(tmp_path):
    import subprocess
    source = tmp_path / 'source.tif'
    coast = tmp_path / 'coast.geojson'
    config = tmp_path / 'config.yaml'
    report = tmp_path / 'report.json'
    coast.write_text(json.dumps({'type': 'FeatureCollection', 'features': [
        {'type': 'Feature', 'properties': {'surface': 'land'},
         'geometry': mapping(box(0, 0, .8, 2))}]}))
    config.write_text('run:\n  region:\n    name: Test\n    bbox: [0.2, 0.2, 1.8, 1.8]\ncoastline: coast.geojson\n')
    data = np.full((20, 20), 100, dtype='float32')
    data[:, 10:] = -9999
    with rasterio.open(source, 'w', driver='GTiff', width=20, height=20,
                       count=1, dtype='float32', crs='EPSG:4326',
                       transform=from_origin(0, 2, .1, .1), nodata=-9999) as dst:
        dst.write(data, 1)
    subprocess.run([sys.executable, str(scripts / 'verify_dem.py'),
                    '--config', str(config), '--source', str(source),
                    '--samples', '16', '--report', str(report)], check=True, capture_output=True)
    result = json.loads(report.read_text())
    assert result['coverage']['ADD land/shelf']['missing'] == 0
    assert result['coverage']['Ocean outside ADD']['missing'] > 0
