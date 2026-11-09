import hashlib
import json

import pytest
import numpy as np
from types import SimpleNamespace
from PIL import Image

from app import contract as contract_module
from app.contract import CLASSES, write_contract
from app.schemas import JobResult


def _image(path, value=0, size=(4, 3)):
    Image.new('L', size, value).save(path)
    return path


def test_versioned_contract_preserves_order_hashes_and_blocks_unverified_space(tmp_path):
    pre = _image(tmp_path / '灾前.png')
    post = _image(tmp_path / '灾后.png')
    masks = {name: _image(tmp_path / f'{name}.png', 255 if name == 'flooded_road' else 0)
             for name in CLASSES}
    result = JobResult(mask_path=masks['flooded_road'], preview_path=post, class_masks={**masks, 'flood_mask': masks['flooded_road']},
                       statistics={}, inference_seconds=0.1, model_version='test')
    finished = write_contract('abc123', pre, post, result)
    contract = json.loads(finished.contract_path.read_text(encoding='utf-8'))
    assert contract['schema_version'] == 2
    assert contract['execution_mode'] == 'FALLBACK'
    assert contract['class_order'] == list(CLASSES)
    assert contract['validation_status'] == 'BLOCKED'
    assert contract['spatial_reference'] is None
    assert contract['objects'] == []
    assert 'NOT_continuous_flood_extent' in contract['derived_outputs']['flood_mask']['meaning']
    assert contract['input_metadata']['pre']['sha256'] == hashlib.sha256(pre.read_bytes()).hexdigest()
    assert finished.contract_sha256 == hashlib.sha256(finished.contract_path.read_bytes()).hexdigest()


def test_contract_rejects_wrong_size_nonbinary_or_missing_class(tmp_path):
    pre = _image(tmp_path / 'pre.png')
    post = _image(tmp_path / 'post.png')
    masks = {name: _image(tmp_path / f'{name}.png') for name in CLASSES}
    result = JobResult(mask_path=masks[CLASSES[0]], preview_path=post, class_masks={**masks, 'flood_mask': masks[CLASSES[0]]},
                       statistics={}, inference_seconds=0.1, model_version='test')
    _image(masks[CLASSES[1]], size=(2, 2))
    with pytest.raises(ValueError, match='dimensions'):
        write_contract('abc', pre, post, result)
    _image(masks[CLASSES[1]], 128)
    with pytest.raises(ValueError, match='binary'):
        write_contract('abc', pre, post, result)
    _image(masks[CLASSES[1]])
    with pytest.raises(ValueError, match='four ordered'):
        write_contract('abc', pre, post, result.model_copy(update={'class_masks': {CLASSES[0]: masks[CLASSES[0]]}}))


def test_contract_rejects_invalid_uncalibrated_score_grid(tmp_path, monkeypatch):
    pre = _image(tmp_path / 'pre.png')
    post = _image(tmp_path / 'post.png')
    masks = {name: _image(tmp_path / f'{name}.png') for name in CLASSES}
    probability = tmp_path / 'scores.npy'
    np.save(probability, np.zeros((3, 3, 4), dtype=np.float32))
    monkeypatch.setattr(contract_module, 'settings', lambda: SimpleNamespace(backend='siamunet-smoke', image_size=4))
    from app import torch_backend
    monkeypatch.setattr(torch_backend, 'model_state', lambda: (SimpleNamespace(floodguard_metadata={}), 'cpu'))
    result = JobResult(mask_path=masks[CLASSES[0]], preview_path=post,
                       class_masks={**masks, 'flood_mask': masks[CLASSES[0]]},
                       statistics={}, inference_seconds=0.1, model_version='test',
                       probability_path=probability)
    with pytest.raises(ValueError, match='four-channel probability'):
        write_contract('abc', pre, post, result)
