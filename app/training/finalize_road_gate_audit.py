"""Finalize the no-training Stage1 road gate audit."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'experiments/diagnostics/stage1-road-gate-miss-20260912'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 required=['per-image.csv','per-image.json','road-width-audit.json','width-bucket-gate-recall.json','road-components.csv','road-components.json','encoder-scale-audit.json','audit-summary.json','closure-verification.json']
 missing=[x for x in required if not (OUT/x).is_file()]
 if missing:raise FileNotFoundError(missing)
 summary=json.loads((OUT/'audit-summary.json').read_text(encoding='utf-8'))
 artifacts={str(p.relative_to(OUT)):sha(p) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='completion_manifest.json'}
 result={'status':'completed','diagnostic_only':True,'new_model_training':False,'resolution_hypothesis_supported':summary['resolution_hypothesis_supported'],'stage1_e_run':False,'model_research_phase_paused':True,'artifact_sha256':artifacts,'production_ready':False,'blind_holdout_used':False,'louisiana_used':False}
 (OUT/'completion_manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k!='artifact_sha256'},indent=2))
if __name__=='__main__':main()
