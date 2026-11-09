"""Preregister a fresh middle-strip test of mutually exclusive building status loss."""
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'config/training.germany-louisiana-domain-balanced-20260926.json'
RUN = ROOT / 'experiments/louisiana-middle-building-status-20260926'
BASE_CONFIG = ROOT / 'config/training.louisiana-middle-independent-20260926.json'
CANDIDATE_CONFIG = ROOT / 'config/training.louisiana-middle-building-status-20260926.json'


def x_coordinate(item):
    numbers = [int(value) for value in re.findall(r'\d+', Path(item['label']).stem)]
    if len(numbers) < 3:
        raise ValueError('Unexpected tile label: ' + item['label'])
    return numbers[-2]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = json.loads(SOURCE.read_text(encoding='utf-8'))
    pool = source['splits']['train']
    holdout = [item for item in pool if item['area'] == 'Louisiana-East_Training_Public'
               and 19 <= x_coordinate(item) <= 21]
    train = [item for item in pool if item not in holdout]
    if len(holdout) != 106 or len(train) != 591:
        raise RuntimeError(f'Unexpected split sizes train={len(train)} holdout={len(holdout)}')
    train_ids = {(item['area'], item['label']) for item in train}
    holdout_ids = {(item['area'], item['label']) for item in holdout}
    if train_ids & holdout_ids:
        raise RuntimeError('Middle-strip holdout leakage')
    common = json.loads(json.dumps(source))
    common.update(epochs=14, validation_schedule='final_only')
    common['test_scope'] = ('Louisiana-East x=19..21 fresh spatial development holdout, evaluated once after '
                            'fixed epoch 14; not a blind or official test.')
    common['splits'] = {'train': train, 'validation': holdout, 'test': []}
    common.pop('initialization_checkpoint', None)
    common.pop('initialization_allowed_missing', None)
    baseline = json.loads(json.dumps(common))
    baseline.update(model_id='louisiana-middle-independent-20260926',
                    output_dir='models/experiments/louisiana-middle-independent-20260926',
                    loss_type='independent_binary')
    candidate = json.loads(json.dumps(common))
    candidate.update(model_id='louisiana-middle-building-status-20260926',
                     output_dir='models/experiments/louisiana-middle-building-status-20260926',
                     loss_type='building_status_categorical')
    for path, value in ((BASE_CONFIG, baseline), (CANDIDATE_CONFIG, candidate)):
        output = ROOT / value['output_dir']
        if path.exists() or output.exists():
            raise FileExistsError('Refusing to overwrite experiment: ' + str(path))
        path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    RUN.mkdir(parents=True, exist_ok=False)
    manifest = {
        'schema_version': 1,
        'rule': 'Hold out Louisiana-East tiles with filename x coordinate 19 through 21 inclusive.',
        'train_tiles': len(train),
        'holdout_tiles': len(holdout),
        'train_by_area': {area: sum(item['area'] == area for item in train)
                          for area in sorted({item['area'] for item in train})},
        'holdout_labels': [item['label'] for item in holdout],
        'source_config': str(SOURCE.relative_to(ROOT)),
        'source_config_sha256': sha256(SOURCE),
        'excluded_prior_germany_validation_tiles': len(source['splits']['validation']),
        'test_used': False,
    }
    manifest_path = RUN / 'split-manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    prereg = {
        'status': 'preregistered_before_training',
        'purpose': 'Test whether mutually exclusive building status supervision improves flooded-building IoU.',
        'comparison': ['independent binary four-class loss', 'three-state building categorical loss'],
        'single_change': ('Building channels use background/non-flooded/flooded cross-entropy and softmax; '
                          'road channels, sampler, seed, architecture, augmentation, Dice, epoch and threshold stay fixed.'),
        'initialization': 'same-seed random for both models',
        'fixed_epoch': 14,
        'validation_schedule': 'final_only',
        'holdout_access': 'No evaluation or checkpoint selection before final epoch.',
        'promotion_rule': ('Flooded-building IoU improves by at least 0.005, macro IoU does not decline, and each '
                           'other class declines by no more than 0.005.'),
        'interpretation': ('Fresh development fold for this loss comparison; still not the future independent test.'),
        'manifest': str(manifest_path.relative_to(ROOT)),
        'manifest_sha256': sha256(manifest_path),
        'test_used': False,
        'production_ready': False,
    }
    prereg_path = RUN / 'preregistration.json'
    prereg_path.write_text(json.dumps(prereg, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'train': len(train), 'holdout': len(holdout),
                      'baseline_config': str(BASE_CONFIG), 'candidate_config': str(CANDIDATE_CONFIG),
                      'preregistration': str(prereg_path)}), flush=True)


if __name__ == '__main__':
    main()
