"""Rank flooded-road mistakes from a named split without changing model weights."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app/training"))
import train_full as training  # noqa: E402


def score_masks(probability: np.ndarray, truth: np.ndarray, valid: np.ndarray,
                normal_road: np.ndarray, threshold: float) -> dict:
    """Count road-status FP/FN/TP and false positives on known normal roads."""
    if probability.shape != truth.shape or truth.shape != valid.shape:
        raise ValueError("Aligned single-channel arrays required")
    predicted = (probability >= threshold) & valid
    expected = truth & valid
    fp = int((predicted & ~expected).sum())
    predicted_count = int(predicted.sum())
    return {"fp": fp, "fp_ratio": fp / predicted_count if predicted_count else 0.0,
            "fn": int((~predicted & expected).sum()),
            "tp": int((predicted & expected).sum()),
            "fp_on_normal_road": int((predicted & ~expected & normal_road).sum()),
            "predicted": predicted_count, "truth": int(expected.sum())}


def rgb(tensor: torch.Tensor) -> Image.Image:
    """Render a normalized CHW RGB tile for audit, without altering inputs."""
    return Image.fromarray((tensor.permute(1, 2, 0).numpy().clip(0, 1) * 255).astype(np.uint8))


def evidence(path: Path, pre: torch.Tensor, post: torch.Tensor, truth: np.ndarray,
             prediction: np.ndarray, valid: np.ndarray) -> None:
    """Create PRE/POST/GT/prediction/error panels for one ranked case."""
    panels = [rgb(pre), rgb(post)]
    for mask, color in ((truth, (0, 180, 0)), (prediction, (255, 100, 0)),
                        (prediction & ~truth & valid, (255, 0, 0)),
                        (~prediction & truth & valid, (0, 80, 255))):
        image = np.zeros((*mask.shape, 3), dtype=np.uint8)
        image[mask] = color
        panels.append(Image.fromarray(image))
    width, height = panels[0].size
    result = Image.new("RGB", (width * 3, height * 2 + 24), "white")
    draw = ImageDraw.Draw(result)
    for index, (panel, title) in enumerate(zip(panels, ("PRE", "POST", "GT", "PRED", "FP", "FN"))):
        x, y = (index % 3) * width, (index // 3) * height + 24
        result.paste(panel, (x, y))
        draw.text((x + 4, 4), title, fill="black")
    result.save(path)


def main() -> None:
    """Evaluate a fixed checkpoint and write non-overwriting error evidence."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--split", choices=("train", "validation"), required=True)
    parser.add_argument("--limit", type=int, default=0, help="0 means the full split")
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or not 0 < args.threshold < 1 or args.limit < 0:
        raise ValueError("Output must be new; threshold and limit must be valid")
    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    training.DISK_CACHE = ROOT / cfg["cache_dir"]
    training._cached_pair.cache_clear()
    records = training.split_rows(cfg, ROOT)[args.split]
    if args.limit:
        records = records[:args.limit]
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    if checkpoint.get("classes") != training.CLASSES:
        raise ValueError("Checkpoint four-class contract mismatch")
    expected_split_hash = hashlib.sha256(json.dumps(cfg["splits"], sort_keys=True).encode()).hexdigest()
    if checkpoint.get("dataset_split_hash") != expected_split_hash:
        raise ValueError("Checkpoint was not trained on the requested frozen split")
    model = training.build_siamunet(
        ROOT / "upstream/SpaceNet8/baseline/models/other/siamunetdif.py",
        checkpoint["normalization"], checkpoint["groupnorm_groups"])
    model.load_state_dict(checkpoint["state_dict"], strict=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device).eval()
    rows, top = [], []
    with torch.inference_mode():
        for area, row in records:
            pre, post, truth, valid = training.cached_pair(area, row, cfg["image_size"])
            probability = model(pre[None].to(device), post[None].to(device)).sigmoid()[0, 3].cpu().numpy()
            gt, is_valid = truth[3].numpy() > 0, valid.numpy() > 0
            predicted = probability >= args.threshold
            stats = score_masks(probability, gt, is_valid, truth[2].numpy() > 0, args.threshold)
            record = {"area": Path(area).name, "label": row["label"], "split": args.split, **stats}
            rows.append(record)
            top.append((record, pre, post, gt, predicted, is_valid))
    args.output.mkdir(parents=True, exist_ok=False)
    with (args.output / "failure_cases.csv").open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda item: item["fp"], reverse=True))
    for index, item in enumerate(sorted(top, key=lambda value: value[0]["fp"], reverse=True)[:3], 1):
        _, pre, post, gt, predicted, is_valid = item
        evidence(args.output / f"{index:02d}_flooded_road_errors.png", pre, post, gt, predicted, is_valid)
    (args.output / "metadata.json").write_text(json.dumps({
        "split": args.split, "sample_count": len(rows), "limited": bool(args.limit),
        "training_eligible_for_mining": args.split == "train" and not args.limit,
        "threshold": args.threshold, "checkpoint": str(args.checkpoint.resolve()),
        "checkpoint_sha256": training.file_sha256(args.checkpoint),
        "config_sha256": training.file_sha256(args.config),
        "independent_accuracy": False}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"split": args.split, "tiles": len(rows),
                      "flooded_road_fp": sum(row["fp"] for row in rows)}))


if __name__ == "__main__":
    main()
