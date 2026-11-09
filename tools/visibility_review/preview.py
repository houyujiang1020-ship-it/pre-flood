"""Display-only RGB previews and labels in each image's native geographic grid."""
import json
import logging
import threading
from pathlib import Path
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.warp import transform_geom
from PIL import Image
from .manifest import digest, read_json
from .review_store import atomic_json

STRATEGY = 'rgb-clip-0-255-bilinear-native-aspect-1024-overlay-v1'
LAYERS = ('building', 'road', 'flooded_building', 'flooded_road')


class Previews:
    def __init__(self, manifest, directory):
        self.manifest, self.directory = manifest, Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()

    def get(self, sid, slot):
        sample = self.manifest.samples[sid]
        item = sample['images'][slot]
        if not item:
            return {'available': False, 'message': slot.upper() + ' unavailable'}
        with self.lock:
            try:
                source = self.manifest.resolve(item['path'])
                label = Path(sample['label'])
                stat = source.stat()
                stamp = {'strategy': STRATEGY, 'source': str(source), 'size': stat.st_size,
                         'mtime_ns': stat.st_mtime_ns, 'manifest_sha256': self.manifest.sha256,
                         'expected_sha256': item.get('sha256'),
                         'label_sha256': digest(label) if label.is_file() else None}
                folder = self.directory / sid / slot
                meta = folder / 'metadata.json'
                if meta.exists():
                    cached = read_json(meta)
                    if cached['stamp'] == stamp and all((folder / name).is_file() for name in cached['files']):
                        return cached
                folder.mkdir(parents=True, exist_ok=True)
                with rasterio.open(source) as src:
                    scale = min(1.0, 1024 / max(src.width, src.height))
                    w, h = max(1, round(src.width * scale)), max(1, round(src.height * scale))
                    rgb = src.read([1, 2, 3], out_shape=(3, h, w), resampling=Resampling.bilinear)
                    rgb = np.moveaxis(np.clip(rgb, 0, 255).astype('uint8'), 0, 2)
                    Image.fromarray(rgb).save(folder / 'rgb.png')
                    grid = src.transform * src.transform.scale(src.width / w, src.height / h)
                    result = {'available': True, 'stamp': stamp, 'width': src.width, 'height': src.height,
                              'preview_width': w, 'preview_height': h, 'crs': str(src.crs),
                              'transform': list(src.transform)[:6], 'files': ['rgb.png'],
                              'filename': source.name, 'source': str(source), 'metrics': item,
                              'overlay_error': None}
                    try:
                        # SpaceNet8 GeoJSON is WGS84; transform independently onto each PRE/POST grid.
                        doc = read_json(label)
                        label_crs = doc.get('crs', {}).get('properties', {}).get('name', 'EPSG:4326')
                        shapes = {k: [] for k in LAYERS}
                        for feature in doc['features']:
                            prop, geom = feature.get('properties') or {}, feature.get('geometry')
                            building = prop.get('building') not in (None, 'no', '')
                            road = prop.get('highway') not in (None, '')
                            if not geom or not (building or road):
                                continue
                            kind = 'building' if building else 'road'
                            projected = transform_geom(label_crs, src.crs, geom)
                            shapes[kind].append((projected, 1))
                            if prop.get('flooded') in ['yes', 1, True]:
                                shapes['flooded_' + kind].append((projected, 1))
                        colors = {'building': (32, 220, 230), 'road': (255, 208, 65),
                                  'flooded_building': (255, 65, 128), 'flooded_road': (255, 90, 30)}
                        result['label_feature_counts'] = {k: len(v) for k, v in shapes.items()}
                        for kind in LAYERS:
                            mask = rasterize(shapes[kind], out_shape=(h, w), transform=grid,
                                             all_touched=True, dtype='uint8') if shapes[kind] else np.zeros((h, w), dtype='uint8')
                            rgba = np.zeros((h, w, 4), dtype='uint8')
                            rgba[mask > 0] = (*colors[kind], 150)
                            Image.fromarray(rgba).save(folder / (kind + '.png'))
                            result['files'].append(kind + '.png')
                    except Exception as exc:
                        result['overlay_error'] = str(exc)
                        logging.exception('Overlay failed for %s %s', sid, slot)
                atomic_json(meta, result | {'stamp': stamp})
                return result | {'stamp': stamp}
            except Exception as exc:
                logging.exception('Sample Load Error %s %s', sid, slot)
                return {'available': True, 'error': 'Sample Load Error: ' + str(exc), 'source': item['path']}

    def warm(self):
        errors = []
        for sid, sample in self.manifest.samples.items():
            for slot, item in sample['images'].items():
                if item:
                    result = self.get(sid, slot)
                    if result.get('error') or result.get('overlay_error'):
                        errors.append({'sample_id': sid, 'slot': slot, 'error': result.get('error') or result.get('overlay_error')})
        atomic_json(self.directory / 'cache_report.json', {'strategy': STRATEGY, 'errors': errors,
                                                          'total_samples': len(self.manifest.samples)})
        return errors
