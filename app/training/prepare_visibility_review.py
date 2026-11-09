"""Build a review queue for Germany post-event visibility without changing supervision."""
import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def inspect(path):
    with rasterio.open(path) as source:
        data = source.read([1, 2, 3], out_shape=(3, 128, 128)).astype('float32')
        valid = source.dataset_mask(out_shape=(128, 128)) > 0
    rgb = np.moveaxis(np.clip(data, 0, 255).astype('uint8'), 0, 2)
    gray = rgb.mean(2)
    visible = gray[valid]
    gradient = (np.abs(np.diff(gray, axis=0)).mean() + np.abs(np.diff(gray, axis=1)).mean()) / 2
    near_white = ((rgb.min(2) > 205) & valid).sum() / max(1, valid.sum())
    channel_spread = (rgb.max(2).astype('float32') - rgb.min(2))[valid].mean() if valid.any() else 0
    score = float(near_white * 0.65 + max(0, 8-gradient)/8 * 0.25 + max(0, 12-channel_spread)/12 * 0.10)
    return {'valid_fraction': float(valid.mean()), 'mean_brightness': float(visible.mean()),
            'near_white_fraction': float(near_white), 'mean_channel_spread': float(channel_spread),
            'mean_gradient': float(gradient), 'review_priority_score': score}, rgb


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding='utf-8'))
    entries, previews = [], {}
    for split in ('train', 'validation'):
        for item in config['splits'][split]:
            area = ROOT / config['data_root'] / item['area']
            mapping = area / f"{item['area']}_label_image_mapping.csv"
            rows = {r['label']: r for r in csv.DictReader(mapping.open(encoding='utf-8-sig', newline=''))}
            row = rows[item['label']]
            pre_path = area / 'PRE-event' / row['pre-event image']
            pre_metrics, pre_preview = inspect(pre_path)
            post_paths = []
            metrics = []
            for column in ('post-event image 1', 'post-event image 2'):
                filename = row.get(column, '').strip()
                if not filename:
                    continue
                path = area / 'POST-event' / filename
                values, preview = inspect(path)
                values.update({'column': column, 'path': str(path.relative_to(ROOT)), 'sha256': digest(path)})
                post_paths.append(path)
                metrics.append(values)
                previews[(split, item['label'], column)] = preview
            entries.append({'split': split, 'area': item['area'], 'label': item['label'],
                            'pre': {'path': str(pre_path.relative_to(ROOT)), 'sha256': digest(pre_path),
                                    **{k: v for k, v in pre_metrics.items() if k != 'review_priority_score'}},
                            'post_candidates': metrics, 'selected_by_current_pipeline': 'post-event image 1',
                            'review_status': 'pending', 'reviewer': None, 'reviewed_at': None,
                            'decision': None, 'reason': None})
    ranked = sorted(entries, key=lambda e: max(x['review_priority_score'] for x in e['post_candidates']), reverse=True)
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output/'visibility_manifest.json').write_text(json.dumps({
        'schema_version': 1, 'created_at': datetime.now(timezone.utc).isoformat(),
        'scope': 'Germany train/validation only', 'automatic_exclusions': 0,
        'warning': 'Scores only prioritize human review; they are not calibrated cloud masks or training decisions.',
        'entries': entries}, ensure_ascii=False, indent=2), encoding='utf-8')
    top = ranked[:min(20, len(ranked))]
    sheet = Image.new('RGB', (650, len(top)*150), 'white')
    draw = ImageDraw.Draw(sheet)
    for y, entry in enumerate(top):
        draw.text((2, y*150+2), f"{entry['split']} {entry['label']}", fill='black')
        pre_path = ROOT / entry['pre']['path']
        _, pre_preview = inspect(pre_path)
        sheet.paste(Image.fromarray(pre_preview).resize((128,128)), (250, y*150))
        draw.text((250, y*150+130), 'pre', fill='black')
        for i, candidate in enumerate(entry['post_candidates'][:2]):
            image = Image.fromarray(previews[(entry['split'], entry['label'], candidate['column'])]).resize((128,128))
            sheet.paste(image, (380+i*130, y*150))
            draw.text((380+i*130, y*150+130), f'post{i+1}', fill='black')
            draw.text((2, y*150+25+i*22), f"post{i+1} priority={candidate['review_priority_score']:.3f}", fill='black')
    sheet.save(args.output/'review_queue_top20.png')
    print(json.dumps({'entries': len(entries), 'with_post2': sum(len(e['post_candidates'])>1 for e in entries),
                      'automatic_exclusions': 0, 'output': str(args.output)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
