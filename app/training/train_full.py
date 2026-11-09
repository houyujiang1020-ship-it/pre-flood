"""Config-driven research training with resume, best checkpoint, and held-out evaluation."""
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
from class_aware_crop import select_crop as select_class_crop, validate_config as validate_class_crop
from domain_balanced_sampler import DomainBalancedPositiveSampler
from hard_negative_sampler import load_hard_negatives, resample as resample_hard_negatives
from model_factory import build_siamunet, SUPPORTED_NORMALIZATIONS

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


@lru_cache(maxsize=16)
def _cached_pair(area, row_json, size):
    if DISK_CACHE is not None:
        path = DISK_CACHE / (pair_cache_key(area, json.loads(row_json), size) + '.pt')
        if not path.is_file():
            raise FileNotFoundError('Prepared training cache missing: ' + str(path))
        value = torch.load(path, map_location='cpu', weights_only=True)
        if isinstance(value, dict) and value.get('schema') == 'compact-pair-v1':
            return (value['pre'].float() / 255, value['post'].float() / 255,
                    value['labels'].float(), value['valid'].float())
        return value
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


def output_probabilities(logits, activation='sigmoid'):
    if activation == 'sigmoid':
        return logits.sigmoid()
    if activation == 'factorized_object_status':
        building_object = logits[:, 0:1].sigmoid()
        building_flood = logits[:, 1:2].sigmoid()
        road_object = logits[:, 2:3].sigmoid()
        road_flood = logits[:, 3:4].sigmoid()
        return torch.cat((building_object * (1 - building_flood),
                          building_object * building_flood,
                          road_object * (1 - road_flood),
                          road_object * road_flood), dim=1)
    if activation != 'building_status_softmax':
        raise ValueError('Unknown output activation: ' + activation)
    background = torch.zeros_like(logits[:, :1])
    building = torch.softmax(torch.cat((background, logits[:, :2]), dim=1), dim=1)[:, 1:]
    return torch.cat((building, logits[:, 2:].sigmoid()), dim=1)


def building_status_loss(logits, truth, valid, dice_weight=.5):
    if (truth[:, 0] * truth[:, 1] * valid.unsqueeze(1)).sum().item() > 0:
        raise ValueError('Building status targets overlap')
    background = torch.zeros_like(logits[:, :1])
    building_logits = torch.cat((background, logits[:, :2]), dim=1)
    building_target = torch.where(truth[:, 1] > 0, 2, torch.where(truth[:, 0] > 0, 1, 0)).long()
    building_ce = (torch.nn.functional.cross_entropy(
        building_logits, building_target, reduction='none') * valid).sum() / valid.sum()
    road_bce = (torch.nn.functional.binary_cross_entropy_with_logits(
        logits[:, 2:], truth[:, 2:], reduction='none') * valid.unsqueeze(1)).sum() / (valid.sum() * 2)
    loss = (building_ce + road_bce) / 2
    if dice_weight:
        probability = output_probabilities(logits, 'building_status_softmax') * valid.unsqueeze(1)
        target = truth * valid.unsqueeze(1)
        intersection = (probability * target).sum((0, 2, 3))
        denominator = (probability + target).sum((0, 2, 3))
        loss += dice_weight * (1 - (2 * intersection + 1) / (denominator + 1)).mean()
    if not torch.isfinite(loss):
        raise RuntimeError('Nonfinite loss')
    return loss


def _balanced_conditional_bce(logits, target, mask):
    """Average positive and negative conditional pixels without a tunable class weight."""
    values = []
    for channel in range(logits.shape[1]):
        selected = mask[:, channel] > 0
        if not selected.any():
            continue
        channel_loss = torch.nn.functional.binary_cross_entropy_with_logits(
            logits[:, channel][selected], target[:, channel][selected], reduction='none')
        positive = target[:, channel][selected] > 0
        groups = [channel_loss[positive], channel_loss[~positive]]
        values.append(torch.stack([group.mean() for group in groups if group.numel()]).mean())
    return torch.stack(values).mean() if values else logits.sum() * 0


