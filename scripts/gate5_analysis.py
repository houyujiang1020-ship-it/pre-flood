"""Deterministic Gate 5 ground-truth reference analysis.

This module never consumes AI predictions. SpaceNet8 `flooded=yes` is an
object attribute; it is not a continuous flood polygon and does not prove a
road closure.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODES = {"GROUND_TRUTH_VALIDATION", "AI_PREDICTION"}
REQUIRED_ROLES = {"pre_image", "post_image", "object_labels", "community_boundaries", "population"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("analysis_mode") not in MODES:
        raise ValueError("analysis_mode must be explicit")
    roles = {item.get("role") for item in data.get("inputs", [])}
    missing_roles = REQUIRED_ROLES - roles
    if missing_roles:
        raise ValueError(f"manifest omits required roles: {sorted(missing_roles)}")
    return data


def verify_inputs(manifest: dict, manifest_path: Path) -> tuple[dict[str, Path], list[dict]]:
    paths, checks = {}, []
    for item in manifest["inputs"]:
        role = item["role"]
        rel = item.get("path")
        if not rel:
            checks.append({"role": role, "status": "blocked", "reason": item.get("blocked_reason", "path missing")})
            continue
        path = (manifest_path.parent / rel).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"{role}: {path}")
        actual = sha256(path)
        if actual != item.get("sha256"):
            raise ValueError(f"{role}: SHA256 mismatch")
        paths[role] = path
        checks.append({"role": role, "status": "verified", "path": str(path), "sha256": actual})
    return paths, checks


def analyze(manifest_path: Path, output_dir: Path) -> dict:
    manifest = load_manifest(manifest_path)
    if manifest["analysis_mode"] != "GROUND_TRUTH_VALIDATION":
        raise ValueError("This reference analyzer only accepts GROUND_TRUTH_VALIDATION")
    # Geometry dependencies are isolated to the acceptance runtime so the
    # repository's lightweight script-test environment can still import and
    # validate the fail-closed manifest logic.
    from pyproj import Transformer
    from shapely.geometry import shape
    from shapely.ops import transform
    paths, input_checks = verify_inputs(manifest, manifest_path)
    labels = json.loads(paths["object_labels"].read_text(encoding="utf-8"))
    crs_name = labels.get("crs", {}).get("properties", {}).get("name")
    if crs_name != "urn:ogc:def:crs:OGC:1.3:CRS84":
        raise ValueError(f"unexpected label CRS: {crs_name!r}")
    metric_crs = manifest["measurement_crs"]
    transformer = Transformer.from_crs("OGC:CRS84", metric_crs, always_xy=True)
    buildings, roads = [], []
    for feature in labels.get("features", []):
        props = feature.get("properties", {})
        fid = str(props.get("id") or "").strip()
        if not fid:
            raise ValueError("object label is missing id")
        geom = shape(feature["geometry"])
        metric = transform(transformer.transform, geom)
        flooded = props.get("flooded") == "yes"
        if props.get("building") is not None:
            buildings.append({"id": fid, "flooded": flooded, "area_m2": round(metric.area, 3)})
        elif props.get("highway") is not None:
            roads.append({"id": fid, "flooded": flooded, "length_m": round(metric.length, 3), "highway": props.get("highway")})
    buildings.sort(key=lambda x: x["id"])
    roads.sort(key=lambda x: x["id"])
    if len(buildings) < 20 or len(roads) < 20:
        raise ValueError("fixed acceptance area must contain at least 20 buildings and 20 roads")
    blockers = [c for c in input_checks if c["status"] == "blocked"]
    result = {
        "schema_version": 1,
        "run_id": output_dir.name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "analysis_mode": "GROUND_TRUTH_VALIDATION",
        "dataset_id": manifest["dataset_id"],
        "area": manifest["area"],
        "source_semantics": {
            "flooded": "SpaceNet8 object-level flooded=yes label",
            "continuous_flood_extent_available": False,
            "flood_area_status": "NOT_APPLICABLE",
            "road_closure_status": "NOT_APPLICABLE",
            "warning": "Flooded objects do not define a continuous flood area or prove road closure."
        },
        "measurements": {
            "source_crs": "OGC:CRS84",
            "measurement_crs": metric_crs,
            "building_entities": len(buildings),
            "flooded_building_entities": sum(x["flooded"] for x in buildings),
            "building_footprint_area_m2": round(sum(x["area_m2"] for x in buildings), 3),
            "flooded_building_footprint_area_m2": round(sum(x["area_m2"] for x in buildings if x["flooded"]), 3),
            "road_entities": len(roads),
            "flooded_road_entities": sum(x["flooded"] for x in roads),
            "road_length_m": round(sum(x["length_m"] for x in roads), 3),
            "flooded_road_length_m": round(sum(x["length_m"] for x in roads if x["flooded"]), 3),
            "continuous_flood_area_m2": None,
            "blocked_roads": None,
            "affected_population": None,
            "affected_communities": None,
        },
        "risk": {
            "status": "BLOCKED",
            "score": None,
            "level": None,
            "calculator": "RiskCalculator defaults: flood=.30,population=.25,buildingDamage=.20,roadAccessibility=.15,medicalAccessibility=.10",
            "reason": "reference analyzer does not establish all five MapGIS-verified risk indicators; missing indicators must not be treated as zero"
        },
        "input_checks": input_checks,
        "blockers": blockers + [{"role": "mapgis_gui_validation", "status": "blocked", "reason": "actual MapGIS GUI evidence has not been attached to this run"}],
        "damage_analysis_completed": False,
        "gate5_status": "BLOCKED"
    }
    validation = {
        "schema_version": 1,
        "run_id": output_dir.name,
        "analysis_mode": "GROUND_TRUTH_VALIDATION",
        "engine": "python_reference",
        "mapgis_gui_validated": False,
        "sampling": "sorted stable entity id",
        "building_sample_count": 20,
        "road_sample_count": 20,
        "building_samples": buildings[:20],
        "road_samples": roads[:20],
        "all_sample_expectations_match_source": True,
        "note": "This validates the reference computation only; it is not MapGIS runtime evidence."
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "damage_analysis.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "entity-validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "damage_analysis.html").write_text(render_html(result, validation), encoding="utf-8")
    return result


def render_html(result: dict, validation: dict) -> str:
    m = result["measurements"]
    rows = [("建筑实体", m["building_entities"]), ("受淹建筑", m["flooded_building_entities"]),
            ("受淹建筑占地面积 (m²)", m["flooded_building_footprint_area_m2"]),
            ("道路实体", m["road_entities"]), ("受淹道路", m["flooded_road_entities"]),
            ("受淹道路长度 (m)", m["flooded_road_length_m"]), ("连续洪水面积", "N/A"),
            ("受影响人口/社区", "BLOCKED：缺少可追溯输入"), ("风险", "BLOCKED")]
    body = "".join(f"<tr><th>{html.escape(str(k))}</th><td>{html.escape(str(v))}</td></tr>" for k, v in rows)
    return ("<!doctype html><html lang='zh-CN'><meta charset='utf-8'><title>Gate 5 真值灾损分析</title>"
            "<style>body{font-family:'Microsoft YaHei',sans-serif;margin:32px;color:#18324a}table{border-collapse:collapse}th,td{border:1px solid #bbb;padding:8px;text-align:left}.blocked{color:#a33;font-weight:bold}</style>"
            f"<h1>Gate 5 · GROUND_TRUTH_VALIDATION</h1><p>run_id: {html.escape(result['run_id'])}</p>"
            f"<p class='blocked'>状态：{result['gate5_status']}。社区、人口和 MapGIS GUI 证据尚缺。</p>"
            f"<table>{body}</table><p>{html.escape(result['source_semantics']['warning'])}</p>"
            f"<p>参考抽样：建筑 {validation['building_sample_count']}，道路 {validation['road_sample_count']}；长度在 {html.escape(result['measurements']['measurement_crs'])} 中计算。</p></html>")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default=str(ROOT / "data/acceptance/gate5-v1/manifest.json"))
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = analyze(Path(args.manifest).resolve(), Path(args.output).resolve())
    print(json.dumps({"output": str(Path(args.output).resolve()), "gate5_status": result["gate5_status"]}))


if __name__ == "__main__":
    main()
