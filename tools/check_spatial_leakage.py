"""Audit a frozen PRE/POST spatial split for identity and geographic leakage."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path


def read_manifest(path: Path) -> list[dict]:
    """Read a frozen split manifest and attach numeric tile coordinates."""
    with path.open(encoding="utf-8", newline="") as stream:
        records = list(csv.DictReader(stream))
    for row in records:
        row["bbox"] = tuple(float(row[key]) for key in (
            "bbox_minx", "bbox_miny", "bbox_maxx", "bbox_maxy"))
        match = re.fullmatch(r"(\d+)_(\d+)_(\d+)\.geojson", Path(row["label_path"]).name)
        if not match:
            raise ValueError(f"Invalid tile filename: {row['label_path']}")
        row["tile"] = tuple(map(int, match.groups()))
    return records


def positive_overlap(left: tuple, right: tuple) -> bool:
    """Detect strict positive-area WGS84 bounding-box intersection."""
    return min(left[2], right[2]) > max(left[0], right[0]) and min(left[3], right[3]) > max(left[1], right[1])


def sha(path: Path) -> str:
    """Hash one immutable manifest."""
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def audit(train: list[dict], val: list[dict], embargo: list[dict]) -> dict:
    """Report cross-split duplicates, overlaps, neighboring tiles, and AOI reuse."""
    all_rows = train + val + embargo
    ids = [row["sample_id"] for row in all_rows]
    duplicates = len(ids) - len(set(ids))
    def duplicate_path(key: str) -> list[str]:
        groups = defaultdict(set)
        for row in train + val:
            groups[row[key].casefold()].add(row["split"])
        return sorted(path for path, splits in groups.items() if len(splits) > 1)
    overlap, neighbor = [], []
    for first in train:
        for second in val:
            if first["AOI"] != second["AOI"]:
                continue
            if positive_overlap(first["bbox"], second["bbox"]):
                overlap.append((first["sample_id"], second["sample_id"]))
            a, b = first["tile"], second["tile"]
            if a[0] == b[0] and max(abs(a[1] - b[1]), abs(a[2] - b[2])) <= 1:
                neighbor.append((first["sample_id"], second["sample_id"]))
    shared_aoi = sorted({row["AOI"] for row in train} & {row["AOI"] for row in val})
    return {"train": len(train), "validation": len(val), "embargo": len(embargo),
            "duplicate_sample_ids": duplicates,
            "cross_split_pre_paths": duplicate_path("pre_path"),
            "cross_split_post_paths": duplicate_path("post_path"),
            "cross_split_bbox_overlap": overlap,
            "cross_split_neighbor_tiles": neighbor,
            "aoi_shared_but_geographically_separated": shared_aoi,
            "pass": not (duplicates or duplicate_path("pre_path") or duplicate_path("post_path")
                         or overlap or neighbor)}


def main() -> None:
    """Check frozen manifest hashes, audit each split, and save one JSON verdict."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--split-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    report = json.loads((args.split_dir / "split_report.json").read_text(encoding="utf-8"))
    filenames = ("spatial_train_manifest.csv", "spatial_val_manifest.csv", "spatial_embargo_manifest.csv")
    if any(sha(args.split_dir / name) != report["manifests_sha256"][name] for name in filenames):
        raise ValueError("Frozen spatial manifest hash changed")
    train, val, embargo = [read_manifest(args.split_dir / name) for name in filenames]
    result = audit(train, val, embargo)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("train", "validation", "embargo", "pass")}))
    if not result["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
