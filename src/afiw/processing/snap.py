"""Optional laptop SNAP GPT adapter. Raw-SAFE integration requires local validation.
The output is terrain-flattened gamma0 dB, not simple sigma0 calibration.
"""
import logging
from afiw.core.logging import logged_step, logged_workflow, monitor_process_log

from dataclasses import dataclass
from pathlib import Path
import shutil,subprocess
import xml.etree.ElementTree as ET
from shapely.geometry import box
from afiw.core.provenance import write_json,runtime,sha256

logger = logging.getLogger(__name__)

@dataclass
class SnapPreprocessor:
    spec: object
    processing: object
    region: object
    polarization: str='HH'
    @logged_step
    def graph(self,source,output):
        if not self.spec.dem_path or not Path(self.spec.dem_path).is_file():raise FileNotFoundError('Supply a reviewed Antarctic DEM in snap.dem_path (WGS84 geographic, metres, documented vertical datum and matching ocean elevations; see docs/dem_preparation.md)')
        graph=ET.Element('graph',id='AFIW_S1_gamma0');ET.SubElement(graph,'version').text='1.0'
        def node(name,op,previous,params):
            n=ET.SubElement(graph,'node',id=name);ET.SubElement(n,'operator').text=op
            sources=ET.SubElement(n,'sources')
            if previous:ET.SubElement(sources,'sourceProduct',refid=previous)
            p=ET.SubElement(n,'parameters',{'class':'com.bc.ceres.binding.dom.XppDomElement'})
            for k,v in params.items():ET.SubElement(p,k).text=str(v).lower() if isinstance(v,bool) else str(v)
        dem={'demName':'External DEM','externalDEMFile':str(Path(self.spec.dem_path).resolve()),'externalDEMNoDataValue':self.spec.dem_nodata,'externalDEMApplyEGM':self.spec.dem_apply_egm}
        node('Read','Read',None,{'file':str(Path(source).resolve())})
        node('Orbit','Apply-Orbit-File','Read',{'orbitType':'Sentinel Precise (Auto Download)','polyDegree':3,'continueOnFail':False})
        node('Border','Remove-GRD-Border-Noise','Orbit',{'selectedPolarisations':self.polarization})
        node('Noise','ThermalNoiseRemoval','Border',{'selectedPolarisations':self.polarization,'removeThermalNoise':True})
        node('Subset','Subset','Noise',{'geoRegion':box(*self.region.bbox).wkt,'copyMetadata':True})
        node('Calibrate','Calibration','Subset',{'selectedPolarisations':self.polarization,'outputBetaBand':True,'outputSigmaBand':False,'outputImageScaleInDb':False})
        node('Flatten','Terrain-Flattening','Calibrate',{**dem,'sourceBands':f'Beta0_{self.polarization}','outputSigma0':False})
        node('Geocode','Terrain-Correction','Flatten',{**dem,'sourceBands':f'Gamma0_{self.polarization}','pixelSpacingInMeter':self.processing.resolution_m,'mapProjection':self.processing.crs,'nodataValueAtSea':False,'saveSelectedSourceBand':True,'applyRadiometricNormalization':False,'alignToStandardGrid':True,'standardGridOriginX':0,'standardGridOriginY':0})
        node('Decibels','LinearToFromdB','Geocode',{'sourceBands':f'Gamma0_{self.polarization}'})
        node('Write','Write','Decibels',{'file':str(Path(output).resolve()),'formatName':'GeoTIFF-BigTIFF'})
        return ET.tostring(graph,encoding='unicode')
    @logged_workflow
    def run(self,source,output,dry_run=False):
        output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
        graph_path=output.with_suffix('.snap.xml');graph_path.write_text(self.graph(source,output))
        exe=shutil.which(self.spec.executable) or (str(Path(self.spec.executable)) if Path(self.spec.executable).is_file() else None)
        if not exe and not dry_run:raise FileNotFoundError('SNAP gpt unavailable; configure its absolute path')
        command=[exe or self.spec.executable,str(graph_path),'-c',self.spec.memory,'-q',str(self.spec.threads)]
        logger.info('SNAP: source=%s output=%s graph=%s memory=%s threads=%s timeout=%ss', source, output, graph_path, self.spec.memory, self.spec.threads, self.spec.timeout_seconds)
        if dry_run:return command
        # No shell or platform-specific commands. Scene log preserves processing failures.
        log_path=output.with_suffix('.snap.log')
        logger.info('SNAP native stdout/stderr retained in %s', log_path)
        with log_path.open('w') as log, monitor_process_log(log_path, logger, 'SNAP'):
            try:
                subprocess.run(command,check=True,stdout=log,stderr=subprocess.STDOUT,timeout=self.spec.timeout_seconds)
            except subprocess.CalledProcessError as error:
                raise RuntimeError(f'SNAP failed with exit status {error.returncode}; inspect {log_path}. For missing orbit files, run scripts/prepare_orbits.py; see docs/snap_setup.md') from None
            finally:
                log.flush()
        if not output.is_file():raise RuntimeError('SNAP completed without expected GeoTIFF')
        write_json(output.with_suffix('.provenance.json'),{**runtime(),'source':str(source),'source_sha256':sha256(source),'graph':str(graph_path),'graph_sha256':sha256(graph_path),'radiometry':'gamma0_db','dem':self.spec.dem_path})
        return output
