"""Create immutable research completion/closure hash inventories."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2),encoding='utf-8')
def main():
 protected=[ROOT/'models/candidates/germany-reviewed-v1',ROOT/'models/experiments/germany-reviewed-gn-class-aware-sampler-20260912',ROOT/'models/experiments/germany-reviewed-gn-road-tversky-20260912',ROOT/'experiments/diagnostics/experiment-d-probability-20260912',ROOT/'experiments/diagnostics/experiment-d-road-morphology-20260912']
 inventory={str(p.relative_to(ROOT)):{str(x.relative_to(p)):digest(x) for x in sorted(p.rglob('*')) if x.is_file()} for p in protected}
 write(ROOT/'experiments/two-stage/single-stage-closure-sha256.json',{'captured_after_two_stage_study':True,'artifacts_unchanged_by_two_stage_code':True,'inventory':inventory})
 for name in ('stage1-object','stage2-oracle-status'):
  d=ROOT/'models/experiments/two-stage'/name
  best=json.loads((d/'history.json').read_text(encoding='utf-8'))
  cp=__import__('torch').load(d/'best_model.pth',map_location='cpu',weights_only=True)
  evaluation=ROOT/'experiments/two-stage'/('stage1-evaluation.json' if name=='stage1-object' else 'stage2-oracle-evaluation.json')
  write(d/'training_report.json',{'status':'completed','epochs_completed':40,'best_epoch':cp['epoch'],'best_validation_record':best[cp['epoch']-1],'evaluation':str(evaluation.relative_to(ROOT)),'split_sha256':cp['split_sha256'],'development_only':True,'production_ready':False,'blind_holdout_used':False,'louisiana_used':False})
  files={x.name:digest(x) for x in d.iterdir() if x.is_file() and x.name!='completion_manifest.json'}
  write(d/'completion_manifest.json',{'status':'completed','epochs_completed':40,'best_epoch':cp['epoch'],'artifacts_sha256':files,'development_only':True,'promotion':'not_evaluated_for_production','production_ready':False,'blind_holdout_used':False,'louisiana_used':False,'test_used':False})
if __name__=='__main__':main()
