from types import SimpleNamespace
from app import main, torch_backend


def test_model_info_uses_loaded_checkpoint_identity(monkeypatch):
    monkeypatch.setattr(main, 'health', lambda: {'backend':'siamunet-smoke','device':'cpu'})
    metadata = {'model_id':'pilot','architecture':'SiamUnet_diff','normalization':'groupnorm',
                'checkpoint_sha256':'abc','production_ready':False,'thresholds':{},'trained_at':None,
                'metrics_file':None,'training_run_id':'pilot','git_commit':'deadbeef','dataset_split_hash':'split'}
    monkeypatch.setattr(torch_backend,'model_state',lambda: (SimpleNamespace(floodguard_version='research-sha256-abc',floodguard_metadata=metadata),'cpu'))
    info = main.model_info()
    assert info['version']=='research-sha256-abc'
    assert info['normalization']=='groupnorm' and info['checkpoint_sha256']=='abc'


def test_fallback_keeps_own_version(monkeypatch):
    monkeypatch.setattr(main,'health',lambda: {'backend':'spectral-change-fallback','device':'cpu'})
    assert main.model_info()['version']==main.MODEL_VERSION
