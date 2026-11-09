"""Create a fresh preregistration; never reuse an existing experiment directory."""
import json,hashlib,subprocess
from pathlib import Path
from road_overlap_loss import assert_d_configuration
ROOT=Path(__file__).resolve().parents[2]
def main():
    mpath=ROOT/'models/candidates/germany-reviewed-v1/candidate_manifest.json'
    m=json.loads(mpath.read_text());b=m['training_configuration'];c=dict(b)
    name='germany-reviewed-gn-road-tversky-20260912';out=ROOT/'models/experiments'/name
    version=1
    while out.exists():
        version+=1;out=ROOT/'models/experiments'/(name+f'-v{version}')
    c.update(model_id=out.name,output_dir=out.relative_to(ROOT).as_posix(),road_overlap_loss={'type':'road_tversky_replacement','channels':[2,3],'alpha_fp':.4,'beta_fn':.6,'smoothing':.5})
    assert_d_configuration(c,b)
    audit=json.loads((ROOT/'experiments/diagnostics/experiment-d-preflight-20260912/loss-audit.json').read_text());assert audit['status']=='passed'
    out.mkdir(exist_ok=False)
    source_paths=['app/training/train_experiment_d.py','app/training/road_overlap_loss.py','app/training/train_full.py','app/training/positive_sampler.py','app/training/train_smoke.py','app/training/model_factory.py','app/training/calibrate_thresholds.py','app/training/cross_validate_thresholds.py','upstream/SpaceNet8/baseline/models/other/siamunetdif.py']
    manifest={'status':'preregistered_before_training','candidate_type':'development','production_ready':False,'baseline_manifest_sha256':hashlib.sha256(mpath.read_bytes()).hexdigest(),'source_git_hash':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'git_worktree_dirty':bool(subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,text=True).strip()),'loss_source_sha256':hashlib.sha256((ROOT/'app/training/road_overlap_loss.py').read_bytes()).hexdigest(),'split_sha256':m['split_sha256'],'baseline_configuration':b,'experiment_configuration':c,'configuration_diff':{k:{'baseline':b.get(k),'D':c[k]} for k in c if c[k]!=b.get(k)},'only_core_variable':'road overlap Dice replaced by Tversky (FP alpha0.4/FN beta0.6), smooth0.5 equivalent to Dice smooth1 at alpha=beta0.5','administrative_differences':['model_id','output_dir'],'instrumentation':'Online per-class train metrics from same forward logits, detached; no extra RNG or training forward. Validation loss remains BCE only. Separate runner leaves C and shared trainer untouched.','source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in source_paths},'promotion_policy':{'type':'conservative development decision; not statistical significance','required':'At least one road IoU improves >=0.01 at frozen thresholds AND OOF; other road decline <=0.005 and flooded building decline <=0.01 in both; no road collapse at0.5; ranking/morphology must support interpretation. Reject otherwise.','ranking':'Exact tied-score average precision and probability separation; calibration-invariant ranking comparison.','morphology':'8-connected components, exact GT Zhang-Suen skeleton recall and one-pixel tolerance; matched predicted fragments per GT component plus unmatched GT fraction. No GIS entity claim.'},'blind_holdout_used':False,'Louisiana_used':False,'test_used':False,'no_parameter_search':True}
    (out/'experiment_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    configpath=ROOT/'config'/('training.'+out.name+'.json');configpath.write_text(json.dumps(c,indent=2),encoding='utf-8')
    (ROOT/'experiments/diagnostics/experiment-d-preflight-20260912/run-location.json').write_text(json.dumps({'output_dir':str(out.relative_to(ROOT)),'config':str(configpath.relative_to(ROOT))}),encoding='utf-8')
    print(str(out))
if __name__=='__main__':main()
