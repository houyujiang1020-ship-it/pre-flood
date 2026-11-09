"""Freeze one hard-negative variant while preserving the clean E4 budget."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    """Change only train-only hard-negative sampling plus explicit output identity."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-config", type=Path, required=True)
    parser.add_argument("--mining-dir", type=Path, required=True)
    parser.add_argument("--fraction", type=float, required=True)
    parser.add_argument("--weight", type=float, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-config", type=Path, required=True)
    parser.add_argument("--output-run", type=Path, required=True)
    args = parser.parse_args()
    if args.output_config.exists() or args.output_run.exists():
        raise FileExistsError("Variant config or model output exists")
    if not 0 < args.fraction <= 0.4 or not 1.5 <= args.weight <= 5:
        raise ValueError("Fraction/weight outside preregistered range")
    baseline = json.loads(args.baseline_config.read_text(encoding="utf-8"))
    if baseline.get("hard_negative_mining"):
        raise ValueError("Expected a clean baseline configuration")
    if args.seed != baseline["seed"]:
        # A seed variant is fair only against a separate same-seed baseline.
        raise ValueError("Baseline seed differs; create a matching same-seed baseline first")
    mining = json.loads((args.mining_dir / "metadata.json").read_text(encoding="utf-8"))
    if mining.get("split") != "train" or not mining.get("training_eligible_for_mining"):
        raise ValueError("Full train-only mining evidence is required")
    variant = json.loads(json.dumps(baseline))
    variant["model_id"] = args.output_run.name
    variant["output_dir"] = str(args.output_run.resolve().relative_to(ROOT))
    variant["hard_negative_mining"] = {
        "directory": str(args.mining_dir.resolve().relative_to(ROOT)),
        "top_fraction": args.fraction, "weight": args.weight}
    args.output_config.parent.mkdir(parents=True, exist_ok=True)
    args.output_config.write_text(json.dumps(variant, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"model_id": variant["model_id"], "fraction": args.fraction,
                      "weight": args.weight, "seed": args.seed,
                      "epochs": variant["epochs"], "steps": variant["sampler"]["epoch_size"]}))


if __name__ == "__main__":
    main()
