"""Export opt-in E4 probability rasters and JSON without changing API contracts."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app/training"))
from model_factory import build_siamunet  # noqa: E402
from pseudo_label.generate_pseudo_labels import digest, load_aligned_pair  # noqa: E402

CLASSES = ("non_flooded_building", "flooded_building", "non_flooded_road", "flooded_road")


def summarize(probabilities: np.ndarray, valid: np.ndarray) -> dict:
    """Describe four E4 channels and soft object/status unions on the PRE grid."""
    if probabilities.ndim != 3 or probabilities.shape[0] != 4 or valid.shape != probabilities.shape[1:]:
        raise ValueError("Expected four probability maps and aligned validity mask")
    if not np.isfinite(probabilities).all() or (probabilities < 0).any() or (probabilities > 1).any():
        raise ValueError("Invalid model probabilities")
    if not valid.any():
        raise ValueError("No joint valid PRE/POST pixels")
    building = np.maximum(probabilities[0], probabilities[1])
    road = np.maximum(probabilities[2], probabilities[3])
    flooded_object = np.maximum(probabilities[1], probabilities[3])
    return {"class_mean_valid_probability": {
                name: float(probabilities[index][valid].mean()) for index, name in enumerate(CLASSES)},
            "building_probability_mean": float(building[valid].mean()),
            "road_probability_mean": float(road[valid].mean()),
            "flooded_object_probability_mean": float(flooded_object[valid].mean()),
            "note": "Flooded-object probability is not a continuous flood-water mask"}


def main() -> None:
    """Write a fresh extended_prediction.json plus four lossless float maps."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--pre", type=Path, required=True)
    parser.add_argument("--post", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--size", type=int, default=512)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    if checkpoint.get("architecture") != "SiamUnet_diff" or checkpoint.get("classes") != list(CLASSES):
        raise ValueError("Expected four-class E4-compatible checkpoint")
    pre, post, valid = load_aligned_pair(args.pre, args.post, args.size)
    model = build_siamunet(ROOT / "upstream/SpaceNet8/baseline/models/other/siamunetdif.py",
                           checkpoint["normalization"], checkpoint["groupnorm_groups"])
    model.load_state_dict(checkpoint["state_dict"], strict=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device).eval()
    with torch.inference_mode():
        probability = model(pre[None].to(device), post[None].to(device)).sigmoid()[0].cpu().numpy()
    summary = summarize(probability, valid)
    args.output.mkdir(parents=True, exist_ok=False)
    np.savez_compressed(args.output / "probability_maps.npz", final_class_probability=probability,
                        building_probability=np.maximum(probability[0], probability[1]),
                        road_probability=np.maximum(probability[2], probability[3]),
                        flooded_object_probability=np.maximum(probability[1], probability[3]),
                        valid=valid)
    record = {"schema": "floodguard-extended-prediction-research-v1", "classes": CLASSES,
              "pre": str(args.pre.resolve()), "pre_sha256": digest(args.pre),
              "post": str(args.post.resolve()), "post_sha256": digest(args.post),
              "checkpoint_sha256": digest(args.checkpoint), "image_size": args.size,
              "probability_file": "probability_maps.npz", "summary": summary,
              "changes_existing_flood_prediction_json": False,
              "independent_ground_truth_evaluation": False}
    (args.output / "extended_prediction.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), **summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
