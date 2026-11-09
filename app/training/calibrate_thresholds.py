"""Select thresholds on validation only; never select them using the test results."""
import argparse
import hashlib
import json
from pathlib import Path
import torch
import train_full as training
from model_factory import build_siamunet


def select_thresholds(tp, fp, positives, candidates):
    if (positives <= 0).any():
        raise ValueError('Calibration requires positive validation labels in every class')
    ious = tp / (positives[:,None] + fp).clamp_min(1)
    indices = ious.argmax(1)
    return [candidates[int(i)] for i in indices]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args=parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Existing report will not be overwritten')
    root=Path(__file__).resolve().parents[2]
    config=json.loads(args.config.read_text(encoding='utf-8'))
    training.validate_frozen_dataset(config, root)
    splits=training.split_rows(config,root)
    training.DISK_CACHE=root/config['cache_dir']
    training._cached_pair.cache_clear()
    checkpoint=torch.load(args.checkpoint,map_location=config['device'],weights_only=True)
    source=root/'upstream/SpaceNet8/baseline/models/other/siamunetdif.py'
    model=build_siamunet(source, checkpoint.get('normalization', 'batchnorm'),
                         checkpoint.get('groupnorm_groups') or 8).to(config['device']).eval()
    model.load_state_dict(checkpoint['state_dict'])
    candidates=[i/100 for i in range(1,100)]
    tp=torch.zeros(4,len(candidates),dtype=torch.float64)
    fp=torch.zeros_like(tp); positives=torch.zeros(4,dtype=torch.float64)
    with torch.inference_mode():
        for area,row in splits['validation']:
            pre,post,truth,valid=[t.unsqueeze(0).to(config['device']) for t in training.cached_pair(area,row,config['image_size'])]
            probability=model(pre,post).sigmoid()
            expected=(truth>0)&(valid.unsqueeze(1)>0)
            positives += expected.sum((0,2,3)).cpu()
            for j,threshold in enumerate(candidates):
                prediction=(probability>threshold)&(valid.unsqueeze(1)>0)
                tp[:,j]+=(prediction&expected).sum((0,2,3)).cpu()
                fp[:,j]+=(prediction&~expected).sum((0,2,3)).cpu()
    thresholds=select_thresholds(tp,fp,positives,candidates)
    report={'checkpoint_sha256':hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
            'checkpoint_epoch':checkpoint['epoch'],'selection_split':'validation',
            'thresholds':dict(zip(training.CLASSES,thresholds)),
            'validation_tiles':len(splits['validation']), 'production_ready':False,
            'warning':'Thresholds fit on Germany validation only. This is not an independent accuracy estimate. Not deployed.'}
    print(json.dumps({'thresholds_frozen':report['thresholds']}),flush=True)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    frozen=args.output.with_suffix('.thresholds.json')
    with frozen.open('x',encoding='utf-8') as stream: json.dump(report,stream,indent=2)
    report['validation']=training.evaluate(model,splits['validation'],config['image_size'],config['device'],thresholds)
    report['test']=training.evaluate(model,splits['test'],config['image_size'],config['device'],thresholds) if splits['test'] else None
    with args.output.open('x',encoding='utf-8') as stream: json.dump(report,stream,indent=2)
    print(json.dumps(report),flush=True)


if __name__=='__main__':main()
