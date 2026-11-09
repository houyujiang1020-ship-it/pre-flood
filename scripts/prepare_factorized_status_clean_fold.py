"""Preregister the clean x=13..15 paired test of factorized object/status supervision."""
import hashlib
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app' / 'training'))
from train_full import CLASSES, cached_pair, split_rows  # noqa: E402

SOURCE = ROOT / 'config/training.germany-louisiana-domain-balanced-20260926.json'
RUN = ROOT / 'experiments/louisiana-x13-15-factorized-status-20260926'
BASE_CONFIG = ROOT / 'config/training.louisiana-x13-15-independent-20260926.json'
CANDIDATE_CONFIG = ROOT / 'config/training.louisiana-x13-15-factorized-status-20260926.json'


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def x_coordinate(item):
    values = [int(value) for value in re.findall(r'\d+', Path(item['label']).stem)]
    if len(values) < 3:
        raise ValueError('Unexpected tile label: ' + item['label'])
    return values[-2]


def main():
    source = json.loads(SOURCE.read_text(encoding='utf-8'))
    pool = source['splits']['train']
    holdout = [item for item in pool if item['area'] == 'Louisiana-East_Training_Public'
               and 13 <= x_coordinate(item) <= 15]
    train = [item for item in pool if item not in holdout]
    if len(holdout) != 105 or len(train) != 592:
        raise RuntimeError(f'Unexpected split sizes train={len(train)} holdout={len(holdout)}')
    if {(i['area'], i['label']) for i in train} & {(i['area'], i['label']) for i in holdout}:
        raise RuntimeError('x=13..15 spatial holdout leakage')

    common = json.loads(json.dumps(source))
    common.update(epochs=14, validation_schedule='final_only')
    common['test_scope'] = ('Louisiana-East x=13..15 fresh spatial development holdout, evaluated once after '
                            'fixed epoch 14; not a blind or official test.')
    common['splits'] = {'train': train, 'validation': holdout, 'test': []}
    common.pop('initialization_checkpoint', None)
    common.pop('initialization_allowed_missing', None)
    baseline = json.loads(json.dumps(common))
    baseline.update(model_id='louisiana-x13-15-independent-20260926',
                    output_dir='models/experiments/louisiana-x13-15-independent-20260926',
                    loss_type='independent_binary')
    candidate = json.loads(json.dumps(common))
    candidate.update(model_id='louisiana-x13-15-factorized-status-20260926',
                     output_dir='models/experiments/louisiana-x13-15-factorized-status-20260926',
                     loss_type='factorized_object_status')
    for path, value in ((BASE_CONFIG, baseline), (CANDIDATE_CONFIG, candidate)):
        if path.exists() or (ROOT / value['output_dir']).exists():
            raise FileExistsError('Refusing to overwrite experiment: ' + str(path))
        path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')

    positive_tiles = [0] * 4
    overlap_pixels = [0, 0]
    for area, row in split_rows(candidate, ROOT)['validation']:
        truth = cached_pair(area, row, int(candidate['image_size']))[2] > 0
        for channel in range(4):
            positive_tiles[channel] += int(truth[channel].any())
        overlap_pixels[0] += int((truth[0] & truth[1]).sum())
        overlap_pixels[1] += int((truth[2] & truth[3]).sum())
    if any(value == 0 for value in positive_tiles):
        raise RuntimeError('Fresh holdout lacks one or more target classes')

    RUN.mkdir(parents=True, exist_ok=False)
    manifest = {
        'schema_version': 1,
        'rule': 'Hold out Louisiana-East tiles with filename x coordinate 13 through 15 inclusive.',
        'train_tiles': len(train), 'holdout_tiles': len(holdout),
        'holdout_positive_tiles': dict(zip(CLASSES, positive_tiles)),
        'holdout_rasterized_status_overlap_pixels': {'building': overlap_pixels[0], 'road': overlap_pixels[1]},
        'factorized_overlap_policy': ('Flooded status wins only where separately buffered/rasterized status '
                                      'geometries overlap; object union remains supervised.'),
        'train_by_area': {area: sum(item['area'] == area for item in train)
                          for area in sorted({item['area'] for item in train})},
        'holdout_labels': [item['label'] for item in holdout],
        'source_config': str(SOURCE.relative_to(ROOT)), 'source_config_sha256': sha256(SOURCE),
        'baseline_config': str(BASE_CONFIG.relative_to(ROOT)), 'baseline_config_sha256': sha256(BASE_CONFIG),
        'candidate_config': str(CANDIDATE_CONFIG.relative_to(ROOT)),
        'candidate_config_sha256': sha256(CANDIDATE_CONFIG),
        'training_code': 'app/training/train_full.py',
        'training_code_sha256': sha256(ROOT / 'app/training/train_full.py'),
        'excluded_prior_germany_validation_tiles': len(source['splits']['validation']),
        'pretraining_holdout_access': ('Class-presence and rasterized geometry-overlap counts only; '
                                       'no model inference or metric computation.'),
        'test_used': False,
    }
    manifest_path = RUN / 'split-manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    prereg = {
        'schema_version': 1, 'status': 'preregistered_before_training',
        'purpose': ('Test factorized object presence and conditional flood status on a spatial fold that has '
                    'not been evaluated by either paired model.'),
        'comparison': ['independent four-channel BCE+Dice',
                       'factorized object BCE plus object-conditional balanced flood BCE+Dice'],
        'single_change': ('Four logits are decoded as object probability times conditional status probability. '
                          'Status BCE is supervised only on object pixels; flooded status wins at rasterized '
                          'buffer intersections. All other training and evaluation settings stay fixed.'),
        'initialization': 'same-seed random for both models',
        'fixed_epoch': 14, 'validation_schedule': 'final_only',
        'holdout_access': 'No model inference, checkpoint selection or metric computation before final epoch.',
        'promotion_rule': ('Candidate macro IoU improves by at least 0.010; both flooded-class IoUs decline by '
                           'no more than 0.005; at least one flooded class improves by at least 0.010; no class '
                           'declines by more than 0.010; candidate building and road output-overlap pixels are zero.'),
        'prior_invalidated_fold': 'experiments/louisiana-x16-18-factorized-status-20260926/invalidation.json',
        'interpretation': ('Development spatial evidence only. Louisiana-West public test is not read; no '
                           'independent or production accuracy is claimed.'),
        'manifest': str(manifest_path.relative_to(ROOT)), 'manifest_sha256': sha256(manifest_path),
        'test_used': False, 'production_ready': False,
    }
    prereg_path = RUN / 'preregistration.json'
    prereg_path.write_text(json.dumps(prereg, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'train': len(train), 'holdout': len(holdout),
                      'holdout_positive_tiles': dict(zip(CLASSES, positive_tiles)),
                      'holdout_status_overlap_pixels': {'building': overlap_pixels[0], 'road': overlap_pixels[1]},
                      'baseline_config': str(BASE_CONFIG), 'candidate_config': str(CANDIDATE_CONFIG),
                      'preregistration': str(prereg_path)}), flush=True)


if __name__ == '__main__':
    main()
