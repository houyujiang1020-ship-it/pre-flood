"""Paired causal test of BN statistics with identical checkpoint and input tensors."""
import argparse
import importlib.util
from pathlib import Path
import torch
from diagnose_overfit import ROOT, metrics, write_json, preview
from train_full import masked_loss


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--run', type=Path, required=True)
    args=p.parse_args()
    torch.set_num_threads(2)
    source=ROOT/'upstream/SpaceNet8/baseline/models/other/siamunetdif.py'
    spec=importlib.util.spec_from_file_location('official_bn_diagnostic',source)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    samples=torch.load(args.run/'fixed_patches.pt',weights_only=True)
    results=[]
    for n in (2,4,8):
        checkpoint=args.run/f'patches-{n}'/'best_model.pth'
        if not checkpoint.is_file():
            continue
        model=module.SiamUnet_diff(num_classes=4,num_channels=3).cuda()
        payload=torch.load(checkpoint,weights_only=True)
        model.load_state_dict(payload['state_dict'])
        for layer in model.modules():
            if isinstance(layer,torch.nn.Dropout2d):
                layer.p=0
        inputs=[torch.stack([s[i] for s in samples[:n]]).cuda() for i in range(4)]
        pre,post,truth,valid=inputs
        model.eval()
        with torch.no_grad():
            logits=model(pre,post)
            running=metrics(logits.sigmoid(),truth,valid)
            running_loss=float(masked_loss(logits,truth,valid))
        # Encoder BN is reused sequentially on pre and post in the upstream model.
        # In train mode it normalizes each separately; eval uses one mixed EMA.
        bns=[(name,l) for name,l in model.named_modules() if isinstance(l,torch.nn.BatchNorm2d)]
        modes={}
        for mode in ('encoder_only','all_batchnorm'):
            model.load_state_dict(payload['state_dict'])
            model.eval()
            for name,layer in bns:
                layer.track_running_stats=False
                if mode=='all_batchnorm' or not name.endswith('d'):
                    layer.train()
            with torch.no_grad():
                logits=model(pre,post)
                prob=logits.sigmoid()
                modes[mode]=dict(loss=float(masked_loss(logits,truth,valid)),per_class=metrics(prob,truth,valid))
            for _,layer in bns:
                layer.track_running_stats=True
            if mode=='all_batchnorm':
                out=args.run/f'patches-{n}'/'batch-statistics-control'
                out.mkdir(exist_ok=False)
                preview(out,pre,post,truth,valid,prob)
        results.append(dict(n=n,checkpoint=str(checkpoint),checkpoint_step=payload['step'],
                            running_statistics=dict(loss=running_loss,per_class=running),controls=modes,
                            warning='Batch statistics control depends on input batch; not a deployable repair'))
    write_json(args.run/'normalization_control.json',dict(results=results,production_ready=False,
               intervention='Weights, input, labels, threshold held fixed. Only BN running/batch statistics change.'))
    print(args.run/'normalization_control.json')


if __name__=='__main__':
    main()
