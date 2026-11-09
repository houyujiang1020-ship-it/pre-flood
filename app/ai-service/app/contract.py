"""Versioned inference evidence; spatial coordinates require independent MapGIS verification."""
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

from .schemas import JobResult
from .settings import settings

CLASSES = ('non_flooded_building', 'flooded_building', 'non_flooded_road', 'flooded_road')


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def dimensions(path: Path) -> list[int]:
    with Image.open(path) as image:
        image.load()
        return list(image.size)


def write_contract(task_id: str, pre: Path, post: Path, result: JobResult) -> JobResult:
    if not task_id or not task_id.isascii() or not task_id.isalnum():
        raise ValueError('Invalid task ID')
    size = dimensions(pre)
    if dimensions(post) != size:
        raise ValueError('Pre/post dimensions differ')
    if set(result.class_masks) != set(CLASSES) | {'flood_mask'}:
        raise ValueError('Exactly four ordered class masks are required')
    if result.class_masks['flood_mask'].resolve() != result.mask_path.resolve():
        raise ValueError('Flood mask path differs from task result')
    outputs = {}
    for name in (*CLASSES, 'flood_mask'):
        path = result.class_masks[name]
        if dimensions(path) != size:
            raise ValueError(f'Mask dimensions differ: {name}')
        with Image.open(path) as image:
            values = set(image.convert('L').getdata())
            if not values.issubset({0, 255}):
                raise ValueError(f'Mask is not binary: {name}')
        if name != 'flood_mask':
            outputs[name] = {'path': str(path.resolve()), 'sha256': digest(path),
                             'width': size[0], 'height': size[1], 'meaning': 'predicted_object_pixels'}
    backend = settings().backend
    metadata = {}
    if backend in ('siamunet-smoke', 'e4-research'):
        from .torch_backend import model_state
        metadata = model_state()[0].floodguard_metadata
    mode = ('FALLBACK' if backend == 'spectral-change-fallback' else
            'LIVE_E4' if backend == 'e4-research' else 'SMOKE')
    probability_output = None
    if mode != 'FALLBACK':
        if result.probability_path is None:
            raise ValueError('Four probability maps are missing')
        probabilities = np.load(result.probability_path, allow_pickle=False)
        if (probabilities.shape != (4, size[1], size[0]) or not np.isfinite(probabilities).all()
                or np.any(probabilities < 0) or np.any(probabilities > 1)):
            raise ValueError('Invalid four-channel probability grid')
        probability_output = {'path': str(result.probability_path.resolve()),
                              'sha256': digest(result.probability_path), 'shape': list(probabilities.shape),
                              'dtype': str(probabilities.dtype), 'class_order': list(CLASSES),
                              'semantics': 'independent_uncalibrated_sigmoid_scores'}
    contract = {
        'schema_version': 2, 'task_id': task_id, 'execution_mode': mode,
        'model_identity': {'name': backend, 'version': result.model_version,
                           'checkpoint_sha256': metadata.get('checkpoint_sha256'),
                           'architecture': metadata.get('architecture'),
                           'thresholds': metadata.get('thresholds', {})},
        'input_metadata': {
            'pre': {'path': str(pre.resolve()), 'sha256': digest(pre), 'width': size[0], 'height': size[1]},
            'post': {'path': str(post.resolve()), 'sha256': digest(post), 'width': size[0], 'height': size[1]}},
        'spatial_reference': None, 'class_order': list(CLASSES),
        'prediction_outputs': outputs,
        'probability_output': probability_output,
        'derived_outputs': {'flood_mask': {'path': str(result.mask_path.resolve()),
                            'sha256': digest(result.mask_path),
                            'meaning': 'flooded_building_or_road_pixels_NOT_continuous_flood_extent'}},
        'preprocessing': {'output_grid': 'original_image_pixels',
                          'model_resize': settings().image_size if mode != 'FALLBACK' else None,
                          'output_resampling': 'nearest' if mode != 'FALLBACK' else None},
        'objects': [], 'provenance': {'kind': 'service_inference', 'object_matching': 'NOT_PERFORMED'},
        'validation_status': 'BLOCKED',
        'warnings': ['No verified CRS/affine transform or MapGIS reference objects; masks are pixel-space only.'],
        'errors': [], 'artifacts': {'preview_path': str(result.preview_path.resolve())},
    }
    path = result.mask_path.parent / 'prediction-contract.json'
    path.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return result.model_copy(update={'contract_path': path, 'contract_sha256': digest(path)})
