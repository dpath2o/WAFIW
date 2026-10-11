"""Build the consolidated notebook from public workflow APIs."""
from pathlib import Path
import nbformat as nbf

root = Path(__file__).resolve().parents[1]
notebook = nbf.v4.new_notebook()
cells = []

def markdown(text):
    cells.append(nbf.v4.new_markdown_cell(text))

def code(text):
    cells.append(nbf.v4.new_code_cell(text))

markdown('''# WAFIW primary workflow

This notebook calls the same public APIs as `afiw-primary`. The default run uses
explicitly synthetic inputs and produces no real ice assessment. Real training
and Davis production are opt-in cells with paths you must configure. Read
`docs/workflow.md` and `docs/research_review.md` before enabling them.''')
code('''from pathlib import Path
import json
from afiw import WorkflowSpec
from afiw.workflows.demo import run_demo
from afiw.classify.research import train_research
from afiw.workflows.maps import render_from_manifest
from afiw.products.bulletin import BulletinBuilder

PROJECT = Path.cwd().resolve()
if PROJECT.name == 'notebooks':
    PROJECT = PROJECT.parent
assert (PROJECT / 'configs/davis.yaml').is_file()
SPEC = WorkflowSpec.load(PROJECT / 'configs/davis.yaml')
WORK = PROJECT / 'notebook_output'
WORK.mkdir(exist_ok = True)
print('Configured station:', SPEC.run.region.name)
''')
markdown('''## Offline software check

Synthetic textures test processing, SLIC segmentation, georeferenced composite
export, PyGMT mapping and publication. Segment IDs are not physical ice labels;
this diagnostic therefore has no classification raster.''')
code('''result = run_demo(WORK / 'synthetic_demo')
record = json.loads(result.manifest.read_text())
assert record['synthetic'] and record['status'] == 'segmentation_only'
assert not record['classification_available']
assert result.composite_png.is_file() and result.composite_tif.is_file()
print(result.manifest)
''')
code('''pdf = BulletinBuilder(result.directory, 'Davis').build('2021-10-24', WORK / 'synthetic_bulletin')
assert pdf.is_file()
print(pdf)
''')
markdown('''## Train once from existing research labels

New station annotation is not a prerequisite. This imports the canonical ten
Prydz/Thwaites scenes, excludes the duplicate/conflicting additional scene and
SAM background, and assesses grouped/site holdouts. It creates an unvalidated
candidate SVM and a neighbouring training report. No LLM training is involved.
Use a new model filename for a new training run.''')
code('''RUN_RESEARCH_TRAINING = False
TRAINING_ROOT = Path('/path/to/SVM_trainingdata')
MODEL = PROJECT / 'afiw_data/models/fastice_HH_svm.npz'
if RUN_RESEARCH_TRAINING:
    model_path = train_research(TRAINING_ROOT, MODEL,
                               'Research segment annotations; reviewed source/history', polarization = 'HH')
    report = json.loads(model_path.with_suffix('.training.json').read_text())
    print(report['class_counts'])
    print(report['assessment'])
''')
markdown('''## Complete the persisted Davis pair

This cell applies the trusted research classifier to existing saved analytical
inputs, explicitly records candidate model transfer, exports both separate maps
and assembles a bulletin. The source remains untouched. The output directory
must be new/empty. The old Davis product uses SLIC, which differs from research
SAM; do not treat this candidate transfer as validated station performance.''')
code('''RUN_REAL_PRODUCTION = False
DAVIS_PAIR = '20211002T143959_20211014T143959_45c821c8'
MANIFEST = PROJECT / 'afiw_data/davis/products' / DAVIS_PAIR / 'manifest.json'
OUTPUT = PROJECT / 'afiw_data/davis/products' / (DAVIS_PAIR + '_classified_notebook')
if RUN_REAL_PRODUCTION:
    completed = render_from_manifest(MANIFEST, OUTPUT, MODEL,
                                     allow_model_transfer = True, require_classification = True)
    record = json.loads(completed.read_text())
    assert record['classification_available']
    print(completed)
    print(BulletinBuilder(completed.parent, 'Davis').build('2021-10-15', WORK / 'davis_bulletin'))
''')
markdown('''## New acquisitions and station assessment

Use the same `PrimaryWorkflow(SPEC)` API or the documented `run-catalog` /
`process-raster` commands after configuring model, reviewed mask, DEM and SAM.
`require_classification: true` prevents a partial product. Assess transfer with
independent, date-matched outlines and an explicit reviewed evaluation domain
using `afiw-primary validate`. Registration, preprocessing and summer/melt
coverage need review before deciding whether additional station labels are
necessary. All workflow calls write console/file logs by default.''')
notebook.cells = cells
notebook.metadata = {'kernelspec' : {'display_name' : 'Python (WAFIW)', 'language' : 'python', 'name' : 'WAFIW'},
                     'language_info' : {'name' : 'python', 'version' : '3.12'}}
path = root / 'notebooks/primary_workflow.ipynb'
nbf.write(notebook, path)
print(path)
