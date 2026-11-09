"""Create research-only building/road weak masks from georeferenced vector sources."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
import shapefile
from pyproj import CRS, Transformer
from rasterio.features import rasterize
from shapely.geometry import shape
from shapely.ops import transform


def digest(path: Path) -> str:
    """Hash source bytes for provenance."""
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_features(path: Path, declared_crs: str | None):
    """Read GeoJSON or SHP with an explicit or companion-file CRS."""
    if path.suffix.lower() in (".geojson", ".json"):
        if not declared_crs:
            raise ValueError("GeoJSON requires --vector-crs; CRS must not be guessed")
        value = json.loads(path.read_text(encoding="utf-8"))
        features = [shape(feature["geometry"]) for feature in value["features"]]
        crs = CRS.from_user_input(declared_crs)
    elif path.suffix.lower() == ".shp":
        prj = path.with_suffix(".prj")
        if not declared_crs and not prj.is_file():
            raise ValueError("Shapefile requires .prj or --vector-crs")
        crs = CRS.from_user_input(declared_crs or prj.read_text(encoding="utf-8"))
        with shapefile.Reader(str(path)) as reader:
            features = [shape(item.__geo_interface__) for item in reader.iterShapes()]
    else:
        raise ValueError("Only GeoJSON and SHP are supported")
    if not features or any(geom.is_empty or not geom.is_valid for geom in features):
        raise ValueError("Empty or invalid vector geometry")
    return features, crs


def project(geom, source_crs: CRS, target_crs: CRS):
    """Reproject a geometry with longitude/latitude axis order fixed."""
    transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
    return transform(transformer.transform, geom)


def metric_buffer(line, source_crs: CRS, target_crs: CRS, metres: float):
    """Buffer a road in local UTM metres, then return geometry in image CRS."""
    geographic = project(line.centroid, source_crs, CRS.from_epsg(4326))
    lon, lat = geographic.x, geographic.y
    if not (-180 <= lon <= 180 and -80 <= lat <= 84):
        raise ValueError("Road is outside supported UTM region")
    zone = min(60, int((lon + 180) // 6) + 1)
    utm = CRS.from_epsg((32600 if lat >= 0 else 32700) + zone)
    return project(project(line, source_crs, utm).buffer(metres), utm, target_crs)


def main() -> None:
    """Write separate weak masks and immutable metadata in a fresh output directory."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--buildings", type=Path, required=True)
    parser.add_argument("--roads", type=Path, required=True)
    parser.add_argument("--building-crs")
    parser.add_argument("--road-crs")
    parser.add_argument("--road-buffer-meters", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not np.isfinite(args.road_buffer_meters) or args.road_buffer_meters <= 0:
        raise ValueError("Road buffer must be finite and positive metres")
    if args.output.exists():
        raise FileExistsError(args.output)
    buildings, building_crs = read_features(args.buildings, args.building_crs)
    roads, road_crs = read_features(args.roads, args.road_crs)
    if any(g.geom_type not in ("Polygon", "MultiPolygon") for g in buildings):
        raise ValueError("Building layer must contain polygons")
    if any(g.geom_type not in ("LineString", "MultiLineString") for g in roads):
        raise ValueError("Road layer must contain lines")
    with rasterio.open(args.image) as raster:
        if raster.crs is None or raster.transform.is_identity:
            raise ValueError("Image requires a valid CRS and non-identity transform")
        image_crs = CRS.from_user_input(raster.crs)
        destination = [project(g, building_crs, image_crs) for g in buildings]
        road_polygons = [metric_buffer(g, road_crs, image_crs, args.road_buffer_meters) for g in roads]
        valid = raster.dataset_mask() > 0
        shape_hw = (raster.height, raster.width)
        building_mask = rasterize(((g, 1) for g in destination), out_shape=shape_hw,
                                  transform=raster.transform, fill=0, dtype="uint8")
        road_mask = rasterize(((g, 1) for g in road_polygons), out_shape=shape_hw,
                              transform=raster.transform, fill=0, dtype="uint8")
        building_mask[~valid] = 255
        road_mask[~valid] = 255
        profile = raster.profile.copy()
        profile.update(driver="GTiff", count=1, dtype="uint8", nodata=255, compress="deflate")
        metadata = {"created_at": datetime.now(timezone.utc).isoformat(),
                    "label_type": "GIS-derived weak label, not human flood ground truth",
                    "image": str(args.image.resolve()), "image_sha256": digest(args.image),
                    "buildings": str(args.buildings.resolve()), "buildings_sha256": digest(args.buildings),
                    "roads": str(args.roads.resolve()), "roads_sha256": digest(args.roads),
                    "image_crs": image_crs.to_string(), "building_crs": building_crs.to_string(),
                    "road_crs": road_crs.to_string(), "transform": list(raster.transform)[:6],
                    "resolution": list(raster.res), "width": raster.width, "height": raster.height,
                    "road_buffer_meters": args.road_buffer_meters,
                    "building_positive_pixels": int((building_mask == 1).sum()),
                    "road_positive_pixels": int((road_mask == 1).sum()),
                    "ignored_nodata_pixels": int((~valid).sum())}
    args.output.mkdir(parents=True, exist_ok=False)
    for folder, mask in (("buildings", building_mask), ("roads", road_mask)):
        dest = args.output / folder
        dest.mkdir()
        with rasterio.open(dest / "mask.tif", "w", **profile) as writer:
            writer.write(mask, 1)
    (args.output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: metadata[key] for key in
                      ("building_positive_pixels", "road_positive_pixels", "ignored_nodata_pixels")}))


if __name__ == "__main__":
    main()
