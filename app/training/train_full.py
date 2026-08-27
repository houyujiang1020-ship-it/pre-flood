"""Config-driven research training with resume, best checkpoint, and held-out evaluation."""
import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path

import torch
from train_smoke import load_pair

CLASSES = ['non_flooded_building', 'flooded_building', 'non_flooded_road', 'flooded_road']


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
            for folder, key in [('annotations', 'label'), ('PRE-event', 'pre-event image'), ('POST-event', 'post-event image 1')]:
                if not (area / folder / row[key]).is_file():
                    raise FileNotFoundError(area / folder / row[key])
            records.append((area, row))
        result[name] = records
    return result


def evaluate(model, records, size, device):
    model.eval()
    losses, intersections, unions = [], torch.zeros(4), torch.zeros(4)
    with torch.inference_mode():
        for area, row in records:
            pre, post, truth, valid = [t.unsqueeze(0).to(device) for t in load_pair(area, row, size)]
            logits = model(pre, post)
            loss = masked_loss(logits, truth, valid)
            losses.append(loss.item())
            prediction = (logits.sigmoid() > .5) & (valid.unsqueeze(1) > 0)
            expected = (truth > 0) & (valid.unsqueeze(1) > 0)
            intersections += (prediction & expected).sum(dim=(0, 2, 3)).cpu()
            unions += (prediction | expected).sum(dim=(0, 2, 3)).cpu()
    return {'loss': sum(losses) / len(losses),
            'class_iou': {name: (intersections[i] / unions[i]).item() if unions[i] else None for i, name in enumerate(CLASSES)},
            'tile_count': len(records)}


def masked_loss(logits, truth, valid):
    if valid.sum().item() <= 0:
        raise ValueError('Tile has no valid supervision')
    loss = (torch.nn.functional.binary_cross_entropy_with_logits(logits, truth, reduction='none')
            * valid.unsqueeze(1)).sum() / (valid.sum() * 4)
    if not torch.isfinite(loss):
        raise RuntimeError('Nonfinite loss')
    return loss


def save_checkpoint(payload, path):
    temporary = path.with_suffix('.tmp')
    torch.save(payload, temporary)
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--epochs', type=int)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding='utf-8'))
    root = Path(__file__).resolve().parents[2]
    size = int(config['image_size'])
    epochs = args.epochs if args.epochs is not None else int(config['epochs'])
    if epochs < 1 or size < 32 or size % 16 or size > 1024:
        raise ValueError('Invalid epochs/image_size')
    if float(config['learning_rate']) <= 0:
        raise ValueError('learning_rate must be positive')
    records = split_rows(config, root)
    source = root / 'upstream/SpaceNet8/baseline/models/other/siamunetdif.py'
    signature_data = {key: value for key, value in config.items() if key not in ('epochs', 'output_dir')}
    signature_data['architecture_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
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
    spec = importlib.util.spec_from_file_location('official_siamunet', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    model = module.SiamUnet_diff(num_classes=4, num_channels=3).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=float(config['learning_rate']))
    begin, best, history = 0, float('inf'), []
    if args.resume:
        saved = torch.load(out / 'last_model.pth', map_location=device, weights_only=True)
        if saved['run_signature'] != signature:
            raise ValueError('Resume configuration or architecture differs from saved run')
        model.load_state_dict(saved['state_dict'])
        optimizer.load_state_dict(saved['optimizer'])
        begin, best, history = saved['epoch'], saved['best_validation_loss'], saved['history']
        torch.set_rng_state(saved['rng_state'].cpu())
        if device == 'cuda' and 'cuda_rng_state' in saved:
            torch.cuda.set_rng_state_all([state.cpu() for state in saved['cuda_rng_state']])
    if epochs <= begin:
        raise ValueError(f'Requested epochs must exceed completed epoch {begin}')
    for epoch in range(begin, epochs):
        model.train()
        losses = []
        for index in torch.randperm(len(records['train'])).tolist():
            area, row = records['train'][index]
            pre, post, truth, valid = [t.unsqueeze(0).to(device) for t in load_pair(area, row, size)]
            optimizer.zero_grad(set_to_none=True)
            loss = masked_loss(model(pre, post), truth, valid)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 10.0)
            optimizer.step()
            losses.append(loss.item())
        validation = evaluate(model, records['validation'], size, device)
        improved = validation['loss'] < best
        best = min(best, validation['loss'])
        record = {'epoch': epoch + 1, 'train_loss': sum(losses) / len(losses), 'validation': validation}
        history.append(record)
        print(json.dumps(record), flush=True)
        payload = {'state_dict': model.state_dict(), 'optimizer': optimizer.state_dict(), 'epoch': epoch + 1,
                   'best_validation_loss': best, 'history': history, 'run_signature': signature,
                   'rng_state': torch.get_rng_state(), 'architecture': 'SiamUnet_diff', 'classes': CLASSES,
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
              'split_identity': config['splits'], 'production_ready': False,
              'test': evaluate(model, records['test'], size, device) if records['test'] else None,
              'test_scope': config.get('test_scope', 'No official test accuracy claimed')}
    (out / 'training_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
