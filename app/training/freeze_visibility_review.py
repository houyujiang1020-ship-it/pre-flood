"""Freeze a completed manual visibility review into immutable research configs.

This script never changes the review store. It excludes rejected samples, keeps
the original train/validation boundary, records each human-selected post column,
and prepares cache entries whose identity includes that selected source.
"""
import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(Path(__file__).parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent))

from tools.visibility_review.manifest import Manifest, DEFAULT, digest
from tools.visibility_review.review_store import Store, atomic_json
from tools.visibility_review.validation import integrity
from train_full import CLASSES, pair_cache_key, split_rows
from train_smoke import load_pair
from positive_sampler import PositiveSampler, tile_categories


def freeze_selection(manifest, store):
    summary = store.summary()
    if not summary['review_complete'] or summary['pending'] or summary['needs_review']:
        raise ValueError('Visibility review is incomplete; split cannot be frozen')
    splits = {'train': [], 'validation': [], 'test': []}
    rejected = []
    for sid in sorted(manifest.samples):
        record = store.states[sid]
        sample = manifest.samples[sid]
        if record['decision'] == 'rejected':
            rejected.append(sid)
            continue
        if record['decision'] != 'accepted' or record['selected_post'] not in ('post1', 'post2'):
            raise ValueError('Completed review has invalid final state: ' + sid)
        image = sample['images'][record['selected_post']]
        if not image:
            raise ValueError('Selected post is unavailable: ' + sid)
        column = 'post-event image ' + record['selected_post'][-1]
        splits[sample['split']].append({'area': Path(sample['label']).parent.parent.name,
                                      'label': Path(sample['label']).name,
                                      'post_event_column': column,
                                      'review_sample_id': sid,
                                      'selected_post_sha256': image['sha256']})
    if not splits['train'] or not splits['validation']:
        raise ValueError('Accepted train and validation splits must both be nonempty')
    return splits, rejected


