"""Regional clipping regression and resource/configuration safeguards."""
from pathlib import Path
import runpy

import pytest

gpd = pytest.importorskip("geopandas")
pytest.importorskip("pyogrio")
from shapely.geometry import Point, Polygon
import yaml

prepare = runpy.run_path(str(Path(__file__).parents[1] / 'scripts/prepare_coastline.py'))['prepare']


def config_file(tmp_path):
    path = tmp_path / 'configs' / 'custom.yaml'
    path.parent.mkdir()
    path.write_text(yaml.safe_dump(dict(
        run=dict(region=dict(name='Custom', bbox=[75.5, -69.2, 80.5, -67.3],
                             station_lon=77.9689, station_lat=-68.5762)),
        coastline=None)))
    return path


def test_pole_enclosing_polygon_is_clipped_before_reprojection(tmp_path):
    source = tmp_path / 'ADD.shp'
    # A valid continent-sized polygon enclosing the pole: the original failure
    # arose when such a polygon was converted to geographic coordinates first.
    gpd.GeoDataFrame({'surface': ['land']},
                     geometry=[Point(0, 0).buffer(3_000_000)],
                     crs='EPSG:3031').to_file(source)
    config = config_file(tmp_path)
    output = tmp_path / 'mask.geojson'
    prepare(source, config, output, update_config=True)
    result = gpd.read_file(output)
    assert result.geometry.is_valid.all()
    w, s, e, n = result.total_bounds
    assert 75.29 < w < e < 80.71
    assert -69.41 < s < n < -67.09
    assert set(result.surface) == {'land'}
    from afiw.core.types import WorkflowSpec
    assert WorkflowSpec.load(config).coastline == str(output)
    from afiw.processing.raster import load_exclusions
    assert len(load_exclusions(output, 'EPSG:3031')) == 1
    assert output.with_suffix('.provenance.json').exists()
    with pytest.raises(FileExistsError):
        prepare(source, config, output)


def test_invalid_source_is_not_silently_repaired(tmp_path):
    source = tmp_path / 'invalid.shp'
    centre = gpd.GeoSeries([Point(78, -68)], crs=4326).to_crs(3031).iloc[0]
    x, y = centre.x, centre.y
    polygon = Polygon([(x,y), (x+1000,y+1000), (x,y+1000), (x+1000,y), (x,y)])
    gpd.GeoDataFrame({'surface': ['land']}, geometry=[polygon], crs=3031).to_file(source)
    config = config_file(tmp_path)
    output = tmp_path / 'mask.geojson'
    with pytest.raises(ValueError, match='invalid source geometry'):
        prepare(source, config, output, update_config=True)
    assert not output.exists()
    assert yaml.safe_load(config.read_text())['coastline'] is None


def test_all_station_configs_load():
    from afiw.core.types import WorkflowSpec
    root = Path(__file__).parents[1]
    for name in ['davis', 'mawson', 'casey']:
        spec = WorkflowSpec.load(root / 'configs' / f'{name}.yaml')
        assert spec.run.region.name.lower() == name
        w, s, e, n = spec.run.region.bbox
        assert w < spec.run.region.station_lon < e
        assert s < spec.run.region.station_lat < n
        assert spec.snap.dem_path is None
