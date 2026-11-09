"""Seal the preregistered SpaceNet-5 head-only foundation decision."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "experiments/germany-louisiana-xdxd-sn5-head-foundation-20260926"
MODEL_DIR = ROOT / "models/experiments/germany-louisiana-xdxd-sn5-head-foundation-20260926"
BASELINE_REPORT = ROOT / "models/experiments/germany-louisiana-single-unet-foundation-20260926/training_report.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    prereg = load(RUN / "preregistration.json")
    config_path = ROOT / prereg["configuration"]
    if sha256(config_path) != prereg["configuration_sha256"]:
        raise RuntimeError("configuration changed after preregistration")
    config = load(config_path)
    if config["external_pretrained_sha256"] != prereg["external_checkpoint_sha256"]:
        raise RuntimeError("external checkpoint identity differs from preregistration")
    checkpoint_path = MODEL_DIR / "best_model.pth"
    checkpoint_sha = sha256(checkpoint_path)
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    reload_evaluation = load(RUN / "independent-reload-evaluation.json")
    if reload_evaluation["checkpoint_sha256"] != checkpoint_sha:
        raise RuntimeError("independent evaluation checkpoint mismatch")
    training_report = load(MODEL_DIR / "training_report.json")
    candidate = reload_evaluation["mean_object_iou"]
    if abs(candidate - training_report["best_validation"]["mean_object_iou"]) > 1e-9:
        raise RuntimeError("independent reload did not reproduce selected IoU")
    baseline_report = load(BASELINE_REPORT)
    baseline = baseline_report["best_validation"]["mean_object_iou"]
    passed = candidate > 0.29009
    result = {
        "schema": "xdxd-sn5-head-foundation-decision-v1",
        "sealed_at": datetime.now(timezone.utc).isoformat(),
        "preregistration_sha256": sha256(RUN / "preregistration.json"),
        "configuration_sha256": sha256(config_path),
        "external_checkpoint_sha256": prereg["external_checkpoint_sha256"],
        "candidate_checkpoint": str(checkpoint_path.relative_to(ROOT)),
        "candidate_checkpoint_sha256": checkpoint_sha,
        "best_epoch": checkpoint["epoch"],
        "candidate_validation": {key: reload_evaluation[key] for key in (
            "building_iou", "road_iou", "mean_object_iou", "building_precision",
            "building_recall", "road_precision", "road_recall", "tile_count")},
        "existing_e3c_development": baseline_report["best_validation"],
        "mean_object_iou_delta": candidate - baseline,
        "decision_rule": prereg["decision_rule"],
        "decision_rule_passed": passed,
        "decision": "retain_for_clean_split_full_finetune" if passed else "stop_head_only_transfer",
        "promotion": "ineligible" if passed else "rejected",
        "reason": "The frozen external representation plus a new output head did not reach the preregistered existing E3c development result.",
        "zero_shot_probe_sha256": sha256(RUN / "zero-shot-probe.json"),
        "independent_reload_sha256": sha256(RUN / "independent-reload-evaluation.json"),
        "scope": prereg["scope"],
        "test_used": False,
        "louisiana_west_used": False,
        "production_ready": False,
    }
    output = RUN / "evaluation.json"
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({**result, "evaluation_sha256": sha256(output)}, indent=2))


if __name__ == "__main__":
    main()
