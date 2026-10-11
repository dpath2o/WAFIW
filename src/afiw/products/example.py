import logging
from afiw.core.logging import logged_workflow, monitor_process_log

from pathlib import Path
import shutil,subprocess

logger = logging.getLogger(__name__)

@logged_workflow
def generate_research_example(template_directory,output,compile_pdf=True):
    """Reproduce the supplied McMurdo+SWOT illustrative PDF (not a Davis result)."""
    source=Path(template_directory);output=Path(output)
    if source.resolve()==output.resolve():raise ValueError('Choose a different output directory')
    shutil.copytree(source,output,dirs_exist_ok=True)
    if compile_pdf:
        if not shutil.which('pdflatex'):raise FileNotFoundError('Install MacTeX/TeX Live or select --no-compile')
        with (output / 'latex.log').open('w') as log, monitor_process_log(output / 'latex.log', logger, 'LaTeX'):
            try:
                for _ in range(2):subprocess.run(['pdflatex','-interaction=nonstopmode','-halt-on-error','main.tex'],cwd=output,check=True,stdout=log,stderr=subprocess.STDOUT)
            finally:
                log.flush()
    return output/'main.pdf'
