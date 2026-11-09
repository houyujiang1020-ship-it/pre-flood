"""Measure flooded-road false positives near/far from labeled road geometry."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import torch
import numpy as np
from PIL import Image, ImageFilter
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app/training"))
import train_full as training  # noqa: E402

RADII = (5, 10, 20)


def spatial_counts(predicted: torch.Tensor, truth: torch.Tensor, valid: torch.Tensor,
                   roads: torch.Tensor, radii: tuple[int, ...] = RADII,
                   device: str = "cpu") -> list[dict]:
    """Count FP within/outside road dilation for each configured pixel radius."""
    if any(t.shape != predicted.shape for t in (truth, valid, roads)):
        raise ValueError("Aligned 2D masks required")
    fp = predicted.to(device).bool() & ~truth.to(device).bool() & valid.to(device).bool()
    road = roads.to(device).bool() & valid.to(device).bool()
    rows = []
    for radius in radii:
        if type(radius) is not int or radius < 0 or radius > 64:
            raise ValueError("Invalid road buffer radius")
        if device == "cuda":
            nearby = F.max_pool2d(road.float()[None, None], 2 * radius + 1,
                                  stride=1, padding=radius)[0, 0].bool()
        else:
            nearby = torch.from_numpy(np.asarray(Image.fromarray(
                (road.numpy().astype(np.uint8) * 255)).filter(
                    ImageFilter.MaxFilter(2 * radius + 1))).copy() > 0)
        near = int((fp & nearby).sum())
        far = int((fp & ~nearby).sum())
        rows.append({"buffer_pixels": radius, "fp_near_road": near,
                     "fp_far_from_road": far, "fp_total": near + far,
                     "far_fraction": far / (near + far) if near + far else None})
    return rows


def main() -> None:
    """Evaluate fixed 0.5 predictions on a named validation split."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    expected = hashlib.sha256(json.dumps(cfg["splits"], sort_keys=True).encode()).hexdigest()
    if checkpoint.get("dataset_split_hash") != expected or checkpoint.get("classes") != training.CLASSES:
        raise ValueError("Checkpoint/split/four-class contract mismatch")
    training.DISK_CACHE = ROOT / cfg["cache_dir"]
    training._cached_pair.cache_clear()
    records = training.split_rows(cfg, ROOT)["validation"]
    model = training.build_siamunet(ROOT / "upstream/SpaceNet8/baseline/models/other/siamunetdif.py",
                                    checkpoint["normalization"], checkpoint["groupnorm_groups"])
    model.load_state_dict(checkpoint["state_dict"], strict=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device).eval()
    rows = []
    with torch.inference_mode():
        for area, item in records:
            pre, post, truth, valid = training.cached_pair(area, item, cfg["image_size"])
            probability = model(pre[None].to(device), post[None].to(device))[0, 3].sigmoid().cpu()
            road_union = (truth[2] > 0) | (truth[3] > 0)
            for entry in spatial_counts(probability >= 0.5, truth[3] > 0, valid > 0,
                                        road_union, device=device):
                rows.append({"model_id": cfg["model_id"], "sample_id": f"{Path(area).name}:{item['label']}",
                             "scope": "spatial_development_validation", **entry})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        for radius in RADII:
            group = [row for row in rows if row["buffer_pixels"] == radius]
            near, far = sum(row["fp_near_road"] for row in group), sum(row["fp_far_from_road"] for row in group)
            writer.writerow({"model_id": cfg["model_id"], "sample_id": "ALL", "scope": "aggregate",
                             "buffer_pixels": radius, "fp_near_road": near, "fp_far_from_road": far,
                             "fp_total": near + far, "far_fraction": far / (near + far) if near + far else ""})
    print(json.dumps({"tiles": len(records), "output": str(args.output)}))


if __name__ == "__main__":
    main()