def factorized_object_status_loss(logits, truth, valid, dice_weight=.5):
    """Train object presence everywhere and flood status only inside labeled objects."""
    if logits.shape[1] != 4 or truth.shape[1] != 4:
        raise ValueError('Factorized object/status loss requires four channels')
    valid4 = valid.unsqueeze(1)
    objects = torch.stack((torch.maximum(truth[:, 0], truth[:, 1]),
                           torch.maximum(truth[:, 2], truth[:, 3])), dim=1)
    object_logits = logits[:, (0, 2)]
    object_loss = (torch.nn.functional.binary_cross_entropy_with_logits(
        object_logits, objects, reduction='none') * valid4).sum() / (valid.sum() * 2)
    status_logits = logits[:, (1, 3)]
    status_target = truth[:, (1, 3)]
    status_loss = _balanced_conditional_bce(status_logits, status_target, objects * valid4)
    loss = (object_loss + status_loss) / 2
    if dice_weight:
        probability = output_probabilities(logits, 'factorized_object_status') * valid4
        # Buffered road segments of different status can overlap at junctions. Resolve those
        # geometry-only collisions deterministically while keeping the object union intact.
        target = truth.clone()
        target[:, 0] *= 1 - truth[:, 1]
        target[:, 2] *= 1 - truth[:, 3]
        target *= valid4
        intersection = (probability * target).sum((0, 2, 3))
        denominator = (probability + target).sum((0, 2, 3))
        loss += dice_weight * (1 - (2 * intersection + 1) / (denominator + 1)).mean()
    if not torch.isfinite(loss):
        raise RuntimeError('Nonfinite loss')
    return loss


def road_union_auxiliary_loss(logits, truth, valid):
    """Road-presence Dice derived from existing normal/flooded road labels."""
    if logits.shape[1] != 4 or truth.shape != logits.shape or valid.shape != logits.shape[:1] + logits.shape[2:]:
        raise ValueError('Road union auxiliary loss requires Bx4xHxW logits/labels and BxHxW valid mask')
    if valid.sum().item() <= 0:
        raise ValueError('Tile has no valid supervision')
    probability = logits[:, 2:].sigmoid()
    road_probability = (1 - (1 - probability[:, 0]) * (1 - probability[:, 1])) * valid
    road_target = torch.maximum(truth[:, 2], truth[:, 3]) * valid
    intersection = (road_probability * road_target).sum()
    denominator = road_probability.sum() + road_target.sum()
    result = 1 - (2 * intersection + 1) / (denominator + 1)
    if not torch.isfinite(result):
        raise RuntimeError('Nonfinite road union auxiliary loss')
    return result


def configured_loss(logits, truth, valid, loss_type, dice_weight=0, pos_weight=None,
                    road_union_aux_weight=0.0):
    if loss_type == 'building_status_categorical':
        return building_status_loss(logits, truth, valid, dice_weight)
    if loss_type == 'factorized_object_status':
        return factorized_object_status_loss(logits, truth, valid, dice_weight)
    base = masked_loss(logits, truth, valid, pos_weight, dice_weight)
    if road_union_aux_weight:
        if loss_type != 'independent_binary' or not 0 < road_union_aux_weight <= 1:
            raise ValueError('Road union auxiliary weight requires independent binary loss and (0,1]')
        base = base + road_union_aux_weight * road_union_auxiliary_loss(logits, truth, valid)
    return base


