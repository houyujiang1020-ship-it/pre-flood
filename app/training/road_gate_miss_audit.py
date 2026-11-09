"""Diagnose frozen Stage1 road misses at native and 512 resolution."""
import csv,hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
import rasterio
from rasterio.features import rasterize
from rasterio.warp import transform_geom
from train_smoke import buffered_road,flooded_class
import train_full as base
from road_morphology import components,skeletonize,dilate_one
from two_stage_feasibility import ROOT,setup

OUT=ROOT/'experiments/diagnostics/stage1-road-gate-miss-20260912';TH=.33
def deterministic_tiles(length,patch,overlap):
 if patch>length:raise ValueError('Fake upsample forbidden: patch exceeds native dimension')
 if not 0<=overlap<patch:raise ValueError('Invalid overlap')
 starts=list(range(0,max(1,length-patch+1),patch-overlap))
 if starts[-1]!=length-patch:starts.append(length-patch)
 return starts
def validate_aligned_patch(shape,transform,window_shape,window_transform):
 if window_shape[0]>shape[0] or window_shape[1]>shape[1]:raise ValueError('Patch exceeds native source')
 if transform is None or window_transform is None:raise ValueError('Geographic transforms required')
 return True
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2),encoding='utf-8')
def verify_predicted_gate():
 d=ROOT/'experiments/two-stage/predicted-gate-20260912';m=json.loads((d/'completion_manifest.json').read_text(encoding='utf-8'));bad=[]
 for f,h in m['artifact_sha256'].items():
  p=d/f
  if not p.is_file() or sha(p)!=h:bad.append(f)
 if bad:raise ValueError('Predicted-Gate closure mismatch: '+str(bad))
 return {'status':'passed','completion_manifest_sha256':sha(d/'completion_manifest.json'),'verified_artifact_count':len(m['artifact_sha256'])}
def erode(mask):
 p=np.pad(mask,1);h,w=mask.shape
 return np.logical_and.reduce([p[i:i+h,j:j+w] for i in range(3) for j in range(3)])
def width_samples(mask):
 """Approximate full width from Chebyshev erosion depth sampled on skeleton."""
 mask=np.asarray(mask,bool);depth=np.zeros(mask.shape,np.uint16);cur=mask.copy();d=0
 while cur.any():
  d+=1;depth[cur]=d;cur=erode(cur)
 sk=skeletonize(mask);return (2*depth[sk].astype(float)-1),depth,sk
def summarize(values):
 values=np.asarray(values,float)
 if not len(values):return {'count':0,'p05':None,'p25':None,'p50':None,'p75':None,'p95':None,**{f'width_le_{x}px_ratio':None for x in range(1,5)}}
 q=np.quantile(values,[.05,.25,.5,.75,.95]);r={'count':len(values),**dict(zip(['p05','p25','p50','p75','p95'],map(float,q)))}
 r.update({f'width_le_{x}px_ratio':float((values<=x).mean()) for x in range(1,5)});return r
def native_masks(area,row):
 with rasterio.open(area/'PRE-event'/row['pre-event image']) as src:shape=src.shape;transform=src.transform;crs=src.crs;meta={'width':src.width,'height':src.height,'transform':list(src.transform),'crs':str(src.crs),'pixel_size':[abs(src.transform.a),abs(src.transform.e)]}
 features=json.loads((area/'annotations'/row['label']).read_text(encoding='utf-8'))['features'];shapes=[[],[]]
 for f in features:
  p=f['properties'];building=p.get('building') not in(None,'no','');road=p.get('highway') not in(None,'')
  if not road or building:continue
  geom=buffered_road(f['geometry'],crs);shapes[flooded_class(p.get('flooded'))].append((geom,1))
 masks=np.stack([rasterize(s,out_shape=shape,transform=transform,all_touched=False,dtype='uint8') if s else np.zeros(shape,np.uint8) for s in shapes]).astype(bool)
 return masks,meta
