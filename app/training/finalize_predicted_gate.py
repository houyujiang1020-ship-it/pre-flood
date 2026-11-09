"""Finalize predicted-gate artifacts without modifying frozen model inputs."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];RUN=ROOT/'experiments/two-stage/predicted-gate-20260912'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 required=['threshold-lock.json','hard-gate-evaluation.json','soft-gate-evaluation.json','gate-recall.json','error-decomposition.json','oracle-retention.json','morphology-summary.json','object-component-analysis.json','comparison.json','decision.json']
 missing=[x for x in required if not (RUN/x).is_file()]
 if missing:raise FileNotFoundError(missing)
 decision=json.loads((RUN/'decision.json').read_text(encoding='utf-8'))
 artifacts={str(p.relative_to(RUN)):sha(p) for p in sorted(RUN.rglob('*')) if p.is_file() and p.name!='completion_manifest.json'}
 out={'status':'completed','case':decision['case'],'development_promotion_passed':decision['development_promotion_passed'],'recommended_integration':decision['recommended_integration'],'new_model_training':False,'validation_samples':18,'artifact_sha256':artifacts,'two_stage_feasibility':'completed','predicted_gate_integration':'completed','candidate_result':'retain germany-reviewed-v1 baseline; no predicted-gate candidate promotion','production_ready':False,'blind_holdout_used':False,'louisiana_used':False,'test_used':False}
 (RUN/'completion_manifest.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
 print(json.dumps({k:v for k,v in out.items() if k!='artifact_sha256'},indent=2))
if __name__=='__main__':main()
