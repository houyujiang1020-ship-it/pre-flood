"""Preregister fold-clean foundation and matched short E4/HN training budgets."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "experiments/hard-negative-validation-20261005"
SPLIT = RUN / "split"


def write_new(path: Path, value: dict) -> None:
    """Save one immutable experiment configuration."""
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    """Create same-data/same-budget configs; no prior E4/E3c initialization."""
    audit = json.loads((SPLIT / "leakage_audit.json").read_text(encoding="utf-8"))
    if not audit["pass"] or audit["train"] != 579 or audit["validation"] != 110:
        raise ValueError("Spatial leakage audit must pass before training")
    base = json.loads((SPLIT / "base_training_config.json").read_text(encoding="utf-8"))
    foundation = json.loads((ROOT / "config/training.single-unet-foundation-20260926.json").read_text(encoding="utf-8"))
    foundation.pop("initialization_checkpoint", None)
    foundation.pop("initialization_allowed_missing", None)
    foundation["model_id"] = "hn-spatial-clean-foundation-short-20261005"
    foundation["output_dir"] = str((RUN / "foundation" / "short").relative_to(ROOT))
    foundation["epochs"] = 5
    foundation["sampler"]["epoch_size"] = 80
    foundation["sampler"]["domain_weights"] = {"Louisiana-East_Training_Public": 1}
    foundation["splits"] = {"train": [], "validation": [], "test": []}
    # Foundation selection uses only downstream TRAIN_NEW; it never sees SPATIAL_VAL_NEW.
    for item in base["splits"]["train"]:
        x = int(Path(item["label"]).stem.split("_")[-2])
        key = "validation" if x <= 5 else "train"
        foundation["splits"][key].append(item)
    if not foundation["splits"]["train"] or not foundation["splits"]["validation"]:
        raise ValueError("Foundation internal train/development split is empty")
    foundation["test_scope"] = "Only downstream TRAIN_NEW used for foundation training and internal selection"
    write_new(RUN / "foundation" / "short_config.json", foundation)
    base["model_id"] = "hn-spatial-e4-short-seed42"
    base["output_dir"] = str((RUN / "baseline" / "short-seed42").relative_to(ROOT))
    base["initialization_checkpoint"] = str((RUN / "foundation" / "short" / "best_model.pth").relative_to(ROOT))
    base["initialization_allowed_missing"] = ["conv11d.bias", "conv11d.weight"]
    base["epochs"] = 5
    base["seed"] = 42
    base["sampler"]["epoch_size"] = 80
    base["sampler"]["domain_weights"] = {"Louisiana-East_Training_Public": 1}
    base["validation_schedule"] = "every_epoch"
    base["early_stopping_patience"] = 5
    base.pop("class_aware_crop", None)
    base.pop("hard_negative_mining", None)
    write_new(RUN / "baseline" / "short-seed42-config.json", base)
    prereg = {"status": "preregistered_before_training", "split": "split/split_report.json",
              "clean_foundation": "foundation/short_config.json",
              "baseline": "baseline/short-seed42-config.json",
              "old_e4_checkpoint_used": False, "old_e3c_checkpoint_used": False,
              "foundation_selection_overlap_with_spatial_holdout": 0,
              "same_budget_for_hn": {"epochs": 5, "steps_per_epoch": 80, "seed": 42,
                                      "patience": 5, "threshold": 0.5},
              "stage_a_fractions": [0.1, 0.2, 0.3, 0.4],
              "stage_b_weights": [1.5, 2, 3, 4, 5],
              "production_ready": False}
    write_new(RUN / "preregistration.json", prereg)
    print(json.dumps({"foundation_train": len(foundation["splits"]["train"]),
                      "foundation_internal_val": len(foundation["splits"]["validation"]),
                      "e4_train": len(base["splits"]["train"]),
                      "spatial_val": len(base["splits"]["validation"])}))


if __name__ == "__main__":
    main()
