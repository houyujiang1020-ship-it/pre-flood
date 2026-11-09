"""Freeze an unlabeled SpaceNet8 test for one-time blind inference, never IoU."""
import argparse
import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path

try:
    from freeze_external_test import (ROOT, canonical_sha, footprint, positive_overlap,
                                      reference_footprints, sha256)
except ModuleNotFoundError:  # Imported as scripts.freeze_unlabeled_external_test in tests.
    from scripts.freeze_external_test import (ROOT, canonical_sha, footprint, positive_overlap,
                                              reference_footprints, sha256)


def build_manifest(request, request_path, reference_configs, root=ROOT):
    required = ('dataset_name', 'publisher', 'source_url', 'license_name', 'license_url',
                'region_id', 'event_id', 'event_date', 'downloaded_at', 'archive_path',
                'archive_sha256', 'dataset_root', 'area_name')
    missing = [key for key in required if not str(request.get(key, '')).strip()]
    if missing:
        raise ValueError('Missing fields: ' + ', '.join(missing))
    if request.get('labels_available') is not False or request.get('purpose') != 'blind_inference_only':
        raise ValueError('This protocol is only for explicitly unlabeled blind inference')
    archive = Path(request['archive_path']).resolve()
    if not archive.is_file() or sha256(archive).lower() != request['archive_sha256'].lower():
        raise ValueError('Archive identity differs')
    data_root = Path(request['dataset_root']).resolve()
    if not data_root.is_dir():
        raise FileNotFoundError(data_root)
    evidence = {}
    for key in ('source_evidence_path', 'license_evidence_path'):
        path = Path(request.get(key, '')).resolve()
        if not path.is_file():
            raise FileNotFoundError('Missing provenance evidence: ' + key)
        evidence[key] = {'path': str(path), 'sha256': sha256(path), 'bytes': path.stat().st_size}
    checkpoint_path = (root / request['checkpoint']['path']).resolve()
    if not checkpoint_path.is_file():
        raise FileNotFoundError(checkpoint_path)
    table = data_root / f"{request['area_name']}_label_image_mapping.csv"
    with table.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    post_column = 'post-event image 1'
    references = reference_footprints(reference_configs, root)
    if not references:
        raise ValueError('Reference footprint catalog is empty')
    reference_hashes = {item['pre_sha256'] for item in references}
    pairs, overlaps = [], []
    for row in rows:
        if not all(row.get(key, '').strip() for key in ('label', 'pre-event image', post_column)):
            raise ValueError('Incomplete official pairing row')
        pre = data_root / 'PRE-event' / row['pre-event image']
        post = data_root / 'POST-event' / row[post_column]
        if not pre.is_file() or not post.is_file():
            raise FileNotFoundError('Incomplete image pair: ' + row['label'])
        pre_hash, bounds = sha256(pre), footprint(pre)
        if pre_hash in reference_hashes:
            overlaps.append({'label': row['label'], 'type': 'identical_pre_image'})
        for reference in references:
            if positive_overlap(bounds, reference['bounds_wgs84']):
                overlaps.append({'label': row['label'], 'type': 'positive_area_intersection',
                                 'reference': reference['identity']})
                break
        pairs.append({'label': row['label'], 'pre_event_image': row['pre-event image'],
                      'post_event_image': row[post_column], 'bounds_wgs84': bounds,
                      'pre': {'path': str(pre), 'sha256': pre_hash, 'bytes': pre.stat().st_size},
                      'post': {'path': str(post), 'sha256': sha256(post), 'bytes': post.stat().st_size}})
    if overlaps:
        raise ValueError('Test overlaps known development imagery: ' + json.dumps(overlaps[:5]))
    if len(pairs) < 20:
        raise ValueError('Unlabeled test is unexpectedly small')
    ordered = sorted(pair['label'] for pair in pairs)
    indices = [round(i * (len(ordered) - 1) / 11) for i in range(12)]
    payload = {
        'schema_version': 1, 'status': 'frozen_before_blind_inference',
        'frozen_at': datetime.now(timezone.utc).isoformat(),
        'request_path': str(Path(request_path).resolve()), 'request_sha256': sha256(request_path),
        'provenance': {key: request[key] for key in required if key not in ('archive_path', 'archive_sha256',
                                                                            'dataset_root', 'area_name')},
        'provenance_evidence': evidence,
        'archive': {'path': str(archive), 'sha256': sha256(archive), 'bytes': archive.stat().st_size},
        'dataset_root': str(data_root), 'area_name': request['area_name'],
        'pairing_table': {'path': str(table), 'sha256': sha256(table), 'bytes': table.stat().st_size},
        'pair_count': len(pairs), 'pairs': pairs,
        'reference_configs': [{'path': str(Path(path).resolve()), 'sha256': sha256(path)}
                              for path in reference_configs],
        'reference_tile_count': len(references), 'spatial_overlap_count': 0,
        'checkpoint': {'model_id': request['checkpoint']['model_id'], 'path': str(checkpoint_path),
                       'sha256': sha256(checkpoint_path)},
        'protocol': {'post_event_column': post_column, 'thresholds': dict.fromkeys(
                         ('non_flooded_building', 'flooded_building', 'non_flooded_road', 'flooded_road'), .5),
                     'image_size': 512, 'visual_sample_rule': '12 evenly spaced sorted label identities',
                     'visual_sample_labels': [ordered[index] for index in indices],
                     'model_tuning_after_test': 'forbidden', 'iou_available': False},
        'labels_available': False, 'inference_performed': False, 'accuracy_verified': False,
        'test_used': False, 'production_ready': False,
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
        raise FileExistsError('Manifest already exists: ' + str(args.output))
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
