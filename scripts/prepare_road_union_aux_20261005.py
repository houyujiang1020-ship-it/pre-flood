"""Freeze a no-new-label road-presence auxiliary-loss experiment before training."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "config/training.foundation-initialized-four-class-20260926.json"
CONFIG = ROOT / "config/training.e4-road-union-aux-20261005.json"
RUN = ROOT / "experiments/e4-road-union-aux-20261005"
PREREG = RUN / "preregistration.json"
TRAINER = ROOT / "app/training/train_full.py"
PREPROCESS = ROOT / "app/training/train_smoke.py"
BASELINE = ROOT / "models/experiments/germany-louisiana-foundation-initialized-four-class-20260926/best_model.pth"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    RUN.mkdir(parents=True, exist_ok=True)
    if CONFIG.exists() or PREREG.exists():
        raise FileExistsError("Experiment configuration already frozen; do not overwrite")
    baseline = json.loads(BASE.read_text(encoding="utf-8"))
    if baseline["splits"].get("test"):
        raise ValueError("No test data may be used")
    proposed = dict(baseline)
    proposed.update({"model_id": "e4-road-union-aux-20261005",
                     "output_dir": "models/experiments/e4-road-union-aux-20261005",
                     "road_union_aux_weight": 0.25})
    changed = {key for key in set(baseline) | set(proposed) if baseline.get(key) != proposed.get(key)}
    if changed != {"model_id", "output_dir", "road_union_aux_weight"}:
        raise ValueError("Experiment changed undeclared training fields: " + str(changed))
    CONFIG.write_text(json.dumps(proposed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    archived = json.loads((BASELINE.parent / "history.json").read_text(encoding="utf-8"))[13]["validation"]
    prereg = {"status": "preregistered_before_training", "created_at": datetime.now(timezone.utc).isoformat(),
              "experiment": "e4-road-union-aux-20261005",
              "hypothesis": "An auxiliary road-presence Dice term may improve road localization while retaining four-class flood supervision.",
              "single_change": "BCE + 0.5 * mean four-class Dice + 0.25 * road-union Dice",
              "road_union_target": "max(existing non-flooded-road label, existing flooded-road label)",
              "road_union_probability": "1 - (1 - sigmoid(normal-road)) * (1 - sigmoid(flooded-road))",
              "inputs": {"baseline_config": str(BASE.relative_to(ROOT)), "baseline_config_sha256": sha(BASE),
                         "candidate_config": str(CONFIG.relative_to(ROOT)), "candidate_config_sha256": sha(CONFIG),
                         "baseline_checkpoint_sha256": sha(BASELINE), "trainer_sha256": sha(TRAINER),
                         "preprocess_sha256": sha(PREPROCESS)},
              "baseline_fixed_0_5": archived,
              "promotion_rule": "Candidate macro IoU >= E4 + 0.005; each of four class IoUs >= E4 - 0.005; flooded-road precision does not decline.",
              "validation_scope": "Existing Germany 18-tile development split only; no independent-accuracy claim.",
              "test_used": False, "manual_annotations_added": False, "production_ready": False}
    PREREG.write_text(json.dumps(prereg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(PREREG)


if __name__ == "__main__":
    main()
