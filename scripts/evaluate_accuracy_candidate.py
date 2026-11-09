"""Fixed-threshold development evaluation for a four-class SiamUnet checkpoint."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app/training"))
import train_full as training  # noqa: E402


def main() -> None:
    """Reload checkpoint on its frozen validation split; never access test labels."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    if cfg["splits"].get("test"):
        raise ValueError("This command evaluates development validation only")
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    if checkpoint.get("architecture") != "SiamUnet_diff" or checkpoint.get("classes") != training.CLASSES:
        raise ValueError("Four-class SiamUnet checkpoint required")
    expected_hash = hashlib.sha256(json.dumps(cfg["splits"], sort_keys=True).encode()).hexdigest()
    if checkpoint.get("dataset_split_hash") != expected_hash:
        raise ValueError("Checkpoint split differs from configuration")
    training.DISK_CACHE = ROOT / cfg["cache_dir"]
    training._cached_pair.cache_clear()
    records = training.split_rows(cfg, ROOT)["validation"]
    model = training.build_siamunet(
        ROOT / "upstream/SpaceNet8/baseline/models/other/siamunetdif.py",
        checkpoint["normalization"], checkpoint["groupnorm_groups"])
    model.load_state_dict(checkpoint["state_dict"], strict=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device).eval()
    metrics = training.evaluate(model, records, cfg["image_size"], device,
                                thresholds=[0.5] * 4)
    metrics["macro_iou"] = sum(metrics["class_iou"].values()) / 4
    metrics["development_only"] = True
    metrics["independent_test_accuracy_verified"] = False
    metrics["checkpoint_sha256"] = training.file_sha256(args.checkpoint)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"macro_iou": metrics["macro_iou"],
                      "flooded_road_iou": metrics["class_iou"]["flooded_road"]}))


if __name__ == "__main__":
    main()
