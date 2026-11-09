import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import gate5_phase2 as g

class Phase2Tests(unittest.TestCase):
    def rows(self):
        return [
          {"community_id":"A","community_name":"A","entity_id":"r1","kind":"road","affected":True,"intersection_length_m":40},
          {"community_id":"B","community_name":"B","entity_id":"r1","kind":"road","affected":True,"intersection_length_m":60},
          {"community_id":"A","community_name":"A","entity_id":"b1","kind":"building","affected":True},
          {"community_id":"A","community_name":"A","entity_id":"b2","kind":"building","affected":False}]
    def test_community_spatial_assignment(self): self.assertEqual(["A","B"],[x["community_id"] for x in g.aggregate_community(self.rows())])
    def test_cross_boundary_road_global_dedup(self): self.assertEqual(1,g.global_unique_counts(self.rows())["affected_roads"])
    def test_community_road_length(self): self.assertEqual([40,60],[x["affected_road_length_m"] for x in g.aggregate_community(self.rows())])
    def test_population_aggregation(self):
        x=g.population_grid_aggregate([{"community_id":"A","population":10,"aoi_overlap_fraction":1,"affected_overlap_fraction":.5}])
        self.assertEqual(10,x["total_population_in_analysis_units"]); self.assertEqual(5,x["estimated_affected_population"])
    def test_population_area_weight(self): self.assertEqual(25,g.area_weighted_population(100,5,20))
    def test_missing_population_not_zero(self):
        with self.assertRaises(ValueError): g.area_weighted_population(None,5,20)
    def test_missing_community_not_zero(self):
        with self.assertRaises(ValueError): g.aggregate_community([{"entity_id":"x","kind":"road"}])
    def test_risk_breakdown(self):
        x=g.risk_breakdown({k:.5 for k in g.WEIGHTS}); self.assertEqual(.5,x["score"]); self.assertEqual("HIGH",x["level"])
    def test_report_source_consistency(self):
        s={"source":"VG250","source_url":"u","provider":"BKG","download_date":"d","license":"dl-de/by-2-0","sha256":"h"}
        g.assert_report_sources("VG250 BKG dl-de/by-2-0",[s])
        with self.assertRaises(ValueError): g.assert_report_sources("VG250",[s])
    def test_gui_evidence_manifest_validation(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); p=root/"gui-evidence-manifest.json"; p.write_text(json.dumps({"mode":"GROUND_TRUTH_VALIDATION","screenshots":[]}),encoding="utf-8")
            self.assertEqual(7,len(g.validate_gui_manifest(p,root)))
    def test_dataset_hash_protection(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); f=root/"x"; f.write_text("ok"); m={"inputs":[{"role":"x","path":"x","sha256":g.sha256(f)}]}; g.verify_dataset_hashes(m,root)
            f.write_text("changed")
            with self.assertRaises(ValueError): g.verify_dataset_hashes(m,root)
if __name__=="__main__": unittest.main()
