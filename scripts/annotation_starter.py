"""Prepare a non-destructive MapGIS annotation starter and validate human edits.

The generated working GeoJSON is never connected to a training split automatically.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image, ImageDraw
from rasterio.enums import Resampling
from shapely.geometry import shape


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "11/Louisiana-East_Training_Public"
DEST = ROOT / "annotation_workspace/louisiana-east-review-v1"
TILES = ("0_17_12", "2_20_57")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def image_metadata(path: Path) -> dict:
    with rasterio.open(path) as dataset:
        if dataset.crs is None or dataset.count < 3:
            raise ValueError(f"Invalid RGB GeoTIFF: {path}")
        return {"width": dataset.width, "height": dataset.height, "crs": str(dataset.crs),
                "bounds": list(dataset.bounds), "bands": dataset.count}


def preview_image(path: Path, side: int = 512) -> Image.Image:
    with rasterio.open(path) as dataset:
        bands = dataset.read([1, 2, 3], out_shape=(3, side, side), resampling=Resampling.bilinear)
    return Image.fromarray(np.moveaxis(np.clip(bands, 0, 255).astype("uint8"), 0, -1))


def prepare() -> None:
    if DEST.exists():
        raise FileExistsError(f"Annotation workspace already exists; refusing to overwrite: {DEST}")
    config = json.loads((ROOT / "config/training.foundation-initialized-four-class-20260926.json")
                        .read_text(encoding="utf-8"))
    train = {(item["area"], item["label"]) for item in config["splits"]["train"]}
    validation = {(item["area"], item["label"]) for item in config["splits"]["validation"]}
    with (SOURCE / "Louisiana-East_Training_Public_label_image_mapping.csv").open(
            encoding="utf-8-sig", newline="") as stream:
        rows = {row["label"]: row for row in csv.DictReader(stream)}
    manifest = {"schema_version": 1, "purpose": "Human review and correction of existing training tiles",
                "training_ingestion": "disabled_until_validated_and_explicitly_configured",
                "source_area": SOURCE.name, "tiles": []}
    try:
        DEST.mkdir(parents=True)
        for index, tile in enumerate(TILES, 1):
            label = f"{tile}.geojson"
            identity = (SOURCE.name, label)
            if identity not in train or identity in validation:
                raise ValueError(f"Tile is not exclusively in the existing training split: {label}")
            row = rows[label]
            folder = DEST / f"{index:02d}_{tile}"
            folder.mkdir()
            original = SOURCE / "annotations" / label
            pre = SOURCE / "PRE-event" / row["pre-event image"]
            post = SOURCE / "POST-event" / row["post-event image 1"]
            for path in (original, pre, post):
                if not path.is_file():
                    raise FileNotFoundError(path)
            before, after = image_metadata(pre), image_metadata(post)
            if before["crs"] != "EPSG:4326" or after["crs"] != before["crs"]:
                raise ValueError(f"Unexpected image CRS: {tile}")
            overlap_x = min(before["bounds"][2], after["bounds"][2]) - max(before["bounds"][0], after["bounds"][0])
            overlap_y = min(before["bounds"][3], after["bounds"][3]) - max(before["bounds"][1], after["bounds"][1])
            if overlap_x <= 0 or overlap_y <= 0:
                raise ValueError(f"Image pair does not overlap: {tile}")
            shutil.copy2(pre, folder / "pre.tif")
            shutil.copy2(post, folder / "post.tif")
            shutil.copy2(original, folder / "reference_original.geojson")
            reference = json.loads(original.read_text(encoding="utf-8"))
            grouped = {"buildings": [], "roads": []}
            counts = {"non_flooded_building": 0, "flooded_building": 0,
                      "non_flooded_road": 0, "flooded_road": 0}
            for feature in reference["features"]:
                properties = feature.get("properties", {})
                building = properties.get("building") not in (None, "no", "")
                road = properties.get("highway") not in (None, "")
                if building == road:
                    raise ValueError(f"Ambiguous source feature type: {tile}")
                copied = json.loads(json.dumps(feature))
                copied["properties"]["annotation_status"] = "pending"
                kind = "buildings" if building else "roads"
                grouped[kind].append(copied)
                name = ("building" if building else "road")
                counts[("flooded_" if properties.get("flooded") == "yes" else "non_flooded_") + name] += 1
            for kind, features in grouped.items():
                write_json(folder / f"working_{kind}.geojson", {"type": "FeatureCollection", "features": features})
            panel = Image.new("RGB", (1024, 544), "white")
            panel.paste(preview_image(pre), (0, 32))
            panel.paste(preview_image(post), (512, 32))
            draw = ImageDraw.Draw(panel)
            draw.text((8, 9), f"{tile} PRE-event", fill="black")
            draw.text((520, 9), f"{tile} POST-event", fill="black")
            panel.save(folder / "visual_reference.png")
            manifest["tiles"].append({"tile": tile, "folder": folder.name, "source_split": "train",
                                      "class_counts_from_reference_only": counts,
                                      "files": {name: {"source": str(path), "sha256": digest(path)}
                                                for name, path in (("pre.tif", pre), ("post.tif", post),
                                                                   ("reference_original.geojson", original))},
                                      "pre_metadata": before, "post_metadata": after})
        write_json(DEST / "manifest.json", manifest)
    except Exception:
        # An incomplete new workspace is not safe to present as ready.
        shutil.rmtree(DEST)
        raise
    print(DEST)


def validate() -> None:
    manifest = json.loads((DEST / "manifest.json").read_text(encoding="utf-8"))
    issues = []
    total, verified = 0, 0
    for item in manifest["tiles"]:
        folder = DEST / item["folder"]
        for name, info in item["files"].items():
            if not (folder / name).is_file() or digest(folder / name) != info["sha256"]:
                issues.append(f"{item['tile']}: source copy changed or missing: {name}")
        ids = set()
        for kind, geometry_type in (("buildings", ("Polygon", "MultiPolygon")),
                                    ("roads", ("LineString", "MultiLineString"))):
            path = folder / f"working_{kind}.geojson"
            if not path.is_file():
                issues.append(f"{item['tile']}: missing {path.name}")
                continue
            collection = json.loads(path.read_text(encoding="utf-8"))
            if collection.get("type") != "FeatureCollection":
                issues.append(f"{item['tile']}: invalid FeatureCollection: {path.name}")
                continue
            for number, feature in enumerate(collection.get("features", []), 1):
                total += 1
                prop = feature.get("properties", {})
                identifier = prop.get("id")
                if not identifier or identifier in ids:
                    issues.append(f"{item['tile']}: missing or duplicate id at {kind} feature {number}")
                ids.add(identifier)
                if kind == "buildings" and prop.get("building") in (None, "no", ""):
                    issues.append(f"{item['tile']}: building type missing for {identifier}")
                if kind == "roads" and prop.get("highway") in (None, ""):
                    issues.append(f"{item['tile']}: road type missing for {identifier}")
                geometry = feature.get("geometry") or {}
                if geometry.get("type") not in geometry_type:
                    issues.append(f"{item['tile']}: wrong geometry type for {identifier}")
                else:
                    try:
                        if not shape(geometry).is_valid or shape(geometry).is_empty:
                            issues.append(f"{item['tile']}: invalid geometry for {identifier}")
                    except (ValueError, TypeError):
                        issues.append(f"{item['tile']}: unreadable geometry for {identifier}")
                status = prop.get("annotation_status")
                if status == "verified":
                    verified += 1
                    if prop.get("flooded") not in ("yes", "no"):
                        issues.append(f"{item['tile']}: verified {identifier} needs flooded=yes/no")
                elif status not in ("pending", "uncertain"):
                    issues.append(f"{item['tile']}: invalid annotation_status for {identifier}")
    result = {"status": "ready_for_human_final_review" if not issues and total > 0 and verified == total else "in_progress",
              "verified_features": verified, "total_features": total,
              "remaining_features": total - verified, "issues": issues,
              "training_config_updated": False, "original_labels_overwritten": False}
    write_json(DEST / "validation.json", result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "validate"))
    action = parser.parse_args().action
    (prepare if action == "prepare" else validate)()
