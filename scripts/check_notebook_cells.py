"""Validate offline notebook cells without a Jupyter socket/kernel.
This checks shared-namespace Python execution, not Jupyter UI/kernel integration.
"""
from pathlib import Path
import io,contextlib,traceback,json
import nbformat
import matplotlib
matplotlib.use('Agg')
root=Path(__file__).resolve().parents[1]
import os
os.chdir(root)
notebook=nbformat.read(root/'notebooks/primary_components.ipynb',as_version=4)
nbformat.validate(notebook)
namespace={'__name__':'__main__'};results=[]
for index,cell in enumerate(notebook.cells):
    if cell.cell_type!='code':continue
    capture=io.StringIO()
    with contextlib.redirect_stdout(capture),contextlib.redirect_stderr(capture):
        exec(compile(cell.source,f'notebook-cell-{index}','exec'),namespace)
    results.append({'cell_index':index,'status':'passed','stdout':capture.getvalue()})
(root/'reports/notebook_cells.json').write_text(json.dumps({'execution_method':'sequential shared-namespace Python; Jupyter kernel sockets unavailable','cells':results},indent=2))
print(f'{len(results)} offline notebook code cells passed')
