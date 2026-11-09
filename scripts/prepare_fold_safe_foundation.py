"""Prepare the holdout-clean replacement foundation and downstream spatial run."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FOUNDATION_SOURCE = ROOT / 'config/training.single-unet-foundation-20260926.json'
SPATIAL_RANDOM = ROOT / 'config/training.louisiana-spatial-holdout-random-20260926.json'
DOMAIN_SOURCE = ROOT / 'config/training.germany-louisiana-domain-balanced-20260926.json'
FOUNDATION_CONFIG = ROOT / 'config/training.fold-safe-foundation-east-excluded-20260926.json'
DOWNSTREAM_CONFIG = ROOT / 'config/training.louisiana-spatial-holdout-foundation-clean-20260926.json'
FOUNDATION_OUTPUT = ROOT / 'models/experiments/fold-safe-foundation-east-excluded-20260926'
DOWNSTREAM_OUTPUT = ROOT / 'models/experiments/louisiana-spatial-holdout-foundation-clean-20260926'
RUN = ROOT / 'experiments/louisiana-east-spatial-holdout-20260926'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if FOUNDATION_OUTPUT.exists() or DOWNSTREAM_OUTPUT.exists():
        raise FileExistsError('Fold-safe replacement output already exists')
    foundation = json.loads(FOUNDATION_SOURCE.read_text(encoding='utf-8'))
    spatial = json.loads(SPATIAL_RANDOM.read_text(encoding='utf-8'))
    domain = json.loads(DOMAIN_SOURCE.read_text(encoding='utf-8'))
    holdout_ids = {(item['area'], item['label']) for item in spatial['splits']['validation']}
    foundation.update(model_id='fold-safe-foundation-east-excluded-20260926',
                      output_dir=str(FOUNDATION_OUTPUT.relative_to(ROOT)),
                      foundation_architecture='single_unet_skip')
    foundation.pop('initialization_checkpoint', None)
    foundation['splits'] = {
        'train': spatial['splits']['train'],
        'validation': domain['splits']['validation'],
        'test': [],
    }
    foundation['test_scope'] = 'No test. Louisiana-East x>=22 is excluded from foundation train/validation.'
    foundation_ids = {(item['area'], item['label']) for name in ('train', 'validation')
                      for item in foundation['splits'][name]}
    if holdout_ids & foundation_ids:
        raise RuntimeError('Foundation split leaks spatial holdout')
    FOUNDATION_CONFIG.write_text(json.dumps(foundation, indent=2) + '\n', encoding='utf-8')

    downstream = json.loads(SPATIAL_RANDOM.read_text(encoding='utf-8'))
    downstream.update(model_id='louisiana-spatial-holdout-foundation-clean-20260926',
                      output_dir=str(DOWNSTREAM_OUTPUT.relative_to(ROOT)),
                      initialization_checkpoint=str((FOUNDATION_OUTPUT / 'best_model.pth').relative_to(ROOT)),
                      initialization_allowed_missing=['conv11d.bias', 'conv11d.weight'])
    DOWNSTREAM_CONFIG.write_text(json.dumps(downstream, indent=2) + '\n', encoding='utf-8')
    prereg = {
        'status': 'preregistered_before_replacement_training',
        'correction': 'Replace the holdout-exposed E3c initializer with a random-start fold-safe foundation.',
        'foundation_train_tiles': len(foundation['splits']['train']),
        'foundation_selection_tiles': len(foundation['splits']['validation']),
        'spatial_holdout_tiles': len(spatial['splits']['validation']),
        'holdout_intersection_with_foundation': 0,
        'foundation_initialization': 'random',
        'foundation_epochs': foundation['epochs'],
        'downstream_epochs': downstream['epochs'],
        'downstream_validation_schedule': downstream['validation_schedule'],
        'promotion_rule': ('Clean foundation macro IoU exceeds the existing random baseline by at least 0.005 '
                           'and no class declines by more than 0.005.'),
        'random_baseline_checkpoint': 'models/experiments/louisiana-spatial-holdout-random-20260926/best_model.pth',
        'random_baseline_checkpoint_sha256': sha(
            ROOT / 'models/experiments/louisiana-spatial-holdout-random-20260926/best_model.pth'),
        'test_used': False, 'production_ready': False,
    }
    path = RUN / 'fold-safe-preregistration.json'
    path.write_text(json.dumps(prereg, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'foundation_config': str(FOUNDATION_CONFIG),
                      'downstream_config': str(DOWNSTREAM_CONFIG),
                      'preregistration': str(path), 'holdout_overlap': 0}), flush=True)


if __name__ == '__main__':
    main()
