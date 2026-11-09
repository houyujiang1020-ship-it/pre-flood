from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class InferenceRequest(BaseModel):
    pre_image_path: Path
    post_image_path: Path
    output_dir: Path

    @field_validator("pre_image_path", "post_image_path")
    @classmethod
    def image_must_exist(cls, value: Path) -> Path:
        value = value.expanduser().resolve()
        if not value.is_file():
            raise ValueError(f"Image does not exist: {value}")
        return value

    @field_validator("output_dir")
    @classmethod
    def resolve_output(cls, value: Path) -> Path:
        return value.expanduser().resolve()


class JobResult(BaseModel):
    mask_path: Path
    preview_path: Path
    class_masks: dict[str, Path]
    statistics: dict[str, Any]
    inference_seconds: float
    model_version: str
    contract_path: Path | None = None
    contract_sha256: str | None = None
    probability_path: Path | None = None


class JobResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "failed"]
    progress: int = Field(ge=0, le=100)
    error: str | None = None
    result: JobResult | None = None
