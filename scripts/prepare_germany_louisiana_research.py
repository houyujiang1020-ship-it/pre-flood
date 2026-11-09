"""Prepare an isolated Germany + Louisiana-East research run without test data."""
import csv
import hashlib
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app' / 'training'))
from train_full import pair_cache_key  # noqa: E402


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def main():
    base_path = ROOT / 'config/training.germany-reviewed-gn-sampler-20260912.json'
    selected_path = ROOT / 'experiments/datasets/germany-visibility-frozen-20260912/selected_splits.json'
    freeze_path = ROOT / 'experiments/datasets/germany-visibility-frozen-20260912/freeze_manifest.json'
    audit_path = ROOT / 'data/processed/full-audit-20260830/audit.json'
    config_path = ROOT / 'config/training.germany-louisiana-east-research-20260916.json'
    manifest_path = ROOT / 'experiments/datasets/germany-louisiana-east-research-20260916/manifest.json'
    cache = manifest_path.parent / 'cache512'
    if config_path.exists() or manifest_path.exists():
        raise FileExistsError('Research configuration already exists; refusing to overwrite')

    base = json.loads(base_path.read_text(encoding='utf-8'))
    selected = json.loads(selected_path.read_text(encoding='utf-8'))
    frozen = json.loads(freeze_path.read_text(encoding='utf-8'))
    audit = json.loads(audit_path.read_text(encoding='utf-8'))
    assert frozen['training_split_frozen'] and frozen['review_complete']
    assert len(selected['train']) == 98 and len(selected['validation']) == 18
    assert selected == base['splits']
    assert frozen['dataset_split_hash'] == base['frozen_dataset_sha256']
    assert digest(audit_path) == 'a26a81a12c14659d6ad2ea68a4d9133123363efe14083db670cd78e9a5ff1ad9'

    area_name = 'Louisiana-East_Training_Public'
    area = ROOT / '11' / area_name
    mapping = area / f'{area_name}_label_image_mapping.csv'
    with mapping.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    evidence = {item['label']: item for item in audit['inventory'] if item['area'] == area_name}
    assert len(rows) == len(evidence) == 599
    labels = set()
    louisiana = []
    for row in rows:
        label = row['label']
        if label in labels or label not in evidence:
            raise ValueError('Duplicate or unaudited Louisiana label: ' + label)
        labels.add(label)
        for file in evidence[label]['files']:
            path = ROOT / file['path']
            if not path.is_file() or path.stat().st_size != file['bytes'] or digest(path) != file['sha256']:
                raise ValueError('Louisiana audit file changed: ' + str(path))
        louisiana.append({'area': area_name, 'label': label, 'post_event_column': 'post-event image 1'})
    louisiana.sort(key=lambda item: item['label'])
    train = selected['train'] + louisiana
    validation = selected['validation']
    identities = [(item['area'], item['label']) for item in train + validation]
    if len(set(identities)) != len(identities):
        raise ValueError('Train/validation identity overlap')
    if any(item['area'] != 'Germany_Training_Public' for item in validation):
        raise ValueError('Germany validation boundary changed')

    new = dict(base)
    new.update(model_id='germany-louisiana-east-research-20260916',
               output_dir='models/experiments/germany-louisiana-east-research-20260916',
               cache_dir=str(cache.relative_to(ROOT)), epochs=30,
               test_scope='No test dataset available. Test remains empty; independent evaluation pending.',
               splits={'train': train, 'validation': validation, 'test': []},
               source_audit_sha256=digest(audit_path))
    new.pop('frozen_dataset_manifest', None)
    new.pop('frozen_dataset_sha256', None)
    new['sampler'] = dict(type='positive_aware', epoch_size=400,
                          min_fractions={'has_flooded_building': .25, 'has_flooded_road': .25,
                                         'has_building': .5, 'has_road': .5},
                          max_background_fraction=.1)
    new['balanced_loss'] = False
    new['training_authorized'] = True

    sources = [(ROOT / 'experiments/datasets/germany-visibility-frozen-20260912/cache512',
                train[:98] + validation),
               (ROOT / 'data/processed/full-audit-20260830/cache512', louisiana)]
    cache.mkdir(parents=True, exist_ok=True)
    linked = 0
    for source, entries in sources:
        for item in entries:
            selected_area = ROOT / '11' / item['area']
            table = selected_area / f"{item['area']}_label_image_mapping.csv"
            with table.open(encoding='utf-8-sig', newline='') as stream:
                row = next(row for row in csv.DictReader(stream) if row['label'] == item['label'])
            if item.get('post_event_column') == 'post-event image 2':
                row['post-event image 1'] = row['post-event image 2']
            filename = pair_cache_key(selected_area, row, 512) + '.pt'
            original = source / filename
            target = cache / filename
            if not original.is_file():
                raise FileNotFoundError(original)
            if not target.exists():
                os.link(original, target)
                linked += 1
    split_hash = hashlib.sha256(json.dumps(new['splits'], sort_keys=True).encode()).hexdigest()
    manifest = {'schema_version': 1, 'status': 'research_only', 'train_count': len(train),
                'germany_train_count': 98, 'louisiana_east_train_count': 599,
                'germany_validation_count': 18, 'test_count': 0,
                'germany_frozen_split_sha256': frozen['dataset_split_hash'],
                'louisiana_source_audit_sha256': digest(audit_path),
                'new_split_sha256': split_hash,
                'test_note': 'No independent test yet; Louisiana prior research evaluation is retired for this candidate.',
                'quality_note': 'All Louisiana files match prior full audit; no new visual visibility review is claimed.',
                'sampling_note': '400 appearances/epoch with replacement, not 400 unique samples.'}
    config_path.write_text(json.dumps(new, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'config': str(config_path), 'manifest': str(manifest_path),
                      'cache_entries': len(list(cache.glob('*.pt'))), 'new_links': linked,
                      'split_sha256': split_hash}))


if __name__ == '__main__':
    main()