def metric(gt,pred):
 tp=int((gt&pred).sum());fp=int((~gt&pred).sum());fn=int((gt&~pred).sum());return {'iou':tp/(tp+fp+fn) if tp+fp+fn else None,'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn) if tp+fn else None,'false_negative_pixels':fn,'false_positive_pixels':fp}
def prob_summary(p,gt,valid):
 x=p[gt&valid];return {**summarize(x),'mean':float(x.mean()) if len(x) else None,'max':float(x.max()) if len(x) else None}
def border_flags(region,valid,pre,post):
 edge=np.zeros_like(region);edge[:2]=edge[-2:]=True;edge[:,:2]=edge[:,-2:]=True
 invalid_near=dilate_one(~valid);black=(pre.mean(0)<.02)|(post.mean(0)<.02)
 return bool((region&edge).any()),bool((region&invalid_near).any()),bool((region&black).any())
def render(name,pre,post,gt,p,valid):
 rgb=lambda x:(np.moveaxis(x,0,2)*255).clip(0,255).astype('uint8');gate=(p>=TH)&valid;fn=gt&valid&~gate
 heat=np.stack((p,np.zeros_like(p),1-p),-1);binary=lambda m:np.repeat((m*255).astype('uint8')[...,None],3,2)
 panels=[rgb(pre),rgb(post),binary(gt&valid),(heat*255).astype('uint8'),binary(gate),np.stack((fn,np.zeros_like(fn),np.zeros_like(fn)),-1).astype('uint8')*255];labels=['PRE','POST','GT Road','Stage1 Road Probability','Stage1 Hard Gate','False Negative Road']
 canvas=Image.new('RGB',(1024,830),'white');d=ImageDraw.Draw(canvas);d.text((8,8),f'DEVELOPMENT VALIDATION — {name}',fill='black')
 for i,(im,label) in enumerate(zip(panels,labels)):
  x=i%2*512;y=30+i//2*265;canvas.paste(Image.fromarray(im).resize((512,256)),(x,y));d.text((x+5,y+5),label,fill='white',stroke_width=2,stroke_fill='black')
 return canvas
def main():
 verification=verify_predicted_gate();cfg,records=setup();rows=[];components_out=[];widths={'native':{'all':[],'non_flooded':[],'flooded':[]},'input512':{'all':[],'non_flooded':[],'flooded':[]}};bucket_stats={k:{'gt_pixels':0,'covered_pixels':0,'components':0,'detected_components':0,'flooded_pixels':0,'flooded_covered':0} for k in ('very_thin_1px','thin_2px','medium_3_4px','wide_ge5px')};viz=[];(OUT/'visualizations').mkdir(parents=True,exist_ok=True)
 def bucket(w):return 'very_thin_1px' if w<=1 else ('thin_2px' if w<=2 else ('medium_3_4px' if w<=4 else 'wide_ge5px'))
 for area,row in records['validation']:
  pre,post,y,v=base.cached_pair(area,row,512);valid=v.numpy().astype(bool);road=((y[2]>0)|(y[3]>0)).numpy()&valid;flood=(y[3]>0).numpy()&valid;p=np.load(ROOT/'experiments/two-stage/predicted-gate-20260912/predictions'/f'{Path(row["label"]).stem}.npz')['road_probability'];gate=(p>=TH)&valid
  native,meta=native_masks(area,row)
  for space,masks in [('native',native),('input512',np.stack(((y[2]>0).numpy(),(y[3]>0).numpy())))]:
   for key,mask in [('non_flooded',masks[0]),('flooded',masks[1]),('all',masks[0]|masks[1])]:widths[space][key].extend(width_samples(mask)[0].tolist())
  labels,count=components(road);pl,pc=components(gate);per=[]
  for c in range(1,count+1):
   region=labels==c;ws,depth,sk=width_samples(region);w=float(np.median(ws)) if len(ws) else 1.;isf=bool((region&flood).any());touch,near_invalid,black=border_flags(region,valid,pre.numpy(),post.numpy());covered=int((region&gate).sum());area_px=int(region.sum());det=covered>0;partial=det and covered<area_px
   rec={'sample_id':Path(row['label']).stem,'component_id':c,'area_pixels':area_px,'estimated_width_px':w,'estimated_length_px':int(sk.sum()),'flood_status':'flooded' if isf else 'non_flooded','touches_image_border':touch,'near_valid_mask_edge':near_invalid,'near_black_border':black,'mean_stage1_probability':float(p[region].mean()),'max_stage1_probability':float(p[region].max()),'covered_pixels':covered,'gate_recall':covered/area_px,'detected':det,'partially_detected':partial,'missed':not det};components_out.append(rec);per.append(rec);b=bucket(w);bucket_stats[b]['gt_pixels']+=area_px;bucket_stats[b]['covered_pixels']+=covered;bucket_stats[b]['components']+=1;bucket_stats[b]['detected_components']+=int(det);bucket_stats[b]['flooded_pixels']+=int((region&flood).sum());bucket_stats[b]['flooded_covered']+=int((region&flood&gate).sum())
  mt=metric(road,gate);rows.append({'sample_id':Path(row['label']).stem,'gt_road_pixels':int(road.sum()),'predicted_road_pixels':int(gate.sum()),'gt_road_components':count,'predicted_road_components':pc,'road_gate_recall':mt['recall'],'flooded_road_gate_recall':float((flood&gate).sum()/flood.sum()) if flood.any() else None,'road_precision':mt['precision'],'road_iou':mt['iou'],'false_negative_road_pixels':mt['false_negative_pixels'],'false_positive_road_pixels':mt['false_positive_pixels'],'gt_road_probability':prob_summary(p,road,valid),'false_negative_probability':prob_summary(p,road&~gate,valid),'source_width':meta['width'],'source_height':meta['height'],'model_width':512,'model_height':512,'resize_scale_x':512/meta['width'],'resize_scale_y':512/meta['height']})
 # finalize buckets
 for x in bucket_stats.values():x['gate_recall']=x['covered_pixels']/x['gt_pixels'] if x['gt_pixels'] else None;x['component_detection_rate']=x['detected_components']/x['components'] if x['components'] else None;x['flooded_road_gate_recall']=x['flooded_covered']/x['flooded_pixels'] if x['flooded_pixels'] else None
 width_report={space:{kind:summarize(vals) for kind,vals in groups.items()} for space,groups in widths.items()};write(OUT/'road-width-audit.json',{'method':'Chebyshev erosion distance; full width=2*depth-1 sampled at skeleton pixels','pipeline':'full native 1300x1300 image resized directly to 512x512; no crop','resize_scale':512/1300,'statistics':width_report})
 write(OUT/'per-image.json',rows);write(OUT/'road-components.json',components_out);write(OUT/'width-bucket-gate-recall.json',bucket_stats);write(OUT/'closure-verification.json',verification)
 with (OUT/'per-image.csv').open('w',newline='',encoding='utf-8-sig') as f:
  cols=[k for k in rows[0] if not isinstance(rows[0][k],dict)];w=csv.DictWriter(f,cols);w.writeheader();w.writerows([{k:r[k] for k in cols} for r in rows])
 with (OUT/'road-components.csv').open('w',newline='',encoding='utf-8-sig') as f:w=csv.DictWriter(f,components_out[0].keys());w.writeheader();w.writerows(components_out)
 enc={'architecture':'SiamUnet_diff','max_pool_stages':4,'spatial_scales':[1,.5,.25,.125,.0625],'theoretical_support_pixels':{str(w):[w,w/2,w/4,w/8,w/16] for w in (1,2,3,4)},'interpretation':'Geometric support estimate only; not measured feature activation.'};write(OUT/'encoder-scale-audit.json',enc)
 # deterministic visualization selection: worst, median, best plus all flooded-road positives
 ranked=sorted((x for x in rows if x['road_gate_recall'] is not None),key=lambda x:x['road_gate_recall']);chosen={ranked[0]['sample_id'],ranked[len(ranked)//2]['sample_id'],ranked[-1]['sample_id']}|{x['sample_id'] for x in rows if x['flooded_road_gate_recall'] is not None}
 for area,row in records['validation']:
  name=Path(row['label']).stem
  if name not in chosen:continue
  pre,post,y,v=base.cached_pair(area,row,512);p=np.load(ROOT/'experiments/two-stage/predicted-gate-20260912/predictions'/f'{name}.npz')['road_probability'];render(name,pre.numpy(),post.numpy(),((y[2]>0)|(y[3]>0)).numpy(),p,v.numpy().astype(bool)).save(OUT/'visualizations'/f'{name}.png');viz.append(name)
 # Training gate: ordinary proportional shrink is insufficient evidence by itself.
 # Require material collapse to <=4 px (>=10% of skeleton samples), or >=0.10
 # lower recall for represented thin buckets than wide components.
 native_med=width_report['native']['all']['p50'];input_med=width_report['input512']['all']['p50'];thin_num=sum(bucket_stats[k]['covered_pixels'] for k in ('very_thin_1px','thin_2px'));thin_den=sum(bucket_stats[k]['gt_pixels'] for k in ('very_thin_1px','thin_2px'));thin_recall=thin_num/thin_den if thin_den else None;wide_recall=bucket_stats['wide_ge5px']['gate_recall'];collapsed_ratio=width_report['input512']['all']['width_le_4px_ratio'];supported=collapsed_ratio>=.10 or (thin_recall is not None and wide_recall is not None and wide_recall-thin_recall>=.10)
 summary={'input_representation':'full-image resize 1300x1300 -> 512x512','native_median_width_px':native_med,'input_median_width_px':input_med,'median_width_shrink_ratio':native_med/input_med if input_med else None,'input_width_le_4px_ratio':collapsed_ratio,'thin_1_2px_gate_recall':thin_recall,'wide_ge5px_gate_recall':wide_recall,'resolution_hypothesis_supported':supported,'stage1_e_authorized_by_audit':supported,'decision_basis':'Proportional shrink observed, but material <=4px collapse or width-related recall degradation is required before high-resolution training.','visualized_samples':sorted(viz),'production_ready':False,'blind_holdout_used':False,'louisiana_used':False};write(OUT/'audit-summary.json',summary);print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
