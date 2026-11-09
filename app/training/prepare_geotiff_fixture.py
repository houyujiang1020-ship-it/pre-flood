"""Isolated research fixture preparation, NOT a final MapGIS alignment implementation."""
import csv
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--label',default='0_36_68.geojson')
    args=parser.parse_args()
    if Path(args.label).name != args.label:
        raise ValueError('Label must be a filename')
    root = Path(__file__).resolve().parents[2]
    area = root / 'data/spacenet8/sample/Germany_Training_Public'
    with (area / 'Germany_Training_Public_label_image_mapping.csv').open(encoding='utf-8-sig', newline='') as f:
        row = next(r for r in csv.DictReader(f) if r['label'] == args.label)
    sources = [area / 'PRE-event' / row['pre-event image'], area / 'POST-event' / row['post-event image 1']]
    destination = root / ('data/processed/geotiff-test-'+Path(args.label).stem)
    destination.mkdir(parents=True, exist_ok=True)
    paths = [destination / 'pre.tif', destination / 'post.tif']
    if any(p.exists() for p in paths):
        raise FileExistsError('Fixture already exists; refusing to overwrite')
    size = 512
    with rasterio.open(sources[0]) as source:
        transform = source.transform * source.transform.scale(source.width / size, source.height / size)
        crs = source.crs
        before = source.read([1, 2, 3], out_shape=(3, size, size), resampling=Resampling.bilinear)
    after = np.zeros_like(before)
    with rasterio.open(sources[1]) as source:
        for band in range(3):
            reproject(rasterio.band(source, band + 1), after[band], src_transform=source.transform,
                      src_crs=source.crs, dst_transform=transform, dst_crs=crs, resampling=Resampling.bilinear)
    for path, values in zip(paths, [before, after]):
        with rasterio.open(path, 'w', driver='GTiff', width=size, height=size, count=3,
                           dtype='uint8', crs=crs, transform=transform) as output:
            output.write(values.clip(0, 255).astype('uint8'))
    with rasterio.open(paths[0]) as first, rasterio.open(paths[1]) as second:
        assert first.crs == second.crs and first.transform == second.transform
        assert first.bounds == second.bounds and first.shape == second.shape
        report = {'crs': str(first.crs), 'transform': list(first.transform), 'bounds': list(first.bounds),
                  'width': size, 'height': size, 'label': row['label'],
                  'sources': [{ 'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in sources],
                  'outputs': [str(p) for p in paths],
                  'scope': 'Research-only reprojection fixture for MapGIS loading tests; NOT evidence of MapGIS alignment or model accuracy.'}
    (destination / 'provenance.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True))


if __name__ == '__main__':
    main()
