"""Fixed-data memorization diagnostic, never a production/generalization experiment."""
import argparse
import hashlib
import importlib.util
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageDraw
import train_full as training

ROOT = Path(__file__).resolve().parents[2]


def replace_batchnorm(module):
    """Controlled diagnostic variant; leave pinned upstream and old checkpoints untouched."""
    for name, layer in list(module.named_children()):
        if isinstance(layer, torch.nn.BatchNorm2d):
            setattr(module, name, torch.nn.GroupNorm(8, layer.num_features))
        else:
            replace_batchnorm(layer)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')


def metrics(prob, truth, valid, threshold=.5):
    mask = valid[:, None] > 0
    pred, gt = (prob > threshold) & mask, (truth > 0) & mask
    result = {}
    for i, name in enumerate(training.CLASSES):
        p, t, m = pred[:, i], gt[:, i], mask[:, 0]
        tp, fp, fn, tn = [int(x.sum()) for x in (p & t, p & ~t, ~p & t, ~p & ~t & m)]
        result[name] = dict(tp=tp, fp=fp, fn=fn, tn=tn,
                            iou=tp / (tp+fp+fn) if tp+fp+fn else None,
                            precision=tp/(tp+fp) if tp+fp else None,
                            recall=tp/(tp+fn) if tp+fn else None,
                            f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None)
    return result


def select_patches(config, out, size):
    training.DISK_CACHE = ROOT / config['cache_dir']
    records = training.split_rows(config, ROOT)['train']
    candidates = []
    # Grid crops retain the existing 512 preprocessing without further resizing.
    for area, row in records:
        tensors = training.cached_pair(area, row, config['image_size'])
        for y in range(0, config['image_size']-size+1, size):
            for x in range(0, config['image_size']-size+1, size):
                valid = tensors[3][y:y+size, x:x+size]
                count = (tensors[2][:, y:y+size, x:x+size]*valid).sum((1, 2))
                if min(count).item() >= 16 and valid.mean() > .95:
                    candidates.append((float(count.min()), area, row, x, y, count.tolist()))
    candidates.sort(key=lambda c: (-c[0], c[2]['label'], c[4], c[3]))
    chosen, seen = [], set()
    for c in candidates:
        if c[2]['label'] not in seen:
            chosen.append(c)
            seen.add(c[2]['label'])
        if len(chosen) == 8:
            break
    if len(chosen) != 8:
        raise ValueError(f'Only {len(chosen)} distinct source tiles contain four-class positive crops')
    samples, manifest = [], []
    for score, area, row, x, y, count in chosen:
        tensors = training.cached_pair(area, row, config['image_size'])
        samples.append(tuple(t[..., y:y+size, x:x+size].clone() for t in tensors))
        files = [area/'annotations'/row['label'], area/'PRE-event'/row['pre-event image'],
                 area/'POST-event'/row['post-event image 1']]
        manifest.append(dict(area=area.name, label=row['label'], crop_xywh=[x,y,size,size],
                             class_positive_pixels=dict(zip(training.CLASSES, count)),
                             source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}))
    torch.save(samples, out/'fixed_patches.pt')
    write_json(out/'patch_manifest.json', manifest)
    return samples


def preview(out, pre, post, truth, valid, prob):
    colors = np.array([[40,220,90],[255,40,40],[50,160,255],[255,190,0]], dtype=np.uint8)
    size = pre.shape[-1]
    for sample in range(len(pre)):
        first = (pre[sample].cpu().numpy().transpose(1,2,0)*255).clip(0,255).astype('uint8')
        second = (post[sample].cpu().numpy().transpose(1,2,0)*255).clip(0,255).astype('uint8')
        panel = Image.new('RGB', (size*5, (size+20)*4), 'white')
        draw = ImageDraw.Draw(panel)
        for c, name in enumerate(training.CLASSES):
            gt = truth[sample,c].cpu().numpy()>0
            pp = prob[sample,c].cpu().numpy()
            expected, prediction = second.copy(), second.copy()
            expected[gt] = colors[c]
            prediction[pp>.5] = colors[c]
            heat = np.zeros_like(second)
            heat[:,:,0] = (pp*255).astype('uint8')
            heat[:,:,2] = ((1-pp)*255).astype('uint8')
            for col, (label, img) in enumerate(zip(['pre','post', 'GT '+name, 'pred >0.5','p: blue=0 red=1'], [first,second,expected,prediction,heat])):
                panel.paste(Image.fromarray(img), (col*size, c*(size+20)+20))
                draw.text((col*size, c*(size+20)), label, fill='black')
        panel.save(out/f'sample-{sample:02d}.png')
    np.savez_compressed(out/'probabilities_gt_valid.npz', probability=prob.cpu().numpy(),
                        gt=truth.cpu().numpy(), valid=valid.cpu().numpy())


