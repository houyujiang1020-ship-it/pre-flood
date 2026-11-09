"""Apply fixed development promotion gates without mutating production settings."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

CLASSES = ("non_flooded_building", "flooded_building", "non_flooded_road", "flooded_road")


def decide(baseline: dict, candidate: dict) -> dict:
    """Reject a candidate unless macro, every class, and flooded-road gates pass."""
    reasons = []
    base_iou, next_iou = baseline["class_iou"], candidate["class_iou"]
    if set(base_iou) != set(CLASSES) or set(next_iou) != set(CLASSES):
        raise ValueError("Four identical class names are required")
    baseline_macro = sum(base_iou[name] for name in CLASSES) / 4
    candidate_macro = sum(next_iou[name] for name in CLASSES) / 4
    if candidate_macro < baseline_macro + .005:
        reasons.append("macro_iou_gain_below_0.005")
    for name in CLASSES:
        if next_iou[name] < base_iou[name] - .005:
            reasons.append(f"class_regression:{name}")
    if next_iou["flooded_road"] <= base_iou["flooded_road"]:
        reasons.append("flooded_road_iou_not_higher")
    base_precision = baseline["class_precision"]["flooded_road"]
    precision = candidate["class_precision"]["flooded_road"]
    if precision is None or precision < base_precision:
        reasons.append("flooded_road_precision_declined_or_undefined")
    if candidate["prediction_pixels"]["flooded_road"] <= 0 or candidate["class_recall"]["flooded_road"] <= 0:
        reasons.append("flooded_road_disappeared")
    return {"decision": "PROMOTE_DEVELOPMENT_CANDIDATE" if not reasons else "REJECT",
            "reasons": reasons, "baseline_macro_iou": baseline_macro,
            "candidate_macro_iou": candidate_macro,
            "macro_delta": candidate_macro - baseline_macro,
            "independent_test_accuracy_verified": False,
            "production_ready": False}


def main() -> None:
    """Compare two metric JSON files once and freeze the decision."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    result = decide(baseline, candidate)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
