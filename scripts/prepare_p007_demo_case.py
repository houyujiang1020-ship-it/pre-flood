"""Prepare the existing hand-authored REPLAY exercise without promoting it to ready."""
import hashlib
import json
from pathlib import Path
from pyproj import Transformer
from shapely.geometry import Point
from shapely.geometry import mapping, shape
from shapely.ops import transform

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "DemoDataset_Final"
DEST = ROOT / "data/demo/replay-p007"
INPUTS = {
    "buildings.geojson": "02_buildings.geojson",
    "roads.geojson": "03_roads.geojson",
    "flood_extent.geojson": "07_flood_extent.geojson",
    "flood_prediction.json": "01_flood_prediction.json",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    ledger = {"schema_version": 1, "mode": "REPLAY_SIMULATION", "ready": False,
              "crs": "EPSG:32632", "source": "Hand-authored exercise objects/flood plus separately sourced Gate 5 population and administrative boundaries",
              "files": {}, "limitations": ["Objects are not SpaceNet annotation objects or model inference",
                                        "resource_distance_risk has no verified source rule",
                                        "native MapGIS layer and network binding must be verified"]}
    for target, original in INPUTS.items():
        source = SOURCE / original
        data = json.loads(source.read_text(encoding="utf-8"))
        if target.endswith(".geojson"):
            for index, feature in enumerate(data["features"], 1):
                props = feature["properties"]
                stable_id = props.get("object_id") or props.get("grid_id") or feature.get("id")
                if not stable_id:
                    stable_id = "SIM-A01" if target == "administrative.geojson" else "SIM-FLOOD-01"
                feature["id"] = stable_id
                props["source_id"] = stable_id
                props["source_file"] = original
                props["simulation_only"] = True
                if target == "flood_extent.geojson":
                    props["flood_kind"] = "CONTINUOUS_EXTENT"
                    props["flood_source"] = "DemoDataset_Final manually authored exercise polygon"
                    props["observation_status"] = "SYNTHETIC_TEST"
        destination = DEST / target
        destination.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        ledger["files"][target] = {"path": str(destination), "sha256": digest(destination),
                                   "source_path": str(source), "source_sha256": digest(source),
                                   "transformation": "metadata/ID annotation only; geometry unchanged"
                                   if target.endswith(".geojson") else "bytewise JSON reserialization"}
    gate_manifest = read_json(ROOT / "data/acceptance/gate5-v1/manifest.json")
    for target, original, source_crs in (
            ("population.geojson", "population-grid-100m.geojson", "EPSG:3035"),
            ("administrative.geojson", "community.geojson", "EPSG:25832")):
        source = ROOT / "data/acceptance/gate5-v1" / original
        source_data = read_json(source)
        projected = []
        conversion = Transformer.from_crs(source_crs, "EPSG:32632", always_xy=True)
        for feature in source_data["features"]:
            geometry = transform(conversion.transform, shape(feature["geometry"]))
            if target == "administrative.geojson" and geometry.geom_type == "MultiPolygon" and len(geometry.geoms) == 1:
                geometry = geometry.geoms[0]
            props = dict(feature["properties"])
            if target == "population.geojson":
                stable_id = props["grid_id"]
                props["population_unit"] = "persons_per_cell"
                props["population_source_unit"] = "persons_per_100m_cell"
                props["population_source"] = "Destatis Zensus 2022 population 100m grid"
            else:
                stable_id = feature["id"]
                props["area_id"] = props["community_id"]
                props["area_name"] = props["community_name"]
                props["resource_risk_status"] = "MISSING_VERIFIED_RULE"
            props["source_id"] = stable_id
            props["source_file"] = original
            projected.append({"type": "Feature", "id": stable_id, "properties": props,
                              "geometry": mapping(geometry)})
        data = {"type": "FeatureCollection", "crs": {"type": "name", "properties": {"name": "EPSG:32632"}},
                "features": projected}
        destination = DEST / target
        destination.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        entry = next(item for item in gate_manifest["inputs"] if item["path"] == original)
        if digest(source) != entry["sha256"]:
            raise ValueError(f"Gate 5 source hash differs: {source}")
        ledger["files"][target] = {"path": str(destination), "sha256": digest(destination),
                                   "source_path": str(source), "source_sha256": digest(source),
                                   "source_id": entry["source_id"], "license": entry["license"],
                                   "transformation": source_crs + " -> EPSG:32632 via pyproj; geometry coordinates transformed"}
    (DEST / "source-manifest.json").write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    roads = read_json(DEST / "roads.geojson")["features"]
    road_vertices = [(feature["id"], point) for feature in roads
                     for point in feature["geometry"]["coordinates"]]
    resources = read_json(SOURCE / "05_resources.json")["resources"]
    bindings = []
    for item in resources:
        nearest_id, nearest_xy = min(road_vertices,
                                     key=lambda pair: Point(item["x"], item["y"]).distance(Point(pair[1])))
        distance = Point(item["x"], item["y"]).distance(Point(nearest_xy))
        bindings.append({"resource_id": item["id"], "kind": item["kind"],
                         "nearest_source_road_id": nearest_id,
                         "nearest_source_vertex_xy": nearest_xy,
                         "nearest_source_vertex_distance_m": round(distance, 3),
                         "within_25m_of_source_vertex": distance <= 25,
                         "native_node_verified": False})
    (DEST / "resource-binding-preflight.json").write_text(json.dumps({
        "schema_version": 1, "simulation_only": True,
        "source_resource_sha256": digest(SOURCE / "05_resources.json"),
        "source_road_sha256": digest(SOURCE / "03_roads.geojson"),
        "bindings": bindings, "all_source_vertices_within_25m": all(x["within_25m_of_source_vertex"] for x in bindings),
        "native_network_binding_verified": False}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    statuses = [{"source_road_id": feature["id"],
                 "status": "BLOCKED" if feature["properties"].get("flood_status") == "blocked" else "NORMAL",
                 "status_source": "DemoDataset_Final hand-authored exercise road state",
                 "simulation_only": True, "native_oid": None, "native_edge_ids": []}
                for feature in roads]
    (DEST / "road-status-draft.json").write_text(json.dumps({
        "schema_version": 1, "case_id": "REPLAY-P007-SYNTHETIC",
        "simulation_only": True, "source_road_sha256": digest(SOURCE / "03_roads.geojson"),
        "network_fingerprint_sha256": None, "native_mapping_verified": False,
        "status_time": None, "status_time_note": "No observed event time; exercise design state only",
        "roads": statuses}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    case = {"schema_version": 1, "name": "P0-07 source-traced REPLAY exercise",
            "simulation_only": True, "ai_mode": "REPLAY", "ready": False,
            "readiness_reason": "Native MapGIS layer, network, resource risk and road closure bindings are incomplete",
            "input_files": {"prediction": "flood_prediction.json", "buildings": "buildings.geojson",
                            "roads": "roads.geojson", "population_csv": "../../../DemoDataset_Final/04_population.csv",
                            "resources": "../../../DemoDataset_Final/05_resources.json",
                            "flood_extent": "flood_extent.geojson", "population_grid": "population.geojson",
                            "administrative": "administrative.geojson",
                            "pre_image": "pre-utm32.tif", "post_image": "post-utm32.tif"},
            "scenario": None}
    (DEST / "06_scenario.json").write_text(json.dumps(case, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(DEST / "source-manifest.json")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
