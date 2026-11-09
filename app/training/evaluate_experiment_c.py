"""Evaluate C at original and frozen development thresholds, then same OOF protocol."""
import json,sys,runpy
from pathlib import Path
import torch
import train_full as t
from model_factory import build_siamunet
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'models/experiments/germany-reviewed-gn-class-aware-sampler-20260912'
def main():
    torch.set_num_threads(4)
    config_path=ROOT/'config/training.germany-reviewed-gn-class-aware-sampler-20260912.json'
    config=json.loads(config_path.read_text());t.validate_frozen_dataset(config,ROOT)
    assert not config['splits']['test']
    assert all(v['area']=='Germany_Training_Public' for s in config['splits'].values() for v in s)
    t.DISK_CACHE=ROOT/config['cache_dir'];records=t.split_rows(config,ROOT)['validation']
    source=ROOT/'upstream/SpaceNet8/baseline/models/other/siamunetdif.py'
    results={'scope':'Germany development validation; not independent accuracy; no test, Louisiana or blind holdout','production_ready':False,'split_sha256':config['frozen_dataset_sha256'],'models':{}}
    for name,folder in [('weighted','germany-reviewed-gn-weighted-20260912'),('old_sampler','germany-reviewed-gn-sampler-20260912'),('class_aware','germany-reviewed-gn-class-aware-sampler-20260912')]:
        path=ROOT/'models/experiments'/folder/'best_model.pth'
        cp=torch.load(path,map_location='cpu',weights_only=True)
        model=build_siamunet(source,cp['normalization'],cp['groupnorm_groups']).cuda().eval();model.load_state_dict(cp['state_dict'])
        entry={'checkpoint_sha256':t.file_sha256(path),'epoch':cp['epoch']}
        for key,thresholds in [('A_threshold_0.5',[.5]*4),('B_frozen_development_thresholds',[.54,.45,.18,.25])]:
            metrics=t.evaluate(model,records,512,'cuda',thresholds)
            metrics['macro_iou']=sum(metrics['class_iou'].values())/4
            entry[key]={'thresholds':thresholds,'metrics':metrics}
        results['models'][name]=entry
        del model
    (OUT/'evaluation.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    for script,filename in [('calibrate_thresholds.py','development-calibration.json'),('cross_validate_thresholds.py','threshold-oof.json')]:
        sys.argv=[script,'--config',str(config_path),'--checkpoint',str(OUT/'best_model.pth'),'--output',str(OUT/filename)]
        runpy.run_path(str(ROOT/'app/training'/script),run_name='__main__')
    h=json.loads((OUT/'history.json').read_text())
    curves=[{'epoch':r['epoch'],'train_loss':r['train_loss'],'validation_loss':r['validation']['loss'],'macro_iou':sum(r['validation']['class_iou'].values())/4,'class_iou':r['validation']['class_iou'],'class_precision':r['validation']['class_precision'],'class_recall':r['validation']['class_recall'],'class_f1':r['validation']['class_f1'],'sample_exposure':r['sampling']['class_sample_exposure_count']} for r in h]
    (OUT/'learning-curves.json').write_text(json.dumps(curves,indent=2),encoding='utf-8')
    print('Evaluation complete',flush=True)
if __name__=='__main__':main()
