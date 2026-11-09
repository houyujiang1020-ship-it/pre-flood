"""Run one fixed E4 inference pass on a sealed unlabeled external test.

Produces distribution diagnostics and deterministic visual samples. It cannot
compute IoU, F1, precision or recall and never changes model state.
"""
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject
import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app' / 'training'))
from model_factory import build_siamunet  # noqa: E402
from train_full import CLASSES  # noqa: E402
try:
    from freeze_external_test import canonical_sha, sha256  # noqa: E402
except ModuleNotFoundError:  # Imported as scripts.run_unlabeled_blind_inference_once in tests.
    from scripts.freeze_external_test import canonical_sha, sha256  # noqa: E402


COLORS = np.array([[64, 220, 90], [30, 130, 255], [255, 220, 40], [255, 45, 45]], dtype=np.float32)


def verify_manifest(path):
    manifest = json.loads(path.read_text(encoding='utf-8'))
    seal = manifest.pop('seal_sha256', None)
    if seal != canonical_sha(manifest):
        raise ValueError('Frozen manifest seal differs')
    manifest['seal_sha256'] = seal
    if manifest.get('status') != 'frozen_before_blind_inference' or manifest.get('labels_available') is not False:
        raise ValueError('Expected a frozen unlabeled manifest')
    if manifest.get('spatial_overlap_count') != 0 or manifest.get('inference_performed') is not False:
        raise ValueError('Manifest is not eligible for blind inference')
    locked = [manifest['archive'], manifest['pairing_table'], manifest['checkpoint']]
    locked += list(manifest['provenance_evidence'].values()) + manifest['reference_configs']
    for item in locked:
        path_value = Path(item['path'])
        if not path_value.is_file() or sha256(path_value) != item['sha256']:
            raise ValueError('Locked artifact changed: ' + str(path_value))
        if 'bytes' in item and path_value.stat().st_size != item['bytes']:
            raise ValueError('Locked artifact size changed: ' + str(path_value))
    for pair in manifest['pairs']:
        for item in (pair['pre'], pair['post']):
            file = Path(item['path'])
            if not file.is_file() or file.stat().st_size != item['bytes'] or sha256(file) != item['sha256']:
                raise ValueError('Frozen image changed: ' + str(file))
    return manifest


def read_pair(pair, size=512):
    with rasterio.open(pair['pre']['path']) as pre:
        before = pre.read([1, 2, 3], out_shape=(3, size, size), resampling=Resampling.bilinear)
        before_valid = pre.read_masks(1, out_shape=(size, size), resampling=Resampling.nearest) > 0
        grid = pre.transform * pre.transform.scale(pre.width / size, pre.height / size)
        crs = pre.crs
    after = np.zeros((3, size, size), dtype=np.float32)
    after_valid = np.zeros((size, size), dtype=np.uint8)
    with rasterio.open(pair['post']['path']) as post:
        for band in range(3):
            reproject(rasterio.band(post, band + 1), after[band], src_transform=post.transform,
                      src_crs=post.crs, dst_transform=grid, dst_crs=crs, resampling=Resampling.bilinear)
        reproject(post.dataset_mask(), after_valid, src_transform=post.transform, src_crs=post.crs,
                  dst_transform=grid, dst_crs=crs, resampling=Resampling.nearest)
    valid = before_valid & (after_valid > 0)
    return before.astype(np.float32) / 255, after / 255, valid


