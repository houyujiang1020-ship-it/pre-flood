"""Independently reload both pilots and compare fixed-0.5 development metrics."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app/training"))
import train_full as training  # noqa: E402
from foundation_flood_models import FloodChangeModel  # noqa: E402
from train_flood_change import evaluate as evaluate_fusion, load_foundation  # noqa: E402

from model_promotion import decide

OUT = ROOT / "experiments/accuracy-pipeline-20261005"
ARCH = ROOT / "upstream/SpaceNet8/baseline/models/other/siamunetdif.py"


def write_new(path: Path, payload: dict) -> None:
    """Refuse accidental loss of a previous evaluation artifact."""
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    """Evaluate frozen checkpoints on the same 18 development scenes."""
    paths = [OUT / f"{name}-metrics.json" for name in ("e4", "crop", "fusion")]
    paths += [OUT / f"{name}-promotion.json" for name in ("crop", "fusion")]
    comparison = ROOT / "reports/model_comparison.csv"
    if any(path.exists() for path in paths + [comparison]):
        raise FileExistsError("Finalized pilot output already exists")
    baseline_record = json.loads((ROOT / "experiments/e4-mutual-exclusion-20261005/evaluation.json").read_text())
    if not baseline_record["baseline_replay_verified"]:
        raise ValueError("E4 baseline replay was not verified")
    baseline = baseline_record["baseline"]
    e4 = {key: baseline[key] for key in ("class_iou", "class_precision", "class_recall", "prediction_pixels", "macro_iou")}
    e4["source"] = "reloaded E4, fixed 0.5 Germany development validation"
    config = json.loads((ROOT / "config/training.class-aware-crop-pilot-20261005.json").read_text())
    training.DISK_CACHE = ROOT / config["cache_dir"]
    training._cached_pair.cache_clear()
    records = training.split_rows(config, ROOT)["validation"]
    checkpoint = torch.load(ROOT / config["output_dir"] / "best_model.pth", map_location="cpu", weights_only=True)
    model = training.build_siamunet(ARCH, checkpoint["normalization"], checkpoint["groupnorm_groups"])
    model.load_state_dict(checkpoint["state_dict"], strict=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device).eval()
    crop = training.evaluate(model, records, config["image_size"], device)
    crop["macro_iou"] = sum(crop["class_iou"].values()) / 4
    historical = checkpoint["history"][checkpoint["epoch"] - 1]["validation"]["class_iou"]
    if any(abs(crop["class_iou"][name] - historical[name]) > 1e-5 for name in training.CLASSES):
        raise ValueError("Crop checkpoint reload did not reproduce training evaluation")
    crop["source"] = "reloaded class-aware crop pilot, fixed 0.5 Germany development validation"
    fusion_config = json.loads((ROOT / "config/training.flood-change-pilot-20261005.json").read_text())
    foundation = load_foundation(ROOT / fusion_config["foundation_checkpoint"], device)
    from torch.torch_version import TorchVersion
    with torch.serialization.safe_globals([TorchVersion]):
        status_checkpoint = torch.load(ROOT / fusion_config["output_dir"] / "best_model.pth",
                                       map_location="cpu", weights_only=True)
    status = FloodChangeModel(ARCH)
    status.load_state_dict(status_checkpoint["state_dict"], strict=True)
    status.to(device).eval()
    fused = evaluate_fusion(foundation, status, records, fusion_config["image_size"], device,
                            fusion_config["road_dilation_pixels"], fusion_config["road_prior_floor"])
    historic_fusion = status_checkpoint["history"][status_checkpoint["epoch"] - 1]["validation"]["class_iou"]
    if any(abs(fused["class_iou"][name] - historic_fusion[name]) > 1e-5 for name in training.CLASSES):
        raise ValueError("Fusion checkpoint reload did not reproduce training evaluation")
    fused["source"] = "reloaded E3c + flooded-object status pilot, fixed 0.5 Germany development validation"
    for path, value in zip(paths[:3], (e4, crop, fused)):
        write_new(path, value)
    for path, value in zip(paths[3:], (crop, fused)):
        write_new(path, decide(e4, value))
    comparison.parent.mkdir(parents=True, exist_ok=True)
    with comparison.open("x", encoding="utf-8", newline="") as stream:
        fieldnames = ["Model", "Building IoU", "Flooded Building IoU", "Road IoU", "Flooded Road IoU",
                      "Macro IoU", "Flooded Road Precision", "Flooded Road Recall", "Flooded Road F1",
                      "Flooded Road Predicted Pixels", "Decision", "Scope"]
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for name, result in (("E4", e4), ("ClassAwareCropPilot", crop), ("FoundationFloodFusionPilot", fused)):
            precision = result["class_precision"]["flooded_road"]
            recall = result["class_recall"]["flooded_road"]
            writer.writerow({"Model": name,
                             "Building IoU": result["class_iou"]["non_flooded_building"],
                             "Flooded Building IoU": result["class_iou"]["flooded_building"],
                             "Road IoU": result["class_iou"]["non_flooded_road"],
                             "Flooded Road IoU": result["class_iou"]["flooded_road"],
                             "Macro IoU": result["macro_iou"],
                             "Flooded Road Precision": precision, "Flooded Road Recall": recall,
                             "Flooded Road F1": (2 * precision * recall / (precision + recall)
                                                 if precision is not None and recall is not None and precision + recall else 0),
                             "Flooded Road Predicted Pixels": result["prediction_pixels"]["flooded_road"],
                             "Decision": ("BASELINE" if name == "E4" else
                                          decide(e4, result)["decision"]),
                             "Scope": "Germany development validation only"})
    print(json.dumps({"crop": decide(e4, crop), "fusion": decide(e4, fused)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
