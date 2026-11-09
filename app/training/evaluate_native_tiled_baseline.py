"""Evaluate the frozen 512-trained baseline on the E2 near-native tiled validation grid."""
import json
from pathlib import Path

import torch

import train_full as training


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / 'config/training.germany-louisiana-native-crop-20260926.json'
CHECKPOINT = ROOT / 'models/experiments/germany-louisiana-domain-balanced-20260926/best_model.pth'
OUTPUT = ROOT / 'experiments/germany-louisiana-native-crop-20260926/baseline_native_tiled_evaluation.json'


def main():
    config = json.loads(CONFIG.read_text(encoding='utf-8'))
    training.DISK_CACHE = ROOT / config['cache_dir']
    training._cached_pair.cache_clear()
    records = training.split_rows(config, ROOT)
    checkpoint = torch.load(CHECKPOINT, map_location='cuda', weights_only=True)
    source = ROOT / 'upstream/SpaceNet8/baseline/models/other/siamunetdif.py'
    model = training.build_siamunet(source, checkpoint['normalization'], checkpoint['groupnorm_groups']).cuda()
    model.load_state_dict(checkpoint['state_dict'])
    tiled = config['tiled_validation']
    thresholds = [checkpoint['thresholds'][name] for name in training.CLASSES]
    result = training.evaluate_tiled(model, records['validation'], config['image_size'],
                                     tiled['tile_size'], tiled['stride'], 'cuda', thresholds)
    macro = sum(result['class_iou'].values()) / 4
    report = {'role': 'pre-registered E2 comparison baseline',
              'model_training_grid': 512, 'evaluation_grid': config['image_size'],
              'checkpoint': str(CHECKPOINT.relative_to(ROOT)),
              'checkpoint_sha256': training.file_sha256(CHECKPOINT),
              'validation': result, 'macro_iou': macro,
              'test_evaluated': False, 'production_ready': False}
    OUTPUT.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
