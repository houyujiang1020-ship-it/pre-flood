"""Audit P0-07 source geometry and derive a common projected image grid.

No source file is modified. The output is an exercise-only spatial derivative.
"""
import hashlib
import json
from pathlib import Path

import rasterio
from pyproj import CRS, Transformer
from rasterio.enums import Resampling
from rasterio.warp import calculate_default_transform, reproject
from shapely.geometry import box, shape
from shapely.ops import transform, unary_union

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/demo/replay-p007"
SOURCES = {
    "pre_image": "data/acceptance/gate5-v1/pre.tif",
    "post_image": "data/acceptance/gate5-v1/post.tif",
    "buildings": "data/demo/dispatch-spacenet8-endpoint-v2/buildings.geojson",
    "roads": "data/demo/dispatch-spacenet8-endpoint-v2/roads.geojson",
    "population_grid": "data/acceptance/gate5-v1/population-grid-100m.geojson",
    "administrative": "data/acceptance/gate5-v1/community.geojson",
    "resources": "data/demo/dispatch-spacenet8-endpoint-v2/resources.json",
    "simulation_buildings": "DemoDataset_Final/02_buildings.geojson",
    "simulation_roads": "DemoDataset_Final/03_roads.geojson",
    "simulation_population": "DemoDataset_Final/08_population_grid.geojson",
    "simulation_administrative": "DemoDataset_Final/09_admin_area.geojson",
    "simulation_flood_extent": "DemoDataset_Final/07_flood_extent.geojson",
    "simulation_resources": "DemoDataset_Final/05_resources.json",
    "simulation_prediction": "DemoDataset_Final/01_flood_prediction.json",
}


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def coordinates(value):
    return [round(float(x), 7) for x in value]


