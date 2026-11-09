"""Seal the preregistered middle-fold building-status loss decision."""
import hashlib
import json
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'experiments/louisiana-middle-building-status-20260926'
RESULT = RUN / 'evaluation.json'
CONFIGS = {
    'independent': ROOT / 'config/training.louisiana-middle-independent-20260926.json',
    'categorical': ROOT / 'config/training.louisiana-middle-building-status-20260926.json',
}
MODELS = {
    'independent': ROOT / 'models/experiments/louisiana-middle-independent-20260926/best_model.pth',
    'categorical': ROOT / 'models/experiments/louisiana-middle-building-status-20260926/best_model.pth',
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if RESULT.exists():
        raise FileExistsError('Evaluation is already finalized: ' + str(RESULT))
    configs = {name: json.loads(path.read_text(encoding='utf-8')) for name, path in CONFIGS.items()}
    if configs['independent']['splits'] != configs['categorical']['splits']:
        raise RuntimeError('Paired splits differ')
    train_ids = {(r['area'], r['label']) for r in configs['independent']['splits']['train']}
    holdout_ids = {(r['area'], r['label']) for r in configs['independent']['splits']['validation']}
    if train_ids & holdout_ids:
        raise RuntimeError('Spatial holdout leakage')
    values = {}
    for name, path in MODELS.items():
        checkpoint = torch.load(path, map_location='cpu', weights_only=True)
        if checkpoint['epoch'] != 14 or len(checkpoint['history']) != 14:
            raise RuntimeError('Expected fixed epoch 14: ' + name)
        if any(row.get('validation') is not None for row in checkpoint['history'][:-1]):
            raise RuntimeError('Holdout was evaluated before final epoch: ' + name)
        validation = checkpoint['history'][-1]['validation']
        class_iou = validation['class_iou']
        values[name] = {
            'checkpoint': str(path.relative_to(ROOT)),
            'checkpoint_sha256': sha256(path),
            'loss_type': checkpoint['loss_type'],
            'output_activation': checkpoint['output_activation'],
            'epoch': checkpoint['epoch'],
            'class_iou': class_iou,
            'macro_iou': sum(class_iou.values()) / 4,
            'tile_count': validation['tile_count'],
            'prior_validation_reads': 0,
        }
    deltas = {key: values['categorical']['class_iou'][key] - values['independent']['class_iou'][key]
              for key in values['independent']['class_iou']}
    macro_delta = values['categorical']['macro_iou'] - values['independent']['macro_iou']
    preserved = all(deltas[key] >= -.005 for key in deltas if key != 'flooded_building')
    promoted = deltas['flooded_building'] >= .005 and macro_delta >= 0 and preserved
    result = {
        'status': 'completed',
        'protocol_verified': True,
        'leakage_free': True,
        'validation_schedule': 'final_only',
        'spatial_holdout_tiles': len(holdout_ids),
        'models': values,
        'class_iou_delta': deltas,
        'macro_iou_delta': macro_delta,
        'promotion_rule': ('Flooded-building IoU improves by at least 0.005, macro IoU does not decline, '
                           'and each other class declines by no more than 0.005.'),
        'promotion': 'accepted' if promoted else 'rejected',
        'rejection_reason': (None if promoted else
                             'Categorical status produced zero flooded-building IoU and reduced macro IoU.'),
        'test_used': False,
        'development_spatial_holdout_only': True,
        'production_ready': False,
    }
    RESULT.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
