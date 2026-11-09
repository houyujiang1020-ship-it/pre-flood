"""Optional soft foundation-road prior diagnostic after high road-far FP rate."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app/training"))
import train_full as training  # noqa: E402
from foundation_flood_models import FoundationSegmentationModel  # noqa: E402

ALPHAS = (1.0, 0.5, 0.7, 0.8, 0.9)


def summarize(tp: int, predicted: int, truth: int) -> dict:
    """Compute flooded-road metrics without substituting undefined precision."""
    union = predicted + truth - tp
    return {"iou": tp / union if union else None,
            "precision": tp / predicted if predicted else None,
            "recall": tp / truth if truth else None,
            "predicted_pixels": predicted, "truth_pixels": truth}


def main() -> None:
    """Evaluate alpha>0 soft priors at fixed 0.5; never modify the model."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--foundation-checkpoint", type=Path, required=True)
    parser.add_argument("--fp-analysis", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    with args.fp_analysis.open(encoding="utf-8", newline="") as stream:
        fp_rows = list(csv.DictReader(stream))
    aggregate = [row for row in fp_rows if row["sample_id"] == "ALL" and row["buffer_pixels"] == "5"
                 and row["model_id"] == cfg["model_id"]]
    if len(aggregate) != 1 or float(aggregate[0]["far_fraction"]) < 0.4:
        raise ValueError("Soft prior diagnostic requires >=40% road-far FP at 5-pixel buffer")
    model_record = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    foundation_record = torch.load(args.foundation_checkpoint, map_location="cpu", weights_only=True)
    split_hash = hashlib.sha256(json.dumps(cfg["splits"], sort_keys=True).encode()).hexdigest()
    if model_record.get("dataset_split_hash") != split_hash or model_record.get("classes") != training.CLASSES:
        raise ValueError("Model checkpoint does not match frozen split")
    if foundation_record.get("architecture") != "single_unet_skip":
        raise ValueError("Expected clean single-image foundation")
    training.DISK_CACHE = ROOT / cfg["cache_dir"]
    training._cached_pair.cache_clear()
    records = training.split_rows(cfg, ROOT)["validation"]
    arch = ROOT / "upstream/SpaceNet8/baseline/models/other/siamunetdif.py"
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = training.build_siamunet(arch, model_record["normalization"],
                                    model_record["groupnorm_groups"])
    model.load_state_dict(model_record["state_dict"], strict=True)
    foundation = FoundationSegmentationModel(arch, foundation_record["normalization"],
                                             foundation_record["groupnorm_groups"])
    foundation.network.load_state_dict(foundation_record["state_dict"], strict=True)
    model.to(device).eval()
    foundation.to(device).eval()
    counts = {alpha: {"tp": 0, "pred": 0, "gt": 0} for alpha in ALPHAS}
    with torch.inference_mode():
        for area, row in records:
            pre, post, truth, valid = training.cached_pair(area, row, cfg["image_size"])
            pre_device, post_device = pre[None].to(device), post[None].to(device)
            p_model = model(pre_device, post_device)[0, 3].sigmoid()
            p_road = foundation.probabilities(pre_device)[0, 2]
            expected = (truth[3] > 0).to(device) & (valid > 0).to(device)
            for alpha in ALPHAS:
                final = p_model * (alpha + (1 - alpha) * p_road)
                predicted = (final > 0.5) & (valid > 0).to(device)
                counts[alpha]["tp"] += int((predicted & expected).sum())
                counts[alpha]["pred"] += int(predicted.sum())
                counts[alpha]["gt"] += int(expected.sum())
    rows = []
    for alpha in ALPHAS:
        item = counts[alpha]
        rows.append({"alpha": alpha, "threshold": 0.5,
                     "road_far_fp_fraction_5px_before_prior": aggregate[0]["far_fraction"],
                     "diagnostic_only": True, **summarize(item["tp"], item["pred"], item["gt"])})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(rows))


if __name__ == "__main__":
    main()
