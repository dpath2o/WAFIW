from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
import json
import yaml

@dataclass(frozen=True)
class RegionSpec:
    name: str = 'Davis'
    bbox: tuple[float,float,float,float] = (75.5,-69.2,80.5,-67.3) # W,S,E,N
    station_lon: float = 77.9689
    station_lat: float = -68.5762
    def __post_init__(self):
        w,s,e,n=self.bbox
        if not (-180 <= w < e <=180 and -90 <= s < n <=90): raise ValueError('Invalid W,S,E,N bbox')
        if not self.name.replace('-','').replace('_','').isalnum(): raise ValueError('Unsafe region name')

@dataclass(frozen=True)
class RunSpec:
    start_date: str = '2021-10-01'
    end_date: str = '2021-10-31'
    region: RegionSpec = field(default_factory=RegionSpec)
    def __post_init__(self):
        if datetime.fromisoformat(self.end_date) < datetime.fromisoformat(self.start_date): raise ValueError('End precedes start')

@dataclass(frozen=True)
class AcquisitionSpec:
    beam_modes: tuple[str,...] = ('EW',)
    processing_levels: tuple[str,...] = ('GRD_HD','GRD_MD','GRD_HS')
    polarization: str = 'HH'
    min_pair_days: float = 3
    max_pair_days: float = 24
    min_aoi_overlap: float = .25
    max_results: int = 1000
    def __post_init__(self):
        if not 0 < self.min_pair_days <= self.max_pair_days: raise ValueError('Invalid temporal baseline')
        if not 0 < self.min_aoi_overlap <= 1: raise ValueError('Invalid overlap fraction')
        if self.polarization not in ('HH','VV'): raise ValueError('Select co-polar HH or VV')

@dataclass(frozen=True)
class ProcessingSpec:
    crs: str = 'EPSG:3031'
    resolution_m: float = 40
    windows: tuple[int,...] = (11,21,33)
    tile_size: int = 512
    input_units: str = 'db'
    min_valid_fraction: float = .8
    def __post_init__(self):
        if len(self.windows)!=3 or any(w<3 or w%2==0 for w in self.windows): raise ValueError('Three odd windows >=3 required')
        if self.resolution_m<=0 or self.tile_size<32: raise ValueError('Invalid grid/tile size')
        if self.input_units not in ('db','linear_power'): raise ValueError('input_units must be db or linear_power')
        if not 0 < self.min_valid_fraction <= 1: raise ValueError('Invalid min_valid_fraction')

@dataclass(frozen=True)
class SegmentationSpec:
    backend: str = 'slic'
    downsample: int = 10
    n_segments: int = 1200
    compactness: float = 5
    checkpoint: str | None = None
    sam_model: str = 'vit_b'
    device: str = 'cpu'
    points_per_side: int = 32
    crop_n_layers: int = 0
    max_pixels: int = 4_000_000
    def __post_init__(self):
        if self.backend not in ('slic','sam'): raise ValueError('Unknown segmentation backend')
        if self.downsample<1 or self.n_segments<1 or self.max_pixels<1: raise ValueError('Invalid segmentation size')
        if self.device not in ('cpu','mps','cuda'): raise ValueError('Unsupported device')

@dataclass(frozen=True)
class SnapSpec:
    executable: str = 'gpt'
    dem_path: str | None = None
    dem_nodata: float = -9999
    dem_apply_egm: bool = False
    memory: str = '4G'
    threads: int = 2
    timeout_seconds: int = 7200

@dataclass(frozen=True)
class WorkflowSpec:
    run: RunSpec = field(default_factory=RunSpec)
    acquisition: AcquisitionSpec = field(default_factory=AcquisitionSpec)
    processing: ProcessingSpec = field(default_factory=ProcessingSpec)
    segmentation: SegmentationSpec = field(default_factory=SegmentationSpec)
    snap: SnapSpec = field(default_factory=SnapSpec)
    root: str = './afiw_data'
    coastline: str | None = None
    classifier: str | None = None
    @classmethod
    def load(cls, path):
        path=Path(path).resolve(); d=yaml.safe_load(path.read_text()) or {}
        unknown=set(d)-{'run','acquisition','processing','segmentation','snap','root','coastline','classifier'}
        if unknown: raise ValueError(f'Unknown config keys: {sorted(unknown)}')
        d.setdefault('root','./afiw_data')
        run=d.pop('run',{}); region=RegionSpec(**run.pop('region',{})); run=RunSpec(region=region,**run)
        objects={'acquisition':AcquisitionSpec,'processing':ProcessingSpec,'segmentation':SegmentationSpec,'snap':SnapSpec}
        for k,c in objects.items(): d[k]=c(**d.get(k,{}))
        for k in ['root','coastline','classifier']:
            if d.get(k):
                p=Path(d[k]).expanduser(); d[k]=str((p if p.is_absolute() else path.parent/p).resolve())
        # Paths in nested specs are also relative to the configuration directory.
        from dataclasses import replace
        for key,attr in [('snap','dem_path'),('segmentation','checkpoint')]:
            value=getattr(d[key],attr)
            if value:
                p=Path(value).expanduser();d[key]=replace(d[key],**{attr:str((p if p.is_absolute() else path.parent/p).resolve())})
        return cls(run=run,**d)
    def as_dict(self): return asdict(self)

@dataclass(frozen=True)
class PairResult:
    directory: Path
    manifest: Path
    texture: Path
    segments: Path
    quicklook: Path
    classification: Path | None = None
