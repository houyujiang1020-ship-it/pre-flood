"""Create a research-only checkpoint copy bound to validation-calibrated thresholds."""
import argparse
import hashlib
import json
from pathlib import Path

import torch

from train_full import CLASSES


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--calibration', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Output checkpoint already exists')
    calibration = json.loads(args.calibration.read_text(encoding='utf-8'))
    if calibration.get('checkpoint_sha256') != sha256(args.checkpoint):
        raise ValueError('Calibration does not bind the supplied checkpoint')
    if calibration.get('selection_split') != 'validation' or calibration.get('production_ready') is not False:
        raise ValueError('Expected research-only validation calibration')
    thresholds = calibration.get('thresholds')
    if not isinstance(thresholds, dict) or set(thresholds) != set(CLASSES):
        raise ValueError('Calibration thresholds must identify all four classes')
    checkpoint = torch.load(args.checkpoint, map_location='cpu', weights_only=True)
    if checkpoint.get('production_ready') is not False or checkpoint.get('smoke_only') is not True:
        raise ValueError('Only research checkpoints may be calibrated here')
    checkpoint['thresholds'] = thresholds
    checkpoint['threshold_calibration'] = {
        'report': str(args.calibration),
        'report_sha256': sha256(args.calibration),
        'selection_split': 'validation',
        'independent_accuracy_estimate': False,
    }
    checkpoint['production_ready'] = False
    checkpoint['warning'] = 'Research checkpoint with Germany-validation-calibrated thresholds. Not production approved.'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix('.tmp')
    torch.save(checkpoint, temporary)
    temporary.replace(args.output)
    restored = torch.load(args.output, map_location='cpu', weights_only=True)
    if restored['thresholds'] != thresholds or restored['production_ready'] is not False:
        raise RuntimeError('Serialized threshold checkpoint verification failed')
    print(json.dumps({'output': str(args.output), 'sha256': sha256(args.output),
                      'thresholds': thresholds, 'production_ready': False}))


if __name__ == '__main__':
    main()
