"""Paired three-seed spatial validation, mean/std, and research-only gate."""
from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path

SEEDS = (42, 3407, 2026)
METRICS = ("building_iou", "flooded_building_iou", "road_iou", "flooded_road_iou",
           "macro_iou", "flooded_road_precision", "flooded_road_recall", "flooded_road_f1")


def extract(metrics: dict, model: str, seed: int) -> dict:
    """Read all class metrics from a single fixed-0.5 best-macro checkpoint."""
    iou = metrics["class_iou"]
    raw_precision = metrics["class_precision"]["flooded_road"]
    raw_recall = metrics["class_recall"]["flooded_road"]
    precision = raw_precision if raw_precision is not None else 0.0
    recall = raw_recall if raw_recall is not None else 0.0
    return {"model": model, "seed": seed,
            "flooded_road_precision_defined": raw_precision is not None,
            "building_iou": iou["non_flooded_building"],
            "flooded_building_iou": iou["flooded_building"],
            "road_iou": iou["non_flooded_road"],
            "flooded_road_iou": iou["flooded_road"],
            "macro_iou": metrics["macro_iou"],
            "flooded_road_precision": precision,
            "flooded_road_recall": recall,
            "flooded_road_f1": 2 * precision * recall / (precision + recall)
            if precision + recall else 0}


def decide(rows: list[dict], catastrophic_drop: float = 0.02) -> dict:
    """Require joint mean gain and at least two paired seeds improving all targets."""
    by_seed = {seed: {row["model"]: row for row in rows if row["seed"] == seed}
               for seed in SEEDS}
    if any(set(pair) != {"E4_NEW_BASELINE", "HN10_W5"} for pair in by_seed.values()):
        raise ValueError("Three complete baseline/HN pairs required")
    summary = {}
    for model in ("E4_NEW_BASELINE", "HN10_W5"):
        group = [by_seed[seed][model] for seed in SEEDS]
        summary[model] = {key: {"mean": statistics.mean(row[key] for row in group),
                                "sample_std": statistics.stdev(row[key] for row in group)}
                          for key in METRICS}
    deltas = {}
    joint_improved = 0
    catastrophic = []
    for seed in SEEDS:
        baseline, candidate = (by_seed[seed][name] for name in ("E4_NEW_BASELINE", "HN10_W5"))
        diff = {key: candidate[key] - baseline[key] for key in METRICS}
        deltas[str(seed)] = diff
        if all(diff[key] > 0 for key in ("macro_iou", "flooded_road_iou", "flooded_road_precision")):
            joint_improved += 1
        for key in ("building_iou", "flooded_building_iou", "road_iou"):
            if diff[key] < -catastrophic_drop:
                catastrophic.append({"seed": seed, "class": key, "delta": diff[key]})
    mean_gain = all(summary["HN10_W5"][key]["mean"] > summary["E4_NEW_BASELINE"][key]["mean"]
                    for key in ("macro_iou", "flooded_road_iou", "flooded_road_precision"))
    nonzero_recall = all(by_seed[seed]["HN10_W5"]["flooded_road_recall"] > 0 for seed in SEEDS)
    passed = mean_gain and nonzero_recall and joint_improved >= 2 and not catastrophic
    return {"decision": "PROMOTE_RESEARCH_CANDIDATE" if passed else "KEEP_E4",
            "production_ready": False, "independent_external_test_verified": False,
            "checkpoint_rule": "best_macro_iou, fixed threshold 0.5",
            "mean_and_sample_std": summary, "paired_deltas": deltas,
            "joint_improved_seed_count": joint_improved,
            "all_hn_recall_nonzero": nonzero_recall,
            "catastrophic_class_drop_threshold": catastrophic_drop,
            "catastrophic_regressions": catastrophic}


def main() -> None:
    """Read six completed run metrics and write comparison CSV plus decision JSON."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment", type=Path, required=True)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--decision", type=Path, required=True)
    args = parser.parse_args()
    if args.csv.exists() or args.decision.exists():
        raise FileExistsError("Multiseed result already frozen")
    strict_3407 = (
        args.experiment / "multiseed/strict-baseline-seed3407/fixed05_metrics.json",
        args.experiment / "multiseed/strict-hn10-w5-seed3407/fixed05_metrics.json")
    if strict_3407[0].exists() != strict_3407[1].exists():
        raise ValueError("Strict seed3407 pair is incomplete")
    paths = {
        42: (args.experiment / "baseline/full-seed42/fixed05_metrics.json",
             args.experiment / "weight-search/hn10-w5-full-seed42/fixed05_metrics.json"),
        3407: strict_3407 if strict_3407[0].exists() else (
            args.experiment / "multiseed/baseline-seed3407/fixed05_metrics.json",
            args.experiment / "multiseed/hn10-w5-seed3407/fixed05_metrics.json"),
        2026: (args.experiment / "multiseed/baseline-seed2026/fixed05_metrics.json",
               args.experiment / "multiseed/hn10-w5-seed2026/fixed05_metrics.json")}
    rows = []
    for seed, pair in paths.items():
        for name, path in zip(("E4_NEW_BASELINE", "HN10_W5"), pair):
            rows.append(extract(json.loads(path.read_text(encoding="utf-8")), name, seed))
    verdict = decide(rows)
    verdict["source_metric_files"] = {str(seed): [str(path) for path in pair]
                                      for seed, pair in paths.items()}
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    args.decision.write_text(json.dumps(verdict, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"decision": verdict["decision"],
                      "joint_improved_seed_count": verdict["joint_improved_seed_count"]}))


if __name__ == "__main__":
    main()
