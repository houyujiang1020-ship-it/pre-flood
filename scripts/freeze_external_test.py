"""Freeze a labeled SpaceNet8-compatible external test before any model inference.

The tool inspects provenance, pairing, label semantics, file hashes and geographic
overlap. It never loads a model or computes prediction metrics.
"""
import argparse
import csv
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import rasterio
from rasterio.warp import transform_bounds


ROOT = Path(__file__).resolve().parents[1]
CLASSES = ('non_flooded_building', 'flooded_building', 'non_flooded_road', 'flooded_road')
REQUIRED_PROVENANCE = ('dataset_name', 'publisher', 'source_url', 'license_name', 'license_url',
                       'region_id', 'event_id', 'event_date', 'downloaded_at')


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def read_rows(area, post_column):
    table = area / f'{area.name}_label_image_mapping.csv'
    if not table.is_file():
        raise FileNotFoundError('Missing pairing table: ' + str(table))
    with table.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    required = {'label', 'pre-event image', post_column}
    if not rows or not required.issubset(rows[0]):
        raise ValueError('Pairing table lacks required columns: ' + str(table))
    return table, rows


def footprint(path):
    with rasterio.open(path) as image:
        if not image.crs:
            raise ValueError('Image has no CRS: ' + str(path))
        bounds = transform_bounds(image.crs, 'EPSG:4326', *image.bounds, densify_pts=21)
        return [float(value) for value in bounds]


def positive_overlap(a, b, epsilon=1e-10):
    return min(a[2], b[2]) - max(a[0], b[0]) > epsilon and min(a[3], b[3]) - max(a[1], b[1]) > epsilon


def label_support(path):
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict) or not isinstance(value.get('features'), list):
        raise ValueError('Invalid GeoJSON FeatureCollection: ' + str(path))
    counts = dict.fromkeys(CLASSES, 0)
    for feature in value['features']:
        properties = feature.get('properties', {})
        building = properties.get('building') not in (None, '', 'no')
        road = properties.get('highway') not in (None, '')
        if not building and not road:
            continue
        flooded = properties.get('flooded') in ('yes', 1, True)
        counts[('flooded_' if flooded else 'non_flooded_') + ('building' if building else 'road')] += 1
    return counts


def reference_footprints(config_paths, root=ROOT):
    seen, result = set(), []
    for config_path in config_paths:
        config = json.loads(Path(config_path).read_text(encoding='utf-8'))
        for split in ('train', 'validation', 'test'):
            for item in config.get('splits', {}).get(split, []):
                identity = (item['area'], item['label'])
                if identity in seen:
                    continue
                seen.add(identity)
                area = root / config['data_root'] / item['area']
                table, rows = read_rows(area, item.get('post_event_column', 'post-event image 1'))
                row = next((row for row in rows if row['label'] == item['label']), None)
                if row is None:
                    raise ValueError('Reference label absent from pairing table: ' + str(identity))
                pre = area / 'PRE-event' / row['pre-event image']
                result.append({'identity': list(identity), 'pre_sha256': sha256(pre),
                               'bounds_wgs84': footprint(pre), 'pairing_table': str(table)})
    return result


