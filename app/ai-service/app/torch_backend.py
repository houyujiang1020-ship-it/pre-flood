"""Optional image-only PyTorch backend. No geospatial runtime dependencies."""
import importlib.util
import json
import hashlib
import threading
import time
import math
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

from .schemas import JobResult
from .settings import settings

CLASSES = ['non_flooded_building', 'flooded_building', 'non_flooded_road', 'flooded_road']
E4_SHA256 = 'ba2da68622d79683de2b6a9c30209c509d21cc44c1693e9118a061616c93e4bc'
LOCK = threading.Lock()


@lru_cache(maxsize=1)
def model_state():
    import torch
    config = settings()
    source = config.resolved(config.architecture_source)
    checkpoint_path = config.resolved(config.checkpoint)
    if not source.is_file() or not checkpoint_path.is_file():
        raise FileNotFoundError('Configured architecture or checkpoint is missing')
    checkpoint = torch.load(checkpoint_path, map_location='cpu', weights_only=True)
    if checkpoint.get('architecture') != 'SiamUnet_diff' or checkpoint.get('classes') != CLASSES:
        raise ValueError('Unsupported checkpoint architecture/classes')
    if checkpoint.get('smoke_only') is not True or checkpoint.get('production_ready') is not False:
        raise ValueError('This backend accepts explicitly marked smoke checkpoints only')
    checkpoint_hash = hashlib.sha256(checkpoint_path.read_bytes()).hexdigest()
    if config.backend == 'e4-research' and checkpoint_hash != E4_SHA256:
        raise ValueError('Configured LIVE_E4 checkpoint does not match the frozen E4 SHA-256')
    device = config.device
    if device == 'auto':
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
    if device == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('CUDA requested but unavailable')
    factory_path = Path(__file__).resolve().parents[2] / 'training' / 'model_factory.py'
    spec = importlib.util.spec_from_file_location('floodguard_model_factory', factory_path)
    factory = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(factory)
    normalization = checkpoint.get('normalization', 'batchnorm')
    groups = checkpoint.get('groupnorm_groups') or 8
    thresholds = checkpoint.get('thresholds', dict.fromkeys(CLASSES, .5))
    if not isinstance(thresholds, dict) or set(thresholds) != set(CLASSES):
        raise ValueError('Checkpoint thresholds must identify exactly the four model classes')
    if any(not isinstance(thresholds[name], (int, float)) or isinstance(thresholds[name], bool)
           or not math.isfinite(thresholds[name]) or not 0 < thresholds[name] < 1 for name in CLASSES):
        raise ValueError('Checkpoint thresholds must be finite values between 0 and 1')
    model = factory.build_siamunet(source, normalization, groups)
    model.load_state_dict(checkpoint['state_dict'], strict=True)
    # Bind identity to the bytes actually loaded, not a hard-coded smoke version.
    model.floodguard_version = 'research-sha256-' + checkpoint_hash
    model.floodguard_metadata = {
        'model_id': checkpoint.get('model_id', model.floodguard_version),
        'architecture': checkpoint['architecture'],
        'normalization': normalization,
        'checkpoint_sha256': checkpoint_hash,
        'production_ready': checkpoint['production_ready'],
        'thresholds': thresholds,
        'trained_at': checkpoint.get('trained_at'),
        'metrics_file': checkpoint.get('metrics_file'),
        'training_run_id': checkpoint.get('model_id'),
        'git_commit': checkpoint.get('git_commit'),
        'dataset_split_hash': checkpoint.get('dataset_split_hash'),
    }
    model.to(device).eval()
    return model, device


def predict(pre_path: Path, post_path: Path, output_dir: Path) -> JobResult:
    import torch
    started = time.perf_counter()
    size = settings().image_size
    with Image.open(pre_path) as first, Image.open(post_path) as second:
        if first.size != second.size:
            raise ValueError('Image dimensions differ: align both geographic grids in MapGIS before inference')
        original_size = first.size
        pre = np.array(first.convert('RGB').resize((size, size), Image.Resampling.BILINEAR))
        post = np.array(second.convert('RGB').resize((size, size), Image.Resampling.BILINEAR))
        original_post = np.array(second.convert('RGB'))
    with LOCK:
        model, device = model_state()
        inputs = [torch.from_numpy(a.transpose(2, 0, 1).copy()).float().div(255).unsqueeze(0).to(device) for a in (pre, post)]
        with torch.inference_mode():
            logits = model(*inputs)
            if not torch.isfinite(logits).all():
                raise RuntimeError('Model produced non-finite predictions')
            thresholds = model.floodguard_metadata['thresholds']
            cutoff = torch.tensor([thresholds[name] for name in CLASSES], device=device).reshape(4, 1, 1)
            probabilities = logits.sigmoid()[0].cpu().numpy()
            labels = probabilities > cutoff.cpu().numpy()
    masks = {name: np.array(Image.fromarray(labels[i].astype('uint8')).resize(original_size, Image.Resampling.NEAREST))
             for i, name in enumerate(CLASSES)}
    masks['flood_mask'] = np.maximum(masks['flooded_building'], masks['flooded_road'])
    output_dir.mkdir(parents=True, exist_ok=True)
    original_probabilities = np.stack([np.asarray(Image.fromarray(probabilities[i].astype('float32'))
                                      .resize(original_size, Image.Resampling.BILINEAR), dtype=np.float32)
                                       for i in range(4)])
    probability_path = output_dir / 'class_probabilities_original_grid.npy'
    np.save(probability_path, original_probabilities, allow_pickle=False)
    paths = {}
    for name, mask in masks.items():
        paths[name] = output_dir / f'{name}.png'
        Image.fromarray(mask * 255).save(paths[name])
    overlay = original_post.copy()
    overlay[masks['flooded_building'] > 0] = [255, 40, 40]
    overlay[masks['flooded_road'] > 0] = [255, 190, 0]
    preview_path = output_dir / 'preview.png'
    Image.fromarray(overlay).save(preview_path)
    flood = masks['flood_mask']
    statistics = {'width': original_size[0], 'height': original_size[1], 'total_pixels': int(flood.size),
                  'flood_pixels': int(flood.sum()), 'flood_ratio': float(flood.mean()),
                  'flooded_building_pixels': int(masks['flooded_building'].sum()),
                  'flooded_road_pixels': int(masks['flooded_road'].sum()),
                  'backend': settings().backend, 'device': device, 'production_ready': False,
                  'warning': ('E4 research model: no independent external accuracy. ' if settings().backend == 'e4-research'
                              else 'Smoke model: no validated accuracy. ')
                             + 'flood_mask is flooded structure union, NOT full flood extent.'}
    (output_dir / 'statistics.json').write_text(json.dumps(statistics, indent=2), encoding='utf-8')
    return JobResult(mask_path=paths['flood_mask'], preview_path=preview_path, class_masks=paths,
                     statistics=statistics, inference_seconds=round(time.perf_counter() - started, 6),
                     model_version=model.floodguard_version, probability_path=probability_path)
