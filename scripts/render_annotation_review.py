"""Render paired MapGIS annotation contact sheets for human visual review only."""
from __future__ import annotations

import json
import argparse
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image, ImageDraw
from rasterio.enums import Resampling
from rasterio.warp import reproject
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "annotation_workspace/louisiana-east-review-v1/01_0_17_12"
SIDE = 280
HALF = SIDE // 2


def load_images():
    with rasterio.open(FOLDER / "pre.tif") as pre, rasterio.open(FOLDER / "post.tif") as post:
        before = pre.read([1, 2, 3])
        after = np.zeros_like(before)
        for i in range(3):
            reproject(rasterio.band(post, i + 1), after[i], src_transform=post.transform, src_crs=post.crs,
                      dst_transform=pre.transform, dst_crs=pre.crs, resampling=Resampling.bilinear)
        return [Image.fromarray(np.moveaxis(np.clip(x, 0, 255).astype("uint8"), 0, -1)) for x in (before, after)], pre.transform


def draw_geometry(draw, geometry, transform, left, top, color):
    def coordinates(points):
        return [((x - transform.c) / transform.a - left, (y - transform.f) / transform.e - top)
                for x, y in points]
    if geometry.geom_type in ("Polygon", "MultiPolygon"):
        polygons = [geometry] if geometry.geom_type == "Polygon" else geometry.geoms
        for polygon in polygons:
            draw.line(coordinates(polygon.exterior.coords), fill=color, width=3)
            for ring in polygon.interiors:
                draw.line(coordinates(ring.coords), fill=color, width=2)
    elif geometry.geom_type in ("LineString", "MultiLineString"):
        lines = [geometry] if geometry.geom_type == "LineString" else geometry.geoms
        for line in lines:
            draw.line(coordinates(line.coords), fill=color, width=3)


def main():
    global FOLDER
    parser = argparse.ArgumentParser()
    parser.add_argument("--tile", choices=("01_0_17_12", "02_2_20_57"), default="01_0_17_12")
    FOLDER = ROOT / "annotation_workspace/louisiana-east-review-v1" / parser.parse_args().tile
    out = FOLDER / "review_contacts"
    out.mkdir(exist_ok=True)
    if any(out.iterdir()):
        raise FileExistsError("Review contact directory already contains evidence")
    images, transform = load_images()
    features = []
    for kind in ("buildings", "roads"):
        data = json.loads((FOLDER / f"working_{kind}.geojson").read_text(encoding="utf-8"))
        features.extend((kind, feature) for feature in data["features"])
    index = []
    for start in range(0, len(features), 4):
        page = Image.new("RGB", (SIDE * 2, (SIDE + 30) * 4), "white")
        pen = ImageDraw.Draw(page)
        for row, (kind, feature) in enumerate(features[start:start + 4]):
            geometry = shape(feature["geometry"])
            center = geometry.centroid
            col = (center.x - transform.c) / transform.a
            line = (center.y - transform.f) / transform.e
            left, top = round(col) - HALF, round(line) - HALF
            label = f"{start + row + 1:03d} {kind} {feature['properties']['id']}"
            index.append({"number": start + row + 1, "kind": kind, "id": feature["properties"]["id"],
                          "page": f"page_{start // 4 + 1:02d}.png"})
            pen.text((5, row * (SIDE + 30) + 5), label, fill="black")
            for column, original in enumerate(images):
                crop = original.crop((left, top, left + SIDE, top + SIDE))
                draw_geometry(ImageDraw.Draw(crop), geometry, transform, left, top, "#ff2525")
                page.paste(crop, (column * SIDE, row * (SIDE + 30) + 30))
            pen.text((SIDE - 50, row * (SIDE + 30) + 5), "PRE", fill="black")
            pen.text((SIDE * 2 - 55, row * (SIDE + 30) + 5), "POST", fill="black")
        page.save(out / f"page_{start // 4 + 1:02d}.png")
    (out / "index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    print(f"{len(features)} objects, {(len(features) + 3) // 4} pages: {out}")


if __name__ == "__main__":
    main()
