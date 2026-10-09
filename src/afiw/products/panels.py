"""Bulletin-only assembly of already rendered PyGMT map PNGs."""
from pathlib import Path
from PIL import Image


def assemble_primary_panels(manifest_path, record, output):
    directory = Path(manifest_path).parent
    outputs = record['outputs']
    if 'composite_png' not in outputs:
        # Read-only compatibility with schema-1 publications, never newly generated.
        import shutil
        shutil.copyfile(directory / outputs['quicklook'], output)
        return [str(directory / outputs['quicklook'])]
    sources = [directory / outputs['composite_png']]
    if record.get('classification_available', 'classification' in outputs):
        if 'classification_png' not in outputs:
            raise ValueError('Classified manifest is missing its separate classification PNG')
        sources.append(directory / outputs['classification_png'])
    images = []
    for path in sources:
        with Image.open(path) as image:
            image.load()
            images.append(image.convert('RGB'))
    height = max(image.height for image in images)
    resized = [image.resize((round(image.width * height / image.height), height), Image.Resampling.LANCZOS)
               if image.height != height else image for image in images]
    gutter = 30 if len(images) > 1 else 0
    canvas = Image.new('RGB', (sum(image.width for image in resized) + gutter, height), 'white')
    x = 0
    for image in resized:
        canvas.paste(image, (x, 0))
        x += image.width + gutter
    canvas.save(output)
    return [str(path) for path in sources]
