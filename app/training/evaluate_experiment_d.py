"""Frozen D evaluation, original calibration/OOF code, raw validation probabilities."""
import json,runpy,sys
from pathlib import Path
import numpy as np
import torch
import train_full as t
from model_factory import build_siamunet
from road_morphology import morphology
ROOT=Path(__file__).resolve().parents[2]
def main():
    torch.set_num_threads(4)
    loc=json.loads((ROOT/'experiments/diagnostics/experiment-d-preflight-20260912/run-location.json').read_text());out=ROOT/loc['output_dir'];config_path=ROOT/loc['config']
    config=json.loads(config_path.read_text());assert not config['splits']['test']
    assert all(x['area']=='Germany_Training_Public' for v in config['splits'].values() for x in v)
    t.validate_frozen_dataset(config,ROOT);t.DISK_CACHE=ROOT/config['cache_dir'];records=t.split_rows(config,ROOT)['validation']
    cp=torch.load(out/'best_model.pth',weights_only=True,map_location='cpu')
    source=ROOT/'upstream/SpaceNet8/baseline/models/other/siamunetdif.py'
    model=build_siamunet(source,'groupnorm',8).cuda().eval();model.load_state_dict(cp['state_dict'])
    prior=json.loads((ROOT/'models/experiments/germany-reviewed-gn-class-aware-sampler-20260912/evaluation.json').read_text())
    entry={'checkpoint_sha256':t.file_sha256(out/'best_model.pth'),'epoch':cp['epoch']}
    for key,thresholds in [('A_threshold_0.5',[.5]*4),('B_frozen_development_thresholds',[.54,.45,.18,.25])]:
        metrics=t.evaluate(model,records,512,'cuda',thresholds);metrics['macro_iou']=sum(metrics['class_iou'].values())/4
        entry[key]={'thresholds':thresholds,'metrics':metrics}
    prior['models']['experiment_d']=entry
    prior['scope']='Germany development validation only; prior model metrics copied read-only from verified C evaluation; no independent accuracy claim'
    (out/'evaluation.json').write_text(json.dumps(prior,indent=2),encoding='utf-8')
    del model
    for script,filename in [('calibrate_thresholds.py','development-calibration.json'),('cross_validate_thresholds.py','threshold-oof.json')]:
        sys.argv=[script,'--config',str(config_path),'--checkpoint',str(out/'best_model.pth'),'--output',str(out/filename)]
        runpy.run_path(str(ROOT/'app/training'/script),run_name='__main__')
    oof=json.loads((out/'threshold-oof.json').read_text())
    for path in [ROOT/'experiments/diagnostics/germany-reviewed-threshold-oof-20260912.json',ROOT/'models/experiments/germany-reviewed-gn-class-aware-sampler-20260912/threshold-oof.json']:
        other=json.loads(path.read_text())
        for a,b in zip(oof['folds'],other['folds']):assert a['held_labels']==b['held_labels'] and a['calibration_labels']==b['calibration_labels']
    diag=ROOT/'experiments/diagnostics/experiment-d-road-morphology-20260912';diag.mkdir(parents=True,exist_ok=True)
    mor={'scope':'Germany development validation, valid mask applied; 8-connected components, Zhang-Suen GT skeleton; no GIS entity claims','thresholds':{'A':[.5]*4,'B':[.54,.45,.18,.25]},'models':{}}
    for name,path in [('old_sampler',ROOT/'models/experiments/germany-reviewed-gn-sampler-20260912/best_model.pth'),('experiment_d',out/'best_model.pth')]:
        cp=torch.load(path,weights_only=True,map_location='cpu');model=build_siamunet(source,'groupnorm',8).cuda().eval();model.load_state_dict(cp['state_dict'])
        predout=diag/'validation-predictions'/name;predout.mkdir(parents=True,exist_ok=True)
        rows=[]
        with torch.inference_mode():
            for area,row in records:
                pre,post,truth,valid=t.cached_pair(area,row,512)
                assert set(torch.unique(valid).tolist()) <= {0.,1.}
                probability=model(pre[None].cuda(),post[None].cuda()).sigmoid()[0].cpu().numpy();y=truth.numpy()>0;mask=valid.numpy()>0
                np.savez_compressed(predout/(Path(row['label']).stem+'.npz'),probability=probability,truth=y,valid=mask)
                for strategy,thresholds in mor['thresholds'].items():
                    for c in [2,3]:
                        measures=morphology(y[c],probability[c]>thresholds[c],mask)
                        rows.append({'label':row['label'],'strategy':strategy,'class':t.CLASSES[c],**measures})
                print(name,row['label'],'diagnosed',flush=True)
        mor['models'][name]={'checkpoint_sha256':t.file_sha256(path),'per_tile':rows}
        del model
    (diag/'morphology.json').write_text(json.dumps(mor,indent=2),encoding='utf-8')
    h=json.loads((out/'history.json').read_text());assert len(h)==40
    (out/'learning-curves.json').write_text(json.dumps([{'epoch':r['epoch'],'train_loss':r['train_loss'],'validation_BCE':r['validation']['loss'],'validation_macro_iou':r['validation']['macro_iou'],'training_metrics':r['training_metrics'],'validation':r['validation']} for r in h],indent=2),encoding='utf-8')
    print('D evaluation and raw diagnostic collection complete',flush=True)
if __name__=='__main__':main()
