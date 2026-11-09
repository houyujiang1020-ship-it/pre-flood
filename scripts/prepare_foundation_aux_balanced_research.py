"""Preregister E3b: class-balanced, primary-weighted foundation training."""
import hashlib
import json
import sys
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app' / 'training'))
import train_full as base  # noqa: E402
from foundation_auxiliary import CHANNELS  # noqa: E402
from train_foundation_aux import auxiliary_target  # noqa: E402

SOURCE_CONFIG = ROOT / 'config/training.foundation-aux-20260926.json'
CONFIG = ROOT / 'config/training.foundation-aux-balanced-20260926.json'
RUN = ROOT / 'experiments/germany-louisiana-foundation-aux-balanced-20260926'
PREREG = RUN / 'preregistration.json'
BASELINE = ROOT / 'experiments/germany-louisiana-foundation-aux-20260926/baseline_object_union_evaluation.json'


def main():
    config = json.loads(SOURCE_CONFIG.read_text(encoding='utf-8'))
    config.update(model_id='germany-louisiana-foundation-aux-balanced-20260926',
                  output_dir='models/experiments/germany-louisiana-foundation-aux-balanced-20260926',
                  balanced_loss=True, positive_weight_exponent=.5, positive_weight_cap=20,
                  foundation_channel_weights=[2, .5, .5, 2, .5, .5])
    output = ROOT / config['output_dir']
    if output.exists():
        raise FileExistsError('Foundation balanced output already exists: ' + str(output))
    RUN.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')
    base.DISK_CACHE = ROOT / config['cache_dir']
    base._cached_pair.cache_clear()
    records = base.split_rows(config, ROOT)
    aux_cache = ROOT / config['auxiliary_cache_dir']
    positive = torch.zeros(len(CHANNELS))
    total = 0.0
    for area, row in records['train']:
        target = auxiliary_target(aux_cache, area, row, config['image_size'])
        _, _, _, valid = base.cached_pair(area, row, config['image_size'])
        positive += (target * valid.unsqueeze(0)).sum((1, 2))
        total += valid.sum().item()
    weights = (((total - positive) / positive).pow(.5).clamp(1, 20)).tolist()
    baseline = json.loads(BASELINE.read_text(encoding='utf-8'))
    prereg = {
        'status': 'preregistered_before_training',
        'experiment': config['model_id'],
        'purpose': 'Correct the audited all-background failure caused by unbalanced sparse auxiliary targets.',
        'single_change': ('Use square-root inverse-frequency positive weights capped at 20 and give each primary '
                          'body channel four times each auxiliary channel loss weight.'),
        'channels': CHANNELS,
        'training_positive_pixels': dict(zip(CHANNELS, positive.tolist())),
        'valid_training_pixels': total,
        'positive_weights': dict(zip(CHANNELS, weights)),
        'channel_weights': dict(zip(CHANNELS, config['foundation_channel_weights'])),
        'baseline': baseline,
        'baseline_evaluation_sha256': hashlib.sha256(BASELINE.read_bytes()).hexdigest(),
        'unchanged': ['splits', 'domain_balanced_sampler', '512_grid', 'GroupNorm8',
                      'BCE_plus_0.5_Dice', 'learning_rate_0.0003', '30_epochs', 'fixed_0.5',
                      'initialization_checkpoint', 'auxiliary_targets'],
        'promotion_rule': ('Both building and road fixed-0.5 IoU must exceed the baseline object-union IoU, '
                           'and mean object IoU must improve by at least 0.01.'),
        'test_used': False,
        'production_ready': False,
    }
    PREREG.write_text(json.dumps(prereg, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'config': str(CONFIG), 'preregistration': str(PREREG),
                      'positive_weights': weights}), flush=True)


if __name__ == '__main__':
    main()
