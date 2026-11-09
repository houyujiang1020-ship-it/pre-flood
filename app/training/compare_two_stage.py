"""Fair object-union comparison against frozen old-sampler single-stage model."""
import json
from pathlib import Path
import numpy as np, torch
import train_full as base
from model_factory import build_siamunet
from two_stage_feasibility import ROOT,SOURCE,setup,derive,metrics_from_arrays,calibrate,write,sha

def main():
 cfg,records=setup();device=torch.device(cfg['device']);size=cfg['image_size']
 old_path=ROOT/'models/candidates/germany-reviewed-v1/best_model.pth';cp=torch.load(old_path,map_location=device,weights_only=True)
 old=build_siamunet(SOURCE,'groupnorm',8,4).to(device);old.load_state_dict(cp['state_dict']);old.eval()
 sp=[[],[]];sy=[[],[]];sm=[[],[]]
 with torch.inference_mode():
  for area,row in records['validation']:
   pre,post,label,valid=base.cached_pair(area,row,size);union,_=derive(label,valid,1)
   q=old(pre[None].to(device),post[None].to(device)).sigmoid()[0].cpu().numpy()
   # Inclusion-exclusion is a useful score, but independent sigmoid heads do not define
   # mutually exclusive probabilities, so this is not claimed as an exact P(union).
   p=np.stack((1-(1-q[0])*(1-q[1]),1-(1-q[2])*(1-q[3])))
   for i in range(2):sp[i].append(p[i].ravel());sy[i].append(union[i].numpy().ravel());sm[i].append(valid.numpy().ravel())
 prob=np.array([np.concatenate(x) for x in sp]);truth=np.array([np.concatenate(x) for x in sy]);mask=np.array([np.concatenate(x) for x in sm])
 cal=calibrate(prob,truth,mask)
 # Exact mask union under the four frozen per-class thresholds.
 frozen=[.54,.45,.18,.25];counts=[]
 for i,pair in enumerate(((0,1),(2,3))):
  tp=fp=fn=0
  offset=0
  with torch.inference_mode():
   for area,row in records['validation']:
    pre,post,label,valid=base.cached_pair(area,row,size);u,_=derive(label,valid,1);q=old(pre[None].to(device),post[None].to(device)).sigmoid()[0].cpu()
    pred=((q[pair[0]]>frozen[pair[0]])|(q[pair[1]]>frozen[pair[1]]))&(valid>0);y=(u[i]>0)&(valid>0)
    tp+=int((pred&y).sum());fp+=int((pred&~y).sum());fn+=int((~pred&y).sum())
  counts.append({'threshold_rule':f'ch{pair[0]}>{frozen[pair[0]]} OR ch{pair[1]}>{frozen[pair[1]]}','iou':tp/(tp+fp+fn),'precision':tp/(tp+fp),'recall':tp/(tp+fn),'f1':2*tp/(2*tp+fp+fn),'tp':tp,'fp':fp,'fn':fn})
 result={'single_stage_checkpoint':str(old_path.relative_to(ROOT)),'checkpoint_sha256':sha(old_path),'checkpoint_epoch':cp['epoch'],'binary_mask_union_comparison':dict(zip(['building','road'],counts)),'union_score_formula':'1-(1-p_non_flooded)*(1-p_flooded)','union_score_limitation':'The four sigmoid heads are independent; this score is not an exact mutually-exclusive union probability. Binary OR is the primary fair mask comparison.','development_calibrated_union_score_thresholds':dict(zip(['building','road'],cal)),'development_calibrated_union_score':metrics_from_arrays(prob,truth,mask,['building','road'],cal),'blind_holdout_used':False,'louisiana_used':False,'production_ready':False}
 write(ROOT/'experiments/two-stage/single-stage-union-comparison.json',result)
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
