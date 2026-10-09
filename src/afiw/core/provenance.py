from pathlib import Path
import hashlib,json,platform
from datetime import datetime,timezone
import importlib.metadata

def sha256(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        while block:=f.read(1024*1024):h.update(block)
    return h.hexdigest()
def write_json(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.part');tmp.write_text(json.dumps(data,indent=2,default=str,allow_nan=False)+'\n');tmp.replace(path)
    return path

def runtime():
    versions={}
    for name in ['numpy','rasterio','scipy','scikit-image','scikit-learn','asf-search']:
        try:versions[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:pass
    return {'created_utc':datetime.now(timezone.utc).isoformat(),'python':platform.python_version(),'versions':versions}


def implementation_hash():
    package=Path(__file__).resolve().parents[1]
    records=[str(p.relative_to(package))+':'+sha256(p) for p in sorted(package.rglob('*.py'))]
    return hashlib.sha256('\n'.join(records).encode()).hexdigest()
