"""Frozen horizontal-flip TTA diagnostic for E4; never accesses an external test set."""
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

RUN = ROOT / "experiments/e4-horizontal-flip-tta-20261005"
PREREG = RUN / "preregistration.json"
RESULT = RUN / "evaluation.json"
CONFIG = ROOT / "config/training.foundation-initialized-four-class-20260926.json"
CHECKPOINT = ROOT / "models/experiments/germany-louisiana-foundation-initialized-four-class-20260926/best_model.pth"
ARCH = ROOT / "upstream/SpaceNet8/baseline/models/other/siamunetdif.py"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def prepare() -> None:
    RUN.mkdir(parents=True, exist_ok=True)
    if PREREG.exists() or RESULT.exists():
        raise FileExistsError("Frozen experiment already exists")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    if config["splits"].get("test"):
        raise ValueError("Test is out of scope")
    save(PREREG, {
        "status": "preregistered_before_evaluation",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experiment": "e4-horizontal-flip-tta-20261005",
        "motivation": "SpaceNet8 fifth-place solution used horizontal flip TTA for flooded buildings; test a fixed symmetric two-view average on all four E4 outputs.",
        "formula": "0.5 * sigmoid(model(pre,post)) + 0.5 * unflip(sigmoid(model(flip(pre),flip(post))))",
        "threshold": 0.5,
        "inputs": {"checkpoint_sha256": sha(CHECKPOINT), "config_sha256": sha(CONFIG), "architecture_sha256": sha(ARCH)},
        "promotion_rule": "macro IoU >= baseline + 0.005; every class IoU >= baseline - 0.005; flooded-road precision does not decline",
        "evaluation": "18 Germany development validation tiles only; no hyperparameter search or new labels",
        "test_used": False, "production_ready": False,
    })
    print(PREREG)


def metrics(counts: dict) -> dict:
    tp, pred, truth = (counts[x].double() for x in ("tp", "pred", "truth"))
    union = pred + truth - tp
    def ratios(numerator, denominator):
        return [float((numerator[i]/denominator[i]).item()) if denominator[i] else None for i in range(4)]
    iou = ratios(tp, union)
    return {"class_iou": dict(zip(training.CLASSES, iou)),
            "class_precision": dict(zip(training.CLASSES, ratios(tp, pred))),
            "class_recall": dict(zip(training.CLASSES, ratios(tp, truth))),
            "prediction_pixels": dict(zip(training.CLASSES, pred.tolist())),
            "truth_pixels": dict(zip(training.CLASSES, truth.tolist())),
            "macro_iou": sum(iou)/4}


def evaluate() -> None:
    if not PREREG.is_file() or RESULT.exists():
        raise RuntimeError("Prepare first and do not overwrite results")
    frozen = json.loads(PREREG.read_text(encoding="utf-8"))
    for name, path in (("checkpoint", CHECKPOINT), ("config", CONFIG), ("architecture", ARCH)):
        if sha(path) != frozen["inputs"][name+"_sha256"]:
            raise ValueError("Frozen input changed: " + name)
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    if config["splits"].get("test"):
        raise ValueError("Test is out of scope")
    records = training.split_rows(config, ROOT)["validation"]
    training.DISK_CACHE = ROOT / config["cache_dir"]
    training._cached_pair.cache_clear()
    checkpoint = torch.load(CHECKPOINT, map_location="cpu", weights_only=True)
    model = training.build_siamunet(ARCH, checkpoint["normalization"], checkpoint["groupnorm_groups"])
    model.load_state_dict(checkpoint["state_dict"], strict=True)
    model.cuda().eval()
    counts = {name: {k: torch.zeros(4, dtype=torch.int64) for k in ("tp", "pred", "truth")}
              for name in ("baseline", "candidate")}
    with torch.inference_mode():
        for area, row in records:
            pre, post, truth, valid = training.cached_pair(area, row, config["image_size"])
            pre, post = pre.unsqueeze(0).cuda(), post.unsqueeze(0).cuda()
            original = model(pre, post).sigmoid().cpu()
            mirrored = model(pre.flip(-1), post.flip(-1)).sigmoid().flip(-1).cpu()
            expected = truth.unsqueeze(0) > 0
            mask = valid.unsqueeze(0).unsqueeze(0) > 0
            expected &= mask
            for name, probability in (("baseline", original), ("candidate", (original+mirrored)/2)):
                prediction = (probability > .5) & mask
                current = counts[name]
                current["tp"] += (prediction & expected).sum((0, 2, 3))
                current["pred"] += prediction.sum((0, 2, 3))
                current["truth"] += expected.sum((0, 2, 3))
    baseline, candidate = metrics(counts["baseline"]), metrics(counts["candidate"])
    archived = json.loads((CHECKPOINT.parent / "history.json").read_text(encoding="utf-8"))[13]["validation"]["class_iou"]
    replay = all(abs(baseline["class_iou"][k]-archived[k]) < 1e-5 for k in training.CLASSES)
    if not replay:
        raise ValueError("Baseline does not reproduce archived E4 validation")
    delta = {k: candidate["class_iou"][k]-baseline["class_iou"][k] for k in training.CLASSES}
    macro_delta = candidate["macro_iou"]-baseline["macro_iou"]
    precision_delta = (candidate["class_precision"]["flooded_road"]
                       -baseline["class_precision"]["flooded_road"])
    accepted = macro_delta >= .005 and min(delta.values()) >= -.005 and precision_delta >= 0
    save(RESULT, {"status": "completed", "finished_at": datetime.now(timezone.utc).isoformat(),
                  "preregistration_sha256": sha(PREREG), "tile_count": len(records), "baseline_replay_verified": replay,
                  "baseline": baseline, "candidate": candidate,
                  "delta": {"macro_iou": macro_delta, "class_iou": delta, "flooded_road_precision": precision_delta},
                  "promotion": "development_candidate" if accepted else "rejected",
                  "test_used": False, "independent_accuracy_verified": False, "production_ready": False})
    print(json.dumps({"promotion": "development_candidate" if accepted else "rejected",
                      "macro_delta": macro_delta, "flooded_road_precision_delta": precision_delta}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "evaluate"))
    action = parser.parse_args().command
    (prepare if action == "prepare" else evaluate)()
