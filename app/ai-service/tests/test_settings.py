import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.settings import settings


@pytest.fixture(autouse=True)
def reset_cache():
    settings.cache_clear()
    yield
    settings.cache_clear()


def test_reads_chinese_config_path(tmp_path, monkeypatch):
    path = tmp_path / '配置.yaml'
    path.write_text('ai:\n  backend: siamunet-smoke\n  device: cpu\n  image_size: 64\n', encoding='utf-8')
    monkeypatch.setenv('FLOODGUARD_CONFIG', str(path))
    config = settings()
    assert config.backend == 'siamunet-smoke'
    assert config.image_size == 64


def test_explicit_missing_config_is_not_silently_ignored(tmp_path, monkeypatch):
    monkeypatch.setenv('FLOODGUARD_CONFIG', str(tmp_path / 'missing.yaml'))
    with pytest.raises(FileNotFoundError):
        settings()
    response = TestClient(app).get('/health')
    assert response.status_code == 503


def test_invalid_backend_rejected(tmp_path, monkeypatch):
    path = tmp_path / 'bad.yaml'
    path.write_text('ai:\n  backend: imaginary-production-model\n', encoding='utf-8')
    monkeypatch.setenv('FLOODGUARD_CONFIG', str(path))
    with pytest.raises(ValidationError):
        settings()
