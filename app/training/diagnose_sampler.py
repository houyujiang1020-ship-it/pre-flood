"""CPU-only quota audit; does not import torch, load a model, or train."""
import argparse
import json
from pathlib import Path
from positive_sampler import PositiveSampler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tiles', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--epochs', type=int, default=3)
    args = parser.parse_args()
    if args.epochs < 1:
        raise ValueError('epochs must be positive')
    tiles = json.loads(args.tiles.read_text(encoding='utf-8-sig'))['train']
    config = json.loads(args.config.read_text(encoding='utf-8-sig'))
    sampler = PositiveSampler(tiles, config['sampler'], config.get('seed', 42))
    epochs = []
    for epoch in range(args.epochs):
        indices, report = sampler.sample(epoch)
        report['sampled_train_identities'] = [{'area': tiles[i]['area'], 'label': tiles[i]['label']} for i in indices]
        epochs.append(report)
    result = {'diagnostic_only': True, 'training_started': False,
              'scope': 'Tile appearances overlap; not pixel balance or accuracy evidence.', 'epochs': epochs}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps([{k: v for k, v in r.items() if k != 'sampled_train_identities'} for r in epochs], indent=2))


if __name__ == '__main__':
    main()
