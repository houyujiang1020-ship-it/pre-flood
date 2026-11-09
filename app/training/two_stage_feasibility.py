"""Predeclared Germany-only Stage1 and oracle-gated Stage2 feasibility study."""
import argparse, hashlib, json, random
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch

import train_full as base
from model_factory import build_siamunet
from positive_sampler import PositiveSampler
from road_morphology import morphology

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'upstream/SpaceNet8/baseline/models/other/siamunetdif.py'
BASE_CONFIG = ROOT/'config/training.germany-reviewed-gn-sampler-20260912.json'
STAGE1_CLASSES = ['building', 'road']
STAGE2_CLASSES = ['building_flood_status', 'road_flood_status']

def average_precision(y, p):
    """Non-interpolated binary average precision, equivalent to sklearn AP."""
    y=np.asarray(y,dtype=bool);p=np.asarray(p)
    if not y.any() or y.all(): return None
    order=np.argsort(-p,kind='stable'); ranked=y[order]
    precision=np.cumsum(ranked)/(np.arange(len(ranked))+1)
    return float(precision[ranked].sum()/ranked.sum())

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding='utf-8')

def setup():
    cfg=json.loads(BASE_CONFIG.read_text(encoding='utf-8'))
    base.validate_frozen_dataset(cfg, ROOT)
    if cfg['frozen_dataset_sha256']!='14f57e129972554d64991f956f3e23f29cc947007605e6b052f8b4001ba8e1b1': raise ValueError('Unexpected split')
    base.DISK_CACHE=ROOT/cfg['cache_dir']; base._cached_pair.cache_clear()
    return cfg,base.split_rows(cfg,ROOT)

def derive(label,valid,stage):
    building=((label[0]>0)|(label[1]>0)).float(); road=((label[2]>0)|(label[3]>0)).float()
    if stage==1:return torch.stack((building,road)),valid
    return torch.stack((label[1],label[3])),torch.stack((building,road))*valid.unsqueeze(0)

def loss_fn(logits,target,mask,dice=True):
    if mask.ndim==3: mask=mask.unsqueeze(1)
    if mask.shape[1]==1: mask=mask.expand_as(logits)
    denom=mask.sum()
    if denom<=0: raise ValueError('No valid supervision')
    value=(torch.nn.functional.binary_cross_entropy_with_logits(logits,target,reduction='none')*mask).sum()/denom
    if dice:
        p=logits.sigmoid()*mask; t=target*mask
        inter=(p*t).sum((0,2,3)); total=(p+t).sum((0,2,3))
        value=value+0.5*(1-(2*inter+1)/(total+1)).mean()
    return value

def tiles_for_sampler(records,size):
    result=[]
    for area,row in records:
        _,_,y,v=base.cached_pair(area,row,size); d,_=derive(y,v,1)
        hb,hr=[bool(x.any()) for x in d]
        result.append(dict(split='train',area=str(area),label=row['label'],has_building=hb,has_road=hr,
            has_flooded_building=False,has_flooded_road=False,background_only=not(hb or hr)))
    return result

def metrics_from_arrays(prob,truth,mask,names,thresholds):
    result={}
    for i,name in enumerate(names):
        keep=mask[i].astype(bool); y=truth[i][keep].astype(bool); p=prob[i][keep]; pred=p>thresholds[i]
        tp=int((pred&y).sum()); fp=int((pred&~y).sum()); fn=int((~pred&y).sum()); union=tp+fp+fn
        result[name]={'threshold':thresholds[i],'iou':tp/union if union else None,
          'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn) if tp+fn else None,
          'f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
          'ap':average_precision(y,p),
          'tp':tp,'fp':fp,'fn':fn,'truth_pixels':int(y.sum()),'prediction_pixels':int(pred.sum())}
    return result

def infer(model,records,size,device,stage):
    ps=[[],[]]; ys=[[],[]]; ms=[[],[]]; per=[]
    model.eval()
    with torch.inference_mode():
      for area,row in records:
        pre,post,label,valid=base.cached_pair(area,row,size); target,mask=derive(label,valid,stage)
        p=model(pre[None].to(device),post[None].to(device)).sigmoid()[0].cpu()
        mm=mask if mask.ndim==3 else mask.expand_as(target)
        for i in range(2): ps[i].append(p[i].numpy().ravel());ys[i].append(target[i].numpy().ravel());ms[i].append(mm[i].numpy().ravel())
        per.append((row['label'],p.numpy(),target.numpy(),mm.numpy(),label.numpy(),valid.numpy()))
    return np.array([np.concatenate(x) for x in ps]),np.array([np.concatenate(x) for x in ys]),np.array([np.concatenate(x) for x in ms]),per

