"""Diagnose frozen Germany road supervision and validation logits without training."""
import argparse
import json
from pathlib import Path

import numpy as np
import torch

import train_full as training
from model_factory import build_siamunet


def quantiles(values):
    if not values:
        return None
    array = np.asarray(values, dtype=np.float64)
    return {str(q): float(np.quantile(array, q)) for q in (0, .1, .25, .5, .75, .9, 1)}


def label_summary(records, size):
    rows = []
    for area, row in records:
        _, _, labels, valid = training.cached_pair(area, row, size)
        counts = (((labels > 0) & (valid.unsqueeze(0) > 0)).sum((1, 2))).tolist()
        valid_count = int(valid.sum())
        rows.append({'label': row['label'], 'valid_pixels': valid_count,
                     'class_pixels': dict(zip(training.CLASSES, map(int, counts)))})
    return {
        'tiles': len(rows),
        'positive_tiles': {name: sum(row['class_pixels'][name] > 0 for row in rows)
                           for name in training.CLASSES},
        'total_pixels': {name: sum(row['class_pixels'][name] for row in rows)
                         for name in training.CLASSES},
        'positive_tile_pixel_quantiles': {
            name: quantiles([row['class_pixels'][name] for row in rows if row['class_pixels'][name] > 0])
            for name in training.CLASSES},
        'valid_fraction': {name: sum(row['class_pixels'][name] for row in rows) /
                           max(1, sum(row['valid_pixels'] for row in rows))
                           for name in training.CLASSES},
        'rows': rows,
    }


def checkpoint_diagnostic(root, config, records, checkpoint_path):
    checkpoint = torch.load(checkpoint_path, map_location=config['device'], weights_only=True)
    source = root / 'upstream/SpaceNet8/baseline/models/other/siamunetdif.py'
    model = build_siamunet(source, checkpoint['normalization'], checkpoint.get('groupnorm_groups') or 8)
    model.load_state_dict(checkpoint['state_dict'])
    model.to(config['device']).eval()
    candidates = torch.tensor([.01, .02, .03, .05, .075, .1, .15, .2, .3, .4, .5], dtype=torch.float64)
    tp = torch.zeros(4, len(candidates), dtype=torch.float64)
    fp = torch.zeros_like(tp)
    positives = torch.zeros(4, dtype=torch.float64)
    truth_probabilities = [[] for _ in range(4)]
    background_probabilities = [[] for _ in range(4)]
    with torch.inference_mode():
        for area, row in records:
            pre, post, truth, valid = [value.unsqueeze(0).to(config['device'])
                                       for value in training.cached_pair(area, row, config['image_size'])]
            probability = model(pre, post).sigmoid()
            expected = (truth > 0) & (valid.unsqueeze(1) > 0)
            valid_mask = valid.unsqueeze(1) > 0
            positives += expected.sum((0, 2, 3)).cpu()
            for channel in range(4):
                truth_values = probability[:, channel][expected[:, channel]].cpu().numpy()
                background_values = probability[:, channel][valid_mask[:, 0] & ~expected[:, channel]].cpu().numpy()
                truth_probabilities[channel].extend(truth_values.tolist())
                # Deterministic stride bounds report size while retaining the full range.
                stride = max(1, len(background_values) // 20000)
                background_probabilities[channel].extend(background_values[::stride].tolist())
            for index, threshold in enumerate(candidates):
                prediction = (probability > float(threshold)) & valid_mask
                tp[:, index] += (prediction & expected).sum((0, 2, 3)).cpu()
                fp[:, index] += (prediction & ~expected).sum((0, 2, 3)).cpu()
    iou = tp / (positives[:, None] + fp).clamp_min(1)
    result = {}
    for channel, name in enumerate(training.CLASSES):
        best = int(iou[channel].argmax())
        result[name] = {
            'best_threshold': float(candidates[best]), 'best_iou': float(iou[channel, best]),
            'iou_at_0.5': float(iou[channel, -1]),
            'truth_probability_quantiles': quantiles(truth_probabilities[channel]),
            'background_probability_quantiles': quantiles(background_probabilities[channel]),
        }
    return {'checkpoint': str(checkpoint_path.relative_to(root)), 'epoch': checkpoint['epoch'], 'classes': result}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--checkpoint', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Existing diagnostic will not be overwritten')
    root = Path(__file__).resolve().parents[2]
    config = json.loads(args.config.read_text(encoding='utf-8'))
    training.validate_frozen_dataset(config, root)
    training.DISK_CACHE = root / config['cache_dir']
    training._cached_pair.cache_clear()
    records = training.split_rows(config, root)
    report = {
        'scope': 'Frozen Germany train/validation only; no test or Louisiana access.',
        'image_size': config['image_size'],
        'road_buffer_meters': 3.0,
        'labels': {name: label_summary(records[name], config['image_size']) for name in ('train', 'validation')},
        'checkpoints': [checkpoint_diagnostic(root, config, records['validation'], root / path)
                        for path in args.checkpoint],
        'production_ready': False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'output': str(args.output), 'summaries': {
        split: {key: value for key, value in summary.items() if key != 'rows'}
        for split, summary in report['labels'].items()},
        'checkpoints': report['checkpoints']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
