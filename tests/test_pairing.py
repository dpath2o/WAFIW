from copy import deepcopy
from shapely.geometry import box,mapping
from afiw.observations.sentinel1 import compatible_pairs
from afiw.core.types import RunSpec,AcquisitionSpec

def scene(time,orbit=10,pol='HH+HV',bounds=(75,-70,81,-67)):
    return {'type':'Feature','geometry':mapping(box(*bounds)),'properties':{'startTime':time,'pathNumber':orbit,'beamModeType':'EW','flightDirection':'ASCENDING','polarization':pol,'fileName':time.replace(':',''),'fileID':time}}

def test_pairs_require_geometry_orbit_polarization_and_days():
    a=scene('2021-10-01T00:00:00Z');b=scene('2021-10-13T00:00:00Z');cfg=AcquisitionSpec();run=RunSpec()
    assert len(compatible_pairs({'features':[a,b]},run,cfg))==1
    for bad in [scene('2021-10-13T00:00:00Z',orbit=11),scene('2021-10-13T00:00:00Z',pol='VV+VH'),scene('2021-10-02T00:00:00Z'),scene('2021-10-13T00:00:00Z',bounds=(20,-72,25,-70))]:
        assert not compatible_pairs({'features':[a,bad]},run,cfg)
    missing=deepcopy(b);del missing['properties']['pathNumber'];assert not compatible_pairs({'features':[a,missing]},run,cfg)