def calibrate(prob,truth,mask):
    out=[]
    for i in range(2):
      keep=mask[i].astype(bool); y=truth[i][keep].astype(bool);p=prob[i][keep];best=(-1,.5)
      for t in np.arange(.01,1,.01):
        q=p>t; inter=(q&y).sum();u=(q|y).sum();score=inter/u if u else 0
        if score>best[0]:best=(score,float(round(t,2)))
      out.append(best[1])
    return out

def train(stage,epochs=40):
    cfg,records=setup(); size=cfg['image_size'];device=torch.device(cfg['device'])
    names=STAGE1_CLASSES if stage==1 else STAGE2_CLASSES
    out=ROOT/f'models/experiments/two-stage/{"stage1-object" if stage==1 else "stage2-oracle-status"}'
    out.mkdir(parents=True,exist_ok=True)
    model=build_siamunet(SOURCE,'groupnorm',8,num_classes=2).to(device)
    opt=torch.optim.Adam(model.parameters(),lr=.0003);torch.manual_seed(20260912);random.seed(20260912)
    sampler=None
    if stage==1:
      sampler=PositiveSampler(tiles_for_sampler(records['train'],size),{'type':'positive_aware','epoch_size':98,
        'min_fractions':{'has_building':.6,'has_road':.6},'max_background_fraction':.1},20260912)
    history=[];best=-1
    for epoch in range(epochs):
      model.train(); losses=[]; indices=sampler.sample(epoch)[0] if sampler else torch.randperm(len(records['train'])).tolist()
      for step,index in enumerate(indices):
        pre,post,label,valid=base.cached_pair(*records['train'][index],size);target,mask=derive(label,valid,stage)
        pre,post,target,mask=[x[None].to(device) for x in (pre,post,target,mask)]
        turns=int(torch.randint(4,()).item());pre,post,target,mask=[torch.rot90(x,turns,(-2,-1)) for x in (pre,post,target,mask)]
        if torch.rand(()).item()<.5:pre,post,target,mask=[x.flip(-1) for x in (pre,post,target,mask)]
        opt.zero_grad(set_to_none=True);value=loss_fn(model(pre,post),target,mask);value.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),10);opt.step();losses.append(value.item())
        if (step+1)%25==0:print(json.dumps({'stage':stage,'epoch':epoch+1,'step':step+1,'loss':value.item()}),flush=True)
      prob,truth,mask,_=infer(model,records['validation'],size,device,stage)
      met=metrics_from_arrays(prob,truth,mask,names,[.5,.5]);score=sum(x['iou'] or 0 for x in met.values())/2
      rec={'epoch':epoch+1,'train_loss':float(np.mean(losses)),'validation_macro_iou_0.5':score,'validation':met};history.append(rec);print(json.dumps(rec),flush=True)
      payload={'state_dict':model.state_dict(),'epoch':epoch+1,'history':history,'classes':names,'stage':stage,'architecture':'SiamUnet_diff','num_classes':2,'normalization':'groupnorm','groupnorm_groups':8,'split_sha256':cfg['frozen_dataset_sha256'],'blind_holdout_used':False,'louisiana_used':False,'production_ready':False,'development_only':True}
      torch.save(payload,out/'last_model.pth')
      if score>best:best=score;torch.save(payload,out/'best_model.pth')
      write(out/'history.json',history)
    manifest={'status':'completed','stage':stage,'task':'dual-channel object segmentation' if stage==1 else 'oracle-gated conditional flood status','classes':names,'epochs':epochs,'image_size':size,'backbone':'SiamUnet_diff','normalization':'GroupNorm8','optimizer':'Adam','learning_rate':.0003,'seed':20260912,'augmentation':'same random 90-degree rotations and horizontal flip','loss':'BCE + 0.5 * mean(per-channel Dice); Stage2 mask is GT object union','sampler':({'type':'positive_aware','epoch_size':98,'min_fractions':{'has_building':.6,'has_road':.6},'max_background_fraction':.1,'flood_status_quotas':False} if stage==1 else 'uniform random permutation'),'split_sha256':cfg['frozen_dataset_sha256'],'blind_holdout_used':False,'louisiana_used':False,'production_ready':False}
    write(out/'experiment_manifest.json',manifest);return evaluate(stage)

