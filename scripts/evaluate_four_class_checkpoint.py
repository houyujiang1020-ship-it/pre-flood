"""Independently reload and evaluate a four-class checkpoint on its declared validation split."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app' / 'training'))
import train_full as training  # noqa: E402
from model_factory import build_siamunet  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--checkpoint', type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding='utf-8'))
    device = config['device']
    checkpoint = torch.load(args.checkpoint, map_location=device, weights_only=True)
    training.DISK_CACHE = ROOT / config['cache_dir'] if config.get('cache_dir') else None
    training._cached_pair.cache_clear()
    records = training.split_rows(config, ROOT)
    source = ROOT / 'upstream/SpaceNet8/baseline/models/other/siamunetdif.py'
    model = build_siamunet(
        source, config.get('normalization', 'batchnorm'),
        int(config.get('groupnorm_groups', 8)),
    ).to(device)
    model.load_state_dict(checkpoint['state_dict'])
    activation = checkpoint.get('output_activation', 'sigmoid')
    threshold_config = config.get('thresholds')
    thresholds = ([threshold_config[name] for name in training.CLASSES]
                  if isinstance(threshold_config, dict) else threshold_config)
    tiled = config.get('tiled_validation')
    if tiled:
        result = training.evaluate_tiled(
            model, records['validation'], int(config['image_size']),
            int(tiled['tile_size']), int(tiled['stride']), device,
            thresholds=thresholds, activation=activation,
        )
    else:
        result = training.evaluate(
            model, records['validation'], int(config['image_size']), device,
            thresholds=thresholds, activation=activation,
        )
    result.update(
        checkpoint=str(args.checkpoint),
        checkpoint_sha256=hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
        epoch=checkpoint['epoch'],
        validation_schedule=config.get('validation_schedule', 'every_epoch'),
        prior_validation_reads=sum(
            row.get('validation') is not None for row in checkpoint.get('history', [])[:-1]
        ),
        test_evaluated=False,
        production_ready=False,
    )
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
