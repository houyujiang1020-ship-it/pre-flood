"""Seal the preregistered leakage-free Louisiana-East spatial holdout decision."""
import hashlib
import json
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'experiments/louisiana-east-spatial-holdout-20260926'
RESULT = RUN / 'fold-safe-evaluation.json'
CONFIGS = {
    'foundation_pretraining': ROOT / 'config/training.fold-safe-foundation-east-excluded-20260926.json',
    'random': ROOT / 'config/training.louisiana-spatial-holdout-random-20260926.json',
    'clean_foundation': ROOT / 'config/training.louisiana-spatial-holdout-foundation-clean-20260926.json',
}
MODELS = {
    'foundation_pretraining': ROOT / 'models/experiments/fold-safe-foundation-east-excluded-20260926/best_model.pth',
    'random': ROOT / 'models/experiments/louisiana-spatial-holdout-random-20260926/best_model.pth',
    'clean_foundation': ROOT / 'models/experiments/louisiana-spatial-holdout-foundation-clean-20260926/best_model.pth',
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identities(rows):
    return {(row['area'], row['label']) for row in rows}


def main():
    if RESULT.exists():
        raise FileExistsError('Fold-safe evaluation is already finalized: ' + str(RESULT))
    configs = {name: json.loads(path.read_text(encoding='utf-8')) for name, path in CONFIGS.items()}
    checkpoints = {name: torch.load(path, map_location='cpu', weights_only=True)
                   for name, path in MODELS.items()}
    if configs['random']['splits'] != configs['clean_foundation']['splits']:
        raise RuntimeError('Paired downstream splits differ')
    holdout = identities(configs['random']['splits']['validation'])
    foundation_seen = (identities(configs['foundation_pretraining']['splits']['train']) |
                       identities(configs['foundation_pretraining']['splits']['validation']))
    overlap = sorted(holdout & foundation_seen)
    if overlap:
        raise RuntimeError('Foundation saw spatial holdout: ' + str(overlap[:3]))
    foundation_sha = sha256(MODELS['foundation_pretraining'])
    initialization = checkpoints['clean_foundation'].get('initialization') or {}
    if initialization.get('checkpoint_sha256') != foundation_sha:
        raise RuntimeError('Downstream initialization does not match fold-safe foundation')
    values = {}
    for name in ('random', 'clean_foundation'):
        checkpoint = checkpoints[name]
        if checkpoint['epoch'] != 14 or len(checkpoint['history']) != 14:
            raise RuntimeError('Expected fixed epoch 14: ' + name)
        if any(row.get('validation') is not None for row in checkpoint['history'][:-1]):
            raise RuntimeError('Holdout was evaluated before final epoch: ' + name)
        validation = checkpoint['history'][-1]['validation']
        class_iou = validation['class_iou']
        values[name] = {
            'checkpoint': str(MODELS[name].relative_to(ROOT)),
            'checkpoint_sha256': sha256(MODELS[name]),
            'epoch': checkpoint['epoch'],
            'class_iou': class_iou,
            'macro_iou': sum(class_iou.values()) / 4,
            'tile_count': validation['tile_count'],
            'prior_validation_reads': 0,
        }
    deltas = {name: values['clean_foundation']['class_iou'][name] - values['random']['class_iou'][name]
              for name in values['random']['class_iou']}
    macro_delta = values['clean_foundation']['macro_iou'] - values['random']['macro_iou']
    promoted = macro_delta >= .005 and min(deltas.values()) >= -.005
    result = {
        'status': 'completed',
        'protocol_verified': True,
        'leakage_free': True,
        'validation_schedule': 'final_only',
        'spatial_holdout_tiles': len(holdout),
        'foundation_holdout_intersection': len(overlap),
        'foundation_pretraining': {
            'checkpoint': str(MODELS['foundation_pretraining'].relative_to(ROOT)),
            'checkpoint_sha256': foundation_sha,
            'epoch': checkpoints['foundation_pretraining']['epoch'],
            'initialization': 'random',
        },
        'models': values,
        'class_iou_delta': deltas,
        'macro_iou_delta': macro_delta,
        'promotion_rule': ('Clean foundation macro IoU exceeds random by at least 0.005 and '
                           'no class declines by more than 0.005.'),
        'promotion': 'accepted' if promoted else 'rejected',
        'rejection_reason': (None if promoted else
                             'Flooded-building IoU declined by more than the preregistered 0.005 tolerance.'),
        'test_used': False,
        'development_spatial_holdout_only': True,
        'production_ready': False,
    }
    RESULT.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
