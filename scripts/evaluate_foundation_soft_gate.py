"""Prepare and evaluate one fixed soft object gate for the promoted E4 model."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app' / 'training'))
import train_full as base  # noqa: E402
from train_foundation_aux import build_foundation_model  # noqa: E402

CONFIG = ROOT / 'config/training.foundation-initialized-four-class-20260926.json'
FLOOD = ROOT / 'models/experiments/germany-louisiana-foundation-initialized-four-class-20260926/best_model.pth'
FOUNDATION_CONFIG = ROOT / 'config/training.single-unet-foundation-20260926.json'
FOUNDATION = ROOT / 'models/experiments/germany-louisiana-single-unet-foundation-20260926/best_model.pth'
RUN = ROOT / 'experiments/germany-louisiana-foundation-soft-gate-20260926'
PREREG = RUN / 'preregistration.json'
RESULT = RUN / 'evaluation.json'
EPSILON = .25


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare():
    RUN.mkdir(parents=True, exist_ok=True)
    flood = torch.load(FLOOD, map_location='cpu', weights_only=True)
    baseline = flood['history'][-1]['validation']
    prereg = {
        'status': 'preregistered_before_evaluation',
        'experiment': 'germany-louisiana-foundation-soft-gate-20260926',
        'formula': 'p_gated = p_flood_class * (0.75 + 0.25 * p_foundation_object)',
        'gate_strength': EPSILON,
        'threshold': .5,
        'foundation_mapping': {'building classes': 'building_body', 'road classes': 'road_body'},
        'flood_checkpoint': str(FLOOD.relative_to(ROOT)), 'flood_sha256': sha(FLOOD),
        'foundation_checkpoint': str(FOUNDATION.relative_to(ROOT)), 'foundation_sha256': sha(FOUNDATION),
        'baseline': baseline,
        'promotion_rule': 'Macro IoU improves by at least 0.002 and no class declines by more than 0.003.',
        'no_search': 'Gate strength and threshold will not be tuned on this validation split.',
        'test_used': False, 'production_ready': False,
    }
    PREREG.write_text(json.dumps(prereg, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'preregistration': str(PREREG), 'gate_strength': EPSILON}), flush=True)


def evaluate():
    if not PREREG.exists() or RESULT.exists():
        raise RuntimeError('Prepare first and do not overwrite an existing evaluation')
    config = json.loads(CONFIG.read_text(encoding='utf-8'))
    foundation_config = json.loads(FOUNDATION_CONFIG.read_text(encoding='utf-8'))
    flood_checkpoint = torch.load(FLOOD, map_location='cuda', weights_only=True)
    foundation_checkpoint = torch.load(FOUNDATION, map_location='cuda', weights_only=True)
    flood_model = base.build_siamunet(ROOT / 'upstream/SpaceNet8/baseline/models/other/siamunetdif.py',
                                     flood_checkpoint['normalization'],
                                     flood_checkpoint['groupnorm_groups']).cuda().eval()
    flood_model.load_state_dict(flood_checkpoint['state_dict'])
    foundation_model = build_foundation_model(ROOT, foundation_config).cuda().eval()
    foundation_model.load_state_dict(foundation_checkpoint['state_dict'])
    base.DISK_CACHE = ROOT / config['cache_dir']
    base._cached_pair.cache_clear()
    records = base.split_rows(config, ROOT)['validation']
    intersections = torch.zeros(4)
    unions = torch.zeros(4)
    with torch.inference_mode():
        for area, row in records:
            pre, post, truth, valid = base.cached_pair(area, row, config['image_size'])
            pre_gpu, post_gpu = pre.unsqueeze(0).cuda(), post.unsqueeze(0).cuda()
            flood_probability = flood_model(pre_gpu, post_gpu).sigmoid()
            object_probability = foundation_model(pre_gpu).sigmoid()
            gate = torch.stack((object_probability[:, 0], object_probability[:, 0],
                                object_probability[:, 3], object_probability[:, 3]), dim=1)
            prediction = (flood_probability * (1 - EPSILON + EPSILON * gate) > .5).cpu()
            expected = truth.unsqueeze(0) > 0
            mask = valid.unsqueeze(0).unsqueeze(0) > 0
            prediction &= mask
            expected &= mask
            intersections += (prediction & expected).sum((0, 2, 3))
            unions += (prediction | expected).sum((0, 2, 3))
    values = (intersections / unions).tolist()
    class_iou = dict(zip(base.CLASSES, values))
    prereg = json.loads(PREREG.read_text(encoding='utf-8'))
    baseline_values = prereg['baseline']['class_iou']
    baseline_macro = sum(baseline_values.values()) / 4
    macro = sum(values) / 4
    declines = {name: baseline_values[name] - class_iou[name] for name in base.CLASSES}
    promoted = macro >= baseline_macro + .002 and max(declines.values()) <= .003
    result = {'class_iou': class_iou, 'macro_iou': macro, 'baseline_macro_iou': baseline_macro,
              'macro_delta': macro - baseline_macro, 'class_declines': declines,
              'promotion': 'accepted' if promoted else 'rejected', 'tile_count': len(records),
              'test_evaluated': False, 'production_ready': False}
    RESULT.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['prepare', 'evaluate'])
    args = parser.parse_args()
    prepare() if args.mode == 'prepare' else evaluate()


if __name__ == '__main__':
    main()
