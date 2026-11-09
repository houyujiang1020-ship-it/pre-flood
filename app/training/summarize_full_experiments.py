"""Summarize recorded research results; never choose or deploy a model."""
import hashlib
import json
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[2]
    results = {}
    for name in ('full-germany-20260830', 'full-germany-tempered-20260830'):
        folder = root / 'models/checkpoints' / name
        for report_name in ('training_report.json', 'calibration.json'):
            path = folder / report_name
            report = json.loads(path.read_text(encoding='utf-8'))
            evaluation = report['test']
            results[name + '/' + report_name] = {
                'report': str(path.relative_to(root)),
                'report_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'tile_count': evaluation['tile_count'],
                'class_iou': evaluation['class_iou'],
                'class_f1': evaluation['class_f1'],
                'macro_iou': sum(evaluation['class_iou'].values()) / 4,
                'thresholds': report.get('thresholds', 'uniform 0.5'),
            }
    summary = {
        'production_ready': False, 'accuracy_acceptance_passed': False,
        'deployment_changed': False,
        'scope': 'Repeated Louisiana research benchmark, not blind final acceptance. '
                 'Checkpoints/thresholds selected on Germany validation only. '
                 'No model is selected from this test comparison.',
        'results': results,
    }
    out = root / 'models/checkpoints/full-comparison-20260830.json'
    with out.open('x', encoding='utf-8') as stream:
        json.dump(summary, stream, indent=2)
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
