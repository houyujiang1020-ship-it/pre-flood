"""Probability distributions and ranking diagnostics; operates on saved validation only."""
import json,csv
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
CLASSES=['non_flooded_building','flooded_building','non_flooded_road','flooded_road']
def ranking(pos,neg):
    scores=np.concatenate([pos,neg]);truth=np.r_[np.ones(len(pos),np.int8),np.zeros(len(neg),np.int8)]
    order=np.argsort(-scores,kind='stable');s=scores[order];y=truth[order]
    ends=np.r_[np.flatnonzero(s[:-1]!=s[1:]),len(s)-1];tp=np.cumsum(y,dtype=np.int64)[ends]
    recall=tp/len(pos);precision=tp/(ends+1)
    ap=float(np.sum(np.diff(np.r_[0.,recall])*precision))
    sn=np.sort(neg)
    auc=float(np.mean((np.searchsorted(sn,pos,'left')+np.searchsorted(sn,pos,'right'))*.5/len(neg)))
    return {'average_precision_exact_ties':ap,'ranking_auc_auxiliary':auc}
def main():
    folder=ROOT/'experiments/diagnostics/experiment-d-road-morphology-20260912'
    out=ROOT/'experiments/diagnostics/experiment-d-probability-20260912';out.mkdir(parents=True,exist_ok=True)
    result={'scope':'Germany development validation18, valid pixels only; no independent accuracy; no holdout access','methods':{'histogram':'100 bins [0,1], normalized separately for each GT group','PR':'same0.01 threshold grid as baseline, prediction>threshold','AP':'exact score ranking, tied scores grouped, step-integrated precision-recall','AUC':'auxiliary probability a positive outranks a negative; ties half credit','precision_no_predictions':'null in table; conventional precision1 endpoint in plot only'},'models':{}}
    for model in ['old_sampler','experiment_d']:
        arrays=[[[],[]] for _ in CLASSES]
        for path in sorted((folder/'validation-predictions'/model).glob('*.npz')):
            with np.load(path) as data:
                for c in range(4):
                    mask=data['valid'];gt=data['truth'][c];p=data['probability'][c]
                    arrays[c][0].append(p[mask&gt]);arrays[c][1].append(p[mask&~gt])
        values={};target=out/model;target.mkdir(exist_ok=True)
        for c,name in enumerate(CLASSES):
            pos,neg=[np.concatenate(x) for x in arrays[c]];sp,sn=np.sort(pos),np.sort(neg)
            np.savez_compressed(target/(name+'-probabilities.npz'),positive=pos,negative=neg)
            bins=np.linspace(0,1,101);ph=np.histogram(pos,bins)[0];nh=np.histogram(neg,bins)[0]
            rows=[]
            for threshold in np.linspace(0,1,101):
                tp=len(pos)-int(np.searchsorted(sp,threshold,'right'));fp=len(neg)-int(np.searchsorted(sn,threshold,'right'))
                rows.append({'threshold':float(threshold),'tp':tp,'fp':fp,'fn':len(pos)-tp,'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/len(pos),'iou':tp/(len(pos)+fp),'f1':2*tp/(len(pos)+tp+fp)})
            with (target/(name+'-precision-recall-threshold.csv')).open('w',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
            values[name]={'positive_count':len(pos),'negative_count':len(neg),'prevalence':len(pos)/(len(pos)+len(neg)),'positive_quantiles':dict(zip(['p05','p25','p50','p75','p95'],np.quantile(pos,[.05,.25,.5,.75,.95]).tolist())),'negative_quantiles':dict(zip(['p05','p25','p50','p75','p95'],np.quantile(neg,[.05,.25,.5,.75,.95]).tolist())),'histogram_edges':bins.tolist(),'positive_histogram':ph.tolist(),'negative_histogram':nh.tolist(),'binned_distribution_overlap':float(np.minimum(ph/len(pos),nh/len(neg)).sum()),'threshold_table':rows,**ranking(pos,neg)}
            print(model,name,values[name]['average_precision_exact_ties'],flush=True)
        result['models'][model]=values
    (out/'probability-comparison.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    mor=json.loads((folder/'morphology.json').read_text())
    for model,data in mor['models'].items():
        data['aggregate']={}
        for strategy in ['A','B']:
            data['aggregate'][strategy]={}
            for c in CLASSES[2:]:
                rows=[r for r in data['per_tile'] if r['strategy']==strategy and r['class']==c]
                keys=['gt_components','pred_components','pred_components_ge3pixels','gt_skeleton_pixels','skeleton_covered_pixels','skeleton_covered_within_1px','gt_components_matched','matched_fragment_pairs','excess_matched_fragments','unmatched_pred_components']
                totals={k:sum(r[k] for r in rows) for k in keys}
                totals['skeleton_recall']=totals['skeleton_covered_pixels']/totals['gt_skeleton_pixels']
                totals['skeleton_recall_1px']=totals['skeleton_covered_within_1px']/totals['gt_skeleton_pixels']
                totals['fragments_per_matched_gt']=totals['matched_fragment_pairs']/totals['gt_components_matched'] if totals['gt_components_matched'] else None
                totals['uncovered_gt_fraction']=1-totals['gt_components_matched']/totals['gt_components']
                data['aggregate'][strategy][c]=totals
    (folder/'morphology-summary.json').write_text(json.dumps(mor,indent=2),encoding='utf-8')
if __name__=='__main__':main()