def training_config(splits, cache_dir, output_dir, model_id, sampler=False):
    value = {'model_id': model_id, 'data_root': '11', 'cache_dir': str(cache_dir).replace('/', '\\'),
             'output_dir': str(output_dir).replace('\\', '/'), 'image_size': 512, 'epochs': 40,
             'learning_rate': .0003, 'seed': 20260912, 'device': 'cuda',
             'normalization': 'groupnorm', 'groupnorm_groups': 8,
             'balanced_loss': not sampler, 'dice_weight': .5, 'spatial_augmentation': True,
             'selection_metric': 'macro_iou', 'thresholds': dict.fromkeys(CLASSES, .5),
             'training_authorized': True,
             'test_scope': 'Germany train/validation only. No Louisiana or test split is read for selection.',
             'splits': splits}
    if sampler:
        value['sampler'] = {'type': 'positive_aware', 'epoch_size': len(splits['train']),
                            'min_fractions': {'has_flooded_building': .4, 'has_flooded_road': .4,
                                              'has_building': .6, 'has_road': .6},
                            'max_background_fraction': .1}
    else:
        value.update(positive_weight_exponent=.5, positive_weight_cap=8)
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, default=DEFAULT / 'visibility_manifest.json')
    parser.add_argument('--store', type=Path, default=DEFAULT)
    parser.add_argument('--output', type=Path, default=ROOT / 'experiments/datasets/germany-visibility-frozen-20260912')
    parser.add_argument('--config-a', type=Path, default=ROOT / 'config/training.germany-reviewed-gn-weighted-20260912.json')
    parser.add_argument('--config-b', type=Path, default=ROOT / 'config/training.germany-reviewed-gn-sampler-20260912.json')
    args = parser.parse_args()
    manifest = Manifest(args.manifest)
    store = Store(manifest, args.store)
    checked = integrity(manifest, store, hashes=True)
    if not checked['valid']:
        raise ValueError('Review integrity failed; inspect review_integrity_report.json')
    splits, rejected = freeze_selection(manifest, store)
    if args.output.exists():
        raise FileExistsError('Frozen output already exists; refusing to overwrite: ' + str(args.output))
    if args.config_a.exists() or args.config_b.exists():
        raise FileExistsError('Frozen training config already exists; refusing to overwrite')
    cache = args.output / 'cache512'
    cache.mkdir(parents=True)
    base = {'data_root': '11', 'splits': splits}
    records = split_rows(base, ROOT)
    coverage, created = {name: Counter() for name in ('train', 'validation')}, 0
    sampler_tiles = []
    for split in ('train', 'validation'):
        for area, row in records[split]:
            tensors = load_pair(area, row, 512)
            path = cache / (pair_cache_key(area, row, 512) + '.pt')
            temporary = path.with_suffix('.tmp')
            torch.save(tensors, temporary)
            os.replace(temporary, path)
            created += 1
            categories = tile_categories(area, row, tensors[2], tensors[3])
            for key, value in categories.items():
                if key.startswith('has_') or key == 'background_only':
                    coverage[split][key] += int(value)
            if split == 'train':
                sampler_tiles.append(categories)
    config_a = training_config(splits, cache.relative_to(ROOT),
                               'models/experiments/germany-reviewed-gn-weighted-20260912',
                               'germany-reviewed-gn-weighted-20260912', False)
    config_b = training_config(splits, cache.relative_to(ROOT),
                               'models/experiments/germany-reviewed-gn-sampler-20260912',
                               'germany-reviewed-gn-sampler-20260912', True)
    # Fail before publishing if the declared sampler cannot satisfy its quotas.
    PositiveSampler(sampler_tiles, config_b['sampler'], config_b['seed']).sample(0)
    split_hash = hashlib.sha256(json.dumps(splits, sort_keys=True).encode()).hexdigest()
    freeze = {'schema_version': 1, 'created_at': datetime.now(timezone.utc).isoformat(),
              'training_split_frozen': True, 'review_complete': True,
              'manifest_sha256': manifest.sha256, 'review_state_sha256': digest(store.snapshot),
              'reviews_jsonl_sha256': digest(store.journal), 'review_summary': store.summary(),
              'review_state_path': str(store.snapshot.relative_to(ROOT)).replace('\\', '/'),
              'reviews_jsonl_path': str(store.journal.relative_to(ROOT)).replace('\\', '/'),
              'visibility_manifest_path': str(manifest.path.relative_to(ROOT)).replace('\\', '/'),
              'accepted_counts': {k: len(splits[k]) for k in ('train', 'validation')},
              'rejected_count': len(rejected), 'rejected_sample_ids': rejected,
              'selected_post_counts': dict(Counter(item['post_event_column'] for name in ('train', 'validation') for item in splits[name])),
              'dataset_split_hash': split_hash, 'cache_entries': created,
              'cache_identity': 'pair_cache_key includes area, selected official mapping row, size, and preprocessing SHA256',
              'coverage_tiles': {k: dict(v) for k, v in coverage.items()},
              'selection_policy': 'Human visibility review only; rejected samples excluded; original train/validation boundary retained.',
              'test_policy': 'No test/Louisiana entries in either training config.'}
    config_a['frozen_dataset_manifest'] = str((args.output / 'freeze_manifest.json').relative_to(ROOT)).replace('\\', '/')
    config_a['frozen_dataset_sha256'] = split_hash
    config_b['frozen_dataset_manifest'] = config_a['frozen_dataset_manifest']
    config_b['frozen_dataset_sha256'] = split_hash
    atomic_json(args.output / 'freeze_manifest.json', freeze)
    atomic_json(args.output / 'selected_splits.json', splits)
    atomic_json(args.config_a, config_a)
    atomic_json(args.config_b, config_b)
    print(json.dumps({'frozen': str(args.output), 'accepted': freeze['accepted_counts'],
                      'rejected': len(rejected), 'cache_entries': created,
                      'dataset_split_hash': split_hash, 'coverage_tiles': freeze['coverage_tiles']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
