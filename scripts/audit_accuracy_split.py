"""Freeze the exact E4 pair inventory and check cross-split geospatial overlap."""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import rasterio
from rasterio.warp import transform_bounds

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/training.foundation-initialized-four-class-20260926.json"
CHECKPOINT = ROOT / "models/experiments/germany-louisiana-foundation-initialized-four-class-20260926/best_model.pth"
OUT = ROOT / "experiments/accuracy-pipeline-20261005"


def digest(path: Path) -> str:
    """Hash a file without loading its entire contents in memory."""
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def intersects_positive(a, b) -> bool:
    """Return true only for positive-area bbox overlap in geographic coordinates."""
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def main() -> None:
    """Write a non-overwriting manifest and audit report."""
    OUT.mkdir(parents=True, exist_ok=True)
    csv_out, json_out = OUT / "data_split_manifest.csv", OUT / "split_audit.json"
    if csv_out.exists() or json_out.exists():
        raise FileExistsError("Split audit already frozen")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    entries = []
    for split in ("train", "validation", "test"):
        for item in config["splits"].get(split, []):
            area_name = item["area"]
            area = ROOT / config["data_root"] / area_name
            mapping_path = area / f"{area_name}_label_image_mapping.csv"
            with mapping_path.open(encoding="utf-8-sig", newline="") as stream:
                lookup = {row["label"]: row for row in csv.DictReader(stream)}
            row = lookup[item["label"]]
            pre = area / "PRE-event" / row["pre-event image"]
            post = area / "POST-event" / row[item.get("post_event_column", "post-event image 1")]
            label = area / "annotations" / item["label"]
            if not all(p.is_file() for p in (pre, post, label)):
                raise FileNotFoundError(f"Missing pair/label for {item}")
            with rasterio.open(pre) as src:
                if src.crs is None:
                    raise ValueError(f"Missing CRS: {pre}")
                bbox = transform_bounds(src.crs, "EPSG:4326", *src.bounds, densify_pts=21)
            entries.append({"sample_id": f"{area_name}:{item['label']}", "AOI": area_name,
                            "region": area_name.split("_")[0],
                            "pre_image": str(pre.relative_to(ROOT)), "post_image": str(post.relative_to(ROOT)),
                            "label": str(label.relative_to(ROOT)), "split": split,
                            "bbox_wgs84": bbox})
    ids = [row["sample_id"] for row in entries]
    pre_by_split = {}
    for row in entries:
        pre_by_split.setdefault(row["pre_image"], set()).add(row["split"])
    reused_pre = [path for path, splits in pre_by_split.items() if len(splits) > 1]
    cross_overlap = []
    for i, first in enumerate(entries):
        for second in entries[i + 1:]:
            if first["split"] == second["split"] or first["AOI"] != second["AOI"]:
                continue
            if intersects_positive(first["bbox_wgs84"], second["bbox_wgs84"]):
                cross_overlap.append([first["sample_id"], second["sample_id"]])
    summary = {"created_at": datetime.now(timezone.utc).isoformat(),
               "config_sha256": digest(CONFIG), "checkpoint_sha256": digest(CHECKPOINT),
               "counts": {name: sum(row["split"] == name for row in entries)
                          for name in ("train", "validation", "test")},
               "duplicate_sample_ids": len(ids) - len(set(ids)),
               "cross_split_reused_pre_images": reused_pre,
               "cross_split_positive_bbox_overlaps": cross_overlap,
               "independent_test_ground_truth_available": bool(config["splits"].get("test")),
               "fresh_validation": False,
               "note": "Germany validation has been repeatedly used for development; this is not a fresh blind test."}
    with csv_out.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("sample_id", "AOI", "region", "pre_image",
                                                   "post_image", "label", "split"))
        writer.writeheader()
        writer.writerows({key: row[key] for key in writer.fieldnames} for row in entries)
    json_out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({key: summary[key] for key in ("counts", "duplicate_sample_ids",
                        "independent_test_ground_truth_available")}, ensure_ascii=False))
    print(f"cross_split_positive_bbox_overlaps={len(cross_overlap)} reused_pre={len(reused_pre)}")


if __name__ == "__main__":
    main()