def run(samples, n, out, args):
    out.mkdir()
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    source = ROOT/'upstream/SpaceNet8/baseline/models/other/siamunetdif.py'
    spec = importlib.util.spec_from_file_location('diagnostic_siamunet', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    model = module.SiamUnet_diff(num_classes=4, num_channels=3).cuda()
    if args.normalization == 'groupnorm':
        replace_batchnorm(model)
        model.cuda()
    # Remove stochastic regularization only in this memorization control.
    for layer in model.modules():
        if isinstance(layer, torch.nn.Dropout2d):
            layer.p = 0
    pre, post, truth, valid = [torch.stack([sample[i] for sample in samples[:n]]).cuda() for i in range(4)]
    positives = (truth*valid[:,None]).sum((0,2,3))
    weight = training.positive_weights(positives, float(valid.sum()), .5, 8)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.learning_rate)
    history, consecutive, best = [], 0, -1
    started = time.monotonic()
    for step in range(args.steps+1):
        if step:
            model.train()
            optimizer.zero_grad(set_to_none=True)
            loss = training.masked_loss(model(pre,post), truth,valid,weight,.5)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(),10)
            optimizer.step()
        if step % 25 == 0 or step == args.steps:
            model.eval()
            with torch.no_grad():
                logits = model(pre,post)
                probability = logits.sigmoid()
                eval_loss = float(training.masked_loss(logits,truth,valid,weight,.5))
                stats = metrics(probability,truth,valid)
            mean = sum(v['iou'] for v in stats.values())/4
            entry = dict(step=step, training_loss=float(loss) if step else None, eval_loss=eval_loss,
                         macro_iou=mean, per_class=stats, elapsed_seconds=time.monotonic()-started)
            history.append(entry)
            write_json(out/'history.json',history)
            print(json.dumps(dict(n=n,step=step,loss=eval_loss,macro_iou=mean,
                                  class_iou=[v['iou'] for v in stats.values()])),flush=True)
            if mean > best:
                best = mean
                training.save_checkpoint(dict(state_dict=model.state_dict(), architecture='SiamUnet_diff',
                                               classes=training.CLASSES, smoke_only=True, production_ready=False,
                                               step=step, diagnostic_only=True, normalization=args.normalization,
                                               dropout_p=0, seed=args.seed),out/'best_model.pth')
            consecutive = consecutive+1 if min(v['iou'] for v in stats.values()) >= .90 else 0
            if consecutive >= 3:
                break
    model.load_state_dict(torch.load(out/'best_model.pth',weights_only=True)['state_dict'])
    model.eval()
    with torch.no_grad():
        probability = model(pre,post).sigmoid()
    final = metrics(probability,truth,valid)
    # Same weights and same pixels, only BN running-vs-batch statistics change.
    bn_layers = [layer for layer in model.modules() if isinstance(layer,torch.nn.BatchNorm2d)]
    for layer in bn_layers:
        layer.train()
        layer.track_running_stats=False
    with torch.no_grad():
        batch_probability = model(pre,post).sigmoid()
    batch_metrics = metrics(batch_probability,truth,valid)
    for layer in bn_layers:
        layer.eval()
        layer.track_running_stats=True
    preview(out,pre,post,truth,valid,probability)
    write_json(out/'pr_curve.json', {str(t):metrics(probability,truth,valid,t) for t in [.05,.1,.2,.3,.4,.5,.6,.7,.8,.9,.95]})
    report = dict(patch_count=n, batch_size=n, seed=args.seed, augmentation=False, dropout=0,
                  normalization=args.normalization, batch_statistics_metrics=batch_metrics,
                  fixed_data=True, source_preprocessing='existing cache512 then fixed 128 crop; no further resize',
                  positive_weights=weight.flatten().tolist(), threshold=.5, completed_steps=step,
                  training_metrics=final, macro_iou=sum(v['iou'] for v in final.values())/4,
                  memorization_pass=min(v['iou'] for v in final.values())>=.90,
                  criterion='each class training IoU >=0.90 (diagnostic only, not production threshold)',
                  checkpoint_sha256=hashlib.sha256((out/'best_model.pth').read_bytes()).hexdigest(),
                  elapsed_seconds=time.monotonic()-started, production_ready=False)
    write_json(out/'report.json',report)
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--config', type=Path, default=ROOT/'config/training.full-germany-tempered-20260830.json')
    parser.add_argument('--steps',type=int,default=2000)
    parser.add_argument('--seed',type=int,default=20260830)
    parser.add_argument('--learning-rate',type=float,default=.001)
    parser.add_argument('--normalization',choices=['batchnorm','groupnorm'],default='batchnorm')
    parser.add_argument('--patches',type=Path)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(2)
    torch.backends.cudnn.benchmark=False
    torch.backends.cudnn.deterministic=True
    write_json(args.output/'run.json',dict(pid=os.getpid(),started_at=datetime.now(timezone.utc).isoformat(),
               seed=args.seed,steps=args.steps,learning_rate=args.learning_rate,device=torch.cuda.get_device_name(),
               normalization=args.normalization,
               source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),production_ready=False))
    (args.output/'diagnostic_source.py').write_bytes(Path(__file__).read_bytes())
    config=json.loads(args.config.read_text(encoding='utf-8'))
    samples=torch.load(args.patches,weights_only=True) if args.patches else select_patches(config,args.output,128)
    reports=[run(samples,n,args.output/f'patches-{n}',args) for n in (2,4,8)]
    write_json(args.output/'summary.json',dict(runs=reports,all_passed=all(r['memorization_pass'] for r in reports),production_ready=False))


if __name__=='__main__':
    main()
