"""Adapt three synthetic UTM roads for the existing MapGIS exercise NetCls builder."""
import hashlib
import json
from pathlib import Path

from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "DemoDataset_Final"
OUTPUT = ROOT / "data/demo/replay-p007/network-source"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    original = json.loads((SOURCE / "03_roads.geojson").read_text(encoding="utf-8"))
    transformer = Transformer.from_crs("EPSG:32632", "EPSG:4326", always_xy=True)
    roads = []
    for feature in original["features"]:
        identifier = feature["properties"]["object_id"]
        points = [list(transformer.transform(*point)) for point in feature["geometry"]["coordinates"]]
        roads.append({"type": "Feature", "id": identifier,
                      "properties": {"source_id": identifier, "simulation_only": True},
                      "geometry": {"type": "LineString", "coordinates": points}})
    road_file = OUTPUT / "roads.geojson"
    road_file.write_text(json.dumps({"type": "FeatureCollection", "features": roads},
                                    ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    start = roads[0]["geometry"]["coordinates"][0]
    destination = roads[1]["geometry"]["coordinates"][-1]
    vehicle = json.loads((SOURCE / "05_resources.json").read_text(encoding="utf-8"))["resources"][0]
    resources = {"schema_version": 1, "scenario_only": True,
                 "scope": "network-route-smoke-only; other exercise resources excluded pending 25m binding",
                 "resources": [{"id": vehicle["id"], "type": "rescue_vehicle", "capacity": vehicle["capacity"],
                                "scenario_only": True, "is_real_asset": False,
                                "source_road_id": roads[0]["id"], "source_vertex_index": 0,
                                "longitude": start[0], "latitude": start[1]}]}
    scenario = {"schema_version": 1, "scenario_only": True, "network_ready": False,
                "resource_type": "rescue_vehicle", "demand": vehicle["capacity"],
                "destination": {"source_road_id": roads[1]["id"], "source_vertex_index": 1,
                                "longitude": destination[0], "latitude": destination[1]},
                "scenarios": [{"id": "closure-SIM-R02", "closed_source_road_ids": [roads[1]["id"]]}],
                "assumed_speed_kph": 30, "speed_is_measured": False,
                "native_engine_required": "MapGIS", "target_crs": "EPSG:32632",
                "source_label": "DemoDataset_Final/03_roads.geojson"}
    for name, contents in (("resources.json", resources), ("scenario.json", scenario)):
        (OUTPUT / name).write_text(json.dumps(contents, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {"schema_version": 1, "scenario_only": True,
                "source_utm32_roads": str(SOURCE / "03_roads.geojson"),
                "source_utm32_roads_sha256": digest(SOURCE / "03_roads.geojson"),
                "transformation": "EPSG:32632 -> EPSG:4326 using pyproj; source IDs retained",
                "scope": "NetCls and one-vehicle route diagnostic; not a complete resource library",
                "files": {name: digest(OUTPUT / name) for name in ("roads.geojson", "resources.json", "scenario.json")}}
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(OUTPUT / "manifest.json")


if __name__ == "__main__":
    main()
