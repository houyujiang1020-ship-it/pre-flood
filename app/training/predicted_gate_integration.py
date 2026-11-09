"""Frozen-model predicted-gate integration; no training and no GT inference gate."""
import hashlib,json
from pathlib import Path
import numpy as np, torch
from PIL import Image,ImageDraw
import rasterio
import train_full as base
from model_factory import build_siamunet
from road_morphology import components,morphology
from two_stage_feasibility import ROOT,SOURCE,setup,average_precision

CLASSES=['non_flooded_building','flooded_building','non_flooded_road','flooded_road']
RUN=ROOT/'experiments/two-stage/predicted-gate-20260912'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2),encoding='utf-8')
def load_json(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def reconstruct_hard(obj,status,thresholds):
 bo=obj[0]>=thresholds['stage1_object']['building'];ro=obj[1]>=thresholds['stage1_object']['road']
 fb=bo&(status[0]>=thresholds['stage2_status']['building_flood']);fr=ro&(status[1]>=thresholds['stage2_status']['road_flood'])
 return np.stack((bo&~fb,fb,ro&~fr,fr)),np.stack((bo*(1-status[0]),bo*status[0],ro*(1-status[1]),ro*status[1]))
def soft_product(obj,status):return np.stack((obj[0]*(1-status[0]),obj[0]*status[0],obj[1]*(1-status[1]),obj[1]*status[1]))
def binary_metrics(scores,truth,valid,thresholds,prediction=None):
 out={}
 for i,name in enumerate(CLASSES):
  keep=valid.astype(bool);y=truth[i][keep].astype(bool);p=scores[i][keep];q=prediction[i][keep] if prediction is not None else p>=thresholds[i]
  tp=int((q&y).sum());fp=int((q&~y).sum());fn=int((~q&y).sum());u=tp+fp+fn
  out[name]={'threshold':thresholds[i] if prediction is None else 'logical hard gate','iou':tp/u if u else None,'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn) if tp+fn else None,'f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,'ap':average_precision(y,p),'tp':tp,'fp':fp,'fn':fn}
 out['macro']={k:sum(out[n][k] or 0 for n in CLASSES)/4 for k in ('iou','precision','recall','f1','ap')};return out
def gate_recall(truth,hard,valid):
 gates=[hard[0]|hard[1],hard[2]|hard[3]];targets=[truth[0]|truth[1],truth[2]|truth[3],truth[1],truth[3]];used=[gates[0],gates[1],gates[0],gates[1]];names=['building_object_gate_recall','road_object_gate_recall','flooded_building_gate_recall','flooded_road_gate_recall'];out={}
 for n,y,g in zip(names,targets,used):
  y=y&valid;covered=int((y&g).sum());total=int(y.sum());out[n]={'covered_pixels':covered,'gt_pixels':total,'recall':covered/total if total else None}
 return out
def retention_ratios(predicted,oracle):
 return {m:predicted[m]/oracle[m] for m in ('iou','f1','ap')}
def decompose(truth,obj,status,t):
 result={}
 for name,i,oi,st in [('flooded_building',1,0,'building_flood'),('flooded_road',3,1,'road_flood')]:
  y=truth[i].astype(bool);gate=obj[oi]>=t['stage1_object']['building' if oi==0 else 'road'];flood=status[oi]>=t['stage2_status'][st]
  vals={'stage1_gate_missed':int((y&~gate).sum()),'gate_passed_status_non_flooded':int((y&gate&~flood).sum()),'correctly_classified_flooded':int((y&gate&flood).sum())};total=int(y.sum());result[name]={'gt_pixels':total,**{k:{'pixels':v,'ratio':v/total if total else None} for k,v in vals.items()}}
 return result
def component_analysis(truth,obj,status,t):
 out={}
 for name,i,oi,st in [('flooded_building',1,0,'building_flood'),('flooded_road',3,1,'road_flood')]:
  lab,count=components(truth[i]);gate=obj[oi]>=t['stage1_object']['building' if oi==0 else 'road'];sf=status[oi]>=t['stage2_status'][st];final=gate&sf
  touched=status_ok=detected=0
  for c in range(1,count+1):
   region=lab==c;touched+=int((region&gate).any());status_ok+=int((region&sf).any());detected+=int((region&final).any())
  out[name]={'total_gt_components':count,'components_touched_by_stage1_gate':touched,'components_with_stage2_flood_response':status_ok,'components_finally_detected_flooded':detected,'detection_ratio':detected/count if count else None}
 return out
def aggregate_dict(items):
 if not items:return {}
 keys=items[0].keys();return {k:sum(x[k] for x in items) for k in keys if isinstance(items[0][k],int)}
def render(sample,pre,post,truth,obj,status,hard,soft,valid):
 def rgb(x):return (np.moveaxis(x,0,2)*255).clip(0,255).astype('uint8')
 def color(mask):
  c=np.zeros((*mask.shape[1:],3),dtype=np.uint8);palette=np.array([[40,180,255],[255,40,40],[255,210,40],[190,40,255]],dtype=np.uint8)
  for i in range(4):c[mask[i].astype(bool)]=palette[i]
  return c
 gt=truth.astype(bool)&valid;stage=np.stack((obj[0]>=.41,obj[0]>=.41,obj[1]>=.33,obj[1]>=.33));oracle=np.stack((status[0]<.07,status[0]>=.07,status[1]<.29,status[1]>=.29))&np.stack((truth[0]|truth[1],)*2+(truth[2]|truth[3],)*2)
 softmask=soft>=np.array([.3813,.0287,.2343,.0957])[:,None,None]
 final=rgb(post).copy();overlay=color(hard);sel=hard.any(0);final[sel]=(final[sel]*.35+overlay[sel]*.65).astype('uint8')
 panels=[rgb(pre),rgb(post),color(gt),color(stage),color(oracle),color(hard),color(softmask),final];labels=['PRE','POST','GT four class','Stage1 object gate','Oracle Stage2 (GT gate)','Predicted Hard Gate','Predicted Soft Gate','Final hard overlay']
 canvas=Image.new('RGB',(1024,1100),'white');draw=ImageDraw.Draw(canvas);draw.text((10,8),f'DEVELOPMENT VALIDATION — {sample}',fill='black')
 for k,(im,label) in enumerate(zip(panels,labels)):
  x=(k%2)*512;y=38+(k//2)*265;canvas.paste(Image.fromarray(im).resize((512,256)),(x,y));draw.text((x+5,y+5),label,fill='white',stroke_width=2,stroke_fill='black')
 return canvas
def main():
 lock=load_json(RUN/'threshold-lock.json');locked_sha=load_json(RUN/'threshold-lock.sha256.json')['sha256']
 if sha(RUN/'threshold-lock.json')!=locked_sha:raise ValueError('Threshold lock changed')
 cfg,records=setup();device=torch.device(cfg['device']);models=[]
 paths=[ROOT/'models/experiments/two-stage/stage1-object/best_model.pth',ROOT/'models/experiments/two-stage/stage2-oracle-status/best_model.pth']
 for path in paths:
  cp=torch.load(path,map_location=device,weights_only=True);m=build_siamunet(SOURCE,'groupnorm',8,2).to(device);m.load_state_dict(cp['state_dict']);m.eval();models.append(m)
 old_path=ROOT/'models/candidates/germany-reviewed-v1/best_model.pth';oldcp=torch.load(old_path,map_location=device,weights_only=True);old=build_siamunet(SOURCE,'groupnorm',8,4).to(device);old.load_state_dict(oldcp['state_dict']);old.eval()
 alltruth=[];allvalid=[];allhard=[];allhscore=[];allsoft=[];allold=[];gate_items=[];decomp_items=[];component_items=[];morph_h=[];morph_s=[];morph_old=[];selected=[]
 pred_dir=RUN/'predictions';viz_dir=RUN/'visualizations';pred_dir.mkdir(parents=True,exist_ok=True);viz_dir.mkdir(parents=True,exist_ok=True)
 with torch.inference_mode():
  for area,row in records['validation']:
   pre,post,y,v=base.cached_pair(area,row,cfg['image_size']);obj=models[0](pre[None].to(device),post[None].to(device)).sigmoid()[0].cpu().numpy();status=models[1](pre[None].to(device),post[None].to(device)).sigmoid()[0].cpu().numpy();truth=y.numpy().astype(bool);valid=v.numpy().astype(bool)
   hard,hscore=reconstruct_hard(obj,status,lock);soft=soft_product(obj,status);oq=old(pre[None].to(device),post[None].to(device)).sigmoid()[0].cpu().numpy()
   alltruth.append(truth.reshape(4,-1));allvalid.append(valid.ravel());allhard.append(hard.reshape(4,-1));allhscore.append(hscore.reshape(4,-1));allsoft.append(soft.reshape(4,-1));allold.append(oq.reshape(4,-1));gate_items.append(gate_recall(truth,hard,valid));decomp_items.append(decompose(truth,obj,status,lock));component_items.append(component_analysis(truth,obj,status,lock))
   road_gt=(truth[2]|truth[3])&valid;morph_h.append(morphology(road_gt,(hard[2]|hard[3])&valid));smask=(soft[2]>=lock['soft_output']['non_flooded_road'])|(soft[3]>=lock['soft_output']['flooded_road']);morph_s.append(morphology(road_gt,smask&valid));oldmask=(oq[2]>=.18)|(oq[3]>=.25);morph_old.append(morphology(road_gt,oldmask&valid))
   sample=Path(row['label']).stem
   with rasterio.open(area/'PRE-event'/row['pre-event image']) as src:geo={'crs':str(src.crs),'transform':list(src.transform),'source_width':src.width,'source_height':src.height}
   np.savez_compressed(pred_dir/f'{sample}.npz',building_probability=obj[0],road_probability=obj[1],building_flood_probability=status[0],road_flood_probability=status[1],hard_four_class=hard,soft_four_class=soft)
   write(pred_dir/f'{sample}.json',{'sample_id':sample,'label':row['label'],'array_shape':[512,512],'geo_identity':geo,'stage1_checkpoint_sha256':sha(paths[0]),'stage2_checkpoint_sha256':sha(paths[1]),'threshold_lock_sha256':locked_sha,'GT_used_for_inference':False,'production_ready':False})
   if truth[3].any() or (truth[1].any() and not selected):render(sample,pre.numpy(),post.numpy(),truth,obj,status,hard,soft,valid).save(viz_dir/f'{sample}.png');selected.append(sample)
 truth=np.concatenate(alltruth,axis=1);valid=np.concatenate(allvalid);hard=np.concatenate(allhard,axis=1);hscore=np.concatenate(allhscore,axis=1);soft=np.concatenate(allsoft,axis=1);oldscore=np.concatenate(allold,axis=1)
 hard_eval=binary_metrics(hscore,truth,valid,[0,0,0,0],hard);soft_t=[lock['soft_output'][x] for x in CLASSES];soft_eval=binary_metrics(soft,truth,valid,soft_t);old_eval=binary_metrics(oldscore,truth,valid,[.54,.45,.18,.25])
 write(RUN/'hard-gate-evaluation.json',{'integration':'hard','metrics':hard_eval,'scope':'Germany development validation18','GT_used_for_inference':False,'production_ready':False,'blind_holdout_used':False});write(RUN/'soft-gate-evaluation.json',{'integration':'semantic probability product','formula':['P(object)*(1-P(flood|object))','P(object)*P(flood|object)'],'metrics':soft_eval,'scope':'Germany development validation18','production_ready':False,'blind_holdout_used':False})
 # aggregate gate and error counts across tiles
 gates={};
 for key in gate_items[0]:
  cov=sum(x[key]['covered_pixels'] for x in gate_items);tot=sum(x[key]['gt_pixels'] for x in gate_items);gates[key]={'covered_pixels':cov,'gt_pixels':tot,'recall':cov/tot}
 write(RUN/'gate-recall.json',gates)
 errors={}
 for name in ('flooded_building','flooded_road'):
  tot=sum(x[name]['gt_pixels'] for x in decomp_items);errors[name]={'gt_pixels':tot}
  for k in ('stage1_gate_missed','gate_passed_status_non_flooded','correctly_classified_flooded'):
   n=sum(x[name][k]['pixels'] for x in decomp_items);errors[name][k]={'pixels':n,'ratio':n/tot}
 write(RUN/'error-decomposition.json',errors)
 comps={}
 for name in ('flooded_building','flooded_road'):
  keys=('total_gt_components','components_touched_by_stage1_gate','components_with_stage2_flood_response','components_finally_detected_flooded');vals={k:sum(x[name][k] for x in component_items) for k in keys};vals['detection_ratio']=vals['components_finally_detected_flooded']/vals['total_gt_components'];comps[name]=vals
 write(RUN/'object-component-analysis.json',comps)
 def morph_summary(items):
  sums={k:sum(x[k] for x in items) for k in ('gt_components','pred_components','gt_skeleton_pixels','skeleton_covered_pixels','skeleton_covered_within_1px','gt_components_matched','matched_fragment_pairs','unmatched_pred_components')};sums.update(skeleton_recall=sums['skeleton_covered_pixels']/sums['gt_skeleton_pixels'],one_pixel_tolerance_recall=sums['skeleton_covered_within_1px']/sums['gt_skeleton_pixels'],fragments_per_matched_gt=sums['matched_fragment_pairs']/sums['gt_components_matched'],uncovered_gt_ratio=(sums['gt_components']-sums['gt_components_matched'])/sums['gt_components']);return sums
 write(RUN/'morphology-summary.json',{'hard':morph_summary(morph_h),'soft':morph_summary(morph_s),'single_stage':morph_summary(morph_old)})
 oracle=load_json(ROOT/'experiments/two-stage/stage2-oracle-evaluation.json')['development_calibrated'];ret={}
 for name,key in [('flooded_building','building_flood_status'),('flooded_road','road_flood_status')]:
  ret[name]={'oracle':oracle[key],'hard':hard_eval[name],'soft':soft_eval[name],'retention':{'hard':retention_ratios(hard_eval[name],oracle[key]),'soft':retention_ratios(soft_eval[name],oracle[key])}}
 write(RUN/'oracle-retention.json',ret)
 comparison={'single_stage':old_eval,'hard_gate':hard_eval,'soft_gate':soft_eval,'absolute_and_relative_gain_vs_single_stage':{}}
 for name in CLASSES:
  comparison['absolute_and_relative_gain_vs_single_stage'][name]={mode:{m:{'absolute':ev[name][m]-old_eval[name][m],'relative':(ev[name][m]-old_eval[name][m])/old_eval[name][m] if old_eval[name][m] else None} for m in ('iou','f1','ap')} for mode,ev in [('hard',hard_eval),('soft',soft_eval)]}
 write(RUN/'comparison.json',comparison)
 rules=load_json(RUN/'predicted-gate-decision.json');basei=rules['baseline'];candidates={'hard':hard_eval,'soft':soft_eval};passed=[]
 for mode,ev in candidates.items():
  if ev['flooded_road']['iou']-basei['flooded_road_iou']>=.05 and ev['macro']['iou']-basei['four_class_macro_iou']>=.01 and ev['flooded_building']['iou']>=basei['flooded_building_iou']-.03:passed.append(mode)
 recommended='hard'
 if soft_eval['flooded_road']['iou']-hard_eval['flooded_road']['iou']>=.03 or soft_eval['flooded_road']['ap']-hard_eval['flooded_road']['ap']>=.05:
  if soft_eval['macro']['iou']>=hard_eval['macro']['iou'] and soft_eval['macro']['f1']>=hard_eval['macro']['f1']:recommended='soft'
 decision={'case':'PG-A' if passed else ('PG-B' if ret['flooded_road']['retention']['hard']['iou']<.5 and errors['flooded_road']['stage1_gate_missed']['ratio']>errors['flooded_road']['gate_passed_status_non_flooded']['ratio'] else 'PG-C'),'development_promotion_passed':bool(passed),'passing_integrations':passed,'recommended_integration':recommended,'production_ready':False,'blind_holdout_used':False,'louisiana_used':False}
 write(RUN/'decision.json',decision);write(RUN/'inference-manifest.json',{'validation_samples':len(records['validation']),'visualized_samples':selected,'checkpoint_sha256':{'stage1':sha(paths[0]),'stage2':sha(paths[1])},'threshold_lock_sha256':locked_sha,'GT_used_for_predicted_inference':False,'production_ready':False,'blind_holdout_used':False})
 print(json.dumps({'gate_recall':gates,'hard_macro':hard_eval['macro'],'soft_macro':soft_eval['macro'],'flooded_road':{'single':old_eval['flooded_road'],'hard':hard_eval['flooded_road'],'soft':soft_eval['flooded_road']},'decision':decision},indent=2))
if __name__=='__main__':main()
