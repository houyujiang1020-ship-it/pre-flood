"""Create one controlled comparison, preserving every original spatial split."""
import json
from pathlib import Path

root=Path(__file__).resolve().parents[2]
config=json.loads((root/'config/training.full-germany-20260830.json').read_text(encoding='utf-8'))
config.update(output_dir='models/checkpoints/full-germany-tempered-20260830',epochs=40,
              positive_weight_exponent=.5,positive_weight_cap=8,selection_metric='macro_iou')
config['test_scope']+=' Reused benchmark for refinement; not an untouched final test.'
path=root/'config/training.full-germany-tempered-20260830.json'
with path.open('x',encoding='utf-8') as stream:json.dump(config,stream,indent=2)
print(path)
