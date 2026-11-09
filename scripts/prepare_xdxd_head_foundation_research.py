"""Freeze the external SpaceNet-5 head-only foundation feasibility run."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "config/training.single-unet-foundation-20260926.json"
CONFIG = ROOT / "config/training.xdxd-sn5-head-foundation-20260926.json"
RUN = ROOT / "experiments/germany-louisiana-xdxd-sn5-head-foundation-20260926"
WEIGHT = ROOT / "models/pretrained/spacenet5-xdxd/serx50_focal/fold0/fold0_best.state_dict.pth"
EXPECTED_WEIGHT_SHA = "f3201bb889bd8939d70a87c52ed4b5fb7a737bc8a83ea525416b89c37134b269"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    if sha256(WEIGHT) != EXPECTED_WEIGHT_SHA:
        raise RuntimeError("converted SpaceNet-5 checkpoint SHA-256 mismatch")
    config = json.loads(SOURCE.read_text(encoding="utf-8"))
    config.update(
        model_id="germany-louisiana-xdxd-sn5-head-foundation-20260926",
        output_dir="models/experiments/germany-louisiana-xdxd-sn5-head-foundation-20260926",
        foundation_architecture="xdxd_sn5_serx50_focal",
        foundation_trainable="head_only",
        freeze_batchnorm_statistics=True,
        external_pretrained_checkpoint=str(WEIGHT.relative_to(ROOT)),
        external_pretrained_sha256=EXPECTED_WEIGHT_SHA,
        normalization="batchnorm",
        learning_rate=0.001,
        epochs=10,
    )
    config.pop("initialization_checkpoint", None)
    config.pop("initialization_allowed_missing", None)
    if (ROOT / config["output_dir"]).exists():
        raise FileExistsError(ROOT / config["output_dir"])
    CONFIG.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    RUN.mkdir(parents=True, exist_ok=False)
    preregistration = {
        "schema": "xdxd-sn5-head-foundation-preregistration-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "Test whether frozen SpaceNet-5 road features support the local six-channel foundation targets through a new output head.",
        "external_checkpoint": str(WEIGHT.relative_to(ROOT)),
        "external_checkpoint_sha256": EXPECTED_WEIGHT_SHA,
        "source_url": "https://spacenet-dataset.s3.amazonaws.com/spacenet-model-weights/spacenet-5/xd_xd/serx50_focal/fold0/fold0_best.pth",
        "license": "Apache-2.0 per the checked-in SpaceNet8 fifth-place license inventory",
        "configuration": str(CONFIG.relative_to(ROOT)),
        "configuration_sha256": sha256(CONFIG),
        "fixed_protocol": {
            "split": {name: len(rows) for name, rows in config["splits"].items()},
            "epochs": 10,
            "threshold": 0.5,
            "trainable": "new six-channel 3x3 output head only",
            "frozen": "all pretrained encoder and decoder parameters plus BatchNorm statistics",
            "sampler": config["sampler"],
            "loss": "existing weighted BCE plus 0.5 Dice on six auxiliary channels",
        },
        "decision_rule": "If fixed-0.5 mean building/road object IoU exceeds the existing E3c development value 0.29009, retain this route for a future clean-split full-finetune study; otherwise stop it.",
        "scope": "Repeated Germany development validation only; not an independent accuracy estimate and not eligible for model promotion.",
        "test_used": False,
        "louisiana_west_used": False,
        "production_ready": False,
    }
    (RUN / "preregistration.json").write_text(
        json.dumps(preregistration, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(preregistration, indent=2))


if __name__ == "__main__":
    main()
