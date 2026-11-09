"""Check AI visual review outputs without changing annotation data."""
from __future__ import annotations

import hashlib
import json

import shapefile
from shapely.geometry import shape

from annotation_shapefile import WORKSPACE


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    totals = {"objects": 0, "verified_flooded": 0, "uncertain": 0, "pending": 0}
    for name in ("01_0_17_12", "02_2_20_57"):
        folder = WORKSPACE / name
        report = json.loads((folder / "agent_review_report.json").read_text(encoding="utf-8"))
        if report["pre_sha256"] != digest(folder / "pre.tif") or report["post_sha256"] != digest(folder / "post.tif"):
            raise AssertionError(f"Image hash mismatch: {name}")
        if report["contact_index_sha256"] != digest(folder / "review_contacts/index.json"):
            raise AssertionError(f"Contact index hash mismatch: {name}")
        if report["human_reviewed"] or report["training_ready"] or report["source_split"] != "train":
            raise AssertionError(f"Review provenance invalid: {name}")
        counts = {"verified_flooded": 0, "uncertain": 0, "pending": 0}
        n = 0
        for kind in ("buildings", "roads"):
            source = json.loads((folder / f"working_{kind}.geojson").read_text(encoding="utf-8"))
            review = json.loads((folder / f"agent_review_{kind}.geojson").read_text(encoding="utf-8"))
            if len(source["features"]) != len(review["features"]):
                raise AssertionError(f"Feature count changed: {name}/{kind}")
            with shapefile.Reader(str(folder / f"agent_review_{kind}.shp"), encoding="utf-8") as shp:
                records = list(shp.iterRecords())
                if len(records) != len(review["features"]):
                    raise AssertionError(f"Shapefile count mismatch: {name}/{kind}")
                for old, new, record in zip(source["features"], review["features"], records):
                    old_props, props = old["properties"], new["properties"]
                    if old["geometry"] != new["geometry"] or not shape(new["geometry"]).is_valid:
                        raise AssertionError(f"Geometry changed/invalid: {name}/{kind}")
                    if old_props["id"] != props["id"] or str(record[0]) != props["id"]:
                        raise AssertionError(f"ID mismatch: {name}/{kind}")
                    if str(record[2]).strip() != (props["flooded"] or "") or str(record[3]).strip() != props["annotation_status"]:
                        raise AssertionError(f"SHP attribute mismatch: {name}/{kind}/{props['id']}")
                    if props.get("review_origin") != "AI_assisted_visual_2026-10-05":
                        raise AssertionError(f"Origin missing: {name}/{kind}")
                    status = props["annotation_status"]
                    if status == "verified":
                        if props["flooded"] != "yes":
                            raise AssertionError(f"Unsupported verified status: {name}/{kind}")
                        counts["verified_flooded"] += 1
                    elif status in ("uncertain", "pending"):
                        if props["flooded"] is not None:
                            raise AssertionError(f"Unresolved label is nonempty: {name}/{kind}")
                        counts[status] += 1
                    else:
                        raise AssertionError(f"Unexpected status: {name}/{kind}/{status}")
                    n += 1
        for key, value in counts.items():
            if report.get(key, 0) != value:
                raise AssertionError(f"Report count mismatch: {name}/{key}")
        if report["total"] != n or len(report["entries"]) != n:
            raise AssertionError(f"Report total mismatch: {name}")
        totals["objects"] += n
        for key, value in counts.items():
            totals[key] += value
    print(json.dumps(totals))


if __name__ == "__main__":
    main()
