from pathlib import Path
import shutil,subprocess

def generate_research_example(template_directory,output,compile_pdf=True):
    """Reproduce the supplied McMurdo+SWOT illustrative PDF (not a Davis result)."""
    source=Path(template_directory);output=Path(output)
    if source.resolve()==output.resolve():raise ValueError('Choose a different output directory')
    shutil.copytree(source,output,dirs_exist_ok=True)
    if compile_pdf:
        if not shutil.which('pdflatex'):raise FileNotFoundError('Install MacTeX/TeX Live or select --no-compile')
        for _ in range(2):subprocess.run(['pdflatex','-interaction=batchmode','-halt-on-error','main.tex'],cwd=output,check=True)
    return output/'main.pdf'
