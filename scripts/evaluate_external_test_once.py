"""Evaluate two locked checkpoints once on a frozen external test manifest.

The command refuses an existing output, verifies every frozen hash and uses only
the preregistered fixed thresholds. It never trains, selects epochs or calibrates.
"""
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app' / 'training'))
import train_full as training  # noqa: E402
from model_factory import build_siamunet  # noqa: E402


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def verify_manifest(path):
    manifest = json.loads(path.read_text(encoding='utf-8'))
    seal = manifest.pop('seal_sha256', None)
    if seal != canonical_sha(manifest):
        raise ValueError('Frozen manifest seal differs')
    manifest['seal_sha256'] = seal
    if manifest.get('status') != 'frozen_before_inference' or manifest.get('inference_performed') is not False:
        raise ValueError('Manifest was not frozen before inference')
    if manifest.get('spatial_overlap_count') != 0 or manifest.get('labels_available') is not True:
        raise ValueError('Independent labeled-test requirements are not satisfied')
    for item in manifest['reference_configs']:
        if sha256(item['path']) != item['sha256']:
            raise ValueError('Reference config changed after freeze: ' + item['path'])
    for item in manifest['provenance_evidence'].values():
        file = Path(item['path'])
        if not file.is_file() or file.stat().st_size != item['bytes'] or sha256(file) != item['sha256']:
            raise ValueError('Provenance evidence changed after freeze: ' + str(file))
    for role, item in manifest['checkpoints'].items():
        if sha256(item['path']) != item['sha256']:
            raise ValueError('Locked checkpoint changed: ' + role)
    for pair in manifest['pairs']:
        for item in pair['files'].values():
            file = Path(item['path'])
            if not file.is_file() or file.stat().st_size != item['bytes'] or sha256(file) != item['sha256']:
                raise ValueError('Frozen test file changed: ' + str(file))
        table = pair['pairing_table']
        if sha256(table['path']) != table['sha256']:
            raise ValueError('Pairing table changed after freeze: ' + table['path'])
    return manifest


def records_from_manifest(manifest):
    result = []
    for pair in manifest['pairs']:
        area = Path(manifest['dataset_root']) / pair['area']
        result.append((area, {
            'label': pair['label'], 'pre-event image': pair['pre_event_image'],
            'post-event image 1': pair['post_event_image'],
        }))
    return result


def evaluate_checkpoint(entry, records, device, image_size):
    checkpoint_path = Path(entry['path'])
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=True)
    if checkpoint.get('architecture') != 'SiamUnet_diff' or checkpoint.get('classes') != training.CLASSES:
        raise ValueError('Unsupported checkpoint identity: ' + entry['model_id'])
    normalization = checkpoint.get('normalization', 'batchnorm')
    groups = int(checkpoint.get('groupnorm_groups') or 8)
    source = ROOT / 'upstream/SpaceNet8/baseline/models/other/siamunetdif.py'
    model = build_siamunet(source, normalization, groups).to(device)
    model.load_state_dict(checkpoint['state_dict'])
    activation = checkpoint.get('output_activation') or 'sigmoid'
    metrics = training.evaluate(model, records, image_size, device, thresholds=[.5] * 4,
                                activation=activation)
    del model
    if device == 'cuda':
        torch.cuda.empty_cache()
    return {'checkpoint': str(checkpoint_path), 'checkpoint_sha256': entry['sha256'],
            'checkpoint_epoch': checkpoint.get('epoch'), 'output_activation': activation,
            'evaluation': metrics}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--device', choices=('cpu', 'cuda'), default='cuda')
    parser.add_argument('--image-size', type=int, default=512)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('External test was already evaluated: ' + str(args.output))
    if args.image_size != 512:
        raise ValueError('The preregistered evaluation image size is fixed at 512')
    if args.device == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('CUDA requested but unavailable')
    manifest = verify_manifest(args.manifest)
    training.DISK_CACHE = None
    training._cached_pair.cache_clear()
    records = records_from_manifest(manifest)
    results = {role: evaluate_checkpoint(entry, records, args.device, args.image_size)
               for role, entry in manifest['checkpoints'].items()}
    candidate = results['candidate']['evaluation']
    baseline = results['baseline']['evaluation']
    deltas = {metric: {name: candidate[metric][name] - baseline[metric][name]
                       if candidate[metric][name] is not None and baseline[metric][name] is not None else None
                       for name in training.CLASSES}
              for metric in ('class_iou', 'class_f1', 'class_precision', 'class_recall')}
    research_pass = all(deltas[metric][name] is not None and deltas[metric][name] > 0
                        for metric in ('class_iou', 'class_f1') for name in training.CLASSES)
    report = {
        'schema_version': 1, 'status': 'completed',
        'evaluated_at': datetime.now(timezone.utc).isoformat(),
        'manifest': str(args.manifest.resolve()), 'manifest_sha256': sha256(args.manifest),
        'manifest_seal_sha256': manifest['seal_sha256'],
        'independent_region_test': True, 'pair_count': len(records),
        'fixed_thresholds': dict.fromkeys(training.CLASSES, .5),
        'results': {manifest['checkpoints'][role]['model_id']: results[role]
                    for role in ('candidate', 'baseline')},
        'roles': {role: {'model_id': manifest['checkpoints'][role]['model_id'],
                         'checkpoint_sha256': manifest['checkpoints'][role]['sha256']}
                  for role in ('candidate', 'baseline')},
        'metric_delta_candidate_minus_baseline': deltas,
        'research_promotion': 'accepted' if research_pass else 'rejected',
        'research_promotion_rule': manifest['evaluation_protocol']['research_promotion_rule'],
        'threshold_tuning_performed': False, 'checkpoint_selection_performed': False,
        'test_used': True, 'production_ready': False,
        'production_note': ('Independent metrics do not grant production approval; formal thresholds and signed '
                            'visual/minority/stability reviews remain separate gates.'),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + '.tmp')
    temporary.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    os.replace(temporary, args.output)
    print(json.dumps({'output': str(args.output), 'research_promotion': report['research_promotion'],
                      'pair_count': len(records), 'production_ready': False}))


if __name__ == '__main__':
    main()
