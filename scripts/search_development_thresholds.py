"""One-shot per-class threshold diagnostics on a named development validation split."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app/training"))
import train_full as training  # noqa: E402

ARCH = ROOT / "upstream/SpaceNet8/baseline/models/other/siamunetdif.py"
THRESHOLDS = [round(.30 + .05 * step, 2) for step in range(14)]


def sha(path: Path) -> str:
    """Read-only SHA256."""
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def rows_from_counts(tp: torch.Tensor, pred: torch.Tensor, gt: torch.Tensor) -> list[dict]:
    """Calculate pixel metrics for each class/threshold, with undefined precision as null."""
    rows = []
    for class_index, name in enumerate(training.CLASSES):
        for threshold_index, threshold in enumerate(THRESHOLDS):
            a = int(tp[class_index, threshold_index])
            b = int(pred[class_index, threshold_index])
            c = int(gt[class_index])
            precision = a / b if b else None
            recall = a / c if c else None
            denom_f1 = b + c
            union = b + c - a
            rows.append({"class": name, "threshold": threshold, "precision": precision,
                         "recall": recall, "f1": 2 * a / denom_f1 if denom_f1 else None,
                         "iou": a / union if union else None, "pred_pixels": b,
                         "gt_pixels": c, "tp_pixels": a})
    return rows


def main() -> None:
    """Freeze inputs then evaluate a predetermined grid; no test split is loaded."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    checkpoint_path = args.checkpoint.resolve()
    config_path = args.config.resolve()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(output)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config["splits"].get("test"):
        raise ValueError("Threshold search cannot access a test split")
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    if checkpoint.get("architecture") != "SiamUnet_diff" or checkpoint.get("classes") != training.CLASSES:
        raise ValueError("Expected four-channel SiamUnet_diff checkpoint")
    if checkpoint.get("dataset_split_hash") != hashlib.sha256(json.dumps(
            config["splits"], sort_keys=True).encode()).hexdigest():
        raise ValueError("Checkpoint and config split mismatch")
    records = training.split_rows(config, ROOT)["validation"]
    training.DISK_CACHE = ROOT / config["cache_dir"]
    training._cached_pair.cache_clear()
    model = training.build_siamunet(ARCH, checkpoint["normalization"], checkpoint["groupnorm_groups"])
    model.load_state_dict(checkpoint["state_dict"], strict=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device).eval()
    tp = torch.zeros((4, len(THRESHOLDS)), dtype=torch.int64)
    pred = torch.zeros_like(tp)
    gt = torch.zeros(4, dtype=torch.int64)
    with torch.inference_mode():
        for area, row in records:
            pre, post, truth, valid = training.cached_pair(area, row, config["image_size"])
            probability = training.output_probabilities(
                model(pre.unsqueeze(0).to(device), post.unsqueeze(0).to(device)),
                checkpoint.get("output_activation", "sigmoid")).cpu()[0]
            if not torch.isfinite(probability).all():
                raise ValueError("Nonfinite probabilities")
            mask = valid > 0
            expected = (truth > 0) & mask
            gt += expected.sum((1, 2))
            for idx, cutoff in enumerate(THRESHOLDS):
                predicted = (probability > cutoff) & mask
                pred[:, idx] += predicted.sum((1, 2))
                tp[:, idx] += (predicted & expected).sum((1, 2))
    rows = rows_from_counts(tp, pred, gt)
    output.mkdir(parents=True, exist_ok=False)
    with (output / "threshold_search.csv").open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    meta = {"generated_at": datetime.now(timezone.utc).isoformat(),
            "checkpoint_sha256": sha(checkpoint_path), "config_sha256": sha(config_path),
            "model_id": checkpoint.get("model_id"), "validation_tiles": len(records),
            "grid": THRESHOLDS, "development_only": True,
            "independent_test_accuracy_claim": False,
            "warning": "This Germany validation was previously used for development. Grid results cannot justify production promotion."}
    (output / "metadata.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    for name in training.CLASSES:
        candidates = [row for row in rows if row["class"] == name and row["pred_pixels"] > 0]
        best = max(candidates, key=lambda row: (row["iou"], row["precision"])) if candidates else None
        print(json.dumps({"class": name, "best_development_threshold": best["threshold"] if best else None,
                          "iou": best["iou"] if best else None, "precision": best["precision"] if best else None}))


if __name__ == "__main__":
    main()
