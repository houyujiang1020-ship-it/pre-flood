import json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import gate5_analysis
import validate_gate5

class Gate5Tests(unittest.TestCase):
    def test_missing_required_role_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"manifest.json"; p.write_text(json.dumps({"analysis_mode":"GROUND_TRUTH_VALIDATION","inputs":[]}),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"required roles"): gate5_analysis.load_manifest(p)
    def test_ai_mode_rejected_by_reference_analyzer(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"manifest.json"
            p.write_text(json.dumps({"analysis_mode":"AI_PREDICTION","inputs":[{"role":x} for x in gate5_analysis.REQUIRED_ROLES]}),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"GROUND_TRUTH_VALIDATION"): gate5_analysis.analyze(p,Path(d)/"out")
    def test_query_failure_cannot_become_zero(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"manifest.json"
            p.write_text(json.dumps({"analysis_mode":"GROUND_TRUTH_VALIDATION","inputs":[{"role":x,"path":"missing"} for x in gate5_analysis.REQUIRED_ROLES]}),encoding="utf-8")
            manifest=gate5_analysis.load_manifest(p)
            with self.assertRaises(FileNotFoundError): gate5_analysis.verify_inputs(manifest,p)
    def test_blocked_run_fails_gate(self):
        with tempfile.TemporaryDirectory() as d:
            run=Path(d); (run/"damage_analysis.html").write_text("x")
            (run/"damage_analysis.json").write_text(json.dumps({"analysis_mode":"GROUND_TRUTH_VALIDATION","measurements":{"building_entities":20,"road_entities":20,"continuous_flood_area_m2":None,"blocked_roads":None},"risk":{"status":"BLOCKED"},"blockers":[{}],"damage_analysis_completed":False}))
            (run/"entity-validation.json").write_text(json.dumps({"building_sample_count":20,"road_sample_count":20,"mapgis_gui_validated":False}))
            for name in ("community_analysis.json","population_analysis.json","risk-breakdown.json","environment.json","plugin-build-manifest.json","dataset-manifest.json"):
                (run/name).write_text("{}")
            (run/"gui-evidence-manifest.json").write_text(json.dumps({"mode":"GROUND_TRUTH_VALIDATION","screenshots":[]}))
            errors=validate_gate5.validate(run)
            self.assertIn("risk inputs/results incomplete",errors); self.assertIn("MapGIS GUI validation missing",errors)

if __name__ == "__main__": unittest.main()
