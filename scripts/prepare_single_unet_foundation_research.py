"""Preregister E3c with a true single-image U-Net skip path."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'config/training.foundation-aux-balanced-20260926.json'
CONFIG = ROOT / 'config/training.single-unet-foundation-20260926.json'
RUN = ROOT / 'experiments/germany-louisiana-single-unet-foundation-20260926'
BASELINE = ROOT / 'experiments/germany-louisiana-foundation-aux-20260926/baseline_object_union_evaluation.json'


def main():
    config = json.loads(SOURCE.read_text(encoding='utf-8'))
    config.update(model_id='germany-louisiana-single-unet-foundation-20260926',
                  output_dir='models/experiments/germany-louisiana-single-unet-foundation-20260926',
                  foundation_architecture='single_unet_skip')
    output = ROOT / config['output_dir']
    if output.exists():
        raise FileExistsError('Single U-Net output already exists: ' + str(output))
    RUN.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')
    baseline = json.loads(BASELINE.read_text(encoding='utf-8'))
    prereg = {
        'status': 'preregistered_before_training',
        'experiment': config['model_id'],
        'purpose': 'Train the PRE-event object foundation with valid same-image encoder skip features.',
        'architecture_correction': ('Replace SiamUnet_diff(pre, pre), whose inference skip differences are identically '
                                    'zero, with a shape-compatible single-image U-Net forward graph.'),
        'parameter_compatibility': ('Module names and tensor shapes are unchanged, so all encoder and decoder tensors '
                                    'except the six-channel output layer retain the declared four-class initialization.'),
        'baseline': baseline,
        'baseline_evaluation_sha256': hashlib.sha256(BASELINE.read_bytes()).hexdigest(),
        'unchanged': ['splits', 'domain_balanced_sampler', '512_grid', 'GroupNorm8',
                      'balanced_primary_weighted_BCE_plus_0.5_Dice', 'learning_rate_0.0003',
                      '30_epochs', 'fixed_0.5', 'initialization_checkpoint', 'auxiliary_targets'],
        'promotion_rule': ('Both building and road fixed-0.5 IoU must exceed the baseline object-union IoU, '
                           'and mean object IoU must improve by at least 0.01.'),
        'test_used': False,
        'production_ready': False,
    }
    prereg_path = RUN / 'preregistration.json'
    prereg_path.write_text(json.dumps(prereg, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'config': str(CONFIG), 'preregistration': str(prereg_path)}), flush=True)


if __name__ == '__main__':
    main()
