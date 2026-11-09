"""Freeze reviewed development baseline and diagnose valid-pixel probabilities."""
import json, shutil, re, csv
from pathlib import Path
import numpy as np
import torch
import train_full as t
from model_factory import build_siamunet

ROOT=Path(__file__).resolve().parents[2]
def write(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
def main():
    torch.set_num_threads(4)
    config=json.loads((ROOT/'config/training.germany-reviewed-gn-sampler-20260912.json').read_text())
    assert not config['splits']['test']
    assert all(x['area']=='Germany_Training_Public' for s in config['splits'].values() for x in s)
    t.validate_frozen_dataset(config,ROOT)
    t.DISK_CACHE=ROOT/config['cache_dir']
    records=t.split_rows(config,ROOT)
    base=ROOT/'models/experiments/germany-reviewed-gn-sampler-20260912'
    cp=torch.load(base/'best_model.pth',map_location='cpu',weights_only=True)
    history=json.loads((base/'history.json').read_text())
    best=history[cp['epoch']-1]
    assert cp['history'][-1]['validation']==best['validation']
    value=best['validation']['class_iou']['non_flooded_road']
    report=ROOT/'docs/GERMANY_REVIEWED_TRAINING_COMPARISON_20260912.md'
    report.write_text(report.read_text(encoding='utf-8').replace('0.0012chi8',f'{value:.8f}'),encoding='utf-8')
    scan=[]; errors=[]
    for folder in ['docs','experiments/diagnostics','models/experiments']:
        for p in (ROOT/folder).rglob('*'):
            if p.suffix not in ('.md','.json'): continue
            content=p.read_text(encoding='utf-8-sig'); scan.append(str(p.relative_to(ROOT)))
            if p.suffix=='.json':
                try: json.loads(content,parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
                except ValueError as e: errors.append({'path':str(p),'error':str(e)})
            for match in re.finditer(r'(?<![\w.])0\.\d+[g-zG-Z]+\d*\b',content):
                errors.append({'path':str(p),'text':match.group()})
    out=ROOT/'experiments/diagnostics/road-probability-20260912'
    write(out/'numeric-repair-audit.json',{'restored_value':value,'epoch':cp['epoch'],'source':'history.json and best_model.pth history[-1].validation.class_iou.non_flooded_road','checkpoint_sha256':t.file_sha256(base/'best_model.pth'),'scanned':scan,'findings':errors})
    calibration=json.loads((ROOT/'experiments/diagnostics/germany-reviewed-gn-sampler-threshold-calibration-20260912.json').read_text())
    oof=json.loads((ROOT/'experiments/diagnostics/germany-reviewed-threshold-oof-20260912.json').read_text())
    candidate=ROOT/'models/candidates/germany-reviewed-v1'
    candidate.mkdir(parents=True,exist_ok=True)
    dest=candidate/'best_model.pth'
    if dest.exists(): assert t.file_sha256(dest)==t.file_sha256(base/'best_model.pth')
    else: shutil.copy2(base/'best_model.pth',dest)
    write(candidate/'candidate_manifest.json',{'candidate_type':'development','production_ready':False,'architecture':cp['architecture'],'normalization':cp['normalization'],'groupnorm_groups':cp['groupnorm_groups'],'checkpoint_sha256':t.file_sha256(dest),'epoch':cp['epoch'],'split_sha256':cp['dataset_split_hash'],'training_configuration':config,'validation_metrics':best['validation'],'thresholds':dict(zip(t.CLASSES,[.54,.45,.18,.25])),'threshold_calibration':calibration,'oof_metrics':oof,'scope':'Germany development validation only; checkpoint weights unchanged, use manifest thresholds explicitly. OOF concerns thresholds only: checkpoint selected on all validation; not independent accuracy.','source_checkpoint':str((base/'best_model.pth').relative_to(ROOT))})
    tiles=[]
    names=['HAS_NORMAL_BUILDING','HAS_FLOODED_BUILDING','HAS_NORMAL_ROAD','HAS_FLOODED_ROAD']
    for area,row in records['train']:
        _,_,truth,valid=t.cached_pair(area,row,512)
        flags=((truth>0)&(valid.unsqueeze(0)>0)).sum((1,2)).gt(0).tolist()
        tiles.append({'label':row['label'],'split':'train',**dict(zip(names,flags)),'BACKGROUND_ONLY':not any(flags)})
    write(ROOT/'experiments/diagnostics/train-sample-class-presence.json',{'split_sha256':cp['dataset_split_hash'],'counts':{n:sum(x[n] for x in tiles) for n in names+['BACKGROUND_ONLY']},'tiles':tiles,'old_sampler_audit':'Overlapping epoch quotas, not one positive pool. has_building/has_road include flooded classes; shuffled after quotas. batch size 1.'})
    model=build_siamunet(ROOT/'upstream/SpaceNet8/baseline/models/other/siamunetdif.py',cp['normalization'],8).cuda().eval()
    model.load_state_dict(cp['state_dict'])
    values=[[[],[]] for _ in range(4)]
    with torch.inference_mode():
        for area,row in records['validation']:
            pre,post,truth,valid=t.cached_pair(area,row,512)
            prob=model(pre[None].cuda(),post[None].cuda()).sigmoid()[0].cpu().numpy()
            for c in range(4):
                mask=valid.numpy()>0; pos=truth[c].numpy()>0
                values[c][0].append(prob[c][mask & pos]);values[c][1].append(prob[c][mask & ~pos])
    result={'scope':'Germany development validation, valid pixels only; not independent accuracy','classes':{},'checkpoint_sha256':t.file_sha256(dest)}
    for c,name in enumerate(t.CLASSES):
        pos,neg=[np.concatenate(v) for v in values[c]]
        np.savez_compressed(out/(name+'-probabilities.npz'),positive=pos,negative=neg)
        bins=np.linspace(0,1,101)
        rows=[]
        sp,sn=np.sort(pos),np.sort(neg)
        for threshold in np.linspace(0,1,101):
            tp=len(pos)-np.searchsorted(sp,threshold,side='right');fp=len(neg)-np.searchsorted(sn,threshold,side='right')
            precision=float(tp/(tp+fp)) if tp+fp else 1.
            rows.append({'threshold':float(threshold),'tp':int(tp),'fp':int(fp),'precision':precision,'recall':float(tp/len(pos)),'iou':float(tp/(len(pos)+fp))})
        with (out/(name+'-precision-recall-threshold.csv')).open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        result['classes'][name]={'positive_count':len(pos),'negative_count':len(neg),'positive_quantiles':dict(zip(['p05','p25','p50','p75','p95'],np.quantile(pos,[.05,.25,.5,.75,.95]).tolist())),'negative_quantiles':dict(zip(['p05','p25','p50','p75','p95'],np.quantile(neg,[.05,.25,.5,.75,.95]).tolist())),'histogram_edges':bins.tolist(),'positive_histogram':np.histogram(pos,bins)[0].tolist(),'negative_histogram':np.histogram(neg,bins)[0].tolist(),'threshold_table':rows,'prevalence':len(pos)/(len(pos)+len(neg))}
    write(out/'probability-diagnosis.json',result)
    print(json.dumps({'iou':value,'counts':{n:sum(x[n] for x in tiles) for n in names},'scan_findings':errors,'quantiles':{n:{k:v for k,v in d.items() if 'quantile' in k} for n,d in result['classes'].items()}}),flush=True)
if __name__=='__main__':main()