def render_visual(path, before, after, prediction):
    pre_rgb = (before.transpose(1, 2, 0) * 255).clip(0, 255).astype(np.uint8)
    post_rgb = (after.transpose(1, 2, 0) * 255).clip(0, 255).astype(np.uint8)
    overlay = post_rgb.astype(np.float32)
    for index, color in enumerate(COLORS):
        mask = prediction[index]
        overlay[mask] = overlay[mask] * .45 + color * .55
    canvas = np.concatenate((pre_rgb, post_rgb, overlay.clip(0, 255).astype(np.uint8)), axis=1)
    Image.fromarray(canvas).save(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--device', choices=('cpu', 'cuda'), default='cuda')
    args = parser.parse_args()
    report_path = args.output_dir / 'blind-inference-report.json'
    if args.output_dir.exists() or report_path.exists():
        raise FileExistsError('Blind inference output already exists: ' + str(args.output_dir))
    if args.device == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('CUDA requested but unavailable')
    manifest = verify_manifest(args.manifest)
    checkpoint_path = Path(manifest['checkpoint']['path'])
    checkpoint = torch.load(checkpoint_path, map_location=args.device, weights_only=True)
    if checkpoint.get('architecture') != 'SiamUnet_diff' or checkpoint.get('classes') != CLASSES:
        raise ValueError('Locked checkpoint has incompatible architecture/classes')
    model = build_siamunet(ROOT / 'upstream/SpaceNet8/baseline/models/other/siamunetdif.py',
                           checkpoint.get('normalization', 'batchnorm'),
                           int(checkpoint.get('groupnorm_groups') or 8)).to(args.device)
    model.load_state_dict(checkpoint['state_dict'])
    model.eval()
    temporary_dir = args.output_dir.with_name(args.output_dir.name + '.tmp')
    temporary_dir.mkdir(parents=True, exist_ok=False)
    visuals = temporary_dir / 'visual-samples'
    visuals.mkdir()
    sample_labels = set(manifest['protocol']['visual_sample_labels'])
    histogram = torch.zeros((4, 100), dtype=torch.int64)
    probability_sum = torch.zeros(4, dtype=torch.float64)
    prediction_pixels = torch.zeros(4, dtype=torch.int64)
    valid_pixels = 0
    per_tile, visual_files = [], []
    with torch.inference_mode():
        for index, pair in enumerate(manifest['pairs']):
            before, after, valid = read_pair(pair, manifest['protocol']['image_size'])
            before_device = torch.from_numpy(before).unsqueeze(0).to(args.device)
            after_device = torch.from_numpy(after).unsqueeze(0).to(args.device)
            probability = model(before_device, after_device).sigmoid()[0].cpu()
            valid_tensor = torch.from_numpy(valid)
            prediction = (probability > .5) & valid_tensor.unsqueeze(0)
            count = int(valid_tensor.sum())
            valid_pixels += count
            tile_counts = prediction.sum((1, 2)).to(torch.int64)
            prediction_pixels += tile_counts
            for channel in range(4):
                values = probability[channel][valid_tensor]
                probability_sum[channel] += values.double().sum()
                histogram[channel] += torch.histc(values, bins=100, min=0, max=1).to(torch.int64)
            per_tile.append({'label': pair['label'], 'valid_pixels': count,
                             'prediction_pixels': dict(zip(CLASSES, tile_counts.tolist())),
                             'building_status_overlap_pixels': int((prediction[0] & prediction[1]).sum()),
                             'road_status_overlap_pixels': int((prediction[2] & prediction[3]).sum())})
            if pair['label'] in sample_labels:
                visual = visuals / (Path(pair['label']).stem + '.png')
                render_visual(visual, before, after, prediction.numpy())
                visual_files.append({'label': pair['label'], 'path': str(visual.relative_to(temporary_dir)),
                                     'sha256': sha256(visual)})
            if (index + 1) % 25 == 0 or index + 1 == len(manifest['pairs']):
                print(json.dumps({'processed': index + 1, 'total': len(manifest['pairs'])}), flush=True)
    report = {
        'schema_version': 1, 'status': 'completed',
        'completed_at': datetime.now(timezone.utc).isoformat(),
        'manifest': str(args.manifest.resolve()), 'manifest_sha256': sha256(args.manifest),
        'manifest_seal_sha256': manifest['seal_sha256'],
        'checkpoint': manifest['checkpoint'], 'pair_count': len(manifest['pairs']),
        'fixed_thresholds': manifest['protocol']['thresholds'], 'image_size': 512,
        'valid_pixels': valid_pixels,
        'mean_probability': dict(zip(CLASSES, (probability_sum / valid_pixels).tolist())),
        'prediction_pixels': dict(zip(CLASSES, prediction_pixels.tolist())),
        'prediction_fraction': dict(zip(CLASSES, (prediction_pixels.double() / valid_pixels).tolist())),
        'probability_histogram_100_bins': dict(zip(CLASSES, histogram.tolist())),
        'tiles_with_predictions': {name: sum(row['prediction_pixels'][name] > 0 for row in per_tile)
                                   for name in CLASSES},
        'per_tile': per_tile, 'visual_samples': visual_files,
        'labels_available': False, 'iou': None, 'f1': None, 'precision': None, 'recall': None,
        'accuracy_verified': False, 'visual_review_completed': False,
        'model_tuning_after_test': 'forbidden', 'test_used': True, 'production_ready': False,
        'interpretation': ('Unlabeled geographic-domain response audit only. Nonzero or plausible predictions '
                           'do not establish correctness or production accuracy.'),
    }
    report_path = temporary_dir / 'blind-inference-report.json'
    report_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    os.replace(temporary_dir, args.output_dir)
    print(json.dumps({'output': str(args.output_dir), 'pairs': len(per_tile),
                      'accuracy_verified': False, 'production_ready': False}), flush=True)


if __name__ == '__main__':
    main()
