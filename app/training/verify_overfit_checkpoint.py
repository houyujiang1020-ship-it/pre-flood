"""Reload diagnostic GroupNorm checkpoints and verify probability/batch invariance."""
import importlib.util
from pathlib import Path
import numpy as np
import torch
from diagnose_overfit import ROOT, replace_batchnorm, write_json


def main():
    torch.set_num_threads(2)
    # Match the training run's backend algorithm selection when replaying it.
    torch.backends.cudnn.benchmark=False
    torch.backends.cudnn.deterministic=True
    base=ROOT/'experiments/diagnostics/overfit'
    samples=torch.load(base/'fixed-20260830-v1/fixed_patches.pt',weights_only=True)
    source=ROOT/'upstream/SpaceNet8/baseline/models/other/siamunetdif.py'
    spec=importlib.util.spec_from_file_location('verify_diagnostic',source)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    results=[]
    for n in (2,4,8):
        out=base/f'groupnorm-20260830-v1/patches-{n}'
        model=module.SiamUnet_diff(num_classes=4,num_channels=3)
        replace_batchnorm(model)
        model.load_state_dict(torch.load(out/'best_model.pth',weights_only=True)['state_dict'])
        model.cuda().eval()
        pre,post=[torch.stack([s[i] for s in samples[:n]]).cuda() for i in (0,1)]
        with torch.no_grad():
            batch=model(pre,post).sigmoid().cpu()
            single=torch.cat([model(pre[i:i+1],post[i:i+1]).sigmoid().cpu() for i in range(n)])
        archived=torch.from_numpy(np.load(out/'probabilities_gt_valid.npz')['probability'])
        reload_delta=float((batch-archived).abs().max())
        tf32_batch_delta=float((batch-single).abs().max())
        # Separate tensor-core rounding under different batch algorithms from
        # normalization dependence. No thresholds/checkpoint are changed.
        original_tf32=torch.backends.cudnn.allow_tf32
        torch.backends.cudnn.allow_tf32=False
        with torch.no_grad():
            fp32_batch=model(pre,post).sigmoid().cpu()
            fp32_single=torch.cat([model(pre[i:i+1],post[i:i+1]).sigmoid().cpu() for i in range(n)])
        torch.backends.cudnn.allow_tf32=original_tf32
        batch_delta=float((fp32_batch-fp32_single).abs().max())
        result=dict(patch_count=n,reload_max_probability_delta=reload_delta,
                    tf32_single_vs_batch_max_probability_delta=tf32_batch_delta,
                    fp32_single_vs_batch_max_probability_delta=batch_delta,
                    passed=reload_delta<1e-4 and batch_delta<1e-4)
        results.append(result)
    write_json(base/'groupnorm-20260830-v1/reload_verification.json',dict(results=results,passed=all(r['passed'] for r in results)))
    if not all(r['passed'] for r in results):
        raise RuntimeError(results)
    print(results)


if __name__=='__main__':
    main()
