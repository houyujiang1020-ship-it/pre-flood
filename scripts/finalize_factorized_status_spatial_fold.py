"""Verify independent reload results and seal the factorized-status spatial-fold decision."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'experiments/louisiana-x13-15-factorized-status-20260926'
RESULT = RUN / 'evaluation.json'
CONFIGS = {
    'independent': ROOT / 'config/training.louisiana-x13-15-independent-20260926.json',
    'factorized': ROOT / 'config/training.louisiana-x13-15-factorized-status-20260926.json',
}
MODELS = {
    'independent': ROOT / 'models/experiments/louisiana-x13-15-independent-20260926/best_model.pth',
    'factorized': ROOT / 'models/experiments/louisiana-x13-15-factorized-status-20260926/best_model.pth',
}
RELOADS = {name: RUN / f'{name}-reload-evaluation.json' for name in CONFIGS}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if RESULT.exists():
        raise FileExistsError('Evaluation is already finalized: ' + str(RESULT))
    configs = {name: json.loads(path.read_text(encoding='utf-8')) for name, path in CONFIGS.items()}
    if configs['independent']['splits'] != configs['factorized']['splits']:
        raise RuntimeError('Paired splits differ')
    train_ids = {(r['area'], r['label']) for r in configs['independent']['splits']['train']}
    holdout_ids = {(r['area'], r['label']) for r in configs['independent']['splits']['validation']}
    if train_ids & holdout_ids:
        raise RuntimeError('Spatial holdout leakage')
    values = {}
    expected_activation = {'independent': 'sigmoid', 'factorized': 'factorized_object_status'}
    for name in CONFIGS:
        if not RELOADS[name].is_file():
            raise FileNotFoundError('Missing independent reload evaluation: ' + str(RELOADS[name]))
        reload = json.loads(RELOADS[name].read_text(encoding='utf-8'))
        if reload['checkpoint_sha256'] != sha256(MODELS[name]):
            raise RuntimeError('Reload result checkpoint identity differs: ' + name)
        if reload['epoch'] != 14 or reload['prior_validation_reads'] != 0:
            raise RuntimeError('Expected fixed epoch 14/final-only evaluation: ' + name)
        if reload['tile_count'] != len(holdout_ids):
            raise RuntimeError('Reload result holdout size differs: ' + name)
        import torch
        checkpoint = torch.load(MODELS[name], map_location='cpu', weights_only=True)
        if checkpoint['output_activation'] != expected_activation[name]:
            raise RuntimeError('Unexpected output activation: ' + name)
        values[name] = {
            'checkpoint': str(MODELS[name].relative_to(ROOT)),
            'checkpoint_sha256': reload['checkpoint_sha256'],
            'loss_type': checkpoint['loss_type'], 'output_activation': checkpoint['output_activation'],
            'epoch': reload['epoch'], 'class_iou': reload['class_iou'],
            'class_f1': reload['class_f1'], 'class_precision': reload['class_precision'],
            'class_recall': reload['class_recall'],
            'macro_iou': sum(reload['class_iou'].values()) / 4,
            'status_overlap_pixels': reload['status_overlap_pixels'],
            'tile_count': reload['tile_count'], 'prior_validation_reads': 0,
            'reload_evaluation': str(RELOADS[name].relative_to(ROOT)),
            'reload_evaluation_sha256': sha256(RELOADS[name]),
        }
    deltas = {key: values['factorized']['class_iou'][key] - values['independent']['class_iou'][key]
              for key in values['independent']['class_iou']}
    macro_delta = values['factorized']['macro_iou'] - values['independent']['macro_iou']
    flooded = (deltas['flooded_building'], deltas['flooded_road'])
    promoted = (macro_delta >= .010 and min(flooded) >= -.005 and max(flooded) >= .010 and
                min(deltas.values()) >= -.010 and
                values['factorized']['status_overlap_pixels'] == {'building': 0, 'road': 0})
    result = {
        'schema_version': 1, 'status': 'completed', 'protocol_verified': True,
        'leakage_free': True, 'validation_schedule': 'final_only',
        'spatial_holdout_tiles': len(holdout_ids), 'models': values,
        'class_iou_delta': deltas, 'macro_iou_delta': macro_delta,
        'promotion_rule': ('macro +0.010; both flooded classes >= -0.005; one flooded class >= +0.010; '
                           'every class >= -0.010; candidate status overlap zero'),
        'promotion': 'accepted' if promoted else 'rejected',
        'test_used': False, 'development_spatial_holdout_only': True, 'production_ready': False,
    }
    RESULT.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
