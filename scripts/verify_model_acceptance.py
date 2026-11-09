"""Offline, read-only acceptance of recorded evaluation and review evidence.

Does not run training/inference or promote a checkpoint. Exit 2 means the
production gate is closed; a research review may still pass. Evidence paths
are relative to their containing JSON/YAML file. Missing metrics never mean 0.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

import yaml

CLASSES = ('non_flooded_building', 'flooded_building', 'non_flooded_road', 'flooded_road')
METRICS = ('class_iou', 'class_f1', 'class_precision', 'class_recall')
ROOT = Path(__file__).resolve().parents[1]


def read_object(path):
    try:
        value = yaml.safe_load(Path(path).read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, yaml.YAMLError):
        return {}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def verify(config, comparison, candidate, baseline, checkpoint, reviews=None):
    config, comparison, checkpoint = map(Path, (config, comparison, checkpoint))
    policy, report = read_object(config), read_object(comparison)
    reviews_path = Path(reviews) if reviews else None
    review = read_object(reviews_path) if reviews_path else {}
    results = report.get('results', {})
    results = results if isinstance(results, dict) else {}
    current, reference = results.get(candidate, {}), results.get(baseline, {})
    def expand(entry):
        if not isinstance(entry, dict) or not isinstance(entry.get('report'), str):
            return entry
        source = ROOT / entry['report']
        try:
            if sha256(source) != entry.get('report_sha256'):
                return {}
        except OSError:
            return {}
        data = read_object(source)
        return {'checkpoint_sha256': data.get('checkpoint_sha256'), 'evaluation': data.get('test', {})}
    current, reference = expand(current), expand(reference)
    current = current if isinstance(current, dict) else {}
    reference = reference if isinstance(reference, dict) else {}
    metrics, old = current.get('evaluation', {}), reference.get('evaluation', {})
    metrics = metrics if isinstance(metrics, dict) else {}
    old = old if isinstance(old, dict) else {}
    checks = []

    def check(name, passed, note):
        checks.append({'name': name, 'passed': bool(passed), 'notes': note})

    try:
        actual_hash = sha256(checkpoint)
    except OSError:
        actual_hash = None
    check('checkpoint_identity', actual_hash and actual_hash == current.get('checkpoint_sha256'),
          'Local checkpoint SHA256 must equal evaluation identity.')
    check('distinct_baseline', candidate != baseline and bool(reference.get('checkpoint_sha256'))
          and current.get('checkpoint_sha256') != reference.get('checkpoint_sha256'),
          'A distinct evaluated baseline is required.')
    support = metrics.get('truth_pixels', {})
    check('class_support', isinstance(support, dict) and all(number(support.get(c)) and support[c] > 0 for c in CLASSES),
          'Every class needs ground-truth support; absent flooded buildings are not accepted as perfect.')
    complete = all(isinstance(metrics.get(m), dict) and all(number(metrics[m].get(c))
                   and 0 <= metrics[m][c] <= 1 for c in CLASSES) for m in METRICS)
    check('complete_metrics', complete, 'All four classes require finite IoU, F1, precision and recall.')
    improved = all(isinstance(metrics.get(m), dict) and isinstance(old.get(m), dict)
                   and all(number(metrics[m].get(c)) and number(old[m].get(c))
                           and metrics[m][c] > old[m][c] for c in CLASSES)
                   for m in ('class_iou', 'class_f1'))
    check('baseline_improvement', improved, 'Conservative research screen: each class IoU/F1 improves; no production threshold is inferred.')
    for name in ('visual_quality', 'minority_precision_recall', 'stability'):
        entry = review.get(name, {})
        entry = entry if isinstance(entry, dict) else {}
        refs = entry.get('evidence', [])
        exists = isinstance(refs, list) and bool(refs) and all(isinstance(p, str) and bool(p)
                   and (reviews_path.parent / p).is_file() for p in refs) if reviews_path else False
        check(name, exists and entry.get('passed') is True and bool(entry.get('reviewer'))
              and bool(entry.get('validated_at')) and review.get('checkpoint_sha256') == actual_hash and actual_hash,
              'Signed/datable review with existing evidence must refer to this checkpoint.')
    research_pass = all(c['passed'] for c in checks)
    prod = policy.get('production_candidate', {})
    prod = prod if isinstance(prod, dict) else {}
    approval_ref = prod.get('approval_evidence')
    approval_path = config.parent / approval_ref if isinstance(approval_ref, str) and approval_ref else None
    approval = read_object(approval_path) if approval_path else {}
    thresholds = prod.get('thresholds')
    valid_thresholds = isinstance(thresholds, dict) and all(isinstance(thresholds.get(m), dict)
                       and all(number(thresholds[m].get(c)) and 0 < thresholds[m][c] <= 1 for c in CLASSES)
                       for m in METRICS)
    check('approved_formal_thresholds', valid_thresholds and prod.get('approved') is True
          and approval.get('approved') is True and bool(approval.get('approved_by'))
          and bool(approval.get('approved_at')) and approval.get('thresholds') == thresholds,
          'Formal approval evidence must bind the exact configured thresholds. Null/unapproved means blocked.')
    check('independent_region', report.get('independent_region_test') is True,
          'Independent-region provenance must be supplied by the evaluator; not inferred from file name.')
    threshold_pass = valid_thresholds and complete and all(metrics[m][c] >= thresholds[m][c] for m in METRICS for c in CLASSES)
    check('formal_metrics', threshold_pass, 'All approved class thresholds must pass.')
    return {'schema_version': 1, 'validated_at': datetime.now(timezone.utc).isoformat(),
            'research_candidate': research_pass, 'production_candidate': all(c['passed'] for c in checks),
            'production_ready': False, 'promotion_performed': False,
            'checkpoint_sha256': actual_hash, 'candidate': candidate, 'baseline': baseline,
            'evidence': [str(config.resolve()), str(comparison.resolve()), str(checkpoint.resolve())],
            'checks': checks, 'notes': 'Offline evidence screen only; never modifies model/service metadata or grants deployment approval.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT/'config/model_acceptance.yaml')
    parser.add_argument('--comparison', type=Path, required=True)
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--baseline', required=True)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--reviews', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = verify(args.config, args.comparison, args.candidate, args.baseline, args.checkpoint, args.reviews)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True))
    raise SystemExit(0 if report['production_candidate'] else 2)


if __name__ == '__main__':
    main()
