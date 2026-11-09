"""Create the single-variable domain-balanced follow-up configuration."""
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main():
    source = ROOT / 'config/training.germany-louisiana-east-research-20260916.json'
    target = ROOT / 'config/training.germany-louisiana-domain-balanced-20260926.json'
    output = ROOT / 'models/experiments/germany-louisiana-domain-balanced-20260926'
    if target.exists() or output.exists():
        raise FileExistsError('Domain-balanced run already exists; refusing to overwrite')
    config = json.loads(source.read_text(encoding='utf-8'))
    config.update(model_id='germany-louisiana-domain-balanced-20260926',
                  output_dir='models/experiments/germany-louisiana-domain-balanced-20260926',
                  epochs=30,
                  test_scope='No test dataset available. Germany validation only; independent test pending.')
    config['sampler'] = {
        'type': 'domain_balanced_positive', 'epoch_size': 400,
        'domain_weights': {'Germany_Training_Public': 1, 'Louisiana-East_Training_Public': 1},
        'inner_positive_aware': {
            'min_fractions': {'has_flooded_building': .25, 'has_flooded_road': .25,
                              'has_building': .5, 'has_road': .5},
            'max_background_fraction': .1,
        },
    }
    target.write_text(json.dumps(config, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(target)


if __name__ == '__main__':
    main()
