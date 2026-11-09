"""Align the sourced 0_41_59 post image to its pre image for the legacy entity exposure demo."""
import hashlib
import json
import shutil
from pathlib import Path

import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/acceptance/gate5-v1"
DEST = ROOT / "data/processed/exposure-0_41_59"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(source=SOURCE, dest=DEST):
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    originals = {row["role"]: row for row in manifest["inputs"] if row["role"] in ("pre_image", "post_image")}
    pre_source, post_source = (source / originals[name]["path"] for name in ("pre_image", "post_image"))
    for role, path in (("pre_image", pre_source), ("post_image", post_source)):
        if digest(path) != originals[role]["sha256"]:
            raise ValueError(f"Frozen Gate 5 {role} SHA-256 mismatch: {path}")
    dest.mkdir(parents=True, exist_ok=True)
    pre_target, post_target = dest / "pre.tif", dest / "post-aligned.tif"
    record_path = dest / "manifest.json"
    previous = json.loads(record_path.read_text(encoding="utf-8")) if record_path.exists() else None
    with rasterio.open(pre_source) as pre, rasterio.open(post_source) as post:
        if pre.crs is None or post.crs is None or pre.count != post.count or pre.count != 3:
            raise ValueError("Both sourced RGB images need real CRS and matching bands")
        if pre.transform.b != 0 or pre.transform.d != 0 or pre.transform.a <= 0 or pre.transform.e >= 0:
            raise ValueError("Pre image is not an unrotated north-up grid")
        if pre.crs != post.crs or rasterio.coords.disjoint_bounds(pre.bounds, post.bounds):
            raise ValueError("Original image extents or CRS do not overlap")
        profile = pre.profile.copy()
        profile.update(driver="GTiff", compress="deflate")
        if not pre_target.exists():
            shutil.copy2(pre_source, pre_target)
        elif digest(pre_target) != digest(pre_source):
            raise ValueError("Existing derived pre image differs from frozen source")
        if post_target.exists():
            if previous is None or previous["pre"]["source_sha256"] != digest(pre_source) or \
                    previous["post"]["source_sha256"] != digest(post_source) or \
                    previous["post"]["derived_sha256"] != digest(post_target):
                raise ValueError("Existing aligned post image lacks matching provenance or has changed")
        else:
            with rasterio.open(post_target, "w", **profile) as dst:
                for band in range(1, pre.count + 1):
                    reproject(source=rasterio.band(post, band), destination=rasterio.band(dst, band),
                              src_transform=post.transform, src_crs=post.crs,
                              dst_transform=pre.transform, dst_crs=pre.crs,
                              src_nodata=post.nodata, dst_nodata=pre.nodata,
                              resampling=Resampling.bilinear)
        with rasterio.open(post_target) as aligned:
            if aligned.crs != pre.crs or aligned.transform != pre.transform or aligned.width != pre.width or aligned.height != pre.height:
                raise ValueError("Derived post image grid differs from source pre image")
        result = {"schema_version": 1, "area": "SpaceNet8 Germany_Training_Public 0_41_59",
                  "purpose": "LIVE_AI entity exposure input; not a measured flood extent",
                  "pre": {"source": str(pre_source.resolve()), "source_sha256": digest(pre_source),
                          "derived": str(pre_target.resolve()), "derived_sha256": digest(pre_target),
                          "transformation": "bytewise copy"},
                  "post": {"source": str(post_source.resolve()), "source_sha256": digest(post_source),
                           "derived": str(post_target.resolve()), "derived_sha256": digest(post_target),
                           "transformation": "rasterio.warp.reproject, bilinear RGB, target=source pre CRS/transform/size"},
                  "crs": str(pre.crs), "transform": list(pre.transform)[:6],
                  "width": pre.width, "height": pre.height, "bounds": list(pre.bounds),
                  "source_manifest": str((source / "manifest.json").resolve())}
    record_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(prepare(), ensure_ascii=False, indent=2))
