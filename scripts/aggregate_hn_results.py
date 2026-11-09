"""Aggregate completed matched runs without mixing best-macro and best-road epochs."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

CLASSES = ("non_flooded_building", "flooded_building", "non_flooded_road", "flooded_road")


def selected_row(history: list[dict], rule: str) -> dict:
    """Return one complete epoch record under a single checkpoint rule."""
    if not history or any(row.get("validation") is None for row in history):
        raise ValueError("Completed per-epoch validation history required")
    if rule == "best_macro":
        return max(history, key=lambda row: sum(row["validation"]["class_iou"].values()) / 4)
    if rule == "best_road":
        return max(history, key=lambda row: row["validation"]["class_iou"]["flooded_road"])
    raise ValueError("Unknown checkpoint selection rule")


def main() -> None:
    """Write one row per run/rule, preserving all four class metrics together."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    rows = []
    for run in args.run:
        history = json.loads((run / "history.json").read_text(encoding="utf-8"))
        for rule in ("best_macro", "best_road"):
            chosen = selected_row(history, rule)
            metric = chosen["validation"]
            iou = metric["class_iou"]
            p, r = metric["class_precision"]["flooded_road"], metric["class_recall"]["flooded_road"]
            rows.append({"model": run.name, "checkpoint_rule": rule, "epoch": chosen["epoch"],
                         "epochs_completed": len(history),
                         "building_iou": iou["non_flooded_building"],
                         "flooded_building_iou": iou["flooded_building"],
                         "road_iou": iou["non_flooded_road"],
                         "flooded_road_iou": iou["flooded_road"],
                         "macro_iou": sum(iou.values()) / 4,
                         "flooded_road_precision": p, "flooded_road_recall": r,
                         "flooded_road_f1": 2 * p * r / (p + r) if p is not None and r is not None and p + r else 0,
                         "flooded_road_predicted_pixels": metric["prediction_pixels"]["flooded_road"]})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"runs": len(args.run), "rows": len(rows), "output": str(args.output)}))


if __name__ == "__main__":
    main()
