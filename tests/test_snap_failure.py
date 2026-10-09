from dataclasses import replace
import subprocess
import pytest
from afiw.core.types import SnapSpec, ProcessingSpec, RegionSpec
from afiw.processing.snap import SnapPreprocessor


def test_failed_gpt_retains_log_and_reports_path(tmp_path, monkeypatch):
    dem = tmp_path / 'dem.tif'
    dem.touch()
    cfg = replace(SnapSpec(), dem_path=str(dem), executable='dummy-gpt')
    monkeypatch.setattr('afiw.processing.snap.shutil.which', lambda _: '/dummy/gpt')
    def fail(command, **kwargs):
        kwargs['stdout'].write('Error: [NodeId: Orbit] No valid orbit file found\n')
        raise subprocess.CalledProcessError(1, command)
    monkeypatch.setattr('afiw.processing.snap.subprocess.run', fail)
    output = tmp_path / 'scene.tif'
    with pytest.raises(RuntimeError, match='scene.snap.log'):
        SnapPreprocessor(cfg, ProcessingSpec(), RegionSpec()).run('scene.zip', output)
    assert 'No valid orbit' in output.with_suffix('.snap.log').read_text()
    assert not output.with_suffix('.provenance.json').exists()