def overfit():
    cfg,records=setup(); device=torch.device(cfg['device']); reports={}
    for count in (2,4,8):
      torch.manual_seed(20260912); model=build_siamunet(SOURCE,'groupnorm',8,2).to(device);opt=torch.optim.Adam(model.parameters(),lr=.0003)
      chosen=records['train'][:count]; first=None;last=None
      for epoch in range(60):
       losses=[];model.train()
       for area,row in chosen:
        pre,post,label,valid=base.cached_pair(area,row,cfg['image_size']);target,mask=derive(label,valid,2);pre,post,target,mask=[x[None].to(device) for x in(pre,post,target,mask)]
        opt.zero_grad(set_to_none=True);v=loss_fn(model(pre,post),target,mask);v.backward();opt.step();losses.append(v.item())
       if first is None:first=float(np.mean(losses))
       last=float(np.mean(losses))
      reports[str(count)]={'initial_loss':first,'final_loss':last,'relative_reduction':(first-last)/first,'passed':last<first*.75}
      print(json.dumps({'oracle_overfit':count,**reports[str(count)]}),flush=True)
    result={'status':'passed' if all(x['passed'] for x in reports.values()) else 'failed','patch_counts':reports,'production_ready':False,'blind_holdout_used':False}
    write(ROOT/'experiments/two-stage/oracle-overfit-sanity.json',result)
    if result['status']!='passed':raise SystemExit(3)

def evaluate(stage):
    cfg,records=setup();device=torch.device(cfg['device']);names=STAGE1_CLASSES if stage==1 else STAGE2_CLASSES
    out=ROOT/f'models/experiments/two-stage/{"stage1-object" if stage==1 else "stage2-oracle-status"}'
    cp=torch.load(out/'best_model.pth',map_location=device,weights_only=True);model=build_siamunet(SOURCE,'groupnorm',8,2).to(device);model.load_state_dict(cp['state_dict'])
    prob,truth,mask,per=infer(model,records['validation'],cfg['image_size'],device,stage);cal=calibrate(prob,truth,mask)
    result={'stage':stage,'checkpoint_epoch':cp['epoch'],'checkpoint_sha256':sha(out/'best_model.pth'),'threshold_0.5':metrics_from_arrays(prob,truth,mask,names,[.5,.5]),'development_calibrated_thresholds':dict(zip(names,cal)),'development_calibrated':metrics_from_arrays(prob,truth,mask,names,cal),'scope':'Germany development validation','blind_holdout_used':False,'louisiana_used':False,'production_ready':False}
    if stage==1:
      morph={}
      for threshold_name,ts in [('0.5',[.5,.5]),('development_calibrated',cal)]:
       vals=[]
       for label,p,y,m,*_ in per:vals.append({'label':label,**morphology(y[1]>0,p[1]>ts[1],m[1]>0)})
       sums={k:sum(x[k] for x in vals) for k in ('gt_components','pred_components','gt_skeleton_pixels','skeleton_covered_pixels','skeleton_covered_within_1px','gt_components_matched','matched_fragment_pairs','unmatched_pred_components')}
       sums['skeleton_recall']=sums['skeleton_covered_pixels']/sums['gt_skeleton_pixels']
       sums['one_pixel_tolerance_recall']=sums['skeleton_covered_within_1px']/sums['gt_skeleton_pixels']
       sums['fragments_per_matched_gt']=sums['matched_fragment_pairs']/sums['gt_components_matched']
       sums['uncovered_gt_ratio']=(sums['gt_components']-sums['gt_components_matched'])/sums['gt_components']
       morph[threshold_name]={'aggregate':sums,'per_tile':vals}
      result['road_morphology']=morph
    else:
      fullmask=np.ones_like(mask)
      gated_prob=prob*mask
      result['metric_regions']={'within_gt_object_mask':result['development_calibrated'],'mapped_to_full_image':metrics_from_arrays(gated_prob,truth,fullmask,names,cal)}
    write(ROOT/f'experiments/two-stage/{"stage1-evaluation" if stage==1 else "stage2-oracle-evaluation"}.json',result);return result

def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=['stage1','overfit','stage2','eval1','eval2']);p.add_argument('--epochs',type=int,default=40);a=p.parse_args()
 if a.action=='stage1':train(1,a.epochs)
 elif a.action=='overfit':overfit()
 elif a.action=='stage2':train(2,a.epochs)
 elif a.action=='eval1':evaluate(1)
 else:evaluate(2)

if __name__=='__main__':main()
