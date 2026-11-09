"""Prepare E3 auxiliary targets, baseline object-union metrics, and preregistration."""
import hashlib
import json
import sys
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app' / 'training'))
import train_full as training  # noqa: E402
from foundation_auxiliary import CHANNELS, make_auxiliary_targets  # noqa: E402

BASE_CONFIG = ROOT / 'config/training.germany-louisiana-domain-balanced-20260926.json'
CONFIG = ROOT / 'config/training.foundation-aux-20260926.json'
RUN = ROOT / 'experiments/germany-louisiana-foundation-aux-20260926'
AUX_CACHE = RUN / 'aux-targets512'
BASELINE_OUTPUT = RUN / 'baseline_object_union_evaluation.json'
PREREG = RUN / 'preregistration.json'
CHECKPOINT = ROOT / 'models/experiments/germany-louisiana-domain-balanced-20260926/best_model.pth'


def object_union_evaluation(config, records):
    checkpoint = torch.load(CHECKPOINT, map_location='cuda', weights_only=True)
    model = training.build_siamunet(
        ROOT / 'upstream/SpaceNet8/baseline/models/other/siamunetdif.py',
        checkpoint['normalization'], checkpoint['groupnorm_groups']).cuda().eval()
    model.load_state_dict(checkpoint['state_dict'])
    intersections = torch.zeros(2)
    unions = torch.zeros(2)
    with torch.inference_mode():
        for area, row in records:
            pre, post, labels, valid = training.cached_pair(area, row, config['image_size'])
            probability = model(pre.unsqueeze(0).cuda(), post.unsqueeze(0).cuda()).sigmoid()
            prediction = torch.stack(((probability[:, 0] > .5) | (probability[:, 1] > .5),
                                      (probability[:, 2] > .5) | (probability[:, 3] > .5)), dim=1).cpu()
            truth = torch.stack(((labels[0] > 0) | (labels[1] > 0),
                                 (labels[2] > 0) | (labels[3] > 0))).unsqueeze(0)
            valid_mask = valid.unsqueeze(0).unsqueeze(0) > 0
            prediction &= valid_mask
            truth &= valid_mask
            intersections += (prediction & truth).sum((0, 2, 3))
            unions += (prediction | truth).sum((0, 2, 3))
    values = (intersections / unions).tolist()
    return {'building_iou': values[0], 'road_iou': values[1],
            'mean_object_iou': sum(values) / 2, 'tile_count': len(records),
            'threshold': .5, 'test_evaluated': False, 'production_ready': False}


def main():
    RUN.mkdir(parents=True, exist_ok=True)
    AUX_CACHE.mkdir(exist_ok=True)
    base = json.loads(BASE_CONFIG.read_text(encoding='utf-8'))
    candidate = json.loads(json.dumps(base))
    candidate.update(model_id='germany-louisiana-foundation-aux-20260926',
                     output_dir='models/experiments/germany-louisiana-foundation-aux-20260926',
                     auxiliary_cache_dir=str(AUX_CACHE.relative_to(ROOT)),
                     initialization_checkpoint=str(CHECKPOINT.relative_to(ROOT)),
                     foundation_channels=CHANNELS,
                     selection_metric='mean_object_iou')
    candidate.pop('ema', None)
    output_dir = ROOT / candidate['output_dir']
    if output_dir.exists():
        raise FileExistsError('Foundation training output already exists: ' + str(output_dir))
    CONFIG.write_text(json.dumps(candidate, indent=2) + '\n', encoding='utf-8')
    training.DISK_CACHE = ROOT / candidate['cache_dir']
    training._cached_pair.cache_clear()
    records = training.split_rows(candidate, ROOT)
    written = 0
    for area, row in records['train'] + records['validation']:
        path = AUX_CACHE / (training.pair_cache_key(area, row, candidate['image_size']) + '.pt')
        if path.exists():
            continue
        _, _, labels, valid = training.cached_pair(area, row, candidate['image_size'])
        target = make_auxiliary_targets(labels, valid).to(torch.uint8)
        temporary = path.with_suffix('.tmp')
        torch.save({'schema': 'foundation-aux-v1', 'channels': CHANNELS, 'target': target}, temporary)
        temporary.replace(path)
        written += 1
        if written % 25 == 0:
            print(json.dumps({'aux_written': written}), flush=True)
    expected = len(records['train']) + len(records['validation'])
    if len(list(AUX_CACHE.glob('*.pt'))) != expected:
        raise RuntimeError('Auxiliary cache incomplete')
    baseline = object_union_evaluation(candidate, records['validation'])
    baseline['checkpoint'] = str(CHECKPOINT.relative_to(ROOT))
    baseline['checkpoint_sha256'] = training.file_sha256(CHECKPOINT)
    BASELINE_OUTPUT.write_text(json.dumps(baseline, indent=2), encoding='utf-8')
    baseline_hash = hashlib.sha256(BASELINE_OUTPUT.read_bytes()).hexdigest()
    prereg = {'status': 'preregistered_before_training', 'experiment': candidate['model_id'],
              'purpose': 'Train object foundation on PRE imagery with two primary and four auxiliary shape targets',
              'initialization': ('All shape-compatible SiamUnet_diff weights are initialized from the current '
                                 'four-class research leader; the six-channel output layer is newly initialized.'),
              'channels': CHANNELS, 'primary_channels': ['building_body', 'road_body'],
              'baseline': baseline, 'baseline_evaluation_sha256': baseline_hash,
              'unchanged': ['splits', 'domain_balanced_sampler', '512_grid', 'GroupNorm8',
                            'BCE_plus_0.5_Dice', 'learning_rate_0.0003', '30_epochs', 'fixed_0.5'],
              'promotion_rule': ('Both building and road fixed-0.5 IoU must exceed the baseline object-union IoU, '
                                 'and mean object IoU must improve by at least 0.01.'),
              'test_used': False, 'production_ready': False}
    PREREG.write_text(json.dumps(prereg, indent=2), encoding='utf-8')
    print(json.dumps({'aux_records': expected, 'written': written, 'baseline': baseline,
                      'config': str(CONFIG), 'preregistration': str(PREREG)}), flush=True)


if __name__ == '__main__':
    main()
