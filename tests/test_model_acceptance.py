import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('model_acceptance', ROOT/'scripts/verify_model_acceptance.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write(path, value):
    path.write_text(json.dumps(value), encoding='utf-8')
    return path


def fixture(tmp_path):
    checkpoint = tmp_path/'weights.pth'
    checkpoint.write_bytes(b'research-test-identity-only')
    digest = module.sha256(checkpoint)
    metrics = {m: {c: .8 for c in module.CLASSES} for m in module.METRICS}
    metrics['truth_pixels'] = {c: 10 for c in module.CLASSES}
    comparison = write(tmp_path/'comparison.json', {'independent_region_test': True, 'results': {
        'candidate': {'checkpoint_sha256': digest, 'evaluation': metrics},
        'baseline': {'checkpoint_sha256': 'different', 'evaluation': {
            m: {c: .2 for c in module.CLASSES} for m in module.METRICS}}}})
    evidence = write(tmp_path/'visual.json', {'fixture': True})
    reviews = write(tmp_path/'reviews.json', {'checkpoint_sha256': digest, **{
        k: {'passed': True, 'reviewer': 'TEST ONLY', 'validated_at': '2026-08-30', 'evidence': [evidence.name]}
        for k in ('visual_quality', 'minority_precision_recall', 'stability')}})
    return checkpoint, comparison, reviews


def test_research_never_promotes_without_approved_thresholds(tmp_path):
    checkpoint, comparison, reviews = fixture(tmp_path)
    result = module.verify(ROOT/'config/model_acceptance.yaml', comparison, 'candidate', 'baseline', checkpoint, reviews)
    assert result['research_candidate']
    assert not result['production_candidate']
    assert not result['production_ready'] and not result['promotion_performed']


def test_missing_review_and_checkpoint_mismatch_fail_closed(tmp_path):
    checkpoint, comparison, reviews = fixture(tmp_path)
    checkpoint.write_bytes(b'changed')
    (tmp_path/'visual.json').unlink()
    result = module.verify(ROOT/'config/model_acceptance.yaml', comparison, 'candidate', 'baseline', checkpoint, reviews)
    failed = {c['name'] for c in result['checks'] if not c['passed']}
    assert {'checkpoint_identity', 'visual_quality', 'stability'} <= failed
    assert not result['research_candidate']


def test_absent_minority_class_and_nan_not_accepted(tmp_path):
    checkpoint, comparison, reviews = fixture(tmp_path)
    value = json.loads(comparison.read_text())
    evaluation = value['results']['candidate']['evaluation']
    evaluation['truth_pixels']['flooded_building'] = 0
    evaluation['class_precision']['flooded_road'] = float('nan')
    write(comparison, value)
    result = module.verify(ROOT/'config/model_acceptance.yaml', comparison, 'candidate', 'baseline', checkpoint, reviews)
    failed = {c['name'] for c in result['checks'] if not c['passed']}
    assert {'class_support', 'complete_metrics'} <= failed


def test_malformed_inputs_fail_closed(tmp_path):
    bad = write(tmp_path/'bad.json', [])
    result = module.verify(bad, bad, 'candidate', 'baseline', tmp_path/'missing.pth')
    assert not result['production_candidate'] and not result['research_candidate']

