import json
from pathlib import Path
import sys
# Ensure project root is on sys.path
sys.path.insert(0, str(Path.cwd()))
from backend.dwg_reader import read_drawing
from backend.boq_engine import generate_geometry_boq
from backend.element_classifier import classify_entities

sources = [Path(value) for value in sys.argv[1:]]
if not sources:
    sources = sorted(Path.cwd().glob('backend/uploads/*.[dD][wW][gG]'))
if not sources:
    raise SystemExit('Usage: py -3 tools\\run_boq.py <drawing1.dwg> [drawing2.dxf ...]')

out_dir = Path('C:/temp/boq_run')
out_dir.mkdir(parents=True, exist_ok=True)
for source in sources:
    print(f'Reading drawing: {source}')
    drawing = read_drawing(source)
    print('Entities:', len(drawing.get('entities', [])))
    stem = source.stem
    (out_dir / f'{stem}_raw_drawing.json').write_text(json.dumps(drawing, indent=2))
    groups = classify_entities(drawing)
    (out_dir / f'{stem}_classification.json').write_text(
        json.dumps({k: [e.get('handle') for e in v] for k, v in groups.items()}, indent=2)
    )
    boq = generate_geometry_boq(drawing)
    (out_dir / f'{stem}_boq.json').write_text(json.dumps(boq, indent=2))
    print(f'Saved reports for {source.name} to {out_dir}')
