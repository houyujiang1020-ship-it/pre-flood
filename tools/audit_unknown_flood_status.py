"""Inventory raw flood-status values without changing the frozen E4 label map."""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    """Count status tokens for object features in each frozen spatial partition."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--split-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = {}
    for split, filename in (("train", "spatial_train_manifest.csv"),
                            ("validation", "spatial_val_manifest.csv"),
                            ("embargo", "spatial_embargo_manifest.csv")):
        counts = Counter()
        with (args.split_dir / filename).open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        for row in rows:
            path = ROOT / row["label_path"]
            for feature in json.loads(path.read_text(encoding="utf-8"))["features"]:
                prop = feature["properties"]
                kind = ("building" if prop.get("building") not in (None, "no", "") else
                        "road" if prop.get("highway") not in (None, "") else None)
                if kind:
                    raw = prop.get("flooded")
                    counts[f"{kind}:{str(raw).lower() if raw is not None else '<null>'}"] += 1
        result[split] = dict(sorted(counts.items()))
    result["conclusion"] = (
        "Raw status tokens are inventoried, not reinterpreted. The frozen E4 preprocessing "
        "maps null to non-flooded. Without source semantics proving null means unknown, "
        "relabeling it as ignore would break the matched E4/HN comparison.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"train": result["train"], "validation": result["validation"]}))


if __name__ == "__main__":
    main()
