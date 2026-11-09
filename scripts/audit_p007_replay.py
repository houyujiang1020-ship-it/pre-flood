"""Reconcile P0-07 evidence without changing either readiness flag."""
import json
import shutil
from pathlib import Path

import rasterio
from pyproj import CRS
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports/dev-continuation-20261010"
DERIVED = ROOT / "data/demo/replay-p007"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    original = ROOT / "outputs/demo-dataset-audit.json"
    REPORTS.mkdir(parents=True, exist_ok=True)
    saved = REPORTS / "p007-original-demo-dataset-audit.json"
    if not saved.exists():
        shutil.copy2(original, saved)
    baseline = read(saved)
    matrix = read(REPORTS / "p007-spatial-matrix.json")
    manifest = read(DERIVED / "source-manifest.json")
    derived_preflight_path = REPORTS / "p007-derived-case-preflight.json"
    derived_preflight = read(derived_preflight_path) if derived_preflight_path.is_file() else None
    with rasterio.open(DERIVED / "pre-utm32.tif") as pre, rasterio.open(DERIVED / "post-utm32.tif") as post:
        image_match = (pre.crs == post.crs and pre.crs.to_epsg() == 32632 and pre.transform == post.transform
                       and pre.width == post.width and pre.height == post.height)
    prediction = read(DERIVED / "flood_prediction.json")
    source_objects = {}
    for name, kind in (("buildings.geojson", "building"), ("roads.geojson", "road")):
        for feature in read(DERIVED / name)["features"]:
            source_objects[feature["id"]] = (kind, shape(feature["geometry"]))
    expected = CRS.from_wkt(prediction["crs_wkt"]).to_epsg() == 32632
    predictions = prediction["objects"]
    prediction_match = (expected and len(predictions) == len(source_objects)
                        and {item["object_id"] for item in predictions} == set(source_objects)
                        and all(item["type"] == source_objects[item["object_id"]][0]
                                and shape(item["geometry"]).equals(source_objects[item["object_id"]][1])
                                for item in predictions))
    attempts = [read(path) for path in DERIVED.glob("native-import-*/native-import.json")]
    resource_bindings = read(DERIVED / "resource-binding-preflight.json")
    native_success = any(item.get("native_import_verified") is True
                         and Path(item.get("database_file", "")).is_file() for item in attempts)
    network_source = read(DERIVED / "network-source/manifest.json")
    network_attempts = [read(path) for path in DERIVED.glob("network-*/network-build.json")]
    simulation_network_created = any(item.get("source_sha256") == network_source["files"]["roads.geojson"]
                                     and item.get("native_network_created") is True for item in network_attempts)
    roads_hash = matrix["matrix"]["roads"]["sha256"]
    historical = [item for item in matrix["historic_networks"] if item["source_sha256_matches"]]
    native_real_roads = any(item.get("native_network_created") is True for item in historical)
    case = {
        "schema_version": 1, "mode": "REPLAY_SIMULATION", "simulation_only": True,
        "official_submission_status": "NOT_READY", "full_demo_ready": False,
        "source_file_presence": baseline["offline_source_files_present"],
        "source_crs_matrix": str(REPORTS / "p007-spatial-matrix.json"),
        "derived_projected_images_same_grid": image_match,
        "replay_prediction_matches_simulation_objects": prediction_match,
        "replay_prediction_matches_original_spacenet_objects": False,
        "replay_prediction_origin": prediction.get("origin"),
        "synthetic_flood_extent": "DemoDataset_Final manually authored polygon; no observed flood claim",
        "native_import_verified": native_success,
        "native_import_attempts": attempts,
        "historic_network_source_roads_sha256": roads_hash,
        "historic_real_road_network_created": native_real_roads,
        "historic_network_is_simulation_road_network": False,
        "simulation_network_created": simulation_network_created,
        "simulation_network_attempts": network_attempts,
        "native_resource_library_verified": False,
        "resource_source_vertex_preflight_all_within_25m": resource_bindings["all_source_vertices_within_25m"],
        "resource_source_vertex_preflight": str(DERIVED / "resource-binding-preflight.json"),
        "road_status_ledger_with_native_edge_mapping_verified": False,
        "resource_distance_risk_verified": False,
        "demo_controller_first_blocked_step": "NOT_STARTED",
        "preflight_first_unavailable_stage": "LOAD_DATA",
        "demo_controller_reason": "No complete ScenarioManager binding, verified native resource manifest, or road-status ledger",
        "host_gui_verified_for_new_code": False,
        "source_manifest": str(DERIVED / "source-manifest.json"),
        "derived_case_preflight": str(derived_preflight_path) if derived_preflight else None,
        "derived_case_files_valid": derived_preflight["files_valid"] if derived_preflight else False,
        "derived_case_spatial_valid": derived_preflight["spatial_valid"] if derived_preflight else False,
        "derived_case_issues": derived_preflight["issues"] if derived_preflight else [],
        "original_audit": str(saved),
    }
    report = REPORTS / "p007-replay-readiness.json"
    report.write_text(json.dumps(case, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    updated = dict(baseline)
    updated["p007_replay"] = {key: case[key] for key in (
        "mode", "official_submission_status", "derived_projected_images_same_grid",
        "replay_prediction_matches_simulation_objects", "native_import_verified",
        "native_resource_library_verified", "resource_source_vertex_preflight_all_within_25m",
        "simulation_network_created",
        "road_status_ledger_with_native_edge_mapping_verified",
        "resource_distance_risk_verified", "demo_controller_first_blocked_step",
        "preflight_first_unavailable_stage",
        "derived_case_files_valid", "derived_case_spatial_valid", "derived_case_issues",
        "source_crs_matrix", "original_audit")}
    original.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