def build_manifest(request, request_path, reference_configs, root=ROOT):
    missing = [key for key in REQUIRED_PROVENANCE if not str(request.get(key, '')).strip()]
    if missing:
        raise ValueError('Missing provenance fields: ' + ', '.join(missing))
    if request.get('labels_available') is not True or request.get('purpose') != 'independent_model_accuracy':
        raise ValueError('A labeled test explicitly reserved for independent_model_accuracy is required')
    provenance_evidence = {}
    for key in ('source_evidence_path', 'license_evidence_path'):
        evidence = Path(request.get(key, '')).expanduser().resolve()
        if not evidence.is_file():
            raise FileNotFoundError('Missing local provenance evidence: ' + key)
        provenance_evidence[key] = {'path': str(evidence), 'sha256': sha256(evidence),
                                    'bytes': evidence.stat().st_size}
    data_root = Path(request['dataset_root']).expanduser().resolve()
    if not data_root.is_dir() or not request.get('areas'):
        raise FileNotFoundError('Dataset root/areas are unavailable')
    checkpoints = request.get('checkpoints', {})
    if set(checkpoints) != {'candidate', 'baseline'}:
        raise ValueError('Exactly candidate and baseline checkpoints must be locked')
    locked_checkpoints = {}
    for role, entry in checkpoints.items():
        path = (root / entry['path']).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        locked_checkpoints[role] = {'model_id': entry['model_id'], 'path': str(path), 'sha256': sha256(path)}
    if locked_checkpoints['candidate']['sha256'] == locked_checkpoints['baseline']['sha256']:
        raise ValueError('Candidate and baseline checkpoints must be distinct')
    references = reference_footprints(reference_configs, root)
    if not references:
        raise ValueError('At least one known development tile is required for overlap auditing')
    reference_hashes = {item['pre_sha256'] for item in references}
    pairs, support = [], dict.fromkeys(CLASSES, 0)
    overlaps = []
    post_column = request.get('post_event_column', 'post-event image 1')
    if post_column not in ('post-event image 1', 'post-event image 2'):
        raise ValueError('Unsupported post_event_column')
    for area_name in request['areas']:
        area = data_root / area_name
        table, rows = read_rows(area, post_column)
        for row in rows:
            if not row.get('label', '').strip() or not row.get('pre-event image', '').strip() or not row.get(post_column, '').strip():
                continue
            files = {
                'label': area / 'annotations' / row['label'],
                'pre': area / 'PRE-event' / row['pre-event image'],
                'post': area / 'POST-event' / row[post_column],
            }
            if not all(path.is_file() for path in files.values()):
                raise FileNotFoundError('Incomplete pair: ' + row['label'])
            bounds = footprint(files['pre'])
            pre_hash = sha256(files['pre'])
            if pre_hash in reference_hashes:
                overlaps.append({'label': row['label'], 'type': 'identical_pre_image'})
            for reference in references:
                if positive_overlap(bounds, reference['bounds_wgs84']):
                    overlaps.append({'label': row['label'], 'type': 'positive_area_intersection',
                                     'reference': reference['identity']})
                    break
            counts = label_support(files['label'])
            for name in CLASSES:
                support[name] += counts[name]
            pairs.append({
                'area': area_name, 'label': row['label'], 'pre_event_image': row['pre-event image'],
                'post_event_image': row[post_column], 'post_event_column': post_column,
                'bounds_wgs84': bounds, 'feature_support': counts,
                'files': {name: {'path': str(path.resolve()), 'sha256': sha256(path), 'bytes': path.stat().st_size}
                          for name, path in files.items()},
                'pairing_table': {'path': str(table.resolve()), 'sha256': sha256(table)},
            })
    if not pairs:
        raise ValueError('No complete labeled pairs found')
    if any(support[name] <= 0 for name in CLASSES):
        raise ValueError('Every class needs labeled feature support: ' + str(support))
    if overlaps:
        raise ValueError('External test spatially overlaps known development data: ' + json.dumps(overlaps[:5]))
    payload = {
        'schema_version': 1, 'status': 'frozen_before_inference',
        'frozen_at': datetime.now(timezone.utc).isoformat(),
        'request_path': str(Path(request_path).resolve()), 'request_sha256': sha256(request_path),
        'provenance': {key: request[key] for key in REQUIRED_PROVENANCE},
        'provenance_evidence': provenance_evidence,
        'purpose': request['purpose'], 'labels_available': True, 'dataset_root': str(data_root),
        'areas': list(request['areas']), 'pair_count': len(pairs), 'feature_support': support,
        'pairs': pairs, 'reference_configs': [{'path': str(Path(path).resolve()), 'sha256': sha256(path)}
                                              for path in reference_configs],
        'reference_tile_count': len(references), 'spatial_overlap_count': 0,
        'checkpoints': locked_checkpoints,
        'evaluation_protocol': {
            'thresholds': dict.fromkeys(CLASSES, .5), 'checkpoint_selection': 'forbidden',
            'threshold_tuning': 'forbidden', 'training_on_test': 'forbidden',
            'comparison': 'candidate versus baseline on identical frozen pairs',
            'research_promotion_rule': 'Candidate IoU and F1 must strictly improve for all four classes.',
            'production_ready_after_evaluation': False,
        },
        'inference_performed': False, 'test_used': False, 'production_ready': False,
    }
    payload['seal_sha256'] = canonical_sha(payload)
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--reference-config', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Frozen manifest already exists: ' + str(args.output))
    request = json.loads(args.request.read_text(encoding='utf-8'))
    manifest = build_manifest(request, args.request, args.reference_config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + '.tmp')
    temporary.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    os.replace(temporary, args.output)
    print(json.dumps({'output': str(args.output), 'pair_count': manifest['pair_count'],
                      'spatial_overlap_count': 0, 'seal_sha256': manifest['seal_sha256']}))


if __name__ == '__main__':
    main()
