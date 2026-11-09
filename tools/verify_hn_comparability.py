"""Prove matched baseline/HN configs differ only in sampling and output identity."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def comparable(baseline: dict, candidate: dict) -> dict:
    """Compare deep config values after removing the single intended intervention."""
    remove = ("model_id", "output_dir", "hard_negative_mining")
    first = {key: value for key, value in baseline.items() if key not in remove}
    second = {key: value for key, value in candidate.items() if key not in remove}
    if first != second or "hard_negative_mining" in baseline or "hard_negative_mining" not in candidate:
        raise ValueError("Non-sampling training configuration differs")
    mining = candidate["hard_negative_mining"]
    if not 0 < mining["top_fraction"] <= 0.4 or not 1.5 <= mining["weight"] <= 5:
        raise ValueError("Hard-negative intervention outside search range")
    return {"same_except_hard_negative_sampling": True,
            "same_seed": baseline["seed"] == candidate["seed"],
            "same_train_tiles": baseline["splits"]["train"] == candidate["splits"]["train"],
            "same_spatial_validation": baseline["splits"]["validation"] == candidate["splits"]["validation"],
            "same_max_epochs": baseline["epochs"] == candidate["epochs"],
            "same_steps_per_epoch": baseline["sampler"]["epoch_size"] == candidate["sampler"]["epoch_size"],
            "same_optimizer_lr": baseline["learning_rate"] == candidate["learning_rate"],
            "same_initialization": baseline["initialization_checkpoint"] == candidate["initialization_checkpoint"],
            "intervention": mining}


def main() -> None:
    """Save one non-overwriting matched-config audit."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    result = comparable(baseline, candidate)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
