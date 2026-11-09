"""Prepare compact near-native caches and the E2 crop/tiled research configuration."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app' / 'training'))
import train_full as training  # noqa: E402
from train_smoke import load_pair  # noqa: E402

BASELINE = ROOT / 'config/training.germany-louisiana-domain-balanced-20260926.json'
TARGET = ROOT / 'config/training.germany-louisiana-native-crop-20260926.json'
RUN = ROOT / 'experiments/germany-louisiana-native-crop-20260926'
CACHE = RUN / 'cache1280-compact'
MANIFEST = RUN / 'preparation_manifest.json'
SIZE = 1280


def compact(pair):
    pre, post, labels, valid = pair
    return {'schema': 'compact-pair-v1',
            'pre': (pre * 255).round().clamp(0, 255).to(torch.uint8),
            'post': (post * 255).round().clamp(0, 255).to(torch.uint8),
            'labels': labels.to(torch.uint8), 'valid': valid.to(torch.uint8)}


def write_config():
    baseline = json.loads(BASELINE.read_text(encoding='utf-8'))
    candidate = json.loads(json.dumps(baseline))
    candidate.update(model_id='germany-louisiana-native-crop-20260926',
                     output_dir='models/experiments/germany-louisiana-native-crop-20260926',
                     cache_dir=str(CACHE.relative_to(ROOT)), image_size=SIZE,
                     crop_training={'size': 448, 'positive_probability': .75},
                     tiled_validation={'tile_size': 448, 'stride': 336})
    candidate.pop('ema', None)
    if TARGET.exists():
        current = json.loads(TARGET.read_text(encoding='utf-8'))
        if current != candidate:
            raise FileExistsError('Existing E2 config differs; refusing overwrite')
    else:
        TARGET.write_text(json.dumps(candidate, indent=2) + '\n', encoding='utf-8')
    return baseline, candidate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, help='Prepare only this many missing records for a smoke/resume check')
    args = parser.parse_args()
    baseline, candidate = write_config()
    records = training.split_rows(candidate, ROOT)
    CACHE.mkdir(parents=True, exist_ok=True)
    all_records = records['train'] + records['validation'] + records['test']
    written = skipped = 0
    for index, (area, row) in enumerate(all_records, 1):
        path = CACHE / (training.pair_cache_key(area, row, SIZE) + '.pt')
        if path.exists():
            value = torch.load(path, map_location='cpu', weights_only=True)
            if not isinstance(value, dict) or value.get('schema') != 'compact-pair-v1':
                raise ValueError('Unexpected existing cache schema: ' + str(path))
            skipped += 1
            continue
        if args.limit is not None and written >= args.limit:
            break
        value = compact(load_pair(area, row, SIZE))
        if value['valid'].sum() <= 0 or not all(t.shape[-2:] == (SIZE, SIZE)
                                                for key, t in value.items() if key != 'schema'):
            raise ValueError('Invalid native cache record: ' + row['label'])
        temporary = path.with_suffix('.tmp')
        torch.save(value, temporary)
        temporary.replace(path)
        written += 1
        if written % 10 == 0:
            print(json.dumps({'written_this_run': written, 'skipped': skipped,
                              'processed': index, 'total': len(all_records)}), flush=True)
    complete = len(list(CACHE.glob('*.pt'))) == len(all_records)
    manifest = {'status': 'cache_complete' if complete else 'cache_partial',
                'schema': 'compact-pair-v1', 'size': SIZE,
                'records_expected': len(all_records),
                'records_present': len(list(CACHE.glob('*.pt'))),
                'train_count': len(records['train']), 'validation_count': len(records['validation']),
                'test_count': len(records['test']),
                'baseline_config_sha256': hashlib.sha256(BASELINE.read_bytes()).hexdigest(),
                'candidate_config_sha256': hashlib.sha256(TARGET.read_bytes()).hexdigest(),
                'split_sha256': hashlib.sha256(json.dumps(candidate['splits'], sort_keys=True).encode()).hexdigest(),
                'cache_note': 'RGB stored uint8; labels/valid uint8. Post reprojection is rounded after bilinear alignment.',
                'test_used': False, 'production_ready': False}
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps(manifest), flush=True)
    if not complete and args.limit is None:
        raise RuntimeError('Native cache preparation did not complete')


if __name__ == '__main__':
    main()
