"""Exchange MapGIS annotation working layers through Shapefile, preserving GeoJSON sources."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import shapefile
from shapely.geometry import MultiPolygon, Polygon, mapping, shape
from shapely.geometry.polygon import orient

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT / "annotation_workspace/louisiana-east-review-v1"
WGS84_PRJ = ('GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,'
             '298.257223563]],PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433],'
             'AUTHORITY["EPSG","4326"]]')


def groups():
    manifest = json.loads((WORKSPACE / "manifest.json").read_text(encoding="utf-8"))
    for tile in manifest["tiles"]:
        yield WORKSPACE / tile["folder"]


def polygon_parts(geometry):
    polygons = [geometry] if isinstance(geometry, Polygon) else list(geometry.geoms)
    if not polygons or not all(isinstance(part, Polygon) for part in polygons):
        raise ValueError("Expected Polygon or MultiPolygon")
    rings = []
    for polygon in polygons:
        polygon = orient(polygon, sign=-1.0)  # Shapefile outer ring clockwise.
        rings.append(list(polygon.exterior.coords))
        rings.extend(list(interior.coords) for interior in polygon.interiors)
    return rings


def export() -> None:
    for folder in groups():
        for kind in ("buildings", "roads"):
            source = folder / f"working_{kind}.geojson"
            target = folder / f"mapgis_{kind}"
            if any(target.with_suffix(suffix).exists() for suffix in (".shp", ".shx", ".dbf", ".prj", ".cpg")):
                raise FileExistsError(f"Existing MapGIS working layer: {target}.shp")
            collection = json.loads(source.read_text(encoding="utf-8"))
            with shapefile.Writer(str(target), shapeType=(shapefile.POLYGON if kind == "buildings" else shapefile.POLYLINE),
                                  encoding="utf-8") as writer:
                writer.field("obj_id", "C", size=80)
                writer.field("kind", "C", size=80)
                writer.field("flooded", "C", size=10)
                writer.field("status", "C", size=10)
                for feature in collection["features"]:
                    properties = feature["properties"]
                    geometry = shape(feature["geometry"])
                    if geometry.is_empty or not geometry.is_valid:
                        raise ValueError(f"Invalid source geometry: {properties.get('id')}")
                    if kind == "buildings":
                        writer.poly(polygon_parts(geometry))
                    else:
                        lines = [geometry] if geometry.geom_type == "LineString" else list(geometry.geoms)
                        if not lines or any(line.geom_type != "LineString" for line in lines):
                            raise ValueError(f"Expected road line: {properties.get('id')}")
                        writer.line([list(line.coords) for line in lines])
                    writer.record(properties["id"], properties.get("building" if kind == "buildings" else "highway") or "",
                                  properties.get("flooded") or "", properties.get("annotation_status") or "pending")
            target.with_suffix(".prj").write_text(WGS84_PRJ, encoding="ascii")
            target.with_suffix(".cpg").write_text("UTF-8\n", encoding="ascii")
            with shapefile.Reader(str(target) + ".shp", encoding="utf-8") as reader:
                if len(reader) != len(collection["features"]):
                    raise ValueError(f"Shapefile count mismatch: {target}")
                if any(not shape(record.shape.__geo_interface__).is_valid for record in reader.iterShapeRecords()):
                    raise ValueError(f"Shapefile geometry invalid: {target}")
            print(f"{target}.shp: {len(collection['features'])} features")


def sync() -> None:
    """Update working GeoJSON after MapGIS edits/exports the matching Shapefiles."""
    prepared = []
    for folder in groups():
        for kind in ("buildings", "roads"):
            source = folder / f"mapgis_{kind}.shp"
            working = folder / f"working_{kind}.geojson"
            if not source.is_file():
                raise FileNotFoundError(source)
            original = json.loads(working.read_text(encoding="utf-8"))
            old_by_id = {feature["properties"]["id"]: feature for feature in original["features"]}
            output = []
            seen = set()
            with shapefile.Reader(str(source), encoding="utf-8") as reader:
                fields = [field[0] for field in reader.fields[1:]]
                if fields != ["obj_id", "kind", "flooded", "status"]:
                    raise ValueError(f"MapGIS export changed required fields: {source}: {fields}")
                for item in reader.iterShapeRecords():
                    attrs = dict(zip(fields, item.record))
                    identifier = str(attrs["obj_id"] or "").strip()
                    if not identifier or identifier in seen:
                        raise ValueError(f"Missing or duplicate obj_id: {source}")
                    seen.add(identifier)
                    geom = shape(item.shape.__geo_interface__)
                    if geom.is_empty or not geom.is_valid:
                        raise ValueError(f"Invalid edited geometry: {source}: {identifier}")
                    allowed = ("Polygon", "MultiPolygon") if kind == "buildings" else ("LineString", "MultiLineString")
                    if geom.geom_type not in allowed:
                        raise ValueError(f"Wrong edited geometry type: {source}: {identifier}")
                    old = old_by_id.get(identifier)
                    props = dict(old["properties"]) if old else {"id": identifier}
                    props["id"] = identifier
                    props["building" if kind == "buildings" else "highway"] = str(attrs["kind"] or "").strip()
                    props["flooded"] = str(attrs["flooded"] or "").strip() or None
                    props["annotation_status"] = str(attrs["status"] or "").strip()
                    output.append({"type": "Feature", "properties": props, "geometry": mapping(geom)})
            prepared.append((working, {"type": "FeatureCollection", "features": output}))
    # Read and validate every layer before changing any GeoJSON. Keep an immutable seed backup.
    for working, _ in prepared:
        backup = working.with_suffix(".before_mapgis.geojson")
        if backup.exists():
            raise FileExistsError(f"Backup exists; refusing to overwrite: {backup}")
    for working, collection in prepared:
        backup = working.with_suffix(".before_mapgis.geojson")
        backup.write_bytes(working.read_bytes())
        temp = working.with_suffix(".tmp")
        temp.write_text(json.dumps(collection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temp, working)
        print(f"Synchronized {len(collection['features'])} features: {working}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("export", "sync"))
    action = parser.parse_args().action
    (export if action == "export" else sync)()
