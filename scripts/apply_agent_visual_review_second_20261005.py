"""Freeze conservative AI visual decisions for the second annotation tile.

The output is an independent review layer, never a human ground-truth or test set.
The original and MapGIS-open working layers are not edited.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "annotation_workspace/louisiana-east-review-v1/02_2_20_57"
INDEX = FOLDER / "review_contacts/index.json"

# All 48 paired PRE/POST contact pages were visually inspected. These buildings
# visibly have event water adjacent to their footprints. Road evidence is too
# ambiguous for a confident full-object label.
VERIFIED_FLOODED = (set(range(1, 7)) | set(range(54, 81)) |
                    set(range(97, 111)) | set(range(154, 161)))
INSPECTED = set(range(1, 191))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path: Path, value: dict) -> None:
    if path.exists():
        raise FileExistsError(f"Visual review already exists: {path}")
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    by_id = {(row["kind"], row["id"]): row for row in index}
    if len(index) != 190 or {row["number"] for row in index} != set(range(1, 191)):
        raise ValueError("Unexpected contact index")
    if not VERIFIED_FLOODED <= INSPECTED:
        raise ValueError("Decision was not visually inspected")
    outputs = [FOLDER / f"agent_review_{kind}.geojson" for kind in ("buildings", "roads")]
    outputs.append(FOLDER / "agent_review_report.json")
    if any(path.exists() for path in outputs):
        raise FileExistsError("An agent review output already exists")
    entries = []
    for kind in ("buildings", "roads"):
        source = FOLDER / f"working_{kind}.geojson"
        value = json.loads(source.read_text(encoding="utf-8"))
        for feature in value["features"]:
            properties = feature["properties"]
            row = by_id.get((kind, properties["id"]))
            if row is None:
                raise ValueError(f"Feature absent from contact index: {properties['id']}")
            number = row["number"]
            if number in VERIFIED_FLOODED:
                if kind != "buildings" or properties.get("flooded") != "yes":
                    raise ValueError(f"Visual decision needs separate adjudication: {number}")
                properties["flooded"] = "yes"
                properties["annotation_status"] = "verified"
                reason = "Flood water visibly adjacent to building footprint in POST view"
                decision = "yes"
            else:
                properties["flooded"] = None
                properties["annotation_status"] = "uncertain" if number in INSPECTED else "pending"
                reason = ("Two-view image did not support a confident binary decision" if number in INSPECTED
                          else "Paired crop prepared but not individually inspected")
                decision = properties["annotation_status"]
            properties["review_origin"] = "AI_assisted_visual_2026-10-05"
            entries.append({"number": number, "id": properties["id"], "kind": kind,
                            "decision": decision, "status": properties["annotation_status"],
                            "reason": reason, "evidence": row["page"]})
        write_new(FOLDER / f"agent_review_{kind}.geojson", value)
    report = {"review_type": "AI_assisted_visual_review", "human_reviewed": False,
              "independent_test_accuracy_claim": False, "source_split": "train",
              "geometry_changes": 0, "pre_sha256": sha(FOLDER / "pre.tif"),
              "post_sha256": sha(FOLDER / "post.tif"), "contact_index_sha256": sha(INDEX),
              "verified_flooded": len(VERIFIED_FLOODED), "verified_non_flooded": 0,
              "uncertain": len(INSPECTED - VERIFIED_FLOODED),
              "pending": len(index) - len(INSPECTED), "total": len(index),
              "training_ready": False, "entries": sorted(entries, key=lambda item: item["number"])}
    write_new(FOLDER / "agent_review_report.json", report)
    print(json.dumps({key: report[key] for key in
                      ("total", "verified_flooded", "uncertain", "pending", "training_ready")}))


if __name__ == "__main__":
    main()
