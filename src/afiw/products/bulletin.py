"""Independent publication workflow consuming immutable pair manifests."""
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime,date,timedelta
import json,shutil,subprocess
import numpy as np
import rasterio
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor,red,white
from reportlab.lib.utils import ImageReader
from reportlab.lib.pagesizes import A4
from afiw.core.provenance import write_json
from afiw.metrics.change import change_metrics,cell_areas_km2
from afiw.observations.sentinel1 import utc


def escape_latex(text):
    table={'\\':r'\textbackslash{}','&':r'\&','%':r'\%','$':r'\$','#':r'\#','_':r'\_','{':r'\{','}':r'\}','~':r'\textasciitilde{}','^':r'\textasciicircum{}'}
    return ''.join(table.get(c,c) for c in str(text))

def available_manifests(root,region,as_of):
    cutoff=utc(as_of+'T23:59:59Z');items=[]
    for path in Path(root).rglob('manifest.json'):
        d=json.loads(path.read_text())
        if d.get('region')==region and utc(d['second_time'])<=cutoff:items.append((path,d))
    items.sort(key=lambda item:(item[1]['second_time'],item[1]['first_time'],item[1].get('created_utc','')))
    return items

def summary_text(current,previous=None):
    d=current
    if d['synthetic']:return 'SYNTHETIC TEST DATA. This bulletin tests the software and layout; it describes no observed Davis conditions.'
    dates=f"Observations {d['first_time'][:10]} to {d['second_time'][:10]} ({d['baseline_days']:.1f}-day baseline)."
    if d['status']=='segmentation_only':return dates+' Texture segmentation is available; fast-ice extent, change and persistence cannot yet be reported because no trained classification was applied.'
    area=d['metrics']['candidate_fast_ice_km2'];return dates+f' Candidate fast-ice coverage: {area:.1f} km² within the observed ocean domain. This is an unvalidated research classification.'

def same_grid(a,b):return (a.crs,a.transform,a.shape)==(b.crs,b.transform,b.shape)

