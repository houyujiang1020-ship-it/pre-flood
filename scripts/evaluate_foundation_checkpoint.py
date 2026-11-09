"""Independently reload and evaluate a foundation checkpoint on its declared validation split."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app' / 'training'))
import train_full as base  # noqa: E402
from foundation_auxiliary import CHANNELS  # noqa: E402
from train_foundation_aux import build_foundation_model, evaluate  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--checkpoint', type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding='utf-8'))
    checkpoint = torch.load(args.checkpoint, map_location=config['device'], weights_only=True)
    base.DISK_CACHE = ROOT / config['cache_dir']
    base._cached_pair.cache_clear()
    records = base.split_rows(config, ROOT)
    model = build_foundation_model(ROOT, config).to(config['device'])
    model.load_state_dict(checkpoint['state_dict'])
    result = evaluate(model, records['validation'], ROOT / config['auxiliary_cache_dir'],
                      int(config['image_size']), config['device'],
                      architecture=config.get('foundation_architecture', 'siamunet_pre_pre'))
    result.update(checkpoint=str(args.checkpoint),
                  checkpoint_sha256=hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
                  epoch=checkpoint['epoch'], test_evaluated=False, production_ready=False)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
