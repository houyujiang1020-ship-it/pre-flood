"""Reload the frozen road-union checkpoint and independently replay dev validation."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app/training"))
import train_full as training  # noqa: E402

RUN = ROOT / "experiments/e4-road-union-aux-20261005"
CHECKPOINT = ROOT / "models/experiments/e4-road-union-aux-20261005/best_model.pth"
CONFIG = ROOT / "config/training.e4-road-union-aux-20261005.json"
ARCH = ROOT / "upstream/SpaceNet8/baseline/models/other/siamunetdif.py"
RESULT = RUN / "checkpoint_replay.json"


def main() -> None:
    if RESULT.exists():
        raise FileExistsError(RESULT)
    evaluation = json.loads((RUN / "evaluation.json").read_text(encoding="utf-8"))
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    if config["splits"].get("test"):
        raise ValueError("Test data is out of scope")
    if hashlib.sha256(CHECKPOINT.read_bytes()).hexdigest() != evaluation["candidate_checkpoint_sha256"]:
        raise ValueError("Selected checkpoint changed")
    records = training.split_rows(config, ROOT)["validation"]
    training.DISK_CACHE = ROOT / config["cache_dir"]
    training._cached_pair.cache_clear()
    checkpoint = torch.load(CHECKPOINT, map_location="cpu", weights_only=True)
    model = training.build_siamunet(ARCH, checkpoint["normalization"], checkpoint["groupnorm_groups"])
    model.load_state_dict(checkpoint["state_dict"], strict=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device).eval()
    with torch.inference_mode():
        replay = training.evaluate(model, records, config["image_size"], device,
                                   activation=checkpoint.get("output_activation", "sigmoid"))
    recorded = evaluation["candidate"]
    differences = {name: replay["class_iou"][name] - recorded["class_iou"][name]
                   for name in training.CLASSES}
    verified = all(abs(delta) < 1e-6 for delta in differences.values())
    result = {"checkpoint_epoch": checkpoint["epoch"], "selected_epoch": evaluation["selected_epoch"],
              "tile_count": len(records), "device": device, "class_iou_differences": differences,
              "checkpoint_replay_verified": verified and checkpoint["epoch"] == evaluation["selected_epoch"],
              "independent_accuracy_verified": False, "test_used": False}
    RESULT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    if not result["checkpoint_replay_verified"]:
        raise ValueError("Best checkpoint does not reproduce selected validation metrics")


if __name__ == "__main__":
    main()
