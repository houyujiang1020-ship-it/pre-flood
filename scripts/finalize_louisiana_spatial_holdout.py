"""Finalize the preregistered paired Louisiana-East spatial holdout decision."""
import hashlib
import json
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'experiments/louisiana-east-spatial-holdout-20260926'
RESULT = RUN / 'evaluation.json'
MODELS = {
    'random': ROOT / 'models/experiments/louisiana-spatial-holdout-random-20260926/best_model.pth',
    'foundation': ROOT / 'models/experiments/louisiana-spatial-holdout-foundation-20260926/best_model.pth',
}


def main():
    if RESULT.exists():
        raise FileExistsError('Evaluation is already finalized: ' + str(RESULT))
    values = {}
    for name, path in MODELS.items():
        checkpoint = torch.load(path, map_location='cpu', weights_only=True)
        if checkpoint['epoch'] != 14 or len(checkpoint['history']) != 14:
            raise RuntimeError('Expected fixed epoch 14: ' + name)
        if any(row['validation'] is not None for row in checkpoint['history'][:-1]):
            raise RuntimeError('Holdout was evaluated before final epoch: ' + name)
        validation = checkpoint['history'][-1]['validation']
        values[name] = {
            'checkpoint': str(path.relative_to(ROOT)),
            'checkpoint_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'epoch': checkpoint['epoch'],
            'class_iou': validation['class_iou'],
            'macro_iou': sum(validation['class_iou'].values()) / 4,
            'tile_count': validation['tile_count'],
        }
    deltas = {name: values['foundation']['class_iou'][name] - values['random']['class_iou'][name]
              for name in values['random']['class_iou']}
    macro_delta = values['foundation']['macro_iou'] - values['random']['macro_iou']
    promoted = macro_delta >= .005 and min(deltas.values()) >= -.005
    result = {
        'protocol_verified': True,
        'validation_schedule': 'final_only',
        'models': values,
        'class_iou_delta': deltas,
        'macro_iou_delta': macro_delta,
        'promotion': 'accepted' if promoted else 'rejected',
        'rejection_reason': None if promoted else 'At least one class declined by more than 0.005.',
        'test_used': False,
        'production_ready': False,
    }
    RESULT.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
