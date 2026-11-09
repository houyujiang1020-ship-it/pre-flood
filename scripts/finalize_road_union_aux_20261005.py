"""Finalize the pre-registered road-union experiment without changing deployment."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "experiments/e4-road-union-aux-20261005"
PREREG = RUN / "preregistration.json"
OUTPUT = RUN / "evaluation.json"
CANDIDATE = ROOT / "models/experiments/e4-road-union-aux-20261005"
BASELINE = ROOT / "models/experiments/germany-louisiana-foundation-initialized-four-class-20260926"
CONFIG = ROOT / "config/training.e4-road-union-aux-20261005.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError("Evaluation already exists; do not overwrite")
    protocol = json.loads(PREREG.read_text(encoding="utf-8"))
    inputs = protocol["inputs"]
    for key, path in (("candidate_config", CONFIG), ("baseline_checkpoint", BASELINE / "best_model.pth"),
                      ("trainer", ROOT / "app/training/train_full.py"),
                      ("preprocess", ROOT / "app/training/train_smoke.py")):
        if sha(path) != inputs[key + "_sha256"]:
            raise ValueError("Frozen input changed: " + key)
    report = json.loads((CANDIDATE / "training_report.json").read_text(encoding="utf-8"))
    history = json.loads((CANDIDATE / "history.json").read_text(encoding="utf-8"))
    if report["epochs_completed"] != 30 or len(history) != 30 or report["dataset_split_hash"] != "90302621e46680801fd2a1da1aa07afaaae567c71ec1ecd8a05b033eb2017229":
        raise ValueError("Experiment did not complete the frozen 30-epoch split")
    selected = max((record for record in history if record.get("validation")),
                   key=lambda row: sum(row["validation"]["class_iou"].values()) / 4)
    candidate = selected["validation"]
    baseline = protocol["baseline_fixed_0_5"]
    names = tuple(baseline["class_iou"])
    delta = {name: candidate["class_iou"][name] - baseline["class_iou"][name] for name in names}
    baseline_macro = sum(baseline["class_iou"].values()) / 4
    candidate_macro = sum(candidate["class_iou"].values()) / 4
    precision_delta = (candidate["class_precision"]["flooded_road"]
                       - baseline["class_precision"]["flooded_road"])
    accepted = candidate_macro - baseline_macro >= .005 and min(delta.values()) >= -.005 and precision_delta >= 0
    result = {"status": "completed", "completed_at": datetime.now(timezone.utc).isoformat(),
              "preregistration_sha256": sha(PREREG), "candidate_checkpoint_sha256": sha(CANDIDATE / "best_model.pth"),
              "selected_epoch": selected["epoch"], "baseline": baseline, "candidate": candidate,
              "delta": {"macro_iou": candidate_macro - baseline_macro, "class_iou": delta,
                        "flooded_road_precision": precision_delta},
              "promotion": "development_candidate" if accepted else "rejected",
              "manual_annotations_added": False, "test_used": False,
              "independent_accuracy_verified": False, "production_ready": False}
    OUTPUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"selected_epoch": selected["epoch"], "promotion": result["promotion"],
                      "macro_delta": result["delta"]["macro_iou"],
                      "flooded_road_precision_delta": precision_delta}, ensure_ascii=False))


if __name__ == "__main__":
    main()
