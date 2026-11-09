"""Read-only normalization intervention on historical model, Germany only; no tuning."""
import hashlib
import importlib.util
import json
import random
from pathlib import Path
import torch
import train_full as training
from diagnose_overfit import ROOT, metrics, write_json


def main():
    torch.set_num_threads(2)
    config=json.loads((ROOT/'config/training.full-germany-tempered-20260830.json').read_text(encoding='utf-8'))
    training.DISK_CACHE=ROOT/config['cache_dir']
    splits=training.split_rows(config,ROOT)
    rng=random.Random(20260830)
    selected={name:rng.sample(splits[name],8) for name in ('train','validation')}
    output=ROOT/'experiments/diagnostics/reports/historical_bn_control.json'
    if output.exists():
        raise FileExistsError(output)
    source=ROOT/'upstream/SpaceNet8/baseline/models/other/siamunetdif.py'
    spec=importlib.util.spec_from_file_location('official_historical_bn',source)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    checkpoint=ROOT/'models/checkpoints/full-germany-tempered-20260830/best_model.pth'
    payload=torch.load(checkpoint,map_location='cpu',weights_only=True)
    model=module.SiamUnet_diff(num_classes=4,num_channels=3).cuda()
    reports=[]
    for split,records in selected.items():
        modes={}
        for mode in ('running','encoder_batch','all_batch'):
            probabilities, truths, masks=[],[],[]
            model.load_state_dict(payload['state_dict'])
            model.eval()
            for name,layer in model.named_modules():
                if isinstance(layer,torch.nn.BatchNorm2d):
                    layer.track_running_stats=False
                    if mode=='all_batch' or mode=='encoder_batch' and not name.endswith('d'):
                        layer.train()
            with torch.no_grad():
                for area,row in records:
                    pre,post,truth,valid=[t[None].cuda() for t in training.cached_pair(area,row,512)]
                    probabilities.append(model(pre,post).sigmoid().cpu())
                    truths.append(truth.cpu())
                    masks.append(valid.cpu())
            stats=metrics(torch.cat(probabilities),torch.cat(truths),torch.cat(masks))
            modes[mode]=dict(per_class=stats,macro_iou=sum(v['iou'] for v in stats.values() if v['iou'] is not None)/sum(v['iou'] is not None for v in stats.values()))
        reports.append(dict(split=split,records=[dict(area=a.name,label=r['label']) for a,r in records],modes=modes))
    write_json(output,dict(checkpoint=str(checkpoint),checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        seed=20260830,batch_size=1,image_size=512,threshold=.5,dropout_disabled=True,results=reports,
        warning='Small Germany-only causal diagnostic, not retraining or independent evaluation. Batch statistics depend on input and are not a production fix.',production_ready=False))
    print(output)


if __name__=='__main__':
    main()
