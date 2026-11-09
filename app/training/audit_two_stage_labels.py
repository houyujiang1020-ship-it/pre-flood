"""Audit two-stage labels derived from the frozen official four-channel pipeline."""
import json
from pathlib import Path

import train_full as training


def main():
    root = Path(__file__).resolve().parents[2]
    config_path = root / 'config/training.germany-reviewed-gn-sampler-20260912.json'
    config = json.loads(config_path.read_text(encoding='utf-8'))
    training.validate_frozen_dataset(config, root)
    training.DISK_CACHE = root / config['cache_dir']
    training._cached_pair.cache_clear()
    records = training.split_rows(config, root)
    result = {
        'status': 'passed',
        'source_pipeline': 'app/training/train_smoke.py:load_pair',
        'source_mapping': {
            '0': 'non_flooded_building', '1': 'flooded_building',
            '2': 'non_flooded_road', '3': 'flooded_road'},
        'derivation': {
            'stage1_building': 'channel0 OR channel1',
            'stage1_road': 'channel2 OR channel3',
            'stage2_building_target': 'channel1, supervised only within stage1_building GT union',
            'stage2_road_target': 'channel3, supervised only within stage1_road GT union'},
        'split_sha256': config['frozen_dataset_sha256'],
        'splits': {}, 'subset_violations': [],
        'blind_holdout_used': False, 'louisiana_used': False, 'production_ready': False}
    for split_name in ('train', 'validation'):
        totals = {'building_union_pixel_count': 0, 'road_union_pixel_count': 0,
                  'flooded_building_pixel_count': 0, 'flooded_road_pixel_count': 0}
        samples = []
        for area, row in records[split_name]:
            _, _, label, valid = training.cached_pair(area, row, int(config['image_size']))
            masks = (label > 0) & (valid.unsqueeze(0) > 0)
            building = masks[0] | masks[1]
            road = masks[2] | masks[3]
            bad_b = masks[1] & ~building
            bad_r = masks[3] & ~road
            if bad_b.any() or bad_r.any():
                result['subset_violations'].append({'split': split_name, 'label': row['label'],
                    'flooded_building_outside_union': int(bad_b.sum()),
                    'flooded_road_outside_union': int(bad_r.sum())})
            counts = [int(x.sum()) for x in (building, road, masks[1], masks[3])]
            for key, value in zip(totals, counts): totals[key] += value
            samples.append({'label': row['label'], 'has_building': bool(building.any()),
                'has_road': bool(road.any()), 'has_flooded_building': bool(masks[1].any()),
                'has_flooded_road': bool(masks[3].any())})
        totals['flooded_building_within_building_ratio'] = (totals['flooded_building_pixel_count'] / totals['building_union_pixel_count']) if totals['building_union_pixel_count'] else None
        totals['flooded_road_within_road_ratio'] = (totals['flooded_road_pixel_count'] / totals['road_union_pixel_count']) if totals['road_union_pixel_count'] else None
        result['splits'][split_name] = {'sample_count': len(samples), **totals, 'samples': samples}
    if result['subset_violations']:
        result['status'] = 'failed'
    out = root / 'experiments/two-stage/label-derivation-audit.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'splits'} | {
        'split_statistics': {k: {x:y for x,y in v.items() if x != 'samples'} for k,v in result['splits'].items()}}, indent=2))
    if result['status'] != 'passed': raise SystemExit(2)


if __name__ == '__main__': main()