@dataclass
class BulletinBuilder:
    root: str | Path
    region: str='Davis'
    max_age_days: int=14
    def build(self,as_of,output,compile_latex=False):
        date.fromisoformat(as_of);out=Path(output);out.mkdir(parents=True,exist_ok=True)
        records=available_manifests(self.root,self.region,as_of)
        if not records:raise FileNotFoundError('No processed pair available by bulletin date')
        path,current=records[-1]
        # Never blend real and synthetic results in one historical comparison.
        previous=next(((p,d) for p,d in reversed(records[:-1]) if d['synthetic']==current['synthetic'] and d['status']==current['status']),None)
        text=summary_text(current);metrics={};change_path=None
        age=(date.fromisoformat(as_of)-utc(current['second_time']).date()).days
        if age>self.max_age_days:text+=f' Latest observation is {age} days old; no current-conditions assessment is available.'
        if current['status']=='candidate_classification' and previous:
            pp,pd=previous
            # Different model/mask or algorithm settings cannot produce a defensible change claim.
            compatible=all(pd['config'].get(k)==current['config'].get(k) for k in ['processing','segmentation','classifier','coastline']) and pd.get('resource_hashes')==current.get('resource_hashes') and pd.get('implementation_hash')==current.get('implementation_hash')
            if compatible:
                with rasterio.open(pp.parent/pd['outputs']['classification']) as a,rasterio.open(path.parent/current['outputs']['classification']) as b:
                    if same_grid(a,b):
                        change,metrics=change_metrics(a.read(1),b.read(1),cell_areas_km2(b.shape,b.transform,b.crs))
                        change_path=out/'change.tif';profile=b.profile.copy()
                        with rasterio.open(change_path,'w',**profile) as dst:dst.write(change,1)
                        if metrics['common_ocean_km2']>0:text+=f" On common observed coverage: gain {metrics['gain_km2']:.1f} km², loss {metrics['loss_km2']:.1f} km² since {pd['second_time'][:10]}."
            if not metrics:text+=' No comparable prior classification is available for change assessment.'
        image=out/'primary.png';shutil.copy(path.parent/current['outputs']['quicklook'],image)
        quality=f"Segmentation pixel spacing: {current['segmentation_pixel_size_m'][0]:.0f} × {current['segmentation_pixel_size_m'][1]:.0f} m; valid texture fraction {100*current['valid_texture_fraction']:.1f}%. Acquisition baseline: {current['baseline_days']:.1f} days."
        limits='Land/ice-shelf mask supplied.' if current['mask_provided'] else 'No reviewed land/ice-shelf mask supplied. Segmentation includes unmasked surfaces.'
        limits+=' '+ ' '.join(current['limitations'])
        tex=self._latex(as_of,text,quality,limits);(out/'main.tex').write_text(tex)
        self._pdf(out/'bulletin.pdf',as_of,text,quality,limits,image)
        if compile_latex:
            if not shutil.which('pdflatex'):raise FileNotFoundError('Install TeX Live or MacTeX, or use the generated PDF directly')
            subprocess.run(['pdflatex','-interaction=nonstopmode','-halt-on-error','main.tex'],cwd=out,check=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        write_json(out/'bulletin.json',{'region':self.region,'issue_date':as_of,'source_manifest':str(path),'previous_manifest':str(previous[0]) if previous else None,'synthetic':current['synthetic'],'observation_age_days':age,'summary':text,'quality':quality,'limitations':limits,'change_metrics':metrics,'change_raster':str(change_path) if change_path else None,'swot_status':'not implemented in primary-product milestone'})
        return out/'bulletin.pdf'
    def _latex(self,as_of,text,quality,limits):
        e=escape_latex
        return r'''\documentclass[10pt,a4paper]{article}
\usepackage[margin=16mm]{geometry}
\usepackage[T1]{fontenc}
\usepackage{helvet,graphicx,xcolor}
\renewcommand{\familydefault}{\sfdefault}
\pagestyle{empty}
\newcommand{\classification}{RESEARCH DEMONSTRATION | NOT FOR OPERATIONAL USE}
\begin{document}
\begin{center}\color{red}\small\textbf{\classification}\end{center}
{\LARGE\textbf{Antarctic Fast Ice Watch}}\par
\medskip
'''+e(self.region)+' | '+e(as_of)+r'''\par
\medskip
\textbf{PRIMARY PRODUCT | FAST-ICE EXTENT AND CHANGE}\par
\medskip
'''+e(text)+r'''\par
\begin{center}\includegraphics[width=\linewidth,height=95mm,keepaspectratio]{primary.png}\end{center}
\textbf{Coverage and quality}\par
'''+e(quality)+r'''\par
\medskip
'''+e(limits)+r'''\par
\medskip
\textbf{ADDITIONAL PRODUCT | SWOT FREEBOARD}\par
Not yet processed in this primary-product milestone. No SWOT observations or freeboard values are represented here.\par
\vfill
\begin{center}\color{red}\small\textbf{\classification}\end{center}
\end{document}
'''
    def _pdf(self,path,as_of,text,quality,limits,image):
        from reportlab.platypus import Paragraph
        from reportlab.lib.styles import ParagraphStyle
        from xml.sax.saxutils import escape
        c=canvas.Canvas(str(path),pagesize=A4);w,h=A4
        c.setFillColor(HexColor('#123347'));c.rect(0,h-110,w,110,fill=1,stroke=0)
        c.setFillColor(red);c.setFont('Helvetica-Bold',8);c.drawCentredString(w/2,h-15,'RESEARCH DEMONSTRATION | NOT FOR OPERATIONAL USE')
        c.setFillColor(white);c.setFont('Helvetica-Bold',24);c.drawString(36,h-58,'Antarctic Fast Ice Watch')
        c.setFont('Helvetica',11);c.drawString(36,h-82,f'{self.region} | {as_of}')
        style=ParagraphStyle('body',fontName='Helvetica',fontSize=10,leading=14,textColor=HexColor('#475866'))
        def para(t,y):
            p=Paragraph(escape(t),style);ww,hh=p.wrap(w-72,400);p.drawOn(c,36,y-hh);return y-hh-12
        c.setFillColor(HexColor('#167D8D'));c.setFont('Helvetica-Bold',10);c.drawString(36,h-145,'PRIMARY PRODUCT | FAST-ICE EXTENT AND CHANGE')
        y=para(text,h-163)
        iw,ih=ImageReader(str(image)).getSize();dw=w-72;dh=min(310,dw*ih/iw);dw=dh*iw/ih
        c.drawImage(str(image),(w-dw)/2,y-dh,width=dw,height=dh);y-=dh+20
        y=para(quality,y);y=para(limits,y)
        c.setFillColor(HexColor('#167D8D'));c.setFont('Helvetica-Bold',10);c.drawString(36,y-4,'ADDITIONAL PRODUCT | SWOT FREEBOARD');y-=24
        y=para('Not yet processed in this primary-product milestone. No SWOT observations or freeboard values are represented here.',y)
        if y<55:raise ValueError('Bulletin text exceeds one-page layout; shorten text or reduce the figure')
        c.setFillColor(red);c.setFont('Helvetica-Bold',8);c.drawCentredString(w/2,28,'RESEARCH DEMONSTRATION | NOT FOR OPERATIONAL USE');c.save()
    def season(self,start_year,output,start_month=9,end_month=4):
        # Weekly issue selection is independent of acquisition/processing cadence.
        when=date(start_year,start_month,1);end=date(start_year+1,end_month,1)
        import calendar
        end=end.replace(day=calendar.monthrange(end.year,end.month)[1]);outputs=[]
        while when<=end:
            try:outputs.append(self.build(when.isoformat(),Path(output)/when.isoformat()))
            except FileNotFoundError:pass
            when+=timedelta(days=7)
        return outputs
