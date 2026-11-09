"""Freeze a paired, final-only Louisiana-East spatial validation experiment."""
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'config/training.germany-louisiana-domain-balanced-20260926.json'
FOUNDATION = ROOT / 'models/experiments/germany-louisiana-single-unet-foundation-20260926/best_model.pth'
RUN = ROOT / 'experiments/louisiana-east-spatial-holdout-20260926'
BASE_CONFIG = ROOT / 'config/training.louisiana-spatial-holdout-random-20260926.json'
INIT_CONFIG = ROOT / 'config/training.louisiana-spatial-holdout-foundation-20260926.json'


def x_coordinate(item):
    numbers = [int(value) for value in re.findall(r'\d+', Path(item['label']).stem)]
    if len(numbers) < 3:
        raise ValueError('Unexpected tile label: ' + item['label'])
    return numbers[-2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = json.loads(SOURCE.read_text(encoding='utf-8'))
    original = source['splits']['train']
    holdout = [item for item in original
               if item['area'] == 'Louisiana-East_Training_Public' and x_coordinate(item) >= 22]
    train = [item for item in original if item not in holdout]
    if len(holdout) != 92 or len(train) != 605:
        raise RuntimeError(f'Unexpected split sizes train={len(train)} holdout={len(holdout)}')
    identities = {(item['area'], item['label']) for item in train}
    if identities & {(item['area'], item['label']) for item in holdout}:
        raise RuntimeError('Spatial holdout leakage')
    common = json.loads(json.dumps(source))
    common['epochs'] = 14
    common['validation_schedule'] = 'final_only'
    common['test_scope'] = ('Louisiana-East x>=22 spatial development holdout, evaluated once after fixed epoch 14; '
                            'not a blind or official test.')
    common['splits'] = {'train': train, 'validation': holdout, 'test': []}
    common.pop('initialization_checkpoint', None)
    common.pop('initialization_allowed_missing', None)
    random_config = json.loads(json.dumps(common))
    random_config.update(model_id='louisiana-spatial-holdout-random-20260926',
                         output_dir='models/experiments/louisiana-spatial-holdout-random-20260926')
    initialized_config = json.loads(json.dumps(common))
    initialized_config.update(
        model_id='louisiana-spatial-holdout-foundation-20260926',
        output_dir='models/experiments/louisiana-spatial-holdout-foundation-20260926',
        initialization_checkpoint=str(FOUNDATION.relative_to(ROOT)),
        initialization_allowed_missing=['conv11d.bias', 'conv11d.weight'])
    for path, value in ((BASE_CONFIG, random_config), (INIT_CONFIG, initialized_config)):
        output = ROOT / value['output_dir']
        if output.exists():
            raise FileExistsError('Output already exists: ' + str(output))
        path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    RUN.mkdir(parents=True, exist_ok=True)
    manifest = {
        'schema_version': 1,
        'rule': 'Hold out every Louisiana-East tile whose filename x coordinate is >=22.',
        'fixed_epoch': 14,
        'validation_schedule': 'final_only',
        'train_tiles': len(train), 'holdout_tiles': len(holdout),
        'train_by_area': {area: sum(item['area'] == area for item in train)
                          for area in sorted({item['area'] for item in train})},
        'holdout_labels': [item['label'] for item in holdout],
        'source_config': str(SOURCE.relative_to(ROOT)), 'source_config_sha256': sha(SOURCE),
        'foundation_checkpoint': str(FOUNDATION.relative_to(ROOT)),
        'foundation_checkpoint_sha256': sha(FOUNDATION),
        'excluded_prior_germany_validation_tiles': len(source['splits']['validation']),
        'test_used': False,
    }
    manifest_path = RUN / 'split-manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    prereg = {
        'status': 'preregistered_before_training',
        'purpose': ('Paired spatial generalization check without reusing the repeatedly selected 18-tile Germany '
                    'validation split.'),
        'comparison': ['random initialization', 'E3c foundation initialization'],
        'single_change': '84 compatible foundation tensors; four-class output layer remains same-seed random.',
        'fixed_epoch': 14,
        'holdout_access': 'No validation evaluation or checkpoint selection before the final epoch.',
        'promotion_rule': ('Foundation macro IoU exceeds random initialization by at least 0.005 and no class '
                           'declines by more than 0.005.'),
        'interpretation': ('Development spatial holdout only. Louisiana data has prior research exposure and this is '
                           'not the future user-provided independent test.'),
        'manifest': str(manifest_path.relative_to(ROOT)),
        'manifest_sha256': sha(manifest_path),
        'test_used': False, 'production_ready': False,
    }
    prereg_path = RUN / 'preregistration.json'
    prereg_path.write_text(json.dumps(prereg, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'train': len(train), 'holdout': len(holdout),
                      'random_config': str(BASE_CONFIG), 'foundation_config': str(INIT_CONFIG),
                      'preregistration': str(prereg_path)}), flush=True)


if __name__ == '__main__':
    main()
