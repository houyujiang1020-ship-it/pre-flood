"""Create the preregistered EMA-only follow-up to the domain-balanced research run."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'config/training.germany-louisiana-domain-balanced-20260926.json'
TARGET = ROOT / 'config/training.germany-louisiana-domain-balanced-ema-20260926.json'
MANIFEST = ROOT / 'experiments/germany-louisiana-domain-balanced-ema-20260926/preregistration.json'


def main():
    baseline = json.loads(SOURCE.read_text(encoding='utf-8'))
    candidate = json.loads(json.dumps(baseline))
    candidate['model_id'] = 'germany-louisiana-domain-balanced-ema-20260926'
    candidate['output_dir'] = 'models/experiments/germany-louisiana-domain-balanced-ema-20260926'
    candidate['ema'] = {'enabled': True, 'decay': 0.999}
    allowed = {'model_id', 'output_dir', 'ema'}
    changed = {key for key in set(baseline) | set(candidate) if baseline.get(key) != candidate.get(key)}
    if changed != allowed:
        raise AssertionError(f'EMA experiment changed unexpected fields: {sorted(changed)}')
    TARGET.write_text(json.dumps(candidate, indent=2), encoding='utf-8')
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        'status': 'preregistered_before_training',
        'experiment': candidate['model_id'],
        'single_variable': 'EMA weights updated after every optimizer step with decay=0.999; validation and best checkpoint use EMA weights',
        'baseline_config': str(SOURCE.relative_to(ROOT)),
        'candidate_config': str(TARGET.relative_to(ROOT)),
        'baseline_config_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'unchanged': ['splits', 'cache', 'sampler', 'architecture', 'normalization', 'loss',
                      'learning_rate', 'epochs', 'augmentation', 'selection_metric', 'thresholds'],
        'promotion_rule': ('Fixed-0.5 Germany validation macro IoU must exceed 0.14389857929199934; '
                           'at least three of four class IoUs must not decline by more than 0.005. '
                           'Result remains research-only until independent test.'),
        'test_used': False,
        'production_ready': False,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps(manifest))


if __name__ == '__main__':
    main()
