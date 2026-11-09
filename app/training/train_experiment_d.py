"""Isolated Experiment D runner; inherited baseline protocol, road overlap replacement only."""
import argparse
import csv
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from functools import lru_cache

import torch
from train_smoke import load_pair
from positive_sampler import PositiveSampler, tile_categories
from class_aware_sampler import ClassAwareSampler, class_tiles
from model_factory import build_siamunet, SUPPORTED_NORMALIZATIONS
from road_overlap_loss import road_tversky_loss, assert_d_configuration

CLASSES = ['non_flooded_building', 'flooded_building', 'non_flooded_road', 'flooded_road']
DISK_CACHE = None


def file_sha256(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def validate_frozen_dataset(config, root):
    relative = config.get('frozen_dataset_manifest')
    if not relative:
        return None
    path = root / relative
    frozen = json.loads(path.read_text(encoding='utf-8'))
    split_hash = hashlib.sha256(json.dumps(config['splits'], sort_keys=True).encode()).hexdigest()
    if not frozen.get('training_split_frozen') or not frozen.get('review_complete'):
        raise ValueError('Frozen dataset is not authorized by a complete review')
    if frozen.get('dataset_split_hash') != split_hash or config.get('frozen_dataset_sha256') != split_hash:
        raise ValueError('Training splits differ from frozen dataset')
    for path_key, hash_key in [('review_state_path', 'review_state_sha256'),
                               ('reviews_jsonl_path', 'reviews_jsonl_sha256'),
                               ('visibility_manifest_path', 'manifest_sha256')]:
        source = root / frozen[path_key]
        if not source.is_file() or file_sha256(source) != frozen[hash_key]:
            raise ValueError('Frozen review evidence changed: ' + path_key)
    return frozen


def pair_cache_key(area, row, size):
    identity = [str(Path(area).resolve()), row, size,
                hashlib.sha256(Path(__file__).with_name('train_smoke.py').read_bytes()).hexdigest()]
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()


@lru_cache(maxsize=64)
def _cached_pair(area, row_json, size):
    if DISK_CACHE is not None:
        path = DISK_CACHE / (pair_cache_key(area, json.loads(row_json), size) + '.pt')
        if not path.is_file():
            raise FileNotFoundError('Prepared training cache missing: ' + str(path))
        return torch.load(path, map_location='cpu', weights_only=True)
    return load_pair(area, json.loads(row_json), size)


def cached_pair(area, row, size):
    # Tensors are only read / copied to the device, never augmented in place.
    return _cached_pair(area, json.dumps(row,sort_keys=True),size)


def split_rows(config, root):
    split = config['splits']
    if not split.get('train') or not split.get('validation'):
        raise ValueError('Nonempty train and validation splits are required')
    identities = set()
    result = {}
    for name in ('train', 'validation', 'test'):
        records = []
        for item in split.get(name, []):
            identity = (item['area'], item['label'])
            if identity in identities:
                raise ValueError('Duplicate tile or split leakage: ' + str(identity))
            identities.add(identity)
            area = root / config['data_root'] / item['area']
            with (area / f"{item['area']}_label_image_mapping.csv").open(encoding='utf-8-sig', newline='') as stream:
                rows = {row['label']: row for row in csv.DictReader(stream)}
            if item['label'] not in rows:
                raise ValueError('Label absent from official pairing table: ' + item['label'])
            row = rows[item['label']]
            post_column = item.get('post_event_column', 'post-event image 1')
            if post_column not in ('post-event image 1', 'post-event image 2'):
                raise ValueError('Invalid post_event_column: ' + str(post_column))
            if not row.get(post_column, '').strip():
                raise ValueError(f'{post_column} absent for {item["label"]}')
            if post_column != 'post-event image 1':
                row = dict(row)
                row['post-event image 1'] = row[post_column]
            selected = area / 'POST-event' / row['post-event image 1']
            expected = item.get('selected_post_sha256')
            if expected and file_sha256(selected) != expected:
                raise ValueError('Selected post SHA256 differs from frozen review: ' + item['label'])
            for folder, key in [('annotations', 'label'), ('PRE-event', 'pre-event image'), ('POST-event', 'post-event image 1')]:
                if not (area / folder / row[key]).is_file():
                    raise FileNotFoundError(area / folder / row[key])
            records.append((area, row))
        result[name] = records
    return result


def evaluate(model, records, size, device, thresholds=None):
    if not records:
        raise ValueError('Evaluation requires nonempty records')
    threshold = torch.tensor([.5]*4 if thresholds is None else thresholds, device=device).reshape(1,4,1,1)
    if not torch.isfinite(threshold).all() or not ((threshold > 0) & (threshold < 1)).all():
        raise ValueError('Thresholds must be four finite values between 0 and 1')
    model.eval()
    losses, intersections, unions = [], torch.zeros(4), torch.zeros(4)
    positives, predicted_positives = torch.zeros(4), torch.zeros(4)
    with torch.inference_mode():
        for area, row in records:
            pre, post, truth, valid = [t.unsqueeze(0).to(device) for t in cached_pair(area, row, size)]
            logits = model(pre, post)
            loss = masked_loss(logits, truth, valid)
            losses.append(loss.item())
            prediction = (logits.sigmoid() > threshold) & (valid.unsqueeze(1) > 0)
            expected = (truth > 0) & (valid.unsqueeze(1) > 0)
            intersections += (prediction & expected).sum(dim=(0, 2, 3)).cpu()
            unions += (prediction | expected).sum(dim=(0, 2, 3)).cpu()
            positives += expected.sum(dim=(0, 2, 3)).cpu()
            predicted_positives += prediction.sum(dim=(0, 2, 3)).cpu()
    return {'loss': sum(losses) / len(losses),
            'class_iou': {name: (intersections[i] / unions[i]).item() if unions[i] else None for i, name in enumerate(CLASSES)},
            'truth_pixels': dict(zip(CLASSES, positives.tolist())),
            'prediction_pixels': dict(zip(CLASSES, predicted_positives.tolist())),
            'class_f1': {name: (2*intersections[i]/(positives[i]+predicted_positives[i])).item()
                         if positives[i]+predicted_positives[i] else None for i,name in enumerate(CLASSES)},
            'class_precision': {name: (intersections[i]/predicted_positives[i]).item() if predicted_positives[i] else None for i,name in enumerate(CLASSES)},
            'class_recall': {name: (intersections[i]/positives[i]).item() if positives[i] else None for i,name in enumerate(CLASSES)},
            'tile_count': len(records)}


def positive_weights(positive, total, exponent=1.0, cap=50.0):
    if not 0 <= exponent <= 1 or not 1 <= cap <= 50:
        raise ValueError('Invalid positive weight exponent/cap')
    if not torch.isfinite(positive).all() or (positive <= 0).any() or total <= 0 or (positive > total).any():
        raise ValueError('Invalid class supervision counts')
    return ((total-positive)/positive).pow(exponent).clamp(1,cap).reshape(4,1,1)


def selection_score(validation, metric):
    if metric == 'loss':
        return -validation['loss']
    if metric != 'macro_iou':
        raise ValueError('Unknown selection metric')
    values = list(validation['class_iou'].values())
    if len(values) != 4 or any(value is None for value in values):
        raise ValueError('macro_iou selection requires all four classes')
    return sum(values)/4


def masked_loss(logits, truth, valid, pos_weight=None, dice_weight=0.0):
    if valid.sum().item() <= 0:
        raise ValueError('Tile has no valid supervision')
    loss = (torch.nn.functional.binary_cross_entropy_with_logits(logits, truth, reduction='none', pos_weight=pos_weight)
            * valid.unsqueeze(1)).sum() / (valid.sum() * 4)
    if dice_weight:
        mask = valid.unsqueeze(1)
        probability = logits.sigmoid() * mask
        target = truth * mask
        intersection = (probability * target).sum(dim=(0,2,3))
        denominator = (probability + target).sum(dim=(0,2,3))
        loss = loss + dice_weight * (1 - (2*intersection+1)/(denominator+1)).mean()
    if not torch.isfinite(loss):
        raise RuntimeError('Nonfinite loss')
    return loss


def save_checkpoint(payload, path):
    temporary = path.with_suffix('.tmp')
    torch.save(payload, temporary)
    temporary.replace(path)


def main():
    global DISK_CACHE
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--epochs', type=int)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding='utf-8'))
    baseline_manifest = json.loads((Path(__file__).resolve().parents[2] / 'models/candidates/germany-reviewed-v1/candidate_manifest.json').read_text(encoding='utf-8'))
    assert_d_configuration(config, baseline_manifest['training_configuration'])
    if args.epochs is not None or args.resume:
        raise ValueError('D uses predeclared 40 epochs, no overrides/resume')
    if config.get('diagnostic_only') or config.get('training_authorized') is False:
        raise ValueError('Diagnostic-only configuration cannot start training; use diagnose_sampler.py')
    root = Path(__file__).resolve().parents[2]
    validate_frozen_dataset(config, root)
    DISK_CACHE = root / config['cache_dir'] if config.get('cache_dir') else None
    _cached_pair.cache_clear()
    size = int(config['image_size'])
    epochs = args.epochs if args.epochs is not None else int(config['epochs'])
    if epochs < 1 or size < 32 or size % 16 or size > 1024:
        raise ValueError('Invalid epochs/image_size')
    if float(config['learning_rate']) <= 0:
        raise ValueError('learning_rate must be positive')
    records = split_rows(config, root)
    if config.get('sampler') and config.get('balanced_loss', False) and not config.get('allow_combined_rebalancing', False):
        raise ValueError('Positive-aware sampling and positive-weighted loss cannot be combined without an explicit reviewed override')
    source = root / 'upstream/SpaceNet8/baseline/models/other/siamunetdif.py'
    normalization = config.get('normalization', 'batchnorm')
    groups = int(config.get('groupnorm_groups', 8))
    if normalization not in SUPPORTED_NORMALIZATIONS:
        raise ValueError('Unsupported normalization')
    signature_data = {key: value for key, value in config.items() if key not in ('epochs', 'output_dir')}
    signature_data['architecture_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
    signature_data['preprocessing_sha256'] = hashlib.sha256(Path(__file__).with_name('train_smoke.py').read_bytes()).hexdigest()
    signature_data['road_loss_sha256'] = file_sha256(Path(__file__).with_name('road_overlap_loss.py'))
    signature_data['trainer_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    signature_data['model_factory_sha256'] = hashlib.sha256(Path(__file__).with_name('model_factory.py').read_bytes()).hexdigest()
    if config.get('sampler'):
        signature_data['sampler_sha256'] = hashlib.sha256(Path(__file__).with_name('class_aware_sampler.py' if config['sampler'].get('type') == 'class_aware' else 'positive_sampler.py').read_bytes()).hexdigest()
    signature = hashlib.sha256(json.dumps(signature_data, sort_keys=True).encode()).hexdigest()
    out = root / config['output_dir']
    if not out.is_dir() or not (out / 'experiment_manifest.json').is_file():
        raise ValueError('Prepare fresh D directory and manifest before training')
    preregistered = json.loads((out / 'experiment_manifest.json').read_text(encoding='utf-8'))
    if config != preregistered['experiment_configuration']:
        raise ValueError('Configuration changed after preregistration')
    for relative, expected in preregistered['source_sha256'].items():
        if file_sha256(root / relative) != expected: raise ValueError('Source changed after preregistration')
    if file_sha256(root / 'models/candidates/germany-reviewed-v1/candidate_manifest.json') != preregistered['baseline_manifest_sha256']:
        raise ValueError('Baseline manifest changed')
    gate = json.loads((root / 'experiments/diagnostics/experiment-d-preflight-20260912/test-gate.json').read_text())
    if not gate['full_regression_passed'] or gate['manifest_sha256'] != file_sha256(out / 'experiment_manifest.json'):
        raise ValueError('Full test gate absent/stale')
    with (out / 'training-started.json').open('x', encoding='utf-8') as stream:
        json.dump({'started': datetime.now(timezone.utc).isoformat()}, stream)
    if (out / 'last_model.pth').exists() and not args.resume:
        raise FileExistsError('Existing run found. Use --resume or a different output_dir; nothing overwritten.')
    device = config.get('device', 'cuda')
    if device not in ('cpu', 'cuda'):
        raise ValueError('device must be cpu or cuda')
    if device == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('CUDA requested but unavailable')
    torch.manual_seed(int(config.get('seed', 42)))
    model = build_siamunet(source, normalization, groups).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=float(config['learning_rate']))
    dice_weight = float(config.get('dice_weight', 0))
    if not 0 <= dice_weight <= 1:
        raise ValueError('dice_weight must be between 0 and 1')
    positive = torch.zeros(4)
    total = 0
    sampling_tiles = []
    for area, row in records['train']:
        _, _, labels, valid = cached_pair(area,row,size)
        positive += (labels*valid.unsqueeze(0)).sum(dim=(1,2))
        total += valid.sum().item()
        if config.get('sampler'):
            sampling_tiles.append((class_tiles if config['sampler'].get('type') == 'class_aware' else tile_categories)(area, row, labels, valid))
    sampler = (ClassAwareSampler if config['sampler'].get('type') == 'class_aware' else PositiveSampler)(sampling_tiles, config['sampler'], int(config.get('seed', 42))) if config.get('sampler') else None
    pos_weight = None
    if config.get('balanced_loss', False):
        if (positive == 0).any():
            raise ValueError('Training split lacks classes; expand data before balanced training: '+str(positive.tolist()))
        pos_weight = positive_weights(positive, total, float(config.get('positive_weight_exponent',1)),
                                      float(config.get('positive_weight_cap',50))).to(device)
    metric = config.get('selection_metric', 'loss')
    if metric not in ('loss', 'macro_iou'):
        raise ValueError('Unknown selection metric')
    best_score = -float('inf')
    begin, best, history = 0, float('inf'), []
    trained_at = datetime.now(timezone.utc).isoformat()
    try:
        git_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    except (OSError, subprocess.SubprocessError):
        git_commit = None
    if args.resume:
        saved = torch.load(out / 'last_model.pth', map_location=device, weights_only=True)
        if saved['run_signature'] != signature:
            raise ValueError('Resume configuration or architecture differs from saved run')
        model.load_state_dict(saved['state_dict'])
        optimizer.load_state_dict(saved['optimizer'])
        begin, best, history = saved['epoch'], saved['best_validation_loss'], saved['history']
        trained_at = saved.get('trained_at', trained_at)
        best_score = saved.get('best_selection_score', -best)
        torch.set_rng_state(saved['rng_state'].cpu())
        if device == 'cuda' and 'cuda_rng_state' in saved:
            torch.cuda.set_rng_state_all([state.cpu() for state in saved['cuda_rng_state']])
    if epochs <= begin:
        raise ValueError(f'Requested epochs must exceed completed epoch {begin}')
    for epoch in range(begin, epochs):
        model.train()
        losses = []
        train_counts = torch.zeros((3, 4), dtype=torch.float64)
        sampling_report = None
        if sampler is None:
            indices = torch.randperm(len(records['train'])).tolist()
        else:
            indices, sampling_report = sampler.sample(epoch)
            print(json.dumps({'sampling': sampling_report}), flush=True)
        for index in indices:
            area, row = records['train'][index]
            pre, post, truth, valid = [t.unsqueeze(0).to(device) for t in cached_pair(area, row, size)]
            if config.get('spatial_augmentation', False):
                turns = int(torch.randint(4, ()).item())
                pre, post, truth, valid = [torch.rot90(t, turns, (-2, -1)) for t in (pre, post, truth, valid)]
                if torch.rand(()).item() < .5:
                    pre, post, truth, valid = [t.flip(-1) for t in (pre, post, truth, valid)]
            optimizer.zero_grad(set_to_none=True)
            logits = model(pre, post)
            loss = road_tversky_loss(logits, truth, valid, pos_weight, dice_weight, config['road_overlap_loss']['alpha_fp'], config['road_overlap_loss']['beta_fn'])
            with torch.no_grad():
                prediction = (logits.sigmoid() > .5) & (valid.unsqueeze(1) > 0)
                expected = (truth > 0) & (valid.unsqueeze(1) > 0)
                train_counts[0] += (prediction & expected).sum((0,2,3)).cpu()
                train_counts[1] += prediction.sum((0,2,3)).cpu()
                train_counts[2] += expected.sum((0,2,3)).cpu()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 10.0)
            optimizer.step()
            losses.append(loss.item())
            if len(losses) % 20 == 0:
                print(json.dumps({'epoch': epoch + 1, 'step': len(losses),
                                  'steps': len(indices), 'loss': loss.item()}), flush=True)
        validation = evaluate(model, records['validation'], size, device)
        score = selection_score(validation, metric)
        improved = score > best_score
        best_score = max(best_score, score)
        best = min(best, validation['loss'])
        record = {'epoch': epoch + 1, 'train_loss': sum(losses) / len(losses), 'validation': validation}
        tp, predicted, train_positive = train_counts
        def ratio(a,b):
            return {c: float(a[i]/b[i]) if b[i] else None for i,c in enumerate(CLASSES)}
        record['training_metrics'] = {'scope':'Online training-mode predictions before each optimizer update, sampled/augmented indices, threshold0.5; not comparable to validation', 'class_iou':ratio(tp,train_positive+predicted-tp),'class_precision':ratio(tp,predicted),'class_recall':ratio(tp,train_positive),'class_f1':ratio(2*tp,train_positive+predicted)}
        record['validation']['macro_iou'] = score
        if sampling_report is not None:
            record['sampling'] = sampling_report
        history.append(record)
        print(json.dumps(record), flush=True)
        payload = {'state_dict': model.state_dict(), 'optimizer': optimizer.state_dict(), 'epoch': epoch + 1,
                   'best_selection_score': best_score, 'selection_metric': metric,
                   'best_validation_loss': best, 'history': history, 'run_signature': signature,
                   'rng_state': torch.get_rng_state(), 'architecture': 'SiamUnet_diff', 'classes': CLASSES,
                   'normalization': normalization, 'groupnorm_groups': groups if normalization == 'groupnorm' else None,
                   'model_id': config.get('model_id', out.name), 'thresholds': config.get('thresholds', dict.fromkeys(CLASSES, .5)),
                   'trained_at': trained_at, 'metrics_file': str((out / 'training_report.json').relative_to(root)),
                   'dataset_split_hash': hashlib.sha256(json.dumps(config['splits'], sort_keys=True).encode()).hexdigest(),
                   'git_commit': git_commit,
                   'road_overlap_loss': config['road_overlap_loss'], 'training_configuration': config,
                   'smoke_only': True, 'production_ready': False,
                   'warning': 'Research training; preprocessing and accuracy not approved for production.'}
        if device == 'cuda':
            payload['cuda_rng_state'] = torch.cuda.get_rng_state_all()
        save_checkpoint(payload, out / 'last_model.pth')
        if improved:
            save_checkpoint(payload, out / 'best_model.pth')
        (out / 'history.json').write_text(json.dumps(history, indent=2), encoding='utf-8')
    # Test is never used for checkpoint selection. A labeled held-out tile is not the official competition test set.
    model.load_state_dict(torch.load(out / 'best_model.pth', map_location=device, weights_only=True)['state_dict'])
    report = {'device': device, 'epochs_completed': epochs, 'best_validation_loss': best,
              'selection_metric': metric, 'best_selection_score': best_score,
              'positive_weights': pos_weight.detach().cpu().flatten().tolist() if pos_weight is not None else None,
              'training_positive_pixels': dict(zip(CLASSES,positive.tolist())),
              'balanced_loss': config.get('balanced_loss',False), 'dice_weight': dice_weight,
              'road_overlap_loss': config['road_overlap_loss'], 'validation_loss_scope': 'BCE only, inherited baseline protocol',
              'model_id': config.get('model_id', out.name), 'architecture': 'SiamUnet_diff',
              'normalization': normalization, 'groupnorm_groups': groups if normalization == 'groupnorm' else None,
              'dataset_split_hash': hashlib.sha256(json.dumps(config['splits'], sort_keys=True).encode()).hexdigest(),
              'git_commit': git_commit, 'trained_at': trained_at,
              'split_identity': config['splits'], 'production_ready': False,
              'test': evaluate(model, records['test'], size, device) if records['test'] else None,
              'test_scope': config.get('test_scope', 'No official test accuracy claimed')}
    (out / 'training_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
