"""Verify and freeze all inputs before predicted-gate evaluation."""
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
RUN=ROOT/'experiments/two-stage/predicted-gate-20260912'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2),encoding='utf-8')
def verify_stage(name):
 d=ROOT/'models/experiments/two-stage'/name;m=json.loads((d/'completion_manifest.json').read_text(encoding='utf-8'))
 bad={f:{'expected':h,'actual':sha(d/f)} for f,h in m['artifacts_sha256'].items() if not (d/f).is_file() or sha(d/f)!=h}
 if bad:raise ValueError(f'{name} frozen artifact mismatch: {bad}')
 return {'directory':str(d.relative_to(ROOT)),'completion_manifest_sha256':sha(d/'completion_manifest.json'),'verified_artifacts':m['artifacts_sha256'],'verification':'passed'}
def main():
 if (RUN/'hard-gate-evaluation.json').exists() or (RUN/'soft-gate-evaluation.json').exists():raise FileExistsError('Evaluation already exists; threshold lock cannot be recreated')
 stages={x:verify_stage(x) for x in ('stage1-object','stage2-oracle-status')}
 supporting=['experiments/two-stage/label-derivation-audit.json','experiments/two-stage/stage1-evaluation.json','experiments/two-stage/stage2-oracle-evaluation.json','experiments/two-stage/single-stage-union-comparison.json']
 closure={'status':'completed','case':'A','promotion_to_predicted_gate':True,'stages':stages,'supporting_sha256':{p:sha(ROOT/p) for p in supporting},'production_ready':False,'blind_holdout_used':False,'louisiana_used':False}
 write(RUN/'feasibility-input-verification.json',closure)
 thresholds={'version':'predicted_gate_thresholds_v1','locked_before_evaluation':True,'source':'existing Germany development calibrations only','stage1_object':{'building':.41,'road':.33},'stage2_status':{'building_flood':.07,'road_flood':.29},'soft_output':{'non_flooded_building':.41*(1-.07),'flooded_building':.41*.07,'non_flooded_road':.33*(1-.29),'flooded_road':.33*.29},'no_post_result_search':True,'split_sha256':'14f57e129972554d64991f956f3e23f29cc947007605e6b052f8b4001ba8e1b1','production_ready':False,'blind_holdout_used':False}
 write(RUN/'threshold-lock.json',thresholds);write(RUN/'threshold-lock.sha256.json',{'path':'threshold-lock.json','sha256':sha(RUN/'threshold-lock.json')})
 decision={'locked_before_evaluation':True,'baseline':{'flooded_building_iou':.10148987174034119,'flooded_road_iou':.05324335768818855,'four_class_macro_iou':.13386830755670175},'PG-A':{'flooded_road_absolute_iou_gain_min':.05,'four_class_macro_iou_gain_min':.01,'flooded_building_iou_drop_max':.03,'meaning':'Promote two-stage as final development candidate if all pass.'},'PG-B':{'oracle_flooded_road_iou_retention_max':.50,'stage1_miss_share_must_exceed_status_error_share':True},'PG-C':{'flooded_road_gate_recall_min':.80,'stage2_status_error_share_must_exceed_stage1_miss_share':True,'predicted_flooded_road_iou_max':.10324335768818855},'hard_vs_soft':'Prefer hard for GIS interpretability unless soft materially improves flooded-road IoU by >=0.03 or AP by >=0.05 without reducing macro IoU/F1 or worsening road morphology.','no_post_result_threshold_or_rule_changes':True,'production_ready':False,'blind_holdout_used':False}
 write(RUN/'predicted-gate-decision.json',decision)
 git=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
 sources=['app/training/two_stage_feasibility.py','app/training/model_factory.py','app/training/train_smoke.py','upstream/SpaceNet8/baseline/models/other/siamunetdif.py']
 candidate={'candidate_type':'development','models':{'stage1':{'checkpoint':'models/experiments/two-stage/stage1-object/best_model.pth','sha256':sha(ROOT/'models/experiments/two-stage/stage1-object/best_model.pth')},'stage2':{'checkpoint':'models/experiments/two-stage/stage2-oracle-status/best_model.pth','sha256':sha(ROOT/'models/experiments/two-stage/stage2-oracle-status/best_model.pth')}},'germany_split_sha256':thresholds['split_sha256'],'source_git_hash':git,'source_file_sha256':{p:sha(ROOT/p) for p in sources},'threshold_lock':str((RUN/'threshold-lock.json').relative_to(ROOT)),'threshold_lock_sha256':sha(RUN/'threshold-lock.json'),'production_ready':False,'blind_holdout_used':False,'louisiana_used':False}
 write(ROOT/'models/candidates/two-stage-development-v1/manifest.json',candidate)
 print(json.dumps({'verification':'passed','threshold_lock_sha256':sha(RUN/'threshold-lock.json'),'stage1_checkpoint_sha256':candidate['models']['stage1']['sha256'],'stage2_checkpoint_sha256':candidate['models']['stage2']['sha256']},indent=2))
if __name__=='__main__':main()
