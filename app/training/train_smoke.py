"""Research-only SpaceNet8 SiamUnet smoke training. NOT a production model."""
import argparse
import csv
import importlib.util
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.warp import reproject, transform_geom
import torch
from PIL import Image
from pyproj import Transformer
from shapely.geometry import shape, mapping
from shapely.ops import transform as geometry_transform


def buffered_road(geometry, target_crs):
    """Research-only 3m UTM buffer, matching pinned baseline/create_masks.py radius.

    No Shapely/pyproj use is permitted in the final AI service or MapGIS application.
    """
    line = shape(geometry)
    if line.is_empty or not line.is_valid or line.geom_type not in ('LineString', 'MultiLineString'):
        raise ValueError('Invalid road geometry')
    lon, lat = line.centroid.x, line.centroid.y
    if not (-180 <= lon <= 180 and -80 <= lat <= 84):
        raise ValueError('Road outside supported UTM region')
    zone = min(60, int((lon + 180) // 6) + 1)
    utm = (32600 if lat >= 0 else 32700) + zone
    forward = Transformer.from_crs('EPSG:4326', utm, always_xy=True).transform
    backward = Transformer.from_crs(utm, target_crs, always_xy=True).transform
    return mapping(geometry_transform(backward, geometry_transform(forward, line).buffer(3.0)))


def flooded_class(value):
    # Match pinned upstream baseline/data_prep/geojson_prep.py:geojson_to_shapefile.
    # Official SpaceNet8 null values map to non-flooded, not ignored supervision.
    return int(value in ['yes', 1, True])


def load_pair(area, row, size):
    with rasterio.open(area / 'PRE-event' / row['pre-event image']) as pre:
        before = pre.read([1, 2, 3], out_shape=(3, size, size), resampling=Resampling.bilinear)
        before_valid = pre.read_masks(1, out_shape=(size,size), resampling=Resampling.nearest) > 0
        grid = pre.transform * pre.transform.scale(pre.width / size, pre.height / size)
        crs = pre.crs
    after = np.zeros((3, size, size), dtype=np.float32)
    after_valid = np.zeros((size,size), dtype=np.uint8)
    with rasterio.open(area / 'POST-event' / row['post-event image 1']) as post:
        for band in range(3):
            reproject(rasterio.band(post, band + 1), after[band], src_transform=post.transform,
                      src_crs=post.crs, dst_transform=grid, dst_crs=crs, resampling=Resampling.bilinear)
        reproject(post.dataset_mask(),after_valid,src_transform=post.transform,src_crs=post.crs,
                  dst_transform=grid,dst_crs=crs,resampling=Resampling.nearest)
    features = json.loads((area / 'annotations' / row['label']).read_text(encoding='utf-8'))['features']
    shapes = [[] for _ in range(4)]
    for feature in features:
        prop = feature['properties']
        building = prop.get('building') not in (None, 'no', '')
        road = prop.get('highway') not in (None, '')
        if not building and not road:
            continue
        geom = buffered_road(feature['geometry'], crs) if road and not building else transform_geom('EPSG:4326', crs, feature['geometry'])
        index = (0 if building else 2) + flooded_class(prop.get('flooded'))
        shapes[index].append((geom, 1))
    labels = np.stack([rasterize(s, out_shape=(size, size), transform=grid, all_touched=False, dtype='uint8')
                       if s else np.zeros((size, size), dtype=np.uint8) for s in shapes])
    valid = (before_valid & (after_valid>0)).astype(np.float32)
    return (torch.from_numpy(before.astype(np.float32) / 255), torch.from_numpy(after / 255),
            torch.from_numpy(labels.astype(np.float32)), torch.from_numpy(valid))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--epochs', type=int, default=2)
    parser.add_argument('--size', type=int, default=128)
    parser.add_argument('--device', choices=['auto', 'cpu', 'cuda'], default='auto')
    args = parser.parse_args()
    if args.epochs < 1 or args.size < 32 or args.size % 16:
        parser.error('Positive epochs and size >=32 divisible by 16 required')
    root = Path(__file__).resolve().parents[2]
    source = root / 'upstream/SpaceNet8/baseline/models/other/siamunetdif.py'
    spec = importlib.util.spec_from_file_location('official_siamunet', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    torch.manual_seed(42)
    device = 'cuda' if args.device == 'auto' and torch.cuda.is_available() else ('cpu' if args.device == 'auto' else args.device)
    area = root / 'data/spacenet8/sample/Germany_Training_Public'
    with (area / 'Germany_Training_Public_label_image_mapping.csv').open(encoding='utf-8-sig', newline='') as mapping:
        rows = list(csv.DictReader(mapping))
    rows = [r for r in rows if (area / 'annotations' / r['label']).exists()
            and (area / 'PRE-event' / r['pre-event image']).exists()
            and (area / 'POST-event' / r['post-event image 1']).exists()]
    if len(rows) < 2:
        raise RuntimeError('Download at least 2 complete official pairs first')
    samples = [load_pair(area, row, args.size) for row in rows]
    model = module.SiamUnet_diff(num_classes=4, num_channels=3).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    criterion = torch.nn.BCEWithLogitsLoss(reduction='none')
    history = []
    out = root / 'models/checkpoints/spacenet8-smoke'
    out.mkdir(parents=True, exist_ok=True)
    for epoch in range(args.epochs):
        model.train()
        losses = []
        for before, after, labels, valid in samples[:-1]:
            before, after, labels, valid = [t.unsqueeze(0).to(device) for t in (before, after, labels, valid)]
            optimizer.zero_grad()
            logits = model(before, after)
            loss = (criterion(logits, labels) * valid.unsqueeze(1)).sum() / (valid.sum().clamp_min(1) * 4)
            if not torch.isfinite(loss):
                raise RuntimeError('Nonfinite training loss')
            loss.backward()
            optimizer.step()
            losses.append(loss.item())
        model.eval()
        with torch.no_grad():
            before, after, labels, valid = [t.unsqueeze(0).to(device) for t in samples[-1]]
            logits = model(before, after)
            val_loss = (criterion(logits, labels) * valid.unsqueeze(1)).sum() / (valid.sum().clamp_min(1) * 4)
            predicted = (logits.sigmoid() > 0.5) & (valid.unsqueeze(1) > 0)
            truth = (labels > 0) & (valid.unsqueeze(1) > 0)
            union = (predicted | truth).sum().item()
            iou = (predicted & truth).sum().item() / union if union else None
        record = {'epoch': epoch + 1, 'train_loss': float(np.mean(losses)), 'validation_loss': val_loss.item(), 'micro_iou': iou}
        history.append(record)
        print(json.dumps(record), flush=True)
    checkpoint = {'state_dict': model.cpu().state_dict(), 'architecture': 'SiamUnet_diff', 'num_classes': 4,
                  'smoke_only': True, 'production_ready': False, 'source_commit': '30ca30c2530c6a234d040f60a99a7366ff62d756',
                  'classes': ['non_flooded_building', 'flooded_building', 'non_flooded_road', 'flooded_road']}
    torch.save(checkpoint, out / 'smoke_model.pth')
    # Verify a serialized checkpoint can be reloaded for inference.
    restored = module.SiamUnet_diff(num_classes=4, num_channels=3)
    restored.load_state_dict(torch.load(out / 'smoke_model.pth', weights_only=True)['state_dict'])
    restored.eval()
    with torch.no_grad():
        prediction = restored(samples[-1][0].unsqueeze(0), samples[-1][1].unsqueeze(0)).sigmoid().numpy()
    np.save(out / 'validation_prediction.npy', prediction)
    # Research-only aligned pixel fixtures for API checks, not georeferenced GIS layers.
    for name, tensor in [('pre', samples[-1][0]), ('post', samples[-1][1])]:
        rgb = (tensor.numpy().transpose(1, 2, 0) * 255).clip(0, 255).astype('uint8')
        Image.fromarray(rgb).save(out / f'validation_{name}.png')
    report = {'device': device, 'torch': torch.__version__, 'train_labels': [r['label'] for r in rows[:-1]],
              'validation_labels': [rows[-1]['label']], 'size': args.size, 'history': history,
              'warning': 'Research smoke only. 3m UTM road buffers; reduced-resolution training is not production accuracy.'}
    (out / 'training_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('Saved and reloaded official-architecture smoke checkpoint.', flush=True)


if __name__ == '__main__':
    main()
