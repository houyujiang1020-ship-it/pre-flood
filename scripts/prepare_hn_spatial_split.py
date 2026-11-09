"""Freeze complete Germany AOI plus Louisiana-East far-east spatial holdout."""
from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import rasterio
from rasterio.warp import transform_bounds

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "config/training.foundation-initialized-four-class-20260926.json"
OUT = ROOT / "experiments/hard-negative-validation-20261005/split"
FIELDS = ("sample_id", "region", "AOI", "pre_path", "post_path", "label_path",
          "bbox_minx", "bbox_miny", "bbox_maxx", "bbox_maxy", "split",
          "pre_sha256", "post_sha256", "label_sha256")


def digest(path: Path) -> str:
    """Hash a geospatial input without loading it all into memory."""
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def tile_coordinates(item: dict) -> tuple[int, int, int]:
    """Extract SpaceNet8 zoom/x/y from a public annotation filename."""
    numbers = re.fullmatch(r"(\d+)_(\d+)_(\d+)\.geojson", item["label"])
    if not numbers:
        raise ValueError(f"Unexpected tile identity: {item['label']}")
    return tuple(map(int, numbers.groups()))


def select_split(item: dict) -> str:
    """Reserve Germany AOI and Louisiana far-east; embargo their neighbor x=28."""
    if item["area"] == "Germany_Training_Public":
        return "SPATIAL_VAL_NEW"
    if item["area"] == "Louisiana-East_Training_Public":
        x = tile_coordinates(item)[1]
        if x >= 29:
            return "SPATIAL_VAL_NEW"
        if x == 28:
            return "EMBARGO"
    return "TRAIN_NEW"


def feature_classes(path: Path) -> set[str]:
    """Verify all four object/status types occur as features in the holdout."""
    features = json.loads(path.read_text(encoding="utf-8"))["features"]
    present = set()
    for feature in features:
        properties = feature["properties"]
        object_type = ("building" if properties.get("building") not in (None, "no", "") else
                       "road" if properties.get("highway") not in (None, "") else None)
        if object_type:
            present.add(("flooded_" if properties.get("flooded") in ("yes", 1, True)
                         else "non_flooded_") + object_type)
    return present


def main() -> None:
    """Emit immutable pair manifests and split provenance before model training."""
    if OUT.exists():
        raise FileExistsError(f"Spatial split is already frozen: {OUT}")
    config = json.loads(SOURCE.read_text(encoding="utf-8"))
    items = config["splits"]["train"]
    if len(items) != 697:
        raise ValueError("Expected frozen E4 training inventory of 697")
    rows = []
    classes = set()
    lookups = {}
    for item in items:
        area_name = item["area"]
        area = ROOT / config["data_root"] / area_name
        if area_name not in lookups:
            with (area / f"{area_name}_label_image_mapping.csv").open(encoding="utf-8-sig", newline="") as stream:
                lookups[area_name] = {row["label"]: row for row in csv.DictReader(stream)}
        pairing = lookups[area_name][item["label"]]
        pre = area / "PRE-event" / pairing["pre-event image"]
        post = area / "POST-event" / pairing[item.get("post_event_column", "post-event image 1")]
        label = area / "annotations" / item["label"]
        if not all(path.is_file() for path in (pre, post, label)):
            raise FileNotFoundError(item)
        with rasterio.open(pre) as src:
            if src.crs is None:
                raise ValueError(f"Missing PRE CRS: {pre}")
            bbox = transform_bounds(src.crs, "EPSG:4326", *src.bounds, densify_pts=21)
        split = select_split(item)
        if split == "SPATIAL_VAL_NEW":
            classes.update(feature_classes(label))
        row = dict(zip(FIELDS, (f"{area_name}:{item['label']}", area_name.split("_")[0], area_name,
                                str(pre.relative_to(ROOT)), str(post.relative_to(ROOT)),
                                str(label.relative_to(ROOT)), *bbox, split,
                                digest(pre), digest(post), digest(label))))
        rows.append(row)
    # Cross-zoom tiles can overlap even when their filename x values are far apart.
    validation = [row for row in rows if row["split"] == "SPATIAL_VAL_NEW"]
    for row in rows:
        if row["split"] != "TRAIN_NEW":
            continue
        first = [float(row[key]) for key in ("bbox_minx", "bbox_miny", "bbox_maxx", "bbox_maxy")]
        for other in validation:
            if row["AOI"] != other["AOI"]:
                continue
            second = [float(other[key]) for key in ("bbox_minx", "bbox_miny", "bbox_maxx", "bbox_maxy")]
            if min(first[2], second[2]) > max(first[0], second[0]) and min(first[3], second[3]) > max(first[1], second[1]):
                row["split"] = "EMBARGO"
                break
    partitions = {name: [item for row, item in zip(rows, items) if row["split"] == name]
                  for name in ("TRAIN_NEW", "SPATIAL_VAL_NEW", "EMBARGO")}
    if classes != {"non_flooded_building", "flooded_building", "non_flooded_road", "flooded_road"}:
        raise ValueError(f"Holdout lacks a four-class object type: {classes}")
    counts = Counter(row["split"] for row in rows)
    if counts != {"TRAIN_NEW": 579, "SPATIAL_VAL_NEW": 110, "EMBARGO": 8}:
        raise ValueError(f"Unexpected frozen spatial counts: {counts}")
    OUT.mkdir(parents=True, exist_ok=False)
    for split, filename in (("TRAIN_NEW", "spatial_train_manifest.csv"),
                            ("SPATIAL_VAL_NEW", "spatial_val_manifest.csv"),
                            ("EMBARGO", "spatial_embargo_manifest.csv")):
        with (OUT / filename).open("x", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, FIELDS)
            writer.writeheader()
            writer.writerows(row for row in rows if row["split"] == split)
    report = {"source_config": str(SOURCE.relative_to(ROOT)), "source_sha256": digest(SOURCE),
              "rule": "Whole Germany AOI plus Louisiana-East x>=29 validation; x=28 and all cross-zoom overlapping train tiles embargo; remainder training",
              "counts": dict(counts), "holdout_feature_classes": sorted(classes),
              "old_germany_development_tiles_excluded": len(config["splits"]["validation"]),
              "old_e4_and_e3c_checkpoints_forbidden_as_initializers": True,
              "independent_external_test": False,
              "manifests_sha256": {name: digest(OUT / name) for name in (
                  "spatial_train_manifest.csv", "spatial_val_manifest.csv", "spatial_embargo_manifest.csv")}}
    (OUT / "split_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    split_config = json.loads(json.dumps(config))
    split_config["splits"] = {"train": partitions["TRAIN_NEW"],
                              "validation": partitions["SPATIAL_VAL_NEW"], "test": []}
    split_config.pop("initialization_checkpoint", None)
    split_config.pop("initialization_allowed_missing", None)
    split_config["spatial_split_manifest"] = str((OUT / "split_report.json").relative_to(ROOT))
    split_config["test_scope"] = "Whole Germany AOI and Louisiana-East x>=29 spatial development holdout; x=28 embargo; external test absent"
    (OUT / "base_training_config.json").write_text(json.dumps(split_config, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"counts": counts, "holdout_classes": sorted(classes),
                      "split_report": str(OUT / "split_report.json")}))


if __name__ == "__main__":
    main()