def inspect():
    matrix, geometries = {}, {}
    optional = {key: path for key, path in {
        "derived_population": "data/demo/replay-p007/population.geojson",
        "derived_administrative": "data/demo/replay-p007/administrative.geojson",
        "derived_flood_extent": "data/demo/replay-p007/flood_extent.geojson",
    }.items() if (ROOT / path).is_file()}
    for key, relative in {**SOURCES, **optional}.items():
        path = ROOT / relative
        row = {"path": str(path), "sha256": digest(path), "bytes": path.stat().st_size}
        if path.suffix == ".tif":
            with rasterio.open(path) as dataset:
                row.update(crs=dataset.crs.to_string(), transform=list(dataset.transform)[:6],
                           width=dataset.width, height=dataset.height,
                           bounds=coordinates(dataset.bounds), resolution=list(dataset.res))
                area = box(*dataset.bounds)
                geometries[key] = transform(Transformer.from_crs(dataset.crs, 32632, always_xy=True).transform, area)
        elif path.suffix == ".geojson":
            data = json.loads(path.read_text(encoding="utf-8"))
            declared = data.get("crs", {}).get("properties", {}).get("name")
            crs = CRS.from_user_input(declared or "EPSG:4326")
            features = data["features"]
            parts = [shape(feature["geometry"]) for feature in features]
            merged = unary_union(parts)
            geometries[key] = transform(Transformer.from_crs(crs, 32632, always_xy=True).transform, merged)
            ids = [feature.get("id") or feature.get("properties", {}).get("object_id")
                   or feature.get("properties", {}).get("grid_id") for feature in features]
            row.update(crs=crs.to_string(), crs_declared=bool(declared),
                       crs_basis="GeoJSON RFC 7946 and source manifest" if not declared else "file declaration",
                       count=len(features), geometry_types=sorted({part.geom_type for part in parts}),
                       all_geometries_valid=all(part.is_valid and not part.is_empty for part in parts),
                       bounds=coordinates(merged.bounds), projected_bounds=coordinates(geometries[key].bounds),
                       fields=sorted({field for item in features for field in item.get("properties", {})}),
                       ids_complete=all(ids) and len(set(ids)) == len(ids), sample_ids=ids[:3])
        else:
            data = json.loads(path.read_text(encoding="utf-8"))
            if "resources" in data:
                items = data["resources"]
                row.update(count=len(items), ids=[item.get("id") for item in items],
                           types=sorted({str(item.get("type", item.get("kind"))) for item in items}),
                           fields=sorted({field for item in items for field in item}),
                           coordinates=[[item.get("longitude", item.get("x")),
                                         item.get("latitude", item.get("y"))] for item in items])
                crs = 4326 if "longitude" in items[0] else 32632
                row["crs"] = f"EPSG:{crs}"
                geometries[key] = unary_union([transform(
                    Transformer.from_crs(crs, 32632, always_xy=True).transform,
                    shape({"type": "Point", "coordinates": point})) for point in row["coordinates"]])
            else:
                items = data["objects"]
                row.update(crs=CRS.from_wkt(data["crs_wkt"]).to_string(), count=len(items),
                           ids=[item["object_id"] for item in items],
                           statuses={item["object_id"]: item["flood_status"] for item in items},
                           origin=data.get("origin"))
        matrix[key] = row
    pre, post = matrix["pre_image"], matrix["post_image"]
    comparisons = {"pre_post_same_grid": all(pre[name] == post[name] for name in
                    ("crs", "transform", "width", "height")), "projected_crs": "EPSG:32632"}
    aoi = geometries["pre_image"]
    for key, geometry in geometries.items():
        comparisons[key + "_intersects_image"] = geometry.intersects(aoi)
        if key in ("buildings", "roads", "simulation_buildings", "simulation_roads"):
            comparisons[key + "_within_image"] = geometry.within(aoi.buffer(1))
    comparisons["real_administrative_covers_image"] = geometries["administrative"].covers(aoi)
    comparisons["simulation_administrative_covers_simulation_flood"] = (
        geometries["simulation_administrative"].covers(geometries["simulation_flood_extent"]))
    comparisons["simulation_flood_intersects_simulation_population"] = (
        geometries["simulation_flood_extent"].intersects(geometries["simulation_population"]))
    if "derived_administrative" in geometries:
        comparisons["derived_administrative_covers_simulation_flood"] = (
            geometries["derived_administrative"].covers(geometries["simulation_flood_extent"]))
        comparisons["derived_population_intersects_simulation_flood"] = (
            geometries["derived_population"].intersects(geometries["simulation_flood_extent"]))
    labels = {}
    for key in ("buildings", "roads"):
        data = json.loads((ROOT / SOURCES[key]).read_text(encoding="utf-8"))
        labels[key] = {str(feature["id"]): feature["properties"].get("flooded") for feature in data["features"]}
    comparisons["real_annotation_labels"] = {key: {str(value): list(items.values()).count(value)
                                                   for value in set(items.values())} for key, items in labels.items()}
    comparisons["simulation_prediction_ids_match_simulation_features"] = (
        set(matrix["simulation_prediction"]["ids"]) ==
        {f["properties"]["object_id"] for name in ("simulation_buildings", "simulation_roads")
         for f in json.loads((ROOT / SOURCES[name]).read_text(encoding="utf-8"))["features"]})
    comparisons["simulation_prediction_ids_match_real_features"] = (
        set(matrix["simulation_prediction"]["ids"]) == set(labels["buildings"]) | set(labels["roads"]))
    original_roads = {feature["id"]:feature for feature in json.loads(
        (ROOT / SOURCES["roads"]).read_text(encoding="utf-8"))["features"]}
    resources = json.loads((ROOT / SOURCES["resources"]).read_text(encoding="utf-8"))["resources"]
    comparisons["resource_points_match_declared_road_vertices"] = all(
        resource.get("source_road_id") in original_roads
        and 0 <= resource.get("source_vertex_index", -1) < len(original_roads[resource["source_road_id"]]["geometry"]["coordinates"])
        and abs(resource["longitude"] - original_roads[resource["source_road_id"]]["geometry"]["coordinates"][resource["source_vertex_index"]][0]) < 1e-8
        and abs(resource["latitude"] - original_roads[resource["source_road_id"]]["geometry"]["coordinates"][resource["source_vertex_index"]][1]) < 1e-8
        for resource in resources)
    builds = []
    for evidence in (ROOT / "data/demo/dispatch-spacenet8-endpoint-v2").glob("mapgis-*/network-build.json"):
        item = json.loads(evidence.read_text(encoding="utf-8"))
        builds.append({"evidence": str(evidence), "source_sha256_matches":
                       item.get("source_sha256") == matrix["roads"]["sha256"],
                       "network_url": item.get("network_url"),
                       "native_network_created": item.get("native_network_created"),
                       "dispatch_ready": item.get("dispatch_ready"),
                       "exercise_routes_verified": item.get("exercise_routes_verified")})
    return {"schema_version": 1, "matrix": matrix, "comparisons": comparisons,
            "historic_networks": builds}


def project_images(matrix):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    pre = ROOT / SOURCES["pre_image"]
    post = ROOT / SOURCES["post_image"]
    with rasterio.open(pre) as reference:
        transform_out, width, height = calculate_default_transform(
            reference.crs, "EPSG:32632", reference.width, reference.height, *reference.bounds)
        profile = reference.profile.copy()
        profile.update(crs="EPSG:32632", transform=transform_out, width=width, height=height)
        for name, source in (("pre", pre), ("post", post)):
            destination = OUTPUT / f"{name}-utm32.tif"
            with rasterio.open(source) as dataset, rasterio.open(destination, "w", **profile) as target:
                for band in range(1, reference.count + 1):
                    reproject(source=rasterio.band(dataset, band), destination=rasterio.band(target, band),
                              src_transform=dataset.transform, src_crs=dataset.crs,
                              dst_transform=transform_out, dst_crs="EPSG:32632",
                              resampling=Resampling.bilinear)
            matrix["derived_" + name] = {"path": str(destination), "sha256": digest(destination),
                                         "source_sha256": digest(source), "crs": "EPSG:32632",
                                         "transform": list(transform_out)[:6], "width": width, "height": height,
                                         "resampling": "bilinear", "simulation_only": True}


def main():
    result = inspect()
    project_images(result["matrix"])
    report = ROOT / "reports/dev-continuation-20261010/p007-spatial-matrix.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
