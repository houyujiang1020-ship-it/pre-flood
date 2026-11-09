"""Preregister E4: four-class SiamUnet initialized from the promoted object foundation."""
import hashlib
import json
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parents[1]
BASE_CONFIG = ROOT / 'config/training.germany-louisiana-domain-balanced-20260926.json'
CONFIG = ROOT / 'config/training.foundation-initialized-four-class-20260926.json'
RUN = ROOT / 'experiments/germany-louisiana-foundation-initialized-four-class-20260926'
BASE_CHECKPOINT = ROOT / 'models/experiments/germany-louisiana-domain-balanced-20260926/best_model.pth'
FOUNDATION = ROOT / 'models/experiments/germany-louisiana-single-unet-foundation-20260926/best_model.pth'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    config = json.loads(BASE_CONFIG.read_text(encoding='utf-8'))
    config.update(model_id='germany-louisiana-foundation-initialized-four-class-20260926',
                  output_dir='models/experiments/germany-louisiana-foundation-initialized-four-class-20260926',
                  initialization_checkpoint=str(FOUNDATION.relative_to(ROOT)),
                  initialization_allowed_missing=['conv11d.bias', 'conv11d.weight'])
    output = ROOT / config['output_dir']
    if output.exists():
        raise FileExistsError('E4 output already exists: ' + str(output))
    RUN.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')
    base = torch.load(BASE_CHECKPOINT, map_location='cpu', weights_only=True)
    baseline = base['history'][-1]['validation']
    baseline_macro = sum(baseline['class_iou'].values()) / 4
    prereg = {
        'status': 'preregistered_before_training',
        'experiment': config['model_id'],
        'purpose': 'Transfer the promoted PRE-image building/road shape foundation into four-class flood training.',
        'single_change': ('Initialize all 84 shape-compatible encoder/decoder tensors from the E3c foundation; '
                          'initialize only the four-class output layer anew.'),
        'foundation_checkpoint': str(FOUNDATION.relative_to(ROOT)),
        'foundation_checkpoint_sha256': sha(FOUNDATION),
        'baseline_checkpoint': str(BASE_CHECKPOINT.relative_to(ROOT)),
        'baseline_checkpoint_sha256': sha(BASE_CHECKPOINT),
        'baseline_fixed_0_5': baseline,
        'baseline_macro_iou': baseline_macro,
        'unchanged': ['splits', 'domain_balanced_sampler', '512_grid', 'SiamUnet_diff', 'GroupNorm8',
                      'BCE_plus_0.5_Dice', 'learning_rate_0.0003', '30_epochs', 'fixed_0.5'],
        'promotion_rule': ('Macro IoU must improve by at least 0.005 and no class IoU may decline by more than 0.005.'),
        'test_used': False,
        'production_ready': False,
    }
    prereg_path = RUN / 'preregistration.json'
    prereg_path.write_text(json.dumps(prereg, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'config': str(CONFIG), 'preregistration': str(prereg_path),
                      'baseline_macro_iou': baseline_macro}), flush=True)


if __name__ == '__main__':
    main()
