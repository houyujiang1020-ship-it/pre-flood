"""Create a reproducible, explicitly simulated offline input bundle.

This script prepares source files only. It does not claim MapGIS HDF conversion,
network registration, model inference, or competition acceptance.
"""
from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "DemoDataset_Final"
WKT = ('PROJCS["WGS 84 / UTM zone 32N",GEOGCS["WGS 84",DATUM["WGS_1984",'
       'SPHEROID["WGS 84",6378137,298.257223563]],PRIMEM["Greenwich",0],'
       'UNIT["degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],'
       'PARAMETER["latitude_of_origin",0],PARAMETER["central_meridian",9],'
       'PARAMETER["scale_factor",0.9996],PARAMETER["false_easting",500000],'
       'PARAMETER["false_northing",0],UNIT["metre",1],AUTHORITY["EPSG","32632"]]')


def rectangle(x: float, y: float, size: float = 14) -> dict:
    return {"type": "Polygon", "coordinates": [[[x, y], [x + size, y],
            [x + size, y + size], [x, y + size], [x, y]]]}


def write(name: str, data: object) -> None:
    (DEST / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    buildings = [
        ("SIM-B01", 361100, 5599080, "normal"),
        ("SIM-B02", 361135, 5599120, "flooded"),
        ("SIM-B03", 361180, 5599170, "flooded"),
        ("SIM-B04", 361255, 5599250, "normal"),
    ]
    roads = [
        ("SIM-R01", [[361050, 5599050], [361150, 5599150]], "normal"),
        ("SIM-R02", [[361150, 5599150], [361230, 5599230]], "blocked"),
        ("SIM-R03", [[361050, 5599050], [361100, 5599200], [361230, 5599230]], "normal"),
    ]
    objects = []
    building_features = []
    road_features = []
    for ident, x, y, status in buildings:
        geometry = rectangle(x, y)
        building_features.append({"type": "Feature", "properties": {"object_id": ident,
                "flood_status": status, "simulation_only": True}, "geometry": geometry})
        objects.append({"object_id": ident, "type": "building", "geometry": geometry,
                        "damage_probability": 0.9 if status == "flooded" else 0.1,
                        "flood_status": status})
    for ident, coordinates, status in roads:
        geometry = {"type": "LineString", "coordinates": coordinates}
        road_features.append({"type": "Feature", "properties": {"object_id": ident,
                "flood_status": status, "simulation_only": True}, "geometry": geometry})
        objects.append({"object_id": ident, "type": "road", "geometry": geometry,
                        "damage_probability": 0.95 if status == "blocked" else 0.05,
                        "flood_status": status})
    write("01_flood_prediction.json", {"schema_version": 1, "simulation_only": True,
            "origin": "manually authored exercise geometry, not model inference",
            "crs_wkt": WKT, "objects": objects})
    for name, features in [("02_buildings.geojson", building_features),
                           ("03_roads.geojson", road_features)]:
        write(name, {"type": "FeatureCollection", "name": name, "simulation_only": True,
                     "crs": {"type": "name", "properties": {"name": "EPSG:32632"}},
                     "features": features})
    with (DEST / "04_population.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["grid_id", "x_m", "y_m", "population", "simulation_only"])
        writer.writeheader()
        for index, (x, y, pop) in enumerate([(361100, 5599100, 32), (361200, 5599200, 41),
                                              (361300, 5599300, 26)], 1):
            writer.writerow({"grid_id": f"SIM-G{index:02d}", "x_m": x, "y_m": y,
                             "population": pop, "simulation_only": "true"})
    write("05_resources.json", {"schema_version": 1, "simulation_only": True,
            "resources": [{"id": "SIM-V01", "kind": "VEHICLE", "name": "模拟救援车", "x": 361050, "y": 5599050,
                           "status": "AVAILABLE", "capacity": 5, "current": 0},
                          {"id": "SIM-M01", "kind": "MEDICAL", "name": "模拟医疗点", "x": 361280, "y": 5599320,
                           "status": "AVAILABLE", "capacity": 20, "current": 2},
                          {"id": "SIM-S01", "kind": "SHELTER", "name": "模拟避难点", "x": 361230, "y": 5599230,
                           "status": "AVAILABLE", "capacity": 100, "current": 24}]})
    write("07_flood_extent.geojson", {"type": "FeatureCollection", "simulation_only": True,
            "crs": {"type": "name", "properties": {"name": "EPSG:32632"}},
            "features": [{"type": "Feature", "properties": {"id": "SIM-FLOOD-01", "simulation_only": True},
                          "geometry": rectangle(361120, 5599100, 110)}]})
    grid_features = []
    for index, (x, y, pop) in enumerate([(361100, 5599100, 32), (361200, 5599200, 41),
                                          (361300, 5599300, 26)], 1):
        grid_features.append({"type": "Feature", "properties": {"grid_id": f"SIM-G{index:02d}",
                              "population": pop, "simulation_only": True},
                              "geometry": rectangle(x - 50, y - 50, 100)})
    write("08_population_grid.geojson", {"type": "FeatureCollection", "simulation_only": True,
            "crs": {"type": "name", "properties": {"name": "EPSG:32632"}}, "features": grid_features})
    write("09_admin_area.geojson", {"type": "FeatureCollection", "simulation_only": True,
            "crs": {"type": "name", "properties": {"name": "EPSG:32632"}},
            "features": [{"type": "Feature", "properties": {"area_name": "模拟区域01",
                          "resource_distance_risk": 0.4, "simulation_only": True},
                          "geometry": rectangle(361000, 5599000, 380)}]})
    write("06_scenario.json", {"schema_version": 1, "name": "城市洪涝灾害模拟案例01",
            "simulation_only": True, "ai_mode": "REPLAY", "ready": False,
            "readiness_reason": "原始素材已打包；人口 CSV、洪水面、路网、资源点尚未转换并核验为 MapGIS 原生图层，不能一键完成比赛演示",
            "inputs": ["01_flood_prediction.json", "02_buildings.geojson", "03_roads.geojson",
                       "04_population.csv", "05_resources.json", "07_flood_extent.geojson",
                       "08_population_grid.geojson", "09_admin_area.geojson", "pre.tif", "post.tif"],
            "scenario": None})
    for name in ("pre.tif", "post.tif"):
        shutil.copyfile(ROOT / "data" / "acceptance" / "gate5-v1" / name, DEST / name)


if __name__ == "__main__":
    main()
