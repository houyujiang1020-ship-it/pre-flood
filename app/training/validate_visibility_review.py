"""Validate review decisions against an immutable visibility manifest."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--review', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    review = json.loads(args.review.read_text(encoding='utf-8'))
    available = {(e['split'], e['label']): e for e in manifest['entries']}
    seen, counts = set(), {'reject': 0, 'post-event image 1': 0, 'post-event image 2': 0}
    for decision in review['decisions']:
        key = decision['split'], decision['label']
        if key in seen or key not in available:
            raise ValueError('Duplicate or unknown review entry: ' + str(key))
        seen.add(key)
        value = decision['decision']
        if value not in counts or not decision.get('reason'):
            raise ValueError('Invalid decision or missing reason: ' + str(key))
        if value.startswith('post-event') and value not in {p['column'] for p in available[key]['post_candidates']}:
            raise ValueError('Selected post candidate is absent: ' + str(key))
        counts[value] += 1
    evidence = args.review.parent / review['evidence']
    if not evidence.is_file():
        raise FileNotFoundError(evidence)
    result = {'valid': True, 'reviewed': len(seen), 'total': len(available),
              'complete': len(seen) == len(available), 'pending': len(available)-len(seen),
              'counts': counts, 'reviewer': review.get('reviewer'), 'reviewed_at': review.get('reviewed_at'),
              'evidence': str(evidence.resolve()),
              'training_split_frozen': False,
              'warning': 'Partial review cannot authorize a full training split.'}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
