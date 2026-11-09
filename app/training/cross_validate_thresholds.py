"""Two-fold out-of-fold threshold calibration on a frozen validation split."""
import argparse
import hashlib
import json
from pathlib import Path

import torch

import train_full as training
from calibrate_thresholds import select_thresholds
from model_factory import build_siamunet


def assign_folds(items):
    """Greedily balance rare-class tile presence, then fold size."""
    ordered = sorted(items, key=lambda item: (-sum(item['flags']), item['label']))
    folds = [[], []]
    counts = [[0] * 4 for _ in folds]
    for item in ordered:
        choices = []
        for fold in range(2):
            projected = [counts[fold][i] + int(item['flags'][i]) for i in range(4)]
            other = counts[1 - fold]
            imbalance = sum(abs(projected[i] - other[i]) for i in range(4))
            choices.append((imbalance, len(folds[fold]), fold))
        fold = min(choices)[2]
        folds[fold].append(item)
        counts[fold] = [counts[fold][i] + int(item['flags'][i]) for i in range(4)]
    if any(not fold for fold in folds) or any(any(value == 0 for value in count) for count in counts):
        raise ValueError('Two-fold calibration requires every class in each fold')
    return folds


def counts_at_threshold(items, thresholds):
    tp = torch.zeros(4, dtype=torch.float64)
    fp = torch.zeros(4, dtype=torch.float64)
    positives = torch.zeros(4, dtype=torch.float64)
    for item in items:
        expected = item['truth']
        valid = item['valid']
        prediction = item['probability'] > torch.tensor(thresholds).reshape(4, 1, 1)
        prediction &= valid.unsqueeze(0)
        tp += (prediction & expected).sum((1, 2))
        fp += (prediction & ~expected & valid.unsqueeze(0)).sum((1, 2))
        positives += expected.sum((1, 2))
    return tp, fp, positives


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Existing report will not be overwritten')
    root = Path(__file__).resolve().parents[2]
    config = json.loads(args.config.read_text(encoding='utf-8'))
    training.validate_frozen_dataset(config, root)
    training.DISK_CACHE = root / config['cache_dir']
    training._cached_pair.cache_clear()
    records = training.split_rows(config, root)['validation']
    checkpoint = torch.load(args.checkpoint, map_location=config['device'], weights_only=True)
    model = build_siamunet(root / 'upstream/SpaceNet8/baseline/models/other/siamunetdif.py',
                           checkpoint.get('normalization', 'batchnorm'), checkpoint.get('groupnorm_groups') or 8)
    model.load_state_dict(checkpoint['state_dict'])
    model.to(config['device']).eval()
    items = []
    with torch.inference_mode():
        for area, row in records:
            pre, post, truth, valid = [value.unsqueeze(0).to(config['device'])
                                       for value in training.cached_pair(area, row, config['image_size'])]
            expected = ((truth > 0) & (valid.unsqueeze(1) > 0))[0].cpu()
            items.append({'label': row['label'], 'probability': model(pre, post).sigmoid()[0].cpu(),
                          'truth': expected, 'valid': (valid[0].cpu() > 0),
                          'flags': expected.sum((1, 2)).gt(0).tolist()})
    folds = assign_folds(items)
    candidates = [i / 100 for i in range(1, 100)]
    total_tp = torch.zeros(4, dtype=torch.float64)
    total_fp = torch.zeros(4, dtype=torch.float64)
    total_positive = torch.zeros(4, dtype=torch.float64)
    fold_reports = []
    for held_index in range(2):
        calibration = folds[1 - held_index]
        held = folds[held_index]
        tp_grid = torch.zeros(4, len(candidates), dtype=torch.float64)
        fp_grid = torch.zeros_like(tp_grid)
        positives = None
        for column, threshold in enumerate(candidates):
            tp, fp, positive = counts_at_threshold(calibration, [threshold] * 4)
            tp_grid[:, column], fp_grid[:, column], positives = tp, fp, positive
        thresholds = select_thresholds(tp_grid, fp_grid, positives, candidates)
        tp, fp, positive = counts_at_threshold(held, thresholds)
        total_tp += tp; total_fp += fp; total_positive += positive
        fold_reports.append({'held_labels': [item['label'] for item in held],
                             'calibration_labels': [item['label'] for item in calibration],
                             'thresholds': dict(zip(training.CLASSES, thresholds)),
                             'held_iou': dict(zip(training.CLASSES, (tp / (positive + fp).clamp_min(1)).tolist()))})
    iou = total_tp / (total_positive + total_fp).clamp_min(1)
    f1 = 2 * total_tp / (total_positive + total_tp + total_fp).clamp_min(1)
    report = {'method': 'two-fold out-of-fold threshold calibration',
              'scope': 'Frozen Germany validation only; no test or Louisiana access.',
              'checkpoint_sha256': hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
              'folds': fold_reports, 'class_iou': dict(zip(training.CLASSES, iou.tolist())),
              'class_f1': dict(zip(training.CLASSES, f1.tolist())),
              'macro_iou': float(iou.mean()), 'production_ready': False,
              'warning': 'Only 18 validation tiles, including two flooded-building and three flooded-road tiles; uncertainty is high.'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