def evaluate(model, records, size, device, thresholds=None, activation='sigmoid'):
    if not records:
        raise ValueError('Evaluation requires nonempty records')
    threshold = torch.tensor([.5]*4 if thresholds is None else thresholds, device=device).reshape(1,4,1,1)
    if not torch.isfinite(threshold).all() or not ((threshold > 0) & (threshold < 1)).all():
        raise ValueError('Thresholds must be four finite values between 0 and 1')
    model.eval()
    losses, intersections, unions = [], torch.zeros(4), torch.zeros(4)
    positives, predicted_positives = torch.zeros(4), torch.zeros(4)
    status_overlap_pixels = torch.zeros(2)
    with torch.inference_mode():
        for area, row in records:
            pre, post, truth, valid = [t.unsqueeze(0).to(device) for t in cached_pair(area, row, size)]
            logits = model(pre, post)
            loss_type = ('building_status_categorical' if activation == 'building_status_softmax' else
                         'factorized_object_status' if activation == 'factorized_object_status' else
                         'independent_binary')
            loss = configured_loss(logits, truth, valid, loss_type)
            losses.append(loss.item())
            prediction = (output_probabilities(logits, activation) > threshold) & (valid.unsqueeze(1) > 0)
            expected = (truth > 0) & (valid.unsqueeze(1) > 0)
            intersections += (prediction & expected).sum(dim=(0, 2, 3)).cpu()
            unions += (prediction | expected).sum(dim=(0, 2, 3)).cpu()
            positives += expected.sum(dim=(0, 2, 3)).cpu()
            predicted_positives += prediction.sum(dim=(0, 2, 3)).cpu()
            status_overlap_pixels[0] += (prediction[:, 0] & prediction[:, 1]).sum().cpu()
            status_overlap_pixels[1] += (prediction[:, 2] & prediction[:, 3]).sum().cpu()
    return {'loss': sum(losses) / len(losses),
            'class_iou': {name: (intersections[i] / unions[i]).item() if unions[i] else None for i, name in enumerate(CLASSES)},
            'truth_pixels': dict(zip(CLASSES, positives.tolist())),
            'prediction_pixels': dict(zip(CLASSES, predicted_positives.tolist())),
            'class_f1': {name: (2*intersections[i]/(positives[i]+predicted_positives[i])).item()
                         if positives[i]+predicted_positives[i] else None for i,name in enumerate(CLASSES)},
            'class_precision': {name: (intersections[i]/predicted_positives[i]).item() if predicted_positives[i] else None for i,name in enumerate(CLASSES)},
            'class_recall': {name: (intersections[i]/positives[i]).item() if positives[i] else None for i,name in enumerate(CLASSES)},
            'status_overlap_pixels': {'building': int(status_overlap_pixels[0].item()),
                                      'road': int(status_overlap_pixels[1].item())},
            'tile_count': len(records)}


def sliding_positions(length, tile_size, stride):
    if tile_size > length or tile_size < 32 or tile_size % 16 or stride < 1 or stride > tile_size:
        raise ValueError('Invalid sliding-window geometry')
    positions = list(range(0, length - tile_size + 1, stride))
    if positions[-1] != length - tile_size:
        positions.append(length - tile_size)
    return positions


def crop_training_pair(pair, crop_size, positive_probability=.75):
    pre, post, truth, valid = pair
    height, width = valid.shape
    if crop_size > min(height, width) or crop_size < 32 or crop_size % 16:
        raise ValueError('Invalid training crop size')
    if not 0 <= positive_probability <= 1:
        raise ValueError('positive crop probability must be between 0 and 1')
    top = left = None
    positives = (truth > 0) & (valid.unsqueeze(0) > 0)
    present = torch.where(positives.flatten(1).any(1))[0]
    if len(present) and torch.rand(()).item() < positive_probability:
        channel = int(present[torch.randint(len(present), ())].item())
        coordinates = torch.nonzero(positives[channel], as_tuple=False)
        y, x = coordinates[torch.randint(len(coordinates), ())].tolist()
        top = max(0, min(height - crop_size, y - int(torch.randint(crop_size, ()).item())))
        left = max(0, min(width - crop_size, x - int(torch.randint(crop_size, ()).item())))
    if top is None:
        top = int(torch.randint(height - crop_size + 1, ()).item())
        left = int(torch.randint(width - crop_size + 1, ()).item())
    return tuple(t[..., top:top + crop_size, left:left + crop_size] for t in pair)


