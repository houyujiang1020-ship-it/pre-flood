"""One-shot, fixed argmax-with-abstain diagnostic on E4's four sigmoid channels."""
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

RUN = ROOT / "experiments/e4-mutual-exclusion-20261005"
PREREG = RUN / "preregistration.json"
RESULT = RUN / "evaluation.json"
CONFIG = ROOT / "config/training.foundation-initialized-four-class-20260926.json"
CHECKPOINT = ROOT / "models/experiments/germany-louisiana-foundation-initialized-four-class-20260926/best_model.pth"
ARCH = ROOT / "upstream/SpaceNet8/baseline/models/other/siamunetdif.py"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path: Path, value: dict) -> None:
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def exclusive(probability: torch.Tensor) -> torch.Tensor:
    """For each building/road pair, choose the larger probability iff > 0.5."""
    if probability.shape[1] != 4:
        raise ValueError("Expected four output channels")
    output = torch.zeros_like(probability, dtype=torch.bool)
    for normal, flooded in ((0, 1), (2, 3)):
        p0, p1 = probability[:, normal], probability[:, flooded]
        output[:, normal] = (p0 > .5) & (p0 >= p1)
        output[:, flooded] = (p1 > .5) & (p1 > p0)
    return output


def summary(counts: dict[str, torch.Tensor]) -> dict:
    tp, pred, truth = (counts[k].double() for k in ("tp", "pred", "truth"))
    def ratio(numerator, denominator):
        return [float((numerator[i] / denominator[i]).item()) if denominator[i] else None for i in range(4)]
    iou = ratio(tp, pred + truth - tp)
    return {"class_iou": dict(zip(training.CLASSES, iou)),
            "class_precision": dict(zip(training.CLASSES, ratio(tp, pred))),
            "class_recall": dict(zip(training.CLASSES, ratio(tp, truth))),
            "prediction_pixels": dict(zip(training.CLASSES, pred.tolist())),
            "status_overlap_pixels": counts["overlap"].tolist(),
            "macro_iou": sum(iou) / 4}


def prepare() -> None:
    RUN.mkdir(parents=True, exist_ok=True)
    if PREREG.exists() or RESULT.exists():
        raise FileExistsError("Experiment already frozen")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    if config["splits"].get("test"):
        raise ValueError("Test split must be empty")
    write_new(PREREG, {"status": "preregistered_before_evaluation",
                       "created_at": datetime.now(timezone.utc).isoformat(),
                       "experiment": "e4-mutual-exclusion-20261005",
                       "rule": "Within building (0,1) and road (2,3), emit only higher probability if that probability exceeds 0.5; ties go to non-flooded.",
                       "threshold": .5,
                       "inputs": {"checkpoint_sha256": digest(CHECKPOINT),
                                  "config_sha256": digest(CONFIG), "architecture_sha256": digest(ARCH)},
                       "promotion_rule": "macro IoU >= baseline + 0.005, every class IoU >= baseline - 0.005, flooded-road precision does not decline",
                       "evaluation": "existing Germany 18-tile development validation only",
                       "test_used": False, "production_ready": False})


def evaluate() -> None:
    if not PREREG.is_file() or RESULT.exists():
        raise RuntimeError("Prepare first; do not overwrite")
    frozen = json.loads(PREREG.read_text(encoding="utf-8"))
    for key, path in (("checkpoint", CHECKPOINT), ("config", CONFIG), ("architecture", ARCH)):
        if digest(path) != frozen["inputs"][key + "_sha256"]:
            raise ValueError("Frozen input changed: " + key)
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    if config["splits"].get("test"):
        raise ValueError("Test split must be empty")
    records = training.split_rows(config, ROOT)["validation"]
    training.DISK_CACHE = ROOT / config["cache_dir"]
    training._cached_pair.cache_clear()
    checkpoint = torch.load(CHECKPOINT, map_location="cpu", weights_only=True)
    model = training.build_siamunet(ARCH, checkpoint["normalization"], checkpoint["groupnorm_groups"])
    model.load_state_dict(checkpoint["state_dict"], strict=True)
    model.cuda().eval()
    counts = {name: {k: torch.zeros(n, dtype=torch.int64) for k, n in
                     (("tp", 4), ("pred", 4), ("truth", 4), ("overlap", 2))}
              for name in ("baseline", "candidate")}
    with torch.inference_mode():
        for area, row in records:
            pre, post, truth, valid = training.cached_pair(area, row, config["image_size"])
            probability = model(pre.unsqueeze(0).cuda(), post.unsqueeze(0).cuda()).sigmoid().cpu()
            mask = valid.unsqueeze(0).unsqueeze(0) > 0
            expected = (truth.unsqueeze(0) > 0) & mask
            for name, prediction in (("baseline", probability > .5), ("candidate", exclusive(probability))):
                prediction &= mask
                current = counts[name]
                current["tp"] += (prediction & expected).sum((0, 2, 3))
                current["pred"] += prediction.sum((0, 2, 3))
                current["truth"] += expected.sum((0, 2, 3))
                current["overlap"][0] += (prediction[:, 0] & prediction[:, 1]).sum()
                current["overlap"][1] += (prediction[:, 2] & prediction[:, 3]).sum()
    baseline, candidate = summary(counts["baseline"]), summary(counts["candidate"])
    historical = json.loads((CHECKPOINT.parent / "history.json").read_text(encoding="utf-8"))[13]["validation"]["class_iou"]
    replay = all(abs(baseline["class_iou"][key] - historical[key]) < 1e-5 for key in training.CLASSES)
    if not replay:
        raise ValueError("Baseline replay failed")
    delta = {key: candidate["class_iou"][key] - baseline["class_iou"][key] for key in training.CLASSES}
    macro_delta = candidate["macro_iou"] - baseline["macro_iou"]
    road_precision = candidate["class_precision"]["flooded_road"]
    flooded_precision_delta = (None if road_precision is None else
                               road_precision - baseline["class_precision"]["flooded_road"])
    accepted = (macro_delta >= .005 and min(delta.values()) >= -.005 and
                flooded_precision_delta is not None and flooded_precision_delta >= 0)
    write_new(RESULT, {"status": "completed", "finished_at": datetime.now(timezone.utc).isoformat(),
                       "preregistration_sha256": digest(PREREG), "tile_count": len(records),
                       "baseline_replay_verified": replay, "baseline": baseline, "candidate": candidate,
                       "delta": {"macro_iou": macro_delta, "class_iou": delta,
                                 "flooded_road_precision": flooded_precision_delta},
                       "promotion": "development_candidate" if accepted else "rejected",
                       "test_used": False, "independent_accuracy_verified": False, "production_ready": False})
    print(json.dumps({"promotion": "development_candidate" if accepted else "rejected",
                      "macro_delta": macro_delta, "flooded_road_precision_delta": flooded_precision_delta}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "evaluate"))
    (prepare if parser.parse_args().command == "prepare" else evaluate)()
