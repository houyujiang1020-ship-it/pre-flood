"""Freeze per-tile draw counts from one hard-negative training log."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def main() -> None:
    """Export one row per tile/epoch and over-sampling warnings."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    epochs = []
    for line in args.log.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("{"):
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "hard_negative_sampling" in value:
            epochs.append(value["hard_negative_sampling"])
    if not epochs:
        raise ValueError("No hard-negative sampling records in log")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("epoch", "tile_index", "sample_count",
                                                    "draw_count", "hard_draws", "max_tile_share",
                                                    "oversampling_warning"))
        writer.writeheader()
        for epoch, report in enumerate(epochs, 1):
            for tile, count in report["per_tile_sample_count"].items():
                writer.writerow({"epoch": epoch, "tile_index": tile, "sample_count": count,
                                 "draw_count": report["draw_count"], "hard_draws": report["hard_draws"],
                                 "max_tile_share": report["max_tile_share"],
                                 "oversampling_warning": report["oversampling_warning"]})
    print(json.dumps({"epochs": len(epochs),
                      "any_oversampling_warning": any(row["oversampling_warning"] for row in epochs)}))


if __name__ == "__main__":
    main()
