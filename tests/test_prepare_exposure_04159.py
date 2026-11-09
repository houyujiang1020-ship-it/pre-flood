import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from prepare_exposure_04159 import prepare


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    for name, size, origin in (("pre.tif", 4, 7.0), ("post.tif", 2, 7.0)):
        with rasterio.open(source / name, "w", driver="GTiff", width=size, height=size,
                           count=3, dtype="uint8", crs="EPSG:4326",
                           transform=from_origin(origin, 51.0, 0.01 / size, 0.01 / size)) as dst:
            dst.write(np.full((3, size, size), 73, dtype=np.uint8))
    (source / "manifest.json").write_text(json.dumps({"inputs": [
        {"role": "pre_image", "path": "pre.tif", "sha256": _digest(source / "pre.tif")},
        {"role": "post_image", "path": "post.tif", "sha256": _digest(source / "post.tif")}
    ]}), encoding="utf-8")
    return source


def test_aligns_post_to_sourced_pre_grid_without_modifying_originals(tmp_path):
    source = _source(tmp_path)
    hashes = [_digest(source / name) for name in ("pre.tif", "post.tif")]
    result = prepare(source, tmp_path / "derived")
    with rasterio.open(result["pre"]["derived"]) as pre, rasterio.open(result["post"]["derived"]) as post:
        assert (pre.crs, pre.transform, pre.width, pre.height) == (post.crs, post.transform, post.width, post.height)
        assert post.read().shape == (3, 4, 4)
    assert hashes == [_digest(source / name) for name in ("pre.tif", "post.tif")]
    assert prepare(source, tmp_path / "derived")["post"]["derived_sha256"] == result["post"]["derived_sha256"]


def test_rejects_tampered_derived_image(tmp_path):
    source = _source(tmp_path)
    result = prepare(source, tmp_path / "derived")
    with Path(result["post"]["derived"]).open("ab") as stream:
        stream.write(b"tampered")
    with pytest.raises(ValueError, match="changed"):
        prepare(source, tmp_path / "derived")
