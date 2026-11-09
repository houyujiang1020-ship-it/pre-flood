"""Train the E3 PRE-event object foundation with shape auxiliary targets."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import torch

import train_full as base
from domain_balanced_sampler import DomainBalancedPositiveSampler
from foundation_auxiliary import CHANNELS
from positive_sampler import tile_categories
from single_unet import attach_single_image_forward
from xdxd_sn5 import (build_xdxd_sn5, freeze_batchnorm_statistics,
                      freeze_except_output_head, parameter_counts)


def build_foundation_model(root, config):
    source = root / 'upstream/SpaceNet8/baseline/models/other/siamunetdif.py'
    architecture = config.get('foundation_architecture', 'siamunet_pre_pre')
    if architecture == 'xdxd_sn5_serx50_focal':
        external = root / config['external_pretrained_checkpoint']
        expected = config.get('external_pretrained_sha256')
        if expected and base.file_sha256(external) != expected:
            raise ValueError('External pretrained checkpoint SHA-256 mismatch')
        model = build_xdxd_sn5(
            root / 'upstream/SpaceNet8/05-motokimura/code/spacenet8_model/models/xdxd_sn5/senet.py',
            len(CHANNELS), external, road_target_channel=CHANNELS.index('road_body'))
        trainable = config.get('foundation_trainable', 'all')
        if trainable == 'head_only':
            freeze_except_output_head(model)
        elif trainable != 'all':
            raise ValueError('Unknown foundation_trainable setting')
        return model
    model = base.build_siamunet(source, config['normalization'], config['groupnorm_groups'], len(CHANNELS))
    if architecture == 'single_unet_skip':
        return attach_single_image_forward(model)
    if architecture != 'siamunet_pre_pre':
        raise ValueError('Unknown foundation architecture: ' + architecture)
    return model


def predict(model, pre, architecture):
    single_image = ('single_unet_skip', 'xdxd_sn5_serx50_focal')
    return model(pre) if architecture in single_image else model(pre, pre)


def auxiliary_target(cache, area, row, size):
    path = cache / (base.pair_cache_key(area, row, size) + '.pt')
    value = torch.load(path, map_location='cpu', weights_only=True)
    if value.get('schema') != 'foundation-aux-v1' or value.get('channels') != CHANNELS:
        raise ValueError('Invalid foundation auxiliary cache: ' + str(path))
    return value['target'].float()


def loss_fn(logits, truth, valid, dice_weight=.5, pos_weight=None, channel_weight=None):
    mask = valid.unsqueeze(1)
    if channel_weight is None:
        channel_weight = torch.ones(logits.shape[1], device=logits.device)
    channel_weight = channel_weight / channel_weight.mean()
    bce_map = torch.nn.functional.binary_cross_entropy_with_logits(
        logits, truth, reduction='none', pos_weight=pos_weight) * mask
    bce = (bce_map.sum((0, 2, 3)) / valid.sum() * channel_weight).mean()
    probability = logits.sigmoid() * mask
    target = truth * mask
    intersection = (probability * target).sum((0, 2, 3))
    denominator = (probability + target).sum((0, 2, 3))
    dice = 1 - (2 * intersection + 1) / (denominator + 1)
    return bce + dice_weight * (dice * channel_weight).mean()


def evaluate(model, records, aux_cache, size, device, pos_weight=None, channel_weight=None,
             architecture='siamunet_pre_pre'):
    intersections = torch.zeros(2)
    unions = torch.zeros(2)
    predicted = torch.zeros(2)
    positives = torch.zeros(2)
    losses = []
    model.eval()
    with torch.inference_mode():
        for area, row in records:
            pre, _, _, valid = base.cached_pair(area, row, size)
            target = auxiliary_target(aux_cache, area, row, size)
            logits = predict(model, pre.unsqueeze(0).to(device), architecture)
            valid_device = valid.unsqueeze(0).to(device)
            target_device = target.unsqueeze(0).to(device)
            losses.append(loss_fn(logits, target_device, valid_device, .5, pos_weight, channel_weight).item())
            choice = torch.stack((logits[:, 0] > 0, logits[:, 3] > 0), dim=1)
            expected = torch.stack((target_device[:, 0] > 0, target_device[:, 3] > 0), dim=1)
            mask = valid_device.unsqueeze(1) > 0
            choice &= mask
            expected &= mask
            intersections += (choice & expected).sum((0, 2, 3)).cpu()
            unions += (choice | expected).sum((0, 2, 3)).cpu()
            predicted += choice.sum((0, 2, 3)).cpu()
            positives += expected.sum((0, 2, 3)).cpu()
    iou = intersections / unions
    return {'loss': sum(losses) / len(losses), 'building_iou': iou[0].item(),
            'road_iou': iou[1].item(), 'mean_object_iou': iou.mean().item(),
            'building_precision': (intersections[0] / predicted[0]).item() if predicted[0] else None,
            'building_recall': (intersections[0] / positives[0]).item(),
            'road_precision': (intersections[1] / predicted[1]).item() if predicted[1] else None,
            'road_recall': (intersections[1] / positives[1]).item(), 'tile_count': len(records)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    config = json.loads(args.config.read_text(encoding='utf-8'))
    if config['foundation_channels'] != CHANNELS or config.get('test'):
        raise ValueError('Invalid foundation configuration')
    base.DISK_CACHE = root / config['cache_dir']
    base._cached_pair.cache_clear()
    aux_cache = root / config['auxiliary_cache_dir']
    records = base.split_rows(config, root)
    size = int(config['image_size'])
    device = config['device']
    torch.manual_seed(int(config['seed']))
    architecture = config.get('foundation_architecture', 'siamunet_pre_pre')
    model = build_foundation_model(root, config).to(device)
    compatible = {}
    initialization_name = config.get('initialization_checkpoint')
    if initialization_name:
        initialization_path = root / initialization_name
        initialization = torch.load(initialization_path, map_location=device, weights_only=True)
        current = model.state_dict()
        compatible = {name: value for name, value in initialization['state_dict'].items()
                      if name in current and current[name].shape == value.shape}
        missing = sorted(set(current) - set(compatible))
        if missing != ['conv11d.bias', 'conv11d.weight']:
            raise ValueError('Unexpected foundation initialization mismatch: ' + str(missing))
        current.update(compatible)
        model.load_state_dict(current)
    counts = parameter_counts(model)
    optimizer = torch.optim.Adam(
        (parameter for parameter in model.parameters() if parameter.requires_grad),
        lr=float(config['learning_rate']))
    sampling_tiles = []
    for area, row in records['train']:
        _, _, labels, valid = base.cached_pair(area, row, size)
        sampling_tiles.append(tile_categories(area, row, labels, valid))
    sampler = DomainBalancedPositiveSampler(sampling_tiles, config['sampler'], int(config['seed']))
    positive = torch.zeros(len(CHANNELS))
    total = 0.0
    for area, row in records['train']:
        target = auxiliary_target(aux_cache, area, row, size)
        _, _, _, valid = base.cached_pair(area, row, size)
        positive += (target * valid.unsqueeze(0)).sum((1, 2))
        total += valid.sum().item()
    pos_weight = None
    if config.get('balanced_loss'):
        exponent = float(config.get('positive_weight_exponent', .5))
        cap = float(config.get('positive_weight_cap', 20))
        pos_weight = (((total - positive) / positive).pow(exponent).clamp(1, cap)
                      .reshape(len(CHANNELS), 1, 1).to(device))
    channel_weight = torch.tensor(config.get('foundation_channel_weights', [1] * len(CHANNELS)),
                                  dtype=torch.float32, device=device)
    if channel_weight.shape != (len(CHANNELS),) or (channel_weight <= 0).any():
        raise ValueError('Invalid foundation_channel_weights')
    out = root / config['output_dir']
    out.mkdir(parents=True, exist_ok=False)
    best = -1.0
    history = []
    for epoch in range(int(config['epochs'])):
        model.train()
        if config.get('freeze_batchnorm_statistics'):
            freeze_batchnorm_statistics(model)
        indices, sampling = sampler.sample(epoch)
        losses = []
        for index in indices:
            area, row = records['train'][index]
            pre, _, _, valid = base.cached_pair(area, row, size)
            target = auxiliary_target(aux_cache, area, row, size)
            pre, target, valid = [value.unsqueeze(0).to(device) for value in (pre, target, valid)]
            if config.get('spatial_augmentation'):
                turns = int(torch.randint(4, ()).item())
                pre, target, valid = [torch.rot90(value, turns, (-2, -1)) for value in (pre, target, valid)]
                if torch.rand(()).item() < .5:
                    pre, target, valid = [value.flip(-1) for value in (pre, target, valid)]
            optimizer.zero_grad(set_to_none=True)
            loss = loss_fn(predict(model, pre, architecture), target, valid, float(config['dice_weight']),
                           pos_weight, channel_weight)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 10)
            optimizer.step()
            losses.append(loss.item())
        validation = evaluate(model, records['validation'], aux_cache, size, device,
                              pos_weight, channel_weight, architecture)
        record = {'epoch': epoch + 1, 'train_loss': sum(losses) / len(losses),
                  'validation': validation, 'sampling': sampling}
        history.append(record)
        print(json.dumps({'epoch': epoch + 1, 'train_loss': record['train_loss'],
                          'validation': validation}), flush=True)
        payload = {'state_dict': model.state_dict(), 'optimizer': optimizer.state_dict(),
                   'epoch': epoch + 1, 'history': history, 'best_selection_score': max(best, validation['mean_object_iou']),
                   'selection_metric': 'mean_object_iou', 'architecture': architecture,
                   'num_classes': len(CHANNELS), 'classes': CHANNELS, 'normalization': config['normalization'],
                   'groupnorm_groups': config['groupnorm_groups'], 'model_id': config['model_id'],
                   'dataset_split_hash': hashlib.sha256(json.dumps(config['splits'], sort_keys=True).encode()).hexdigest(),
                   'initialization_checkpoint': initialization_name,
                   'initialized_parameter_tensors': len(compatible),
                   'positive_weights': pos_weight.detach().cpu().flatten().tolist() if pos_weight is not None else None,
                   'foundation_channel_weights': channel_weight.detach().cpu().tolist(),
                   'external_pretrained_checkpoint': config.get('external_pretrained_checkpoint'),
                   'external_pretrained_sha256': config.get('external_pretrained_sha256'),
                   'foundation_trainable': config.get('foundation_trainable', 'all'),
                   'parameter_counts': counts,
                   'training_positive_pixels': dict(zip(CHANNELS, positive.tolist())),
                   'trained_at': datetime.now(timezone.utc).isoformat(), 'test_used': False,
                   'production_ready': False, 'warning': 'Research foundation; PRE image only.'}
        base.save_checkpoint(payload, out / 'last_model.pth')
        if validation['mean_object_iou'] > best:
            best = validation['mean_object_iou']
            payload['best_selection_score'] = best
            base.save_checkpoint(payload, out / 'best_model.pth')
        (out / 'history.json').write_text(json.dumps(history, indent=2), encoding='utf-8')
    checkpoint = torch.load(out / 'best_model.pth', map_location=device, weights_only=True)
    model.load_state_dict(checkpoint['state_dict'])
    report = {'epochs_completed': config['epochs'], 'best_epoch': checkpoint['epoch'],
              'best_validation': evaluate(model, records['validation'], aux_cache, size, device,
                                          pos_weight, channel_weight, architecture),
              'channels': CHANNELS, 'test': None, 'production_ready': False}
    (out / 'training_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
