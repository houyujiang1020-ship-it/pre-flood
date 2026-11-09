"""Export separate AI visual review layers for display in MapGIS Desktop."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import shapefile
from shapely.geometry import shape

from annotation_shapefile import WGS84_PRJ, WORKSPACE, polygon_parts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tile", choices=("01_0_17_12", "02_2_20_57"))
    args = parser.parse_args()
    names = (args.tile,) if args.tile else ("01_0_17_12", "02_2_20_57")
    for folder in (WORKSPACE / name for name in names):
        for kind in ("buildings", "roads"):
            source = folder / f"agent_review_{kind}.geojson"
            target = folder / f"agent_review_{kind}"
            suffixes = (".shp", ".shx", ".dbf", ".prj", ".cpg")
            if any(target.with_suffix(suffix).exists() for suffix in suffixes):
                raise FileExistsError(f"Review Shapefile exists: {target}")
            collection = json.loads(source.read_text(encoding="utf-8"))
            with shapefile.Writer(str(target),
                                  shapeType=(shapefile.POLYGON if kind == "buildings" else shapefile.POLYLINE),
                                  encoding="utf-8") as writer:
                writer.field("obj_id", "C", size=80)
                writer.field("kind", "C", size=80)
                writer.field("flooded", "C", size=10)
                writer.field("status", "C", size=10)
                writer.field("origin", "C", size=50)
                for feature in collection["features"]:
                    props = feature["properties"]
                    geom = shape(feature["geometry"])
                    if geom.is_empty or not geom.is_valid:
                        raise ValueError(f"Invalid geometry: {props['id']}")
                    if kind == "buildings":
                        writer.poly(polygon_parts(geom))
                    else:
                        lines = [geom] if geom.geom_type == "LineString" else list(geom.geoms)
                        if not lines or any(line.geom_type != "LineString" for line in lines):
                            raise ValueError(f"Invalid road geometry: {props['id']}")
                        writer.line([list(line.coords) for line in lines])
                    writer.record(props["id"], props.get("building" if kind == "buildings" else "highway") or "",
                                  props.get("flooded") or "", props["annotation_status"],
                                  props["review_origin"])
            target.with_suffix(".prj").write_text(WGS84_PRJ, encoding="ascii")
            target.with_suffix(".cpg").write_text("UTF-8\n", encoding="ascii")
            with shapefile.Reader(str(target) + ".shp", encoding="utf-8") as reader:
                if len(reader) != len(collection["features"]):
                    raise ValueError(f"Shapefile feature count mismatch: {target}")
                if any(not shape(item.shape.__geo_interface__).is_valid for item in reader.iterShapeRecords()):
                    raise ValueError(f"Invalid exported geometry: {target}")
            print(f"{target}.shp: {len(collection['features'])} features")


if __name__ == "__main__":
    main()
