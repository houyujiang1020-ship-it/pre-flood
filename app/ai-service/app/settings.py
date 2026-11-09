"""Shared configuration; relative paths are resolved against the project root."""
import os
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

ROOT = Path(__file__).resolve().parents[3]


class AiSettings(BaseModel):
    model_config = ConfigDict(extra='ignore')
    backend: Literal['spectral-change-fallback', 'siamunet-smoke', 'e4-research'] = 'spectral-change-fallback'
    device: Literal['auto', 'cpu', 'cuda'] = 'auto'
    checkpoint: Path = Path('models/checkpoints/spacenet8-smoke/smoke_model.pth')
    architecture_source: Path = Path('upstream/SpaceNet8/baseline/models/other/siamunetdif.py')
    image_size: int = Field(default=128, ge=32, le=1024, multiple_of=16)

    def resolved(self, path: Path) -> Path:
        return path if path.is_absolute() else ROOT / path


@lru_cache(maxsize=1)
def settings() -> AiSettings:
    explicit = os.environ.get('FLOODGUARD_CONFIG')
    path = Path(explicit) if explicit else ROOT / 'config/application.local.yaml'
    if explicit and not path.is_file():
        raise FileNotFoundError(f'Configuration does not exist: {path}')
    content = yaml.safe_load(path.read_text(encoding='utf-8')) if path.is_file() else {}
    if content is None:
        content = {}
    if not isinstance(content, dict):
        raise ValueError('Configuration must be a mapping')
    return AiSettings.model_validate(content.get('ai', {}))