def evaluate_tiled(model, records, full_size, tile_size, stride, device, thresholds=None,
                   activation='sigmoid'):
    if not records:
        raise ValueError('Evaluation requires nonempty records')
    threshold = torch.tensor([.5] * 4 if thresholds is None else thresholds,
                             device=device).reshape(1, 4, 1, 1)
    if not torch.isfinite(threshold).all() or not ((threshold > 0) & (threshold < 1)).all():
        raise ValueError('Thresholds must be four finite values between 0 and 1')
    positions = sliding_positions(full_size, tile_size, stride)
    window_1d = torch.hann_window(tile_size, periodic=False, device=device).clamp_min(.05)
    window = (window_1d[:, None] * window_1d[None, :]).reshape(1, 1, tile_size, tile_size)
    losses, intersections, unions = [], torch.zeros(4), torch.zeros(4)
    positives, predicted_positives = torch.zeros(4), torch.zeros(4)
    model.eval()
    with torch.inference_mode():
        for area, row in records:
            pre, post, truth, valid = cached_pair(area, row, full_size)
            probability_sum = torch.zeros(1, 4, full_size, full_size, device=device)
            weight_sum = torch.zeros(1, 1, full_size, full_size, device=device)
            for top in positions:
                for left in positions:
                    before = pre[:, top:top + tile_size, left:left + tile_size].unsqueeze(0).to(device)
                    after = post[:, top:top + tile_size, left:left + tile_size].unsqueeze(0).to(device)
                    probability_sum[..., top:top + tile_size, left:left + tile_size] += output_probabilities(
                        model(before, after), activation) * window
                    weight_sum[..., top:top + tile_size, left:left + tile_size] += window
            probability = probability_sum / weight_sum.clamp_min(1e-6)
            expected = (truth.unsqueeze(0).to(device) > 0) & (valid.unsqueeze(0).unsqueeze(0).to(device) > 0)
            valid_device = valid.unsqueeze(0).unsqueeze(0).to(device)
            loss = (torch.nn.functional.binary_cross_entropy(probability.clamp(1e-6, 1 - 1e-6),
                                                              truth.unsqueeze(0).to(device), reduction='none')
                    * valid_device).sum() / (valid_device.sum() * 4)
            prediction = (probability > threshold) & (valid_device > 0)
            losses.append(loss.item())
            intersections += (prediction & expected).sum(dim=(0, 2, 3)).cpu()
            unions += (prediction | expected).sum(dim=(0, 2, 3)).cpu()
            positives += expected.sum(dim=(0, 2, 3)).cpu()
            predicted_positives += prediction.sum(dim=(0, 2, 3)).cpu()
    return {'loss': sum(losses) / len(losses),
            'class_iou': {name: (intersections[i] / unions[i]).item() if unions[i] else None for i, name in enumerate(CLASSES)},
            'truth_pixels': dict(zip(CLASSES, positives.tolist())),
            'prediction_pixels': dict(zip(CLASSES, predicted_positives.tolist())),
            'class_f1': {name: (2 * intersections[i] / (positives[i] + predicted_positives[i])).item()
                         if positives[i] + predicted_positives[i] else None for i, name in enumerate(CLASSES)},
            'class_precision': {name: (intersections[i] / predicted_positives[i]).item()
                                if predicted_positives[i] else None for i, name in enumerate(CLASSES)},
            'class_recall': {name: (intersections[i] / positives[i]).item()
                             if positives[i] else None for i, name in enumerate(CLASSES)},
            'tile_count': len(records), 'full_size': full_size, 'tile_size': tile_size,
            'stride': stride, 'windows_per_tile': len(positions) ** 2}


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


def should_run_validation(schedule, epoch_index, epochs):
    if schedule not in ('every_epoch', 'final_only'):
        raise ValueError('validation_schedule must be every_epoch or final_only')
    return schedule == 'every_epoch' or epoch_index + 1 == epochs


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


def initialize_ema_state(model):
    return {name: value.detach().clone() for name, value in model.state_dict().items()}


def update_ema_state(ema_state, model, decay):
    if not 0 < decay < 1:
        raise ValueError('EMA decay must be between 0 and 1')
    current = model.state_dict()
    if current.keys() != ema_state.keys():
        raise ValueError('EMA state does not match model state')
    with torch.no_grad():
        for name, value in current.items():
            if value.is_floating_point():
                ema_state[name].mul_(decay).add_(value.detach(), alpha=1 - decay)
            else:
                ema_state[name].copy_(value)


def evaluate_state(model, state_dict, records, size, device, thresholds=None):
    online_state = initialize_ema_state(model)
    model.load_state_dict(state_dict)
    try:
        return evaluate(model, records, size, device, thresholds)
    finally:
        model.load_state_dict(online_state)


