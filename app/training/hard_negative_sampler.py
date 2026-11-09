"""Optional train-only resampling of model-mined flooded-road false positives."""
from __future__ import annotations

import csv
import json
import math
import random
from collections import defaultdict
from pathlib import Path


def load_hard_negatives(directory: Path, records: list[tuple], weight: float,
                        top_fraction: float = 0.2) -> set[tuple[str, str]]:
    """Accept only a complete train-split mining run and matching tile IDs."""
    if not 1.5 <= weight <= 5:
        raise ValueError("hard_negative_weight must be within [1.5,5]")
    if not 0 < top_fraction <= 1:
        raise ValueError("top_fraction must be within (0,1]")
    metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    if metadata.get("split") != "train" or not metadata.get("training_eligible_for_mining"):
        raise ValueError("Only a complete train-only mining run may affect sampling")
    identities = {(Path(area).name, row["label"]) for area, row in records}
    with (directory / "failure_cases.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != len(records) or {(row["area"], row["label"]) for row in rows} != identities:
        raise ValueError("Mining rows differ from the frozen training split")
    ranked = sorted((row for row in rows if int(row["fp"]) > 0),
                    key=lambda row: int(row["fp"]), reverse=True)
    return {(row["area"], row["label"]) for row in ranked[:math.ceil(len(rows) * top_fraction)]}


def resample(indices: list[int], records: list[tuple], hard: set[tuple[str, str]],
             weight: float, seed: int) -> tuple[list[int], dict]:
    """Weight mined tiles within each sampled domain, preserving domain quotas."""
    if not 1.5 <= weight <= 5:
        raise ValueError("hard_negative_weight must be within [1.5,5]")
    by_domain: dict[str, list[int]] = defaultdict(list)
    for index in indices:
        by_domain[Path(records[index][0]).name].append(index)
    rng = random.Random(seed)
    result = []
    for domain, candidates in sorted(by_domain.items()):
        weights = [weight if (domain, records[index][1]["label"]) in hard else 1.0
                   for index in candidates]
        result.extend(rng.choices(candidates, weights=weights, k=len(candidates)))
    rng.shuffle(result)
    counts = {str(index): result.count(index) for index in sorted(set(result))}
    max_share = max(counts.values()) / len(result)
    return result, {"hard_negative_weight": weight, "hard_tiles_in_pool": len(hard),
                    "hard_draws": sum((Path(records[i][0]).name, records[i][1]["label"]) in hard
                                      for i in result), "draw_count": len(result),
                    "per_tile_sample_count": counts, "max_tile_share": max_share,
                    "oversampling_warning": max_share > 0.1}
