"""Freeze conservative visual decisions for the first annotation tile.

This is AI-assisted image review, not an independent human ground-truth audit.
No MapGIS-open working layer or original SpaceNet label is overwritten.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "annotation_workspace/louisiana-east-review-v1/01_0_17_12"
INDEX = FOLDER / "review_contacts/index.json"

# Decisions were made after viewing all 15 paired contact pages at native detail.
# Anything not listed here remains uncertain instead of inheriting a source yes/no.
VERIFIED_FLOODED = {1, 4, 5, 6, 8, 9, 18, 19, 20, 21, 22, 23, 30, 33, 35, 41, 46,
                    49, 50, 56, 59}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path: Path, value: dict) -> None:
    if path.exists():
        raise FileExistsError(f"Visual review already exists: {path}")
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    if len(index) != 59 or {item["number"] for item in index} != set(range(1, 60)):
        raise ValueError("Unexpected contact index")
    if not VERIFIED_FLOODED <= {item["number"] for item in index}:
        raise ValueError("Unknown review object")
    for kind in ("buildings", "roads"):
        out = FOLDER / f"agent_review_{kind}.geojson"
        if out.exists():
            raise FileExistsError(out)
    if (FOLDER / "agent_review_report.json").exists():
        raise FileExistsError("Agent review report already exists")
    entries = []
    for kind in ("buildings", "roads"):
        source = FOLDER / f"working_{kind}.geojson"
        value = json.loads(source.read_text(encoding="utf-8"))
        for feature in value["features"]:
            properties = feature["properties"]
            item = next((row for row in index if row["kind"] == kind and row["id"] == properties["id"]), None)
            if item is None:
                raise ValueError(f"Feature absent from reviewed contacts: {properties['id']}")
            number = item["number"]
            if number in VERIFIED_FLOODED:
                if properties.get("flooded") != "yes":
                    raise ValueError(f"Visual label disagrees with seed label; requires separate adjudication: {number}")
                properties["flooded"] = "yes"
                properties["annotation_status"] = "verified"
                reason = ("Flood water visibly adjacent to building footprint" if kind == "buildings" else
                          "Road surface visibly covered in post-event scene")
            else:
                properties["flooded"] = None
                properties["annotation_status"] = "uncertain"
                reason = "Two-view imagery does not support a confident binary decision"
            properties["review_origin"] = "AI_assisted_visual_2026-10-05"
            entries.append({"number": number, "id": properties["id"], "kind": kind,
                            "decision": properties["flooded"] if number in VERIFIED_FLOODED else "uncertain",
                            "status": properties["annotation_status"], "reason": reason,
                            "evidence": item["page"]})
        write_new(FOLDER / f"agent_review_{kind}.geojson", value)
    report = {"review_type": "AI_assisted_visual_review", "human_reviewed": False,
              "independent_test_accuracy_claim": False, "source_split": "train",
              "geometry_changes": 0, "pre_sha256": sha(FOLDER / "pre.tif"),
              "post_sha256": sha(FOLDER / "post.tif"), "contact_index_sha256": sha(INDEX),
              "verified_flooded": len(VERIFIED_FLOODED), "verified_non_flooded": 0,
              "uncertain": len(index) - len(VERIFIED_FLOODED), "total": len(index),
              "training_ready": False, "entries": sorted(entries, key=lambda item: item["number"])}
    write_new(FOLDER / "agent_review_report.json", report)
    print(json.dumps({k: report[k] for k in ("total", "verified_flooded", "uncertain", "training_ready")}))


if __name__ == "__main__":
    main()