def main():
    global DISK_CACHE
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--epochs', type=int)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding='utf-8'))
    if config.get('diagnostic_only') or config.get('training_authorized') is False:
        raise ValueError('Diagnostic-only configuration cannot start training; use diagnose_sampler.py')
    root = Path(__file__).resolve().parents[2]
    validate_frozen_dataset(config, root)
    DISK_CACHE = root / config['cache_dir'] if config.get('cache_dir') else None
    _cached_pair.cache_clear()
    size = int(config['image_size'])
    crop_config = config.get('crop_training')
    class_crop_config = config.get('class_aware_crop')
    if class_crop_config:
        validate_class_crop(class_crop_config, size)
    if class_crop_config and crop_config:
        raise ValueError('class_aware_crop and crop_training are mutually exclusive')
    crop_size = int(crop_config['size']) if crop_config else None
    positive_crop_probability = float(crop_config.get('positive_probability', .75)) if crop_config else None
    tiled_config = config.get('tiled_validation')
    if bool(crop_config) != bool(tiled_config):
        raise ValueError('crop_training and tiled_validation must be enabled together')
    if crop_config and int(tiled_config['tile_size']) != crop_size:
        raise ValueError('Training crop and validation tile size must match')
    epochs = args.epochs if args.epochs is not None else int(config['epochs'])
    if epochs < 1 or size < 32 or size % 16 or size > 2048 or (size > 1024 and not tiled_config):
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
    signature_data['trainer_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    signature_data['model_factory_sha256'] = hashlib.sha256(Path(__file__).with_name('model_factory.py').read_bytes()).hexdigest()
    if class_crop_config:
        signature_data['class_aware_crop_sha256'] = hashlib.sha256(
            Path(__file__).with_name('class_aware_crop.py').read_bytes()).hexdigest()
    if config.get('sampler'):
        sampler_file = {'class_aware': 'class_aware_sampler.py',
                        'domain_balanced_positive': 'domain_balanced_sampler.py'}.get(
                            config['sampler'].get('type'), 'positive_sampler.py')
        signature_data['sampler_sha256'] = hashlib.sha256(Path(__file__).with_name(sampler_file).read_bytes()).hexdigest()
    signature = hashlib.sha256(json.dumps(signature_data, sort_keys=True).encode()).hexdigest()
    out = root / config['output_dir']
    out.mkdir(parents=True, exist_ok=True)
    if (out / 'last_model.pth').exists() and not args.resume:
        raise FileExistsError('Existing run found. Use --resume or a different output_dir; nothing overwritten.')
    device = config.get('device', 'cuda')
    if device not in ('cpu', 'cuda'):
        raise ValueError('device must be cpu or cuda')
    if device == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('CUDA requested but unavailable')
    torch.manual_seed(int(config.get('seed', 42)))
    model = build_siamunet(source, normalization, groups).to(device)
    initialization_report = None
    if config.get('initialization_checkpoint') and not args.resume:
        initialization_path = root / config['initialization_checkpoint']
        initialization = torch.load(initialization_path, map_location=device, weights_only=True)
        current = model.state_dict()
        compatible = {name: value for name, value in initialization['state_dict'].items()
                      if name in current and current[name].shape == value.shape}
        missing = sorted(set(current) - set(compatible))
        allowed_missing = sorted(config.get('initialization_allowed_missing',
                                             ['conv11d.bias', 'conv11d.weight']))
        if missing != allowed_missing:
            raise ValueError('Unexpected initialization mismatch: ' + str(missing))
        current.update(compatible)
        model.load_state_dict(current)
        initialization_report = {'checkpoint': config['initialization_checkpoint'],
                                 'checkpoint_sha256': file_sha256(initialization_path),
                                 'compatible_parameter_tensors': len(compatible),
                                 'new_parameter_tensors': missing}
    optimizer = torch.optim.Adam(model.parameters(), lr=float(config['learning_rate']))
    ema_config = config.get('ema', {})
    ema_enabled = bool(ema_config.get('enabled', False))
    ema_decay = float(ema_config.get('decay', .999))
    if ema_enabled and not 0 < ema_decay < 1:
        raise ValueError('EMA decay must be between 0 and 1')
    ema_state = initialize_ema_state(model) if ema_enabled else None
    dice_weight = float(config.get('dice_weight', 0))
    if not 0 <= dice_weight <= 1:
        raise ValueError('dice_weight must be between 0 and 1')
    loss_type = config.get('loss_type', 'independent_binary')
    if loss_type not in ('independent_binary', 'building_status_categorical', 'factorized_object_status'):
        raise ValueError('Unknown loss_type')
    activation = {'independent_binary': 'sigmoid',
                  'building_status_categorical': 'building_status_softmax',
                  'factorized_object_status': 'factorized_object_status'}[loss_type]
    if loss_type != 'independent_binary' and config.get('balanced_loss', False):
        raise ValueError(loss_type + ' does not support balanced_loss')
    road_union_aux_weight = float(config.get('road_union_aux_weight', 0.0))
    if not 0 <= road_union_aux_weight <= 1 or (road_union_aux_weight and loss_type != 'independent_binary'):
        raise ValueError('Invalid road union auxiliary configuration')
    positive = torch.zeros(4)
    total = 0
    sampling_tiles = []
    for area, row in records['train']:
        _, _, labels, valid = cached_pair(area,row,size)
        positive += (labels*valid.unsqueeze(0)).sum(dim=(1,2))
        total += valid.sum().item()
        if config.get('sampler'):
            sampling_tiles.append((class_tiles if config['sampler'].get('type') == 'class_aware' else tile_categories)(area, row, labels, valid))
    sampler_types = {'class_aware': ClassAwareSampler,
                     'domain_balanced_positive': DomainBalancedPositiveSampler,
                     'positive_aware': PositiveSampler}
    sampler = sampler_types[config['sampler'].get('type')](sampling_tiles, config['sampler'], int(config.get('seed', 42))) if config.get('sampler') else None
    hard_config = config.get('hard_negative_mining')
    hard_tiles = (load_hard_negatives(root / hard_config['directory'], records['train'],
                                     float(hard_config['weight']),
                                     float(hard_config.get('top_fraction', 0.2))) if hard_config else set())
    pos_weight = None
    if config.get('balanced_loss', False):
        if (positive == 0).any():
            raise ValueError('Training split lacks classes; expand data before balanced training: '+str(positive.tolist()))
        pos_weight = positive_weights(positive, total, float(config.get('positive_weight_exponent',1)),
                                      float(config.get('positive_weight_cap',50))).to(device)
    metric = config.get('selection_metric', 'loss')
    if metric not in ('loss', 'macro_iou'):
        raise ValueError('Unknown selection metric')
    validation_schedule = config.get('validation_schedule', 'every_epoch')
    if validation_schedule not in ('every_epoch', 'final_only'):
        raise ValueError('validation_schedule must be every_epoch or final_only')
    best_score = -float('inf')
    best_macro_score = -float('inf')
    best_road_score = -float('inf')
    best_macro_epoch = None
    best_road_epoch = None
    patience = config.get('early_stopping_patience')
    if patience is not None and (type(patience) is not int or patience < 1):
        raise ValueError('early_stopping_patience must be a positive integer')
    minimum_epochs = config.get('early_stopping_min_epochs', 1)
    if type(minimum_epochs) is not int or minimum_epochs < 1:
        raise ValueError('early_stopping_min_epochs must be a positive integer')
    stale_epochs = 0
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
        model.load_state_dict(saved.get('training_state_dict', saved['state_dict']))
        optimizer.load_state_dict(saved['optimizer'])
        if ema_enabled:
            if 'ema_state_dict' not in saved:
                raise ValueError('EMA resume checkpoint lacks ema_state_dict')
            ema_state = saved['ema_state_dict']
        begin, best, history = saved['epoch'], saved['best_validation_loss'], saved['history']
        trained_at = saved.get('trained_at', trained_at)
        best_score = saved.get('best_selection_score', -best)
        best_macro_score = saved.get('best_macro_score', best_score if metric == 'macro_iou' else -float('inf'))
        best_road_score = saved.get('best_road_score', -float('inf'))
        best_macro_epoch = saved.get('best_macro_epoch')
        best_road_epoch = saved.get('best_road_epoch')
        stale_epochs = saved.get('stale_epochs', 0)
        torch.set_rng_state(saved['rng_state'].cpu())
        if device == 'cuda' and 'cuda_rng_state' in saved:
            torch.cuda.set_rng_state_all([state.cpu() for state in saved['cuda_rng_state']])
    if epochs <= begin:
        raise ValueError(f'Requested epochs must exceed completed epoch {begin}')
    for epoch in range(begin, epochs):
        model.train()
        losses = []
        sampling_report = None
        crop_summary = {'epoch': epoch + 1, 'crop_count': 0,
                        'requested_groups': {key: 0 for key in ('flooded_road', 'flooded_building', 'normal_object', 'background')},
                        'fallback_count': 0, 'class_positive_pixels': [0, 0, 0, 0], 'valid_pixels': 0}
        if sampler is None:
            indices = torch.randperm(len(records['train'])).tolist()
        else:
            indices, sampling_report = sampler.sample(epoch)
            print(json.dumps({'sampling': sampling_report}), flush=True)
        if hard_config:
            indices, hard_report = resample_hard_negatives(
                indices, records['train'], hard_tiles, float(hard_config['weight']),
                int(config.get('seed', 42)) + epoch)
            print(json.dumps({'hard_negative_sampling': hard_report}), flush=True)
        for index in indices:
            area, row = records['train'][index]
            pair = cached_pair(area, row, size)
            if crop_config:
                pair = crop_training_pair(pair, crop_size, positive_crop_probability)
            elif class_crop_config:
                pair, crop_info = select_class_crop(pair, class_crop_config)
                crop_summary['crop_count'] += 1
                crop_summary['requested_groups'][crop_info['requested_group']] += 1
                crop_summary['fallback_count'] += int(crop_info['fallback_to_valid'])
                crop_summary['class_positive_pixels'] = [a+b for a,b in zip(
                    crop_summary['class_positive_pixels'], crop_info['positive_pixels'])]
                crop_summary['valid_pixels'] += crop_info['valid_pixels']
            pre, post, truth, valid = [t.unsqueeze(0).to(device) for t in pair]
            if config.get('spatial_augmentation', False):
                turns = int(torch.randint(4, ()).item())
                pre, post, truth, valid = [torch.rot90(t, turns, (-2, -1)) for t in (pre, post, truth, valid)]
                if torch.rand(()).item() < .5:
                    pre, post, truth, valid = [t.flip(-1) for t in (pre, post, truth, valid)]
            optimizer.zero_grad(set_to_none=True)
            logits = model(pre, post)
            loss = configured_loss(logits, truth, valid, loss_type, dice_weight, pos_weight,
                                   road_union_aux_weight)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 10.0)
            optimizer.step()
            if ema_enabled:
                update_ema_state(ema_state, model, ema_decay)
            losses.append(loss.item())
            if len(losses) % 20 == 0:
                print(json.dumps({'epoch': epoch + 1, 'step': len(losses),
                                  'steps': len(indices), 'loss': loss.item()}), flush=True)
        evaluator = (lambda selected_model: evaluate_tiled(
            selected_model, records['validation'], size, int(tiled_config['tile_size']),
            int(tiled_config['stride']), device, activation=activation)) if tiled_config else (
            lambda selected_model: evaluate(selected_model, records['validation'], size, device,
                                            activation=activation))
        should_validate = should_run_validation(validation_schedule, epoch, epochs)
        validation = None
        improved = False
        macro_improved = road_improved = False
        if should_validate:
            if ema_enabled:
                online_state = initialize_ema_state(model)
                model.load_state_dict(ema_state)
                try:
                    validation = evaluator(model)
                finally:
                    model.load_state_dict(online_state)
            else:
                validation = evaluator(model)
            score = selection_score(validation, metric)
            improved = score > best_score
            best_score = max(best_score, score)
            best = min(best, validation['loss'])
            macro = sum(validation['class_iou'].values()) / 4
            macro_improved = macro > best_macro_score
            if macro_improved:
                best_macro_score, best_macro_epoch, stale_epochs = macro, epoch + 1, 0
            else:
                stale_epochs += 1
            road_iou = validation['class_iou']['flooded_road']
            road_improved = road_iou is not None and road_iou > best_road_score
            if road_improved:
                best_road_score, best_road_epoch = road_iou, epoch + 1
        record = {'epoch': epoch + 1, 'train_loss': sum(losses) / len(losses), 'validation': validation,
                  'evaluation_weights': 'ema' if ema_enabled else 'online'}
        if sampling_report is not None:
            record['sampling'] = sampling_report
        if class_crop_config:
            record['class_aware_crop'] = crop_summary
            (out / 'training_sampling_report.json').write_text(
                json.dumps(crop_summary, indent=2) + '\n', encoding='utf-8')
        history.append(record)
        print(json.dumps(record), flush=True)
        payload = {'state_dict': ema_state if ema_enabled else model.state_dict(),
                   'optimizer': optimizer.state_dict(), 'epoch': epoch + 1,
                   'best_selection_score': best_score, 'selection_metric': metric,
                   'best_macro_score': best_macro_score, 'best_road_score': best_road_score,
                   'best_macro_epoch': best_macro_epoch, 'best_road_epoch': best_road_epoch,
                   'stale_epochs': stale_epochs,
                   'best_validation_loss': best, 'history': history, 'run_signature': signature,
                   'rng_state': torch.get_rng_state(), 'architecture': 'SiamUnet_diff', 'classes': CLASSES,
                   'normalization': normalization, 'groupnorm_groups': groups if normalization == 'groupnorm' else None,
                   'model_id': config.get('model_id', out.name), 'thresholds': config.get('thresholds', dict.fromkeys(CLASSES, .5)),
                   'trained_at': trained_at, 'metrics_file': str((out / 'training_report.json').relative_to(root)),
                   'dataset_split_hash': hashlib.sha256(json.dumps(config['splits'], sort_keys=True).encode()).hexdigest(),
                   'initialization': initialization_report,
                   'loss_type': loss_type, 'road_union_aux_weight': road_union_aux_weight,
                   'output_activation': activation,
                   'git_commit': git_commit,
                   'smoke_only': True, 'production_ready': False,
                   'warning': 'Research training; preprocessing and accuracy not approved for production.'}
        if ema_enabled:
            payload['training_state_dict'] = model.state_dict()
            payload['ema_state_dict'] = ema_state
            payload['ema'] = {'enabled': True, 'decay': ema_decay, 'update_interval': 'optimizer_step'}
        if device == 'cuda':
            payload['cuda_rng_state'] = torch.cuda.get_rng_state_all()
        save_checkpoint(payload, out / 'last_model.pth')
        if improved:
            save_checkpoint(payload, out / 'best_model.pth')
        if macro_improved:
            save_checkpoint(payload, out / 'best_macro_iou.pth')
        if road_improved:
            save_checkpoint(payload, out / 'best_flooded_road_iou.pth')
        (out / 'history.json').write_text(json.dumps(history, indent=2), encoding='utf-8')
        if patience is not None and should_validate and epoch + 1 >= minimum_epochs and stale_epochs >= patience:
            print(json.dumps({'early_stopping': True, 'epoch': epoch + 1,
                              'patience': patience, 'best_macro_epoch': best_macro_epoch}), flush=True)
            break
    # Test is never used for checkpoint selection. A labeled held-out tile is not the official competition test set.
    model.load_state_dict(torch.load(out / 'best_model.pth', map_location=device, weights_only=True)['state_dict'])
    report = {'device': device, 'epochs_completed': len(history), 'best_validation_loss': best,
              'selection_metric': metric, 'best_selection_score': best_score,
              'positive_weights': pos_weight.detach().cpu().flatten().tolist() if pos_weight is not None else None,
              'training_positive_pixels': dict(zip(CLASSES,positive.tolist())),
              'balanced_loss': config.get('balanced_loss',False), 'dice_weight': dice_weight,
              'loss_type': loss_type, 'output_activation': activation,
              'validation_schedule': validation_schedule,
              'ema': {'enabled': ema_enabled, 'decay': ema_decay if ema_enabled else None,
                      'update_interval': 'optimizer_step' if ema_enabled else None},
              'crop_training': crop_config, 'tiled_validation': tiled_config,
              'model_id': config.get('model_id', out.name), 'architecture': 'SiamUnet_diff',
              'normalization': normalization, 'groupnorm_groups': groups if normalization == 'groupnorm' else None,
              'dataset_split_hash': hashlib.sha256(json.dumps(config['splits'], sort_keys=True).encode()).hexdigest(),
              'initialization': initialization_report,
              'git_commit': git_commit, 'trained_at': trained_at,
              'split_identity': config['splits'], 'production_ready': False,
              'test': (evaluate_tiled(model, records['test'], size, int(tiled_config['tile_size']),
                                      int(tiled_config['stride']), device, activation=activation)
                       if records['test'] and tiled_config else
                       evaluate(model, records['test'], size, device, activation=activation)
                       if records['test'] else None),
              'test_scope': config.get('test_scope', 'No official test accuracy claimed')}
    (out / 'training_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
