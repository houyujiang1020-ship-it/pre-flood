"""Strict-load and fixed-threshold probe for the external SpaceNet-5 road weight."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "training"))
import train_full as base  # noqa: E402
from xdxd_sn5 import build_xdxd_sn5, parameter_counts  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config_path = ROOT / "config/training.single-unet-foundation-20260926.json"
    weight = ROOT / "models/pretrained/spacenet5-xdxd/serx50_focal/fold0/fold0_best.state_dict.pth"
    source = ROOT / "upstream/SpaceNet8/05-motokimura/code/spacenet8_model/models/xdxd_sn5/senet.py"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    base.DISK_CACHE = ROOT / config["cache_dir"]
    base._cached_pair.cache_clear()
    records = base.split_rows(config, ROOT)["validation"]
    model = build_xdxd_sn5(source, 8, weight).cuda().eval()
    probe_input = torch.zeros(1, 3, 512, 512, device="cuda")
    torch.cuda.reset_peak_memory_stats()
    torch.cuda.synchronize()
    started = time.time()
    with torch.inference_mode():
        probe_output = model(probe_input)
    torch.cuda.synchronize()
    forward = {
        "shape": list(probe_output.shape),
        "seconds": round(time.time() - started, 6),
        "peak_cuda_bytes": torch.cuda.max_memory_allocated(),
        "finite": bool(torch.isfinite(probe_output).all()),
    }
    intersection = union = prediction_pixels = truth_pixels = 0
    per_tile = []
    with torch.inference_mode():
        for area, row in records:
            pre, _, truth, valid = base.cached_pair(area, row, int(config["image_size"]))
            probability = model(pre.unsqueeze(0).cuda())[:, -1].sigmoid().cpu()[0]
            prediction = (probability > 0.5) & (valid > 0)
            expected = ((truth[2] > 0) | (truth[3] > 0)) & (valid > 0)
            tile_intersection = int((prediction & expected).sum())
            tile_union = int((prediction | expected).sum())
            predicted = int(prediction.sum())
            positive = int(expected.sum())
            intersection += tile_intersection
            union += tile_union
            prediction_pixels += predicted
            truth_pixels += positive
            per_tile.append({
                "area": area.name,
                "label": row["label"],
                "intersection": tile_intersection,
                "union": tile_union,
                "prediction_pixels": predicted,
                "truth_pixels": positive,
                "iou": tile_intersection / tile_union if tile_union else None,
            })
    report = {
        "schema": "spacenet5-xdxd-road-probe-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "weight": str(weight.relative_to(ROOT)),
        "weight_sha256": sha256(weight),
        "architecture_source_sha256": sha256(source),
        "strict_state_dict_load": True,
        "parameter_counts": parameter_counts(model),
        "forward_512": forward,
        "zero_shot_fixed_0_5": {
            "scope": "Existing Germany development validation; diagnostic only.",
            "tile_count": len(records),
            "intersection": intersection,
            "union": union,
            "prediction_pixels": prediction_pixels,
            "truth_pixels": truth_pixels,
            "iou": intersection / union,
            "precision": intersection / prediction_pixels if prediction_pixels else None,
            "recall": intersection / truth_pixels if truth_pixels else None,
            "per_tile": per_tile,
        },
        "test_used": False,
        "production_ready": False,
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
