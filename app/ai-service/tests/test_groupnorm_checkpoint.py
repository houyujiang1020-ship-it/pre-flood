import json
from pathlib import Path

import pytest

from app import settings as settings_module
from app import torch_backend


ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.skipif(not (ROOT/'models/experiments/siamunet-gn-pilot-20260912/best_model.pth').is_file(),
                    reason='GroupNorm pilot checkpoint is not present')
def test_groupnorm_checkpoint_reloads_with_bound_identity(monkeypatch):
    monkeypatch.setenv('FLOODGUARD_CONFIG', str(ROOT/'config/application.gn-pilot-20260912.yaml'))
    settings_module.settings.cache_clear()
    torch_backend.model_state.cache_clear()
    model, device = torch_backend.model_state()
    metadata = model.floodguard_metadata
    report = json.loads((ROOT/metadata['metrics_file']).read_text(encoding='utf-8'))
    assert device == 'cuda'
    assert metadata['normalization'] == 'groupnorm'
    assert metadata['model_id'] == report['model_id']
    assert metadata['dataset_split_hash'] == report['dataset_split_hash']
    assert metadata['production_ready'] is False
    torch_backend.model_state.cache_clear()
    settings_module.settings.cache_clear()
