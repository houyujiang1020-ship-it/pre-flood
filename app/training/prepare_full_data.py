"""Audit user-extracted official pairs and freeze a region-held-out research run."""
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio
import torch
from train_smoke import load_pair
from train_full import CLASSES, pair_cache_key


def main():
    root = Path(__file__).resolve().parents[2]
    data = root / '11'
    out = root / 'data/processed/full-audit-20260830'
    cache = out / 'cache512'
    out.mkdir(parents=True, exist_ok=True)
    cache.mkdir(exist_ok=True)
    config_path = root / 'config/training.full-germany-20260830.json'
    if config_path.exists():
        raise FileExistsError('Frozen config already exists; no overwrite: ' + str(config_path))
    inventory, records = [], {}
    for name in ['Germany_Training_Public', 'Louisiana-East_Training_Public']:
        area = data / name
        rows = list(csv.DictReader((area / (name + '_label_image_mapping.csv')).open(encoding='utf-8-sig')))
        if len({r['label'] for r in rows}) != len(rows):
            raise ValueError('Duplicate label identities: ' + name)
        records[name] = []
        for i, row in enumerate(rows):
            files = []
            for column, folder in [('label', 'annotations'), ('pre-event image', 'PRE-event'),
                                   ('post-event image 1', 'POST-event'), ('post-event image 2', 'POST-event')]:
                filename = row.get(column, '').strip()
                if not filename and column == 'post-event image 2':
                    continue
                if not filename or Path(filename).name != filename:
                    raise ValueError('Unsafe or empty pairing entry')
                path = area / folder / filename
                digest = hashlib.sha256()
                with path.open('rb') as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                        digest.update(chunk)
                files.append({'path': str(path.relative_to(root)), 'bytes': path.stat().st_size,
                              'sha256': digest.hexdigest()})
                if folder != 'annotations':
                    with rasterio.open(path) as src:
                        if src.crs is None or src.count < 3:
                            raise ValueError('Missing CRS or RGB bands: ' + str(path))
                        src.read([1, 2, 3])  # Exercise all RGB blocks, not just TIFF headers.
            tensors = load_pair(area, row, 512)
            if not all(torch.isfinite(t).all() for t in tensors) or tensors[3].sum() <= 0:
                raise ValueError('Nonfinite or empty valid supervision: ' + row['label'])
            counts = (tensors[2] * tensors[3].unsqueeze(0)).sum((1, 2)).tolist()
            with rasterio.open(area / 'PRE-event' / row['pre-event image']) as src:
                center_x = (src.bounds.left + src.bounds.right) / 2
                bounds = list(src.bounds)
                crs = str(src.crs)
            path = cache / (pair_cache_key(area, row, 512) + '.pt')
            temporary = path.with_suffix('.tmp')
            torch.save(tensors, temporary)
            temporary.replace(path)
            item = {'area': name, 'label': row['label'], 'center_x': center_x,
                    'bounds': bounds, 'crs': crs, 'positive_pixels': counts, 'files': files}
            inventory.append(item)
            records[name].append(item)
            if (i + 1) % 10 == 0:
                print(json.dumps({'area': name, 'audited': i + 1, 'total': len(rows)}), flush=True)
    germany = sorted(records['Germany_Training_Public'], key=lambda x: (x['center_x'], x['label']))
    cut = germany[int(len(germany) * .8)]['bounds'][0]
    # Hold the eastern strip out, and exclude straddling tiles to avoid shared pixels.
    train = [r for r in germany if r['bounds'][2] < cut]
    val = [r for r in germany if r['bounds'][0] >= cut]
    excluded = [r for r in germany if r not in train and r not in val]
    splits = {'train': train, 'validation': val, 'test': records['Louisiana-East_Training_Public']}
    coverage = {k: np.asarray([r['positive_pixels'] for r in v]).sum(0).tolist() for k, v in splits.items()}
    if any(not v or any(n <= 0 for n in coverage[k]) for k, v in splits.items()):
        raise ValueError('A spatial split lacks samples or classes: ' + str(coverage))
    audit = {'source': str(data), 'size': 512, 'inventory': inventory,
             'excluded_buffer_tiles': [r['label'] for r in excluded],
             'counts': {k: len(v) for k, v in splits.items()}, 'class_order': CLASSES,
             'coverage': coverage, 'test_note': 'Louisiana is region-held-out for this run; two tiles were examined in earlier research, so this is not a blind benchmark.'}
    audit_path = out / 'audit.json'
    audit_path.write_text(json.dumps(audit, indent=2), encoding='utf-8')
    config = {'data_root': '11', 'cache_dir': str(cache.relative_to(root)),
              'source_audit_sha256': hashlib.sha256(audit_path.read_bytes()).hexdigest(),
              'output_dir': 'models/checkpoints/full-germany-20260830', 'image_size': 512,
              'epochs': 40, 'learning_rate': .0003, 'seed': 42, 'device': 'cuda',
              'balanced_loss': True, 'dice_weight': .5, 'spatial_augmentation': True,
              'test_scope': audit['test_note'],
              'splits': {k: [{'area': r['area'], 'label': r['label']} for r in v] for k, v in splits.items()}}
    with config_path.open('x', encoding='utf-8') as stream:
        json.dump(config, stream, indent=2)
    print(json.dumps({'config': str(config_path), 'counts': audit['counts'], 'coverage': coverage}), flush=True)


if __name__ == '__main__':
    main()
