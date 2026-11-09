"""One-shot, preregistered two-checkpoint inference experiment; no model training."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app/training"))
import train_full as training  # noqa: E402

RUN = ROOT / "experiments/e4-fixed-probability-ensemble-20261005"
PREREG = RUN / "preregistration.json"
RESULT = RUN / "evaluation.json"
CONFIG = ROOT / "config/training.foundation-initialized-four-class-20260926.json"
E4 = ROOT / "models/experiments/germany-louisiana-foundation-initialized-four-class-20260926/best_model.pth"
DOMAIN = ROOT / "models/experiments/germany-louisiana-domain-balanced-20260926/best_model.pth"
ARCH = ROOT / "upstream/SpaceNet8/baseline/models/other/siamunetdif.py"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def prepare() -> None:
    RUN.mkdir(parents=True, exist_ok=True)
    if PREREG.exists() or RESULT.exists():
        raise FileExistsError("Experiment already frozen; do not overwrite it")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    if config.get("splits", {}).get("test"):
        raise ValueError("This protocol must not access any test split")
    payload = {
        "status": "preregistered_before_evaluation",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experiment": "e4-fixed-probability-ensemble-20261005",
        "hypothesis": "Fixed equal-probability averaging may reduce four-class false positives without new annotations.",
        "inputs": {"e4": str(E4.relative_to(ROOT)), "e4_sha256": digest(E4),
                   "domain_balanced": str(DOMAIN.relative_to(ROOT)), "domain_balanced_sha256": digest(DOMAIN),
                   "config": str(CONFIG.relative_to(ROOT)), "config_sha256": digest(CONFIG),
                   "architecture_sha256": digest(ARCH)},
        "formula": "probability = 0.5 * sigmoid(E4 logits) + 0.5 * sigmoid(domain-balanced logits)",
        "threshold": 0.5,
        "evaluation": "existing 18-tile Germany development validation only; no test, no threshold search",
        "promotion_rule": "candidate only if macro IoU >= E4 + 0.005, every class IoU >= E4 - 0.005, and flooded-road precision does not decline",
        "scope": "development diagnostic only; cannot establish independent accuracy or production readiness",
        "test_used": False, "production_ready": False,
    }
    save(PREREG, payload)
    print(PREREG)


def stats(counts: dict[str, torch.Tensor]) -> dict:
    tp, pred, truth = (counts[k].double() for k in ("tp", "pred", "truth"))
    union = pred + truth - tp
    ratio = lambda numerator, denominator: [float((numerator[i] / denominator[i]).item()) if denominator[i] else None
                                            for i in range(4)]
    return {"class_iou": dict(zip(training.CLASSES, ratio(tp, union))),
            "class_precision": dict(zip(training.CLASSES, ratio(tp, pred))),
            "class_recall": dict(zip(training.CLASSES, ratio(tp, truth))),
            "truth_pixels": dict(zip(training.CLASSES, truth.tolist())),
            "prediction_pixels": dict(zip(training.CLASSES, pred.tolist())),
            "status_overlap_pixels": counts["overlap"].tolist(),
            "macro_iou": float(sum(ratio(tp, union)) / 4)}


def evaluate() -> None:
    if not PREREG.is_file() or RESULT.exists():
        raise RuntimeError("Prepare first; never overwrite a completed evaluation")
    frozen = json.loads(PREREG.read_text(encoding="utf-8"))
    for name, path in (("e4", E4), ("domain_balanced", DOMAIN), ("config", CONFIG)):
        if digest(path) != frozen["inputs"][name + "_sha256"]:
            raise ValueError("Frozen input changed: " + name)
    if digest(ARCH) != frozen["inputs"]["architecture_sha256"]:
        raise ValueError("Model architecture changed")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    if config.get("splits", {}).get("test"):
        raise ValueError("Test split is out of scope")
    records = training.split_rows(config, ROOT)["validation"]
    training.DISK_CACHE = ROOT / config["cache_dir"]
    training._cached_pair.cache_clear()
    models = []
    checkpoint_ids = []
    for path in (E4, DOMAIN):
        checkpoint = torch.load(path, map_location="cpu", weights_only=True)
        if checkpoint.get("architecture") != "SiamUnet_diff" or checkpoint.get("classes") != training.CLASSES:
            raise ValueError("Checkpoint schema differs from frozen four-class task")
        if checkpoint.get("dataset_split_hash") != "90302621e46680801fd2a1da1aa07afaaae567c71ec1ecd8a05b033eb2017229":
            raise ValueError("Checkpoint split identity differs")
        model = training.build_siamunet(ARCH, checkpoint["normalization"], checkpoint["groupnorm_groups"])
        model.load_state_dict(checkpoint["state_dict"], strict=True)
        models.append(model.cuda().eval())
        checkpoint_ids.append(checkpoint["model_id"])
    counts = {name: {key: torch.zeros(size, dtype=torch.int64) for key, size in
                     (("tp", 4), ("pred", 4), ("truth", 4), ("overlap", 2))}
              for name in ("e4", "ensemble")}
    with torch.inference_mode():
        for area, row in records:
            pre, post, truth, valid = training.cached_pair(area, row, config["image_size"])
            pre, post = pre.unsqueeze(0).cuda(), post.unsqueeze(0).cuda()
            probabilities = [model(pre, post).sigmoid().cpu() for model in models]
            valid_mask = valid.unsqueeze(0).unsqueeze(0) > 0
            expected = (truth.unsqueeze(0) > 0) & valid_mask
            for name, probability in (("e4", probabilities[0]),
                                      ("ensemble", (probabilities[0] + probabilities[1]) / 2)):
                predicted = (probability > .5) & valid_mask
                item = counts[name]
                item["tp"] += (predicted & expected).sum((0, 2, 3)).to(torch.int64)
                item["pred"] += predicted.sum((0, 2, 3)).to(torch.int64)
                item["truth"] += expected.sum((0, 2, 3)).to(torch.int64)
                item["overlap"][0] += (predicted[:, 0] & predicted[:, 1]).sum()
                item["overlap"][1] += (predicted[:, 2] & predicted[:, 3]).sum()
    baseline, candidate = stats(counts["e4"]), stats(counts["ensemble"])
    history = json.loads((E4.parent / "history.json").read_text(encoding="utf-8"))
    historical = history[13]["validation"]["class_iou"]
    replay_ok = all(abs(baseline["class_iou"][key] - historical[key]) < 1e-5 for key in training.CLASSES)
    if not replay_ok:
        raise ValueError("E4 replay does not reproduce archived epoch-14 metrics")
    deltas = {key: candidate["class_iou"][key] - baseline["class_iou"][key] for key in training.CLASSES}
    macro_delta = candidate["macro_iou"] - baseline["macro_iou"]
    flooded_precision_delta = (candidate["class_precision"]["flooded_road"]
                               - baseline["class_precision"]["flooded_road"])
    accepted = (macro_delta >= .005 and min(deltas.values()) >= -.005 and flooded_precision_delta >= 0)
    output = {"status": "completed", "finished_at": datetime.now(timezone.utc).isoformat(),
              "preregistration_sha256": digest(PREREG), "tile_count": len(records),
              "checkpoint_ids": checkpoint_ids, "baseline_replay_verified": replay_ok,
              "baseline": baseline, "candidate": candidate,
              "delta": {"macro_iou": macro_delta, "class_iou": deltas,
                        "flooded_road_precision": flooded_precision_delta},
              "promotion": "development_candidate" if accepted else "rejected",
              "production_ready": False, "independent_accuracy_verified": False,
              "test_used": False}
    save(RESULT, output)
    print(json.dumps({"promotion": output["promotion"], "macro_delta": macro_delta,
                      "flooded_road_precision_delta": flooded_precision_delta}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "evaluate"))
    args = parser.parse_args()
    (prepare if args.command == "prepare" else evaluate)()
