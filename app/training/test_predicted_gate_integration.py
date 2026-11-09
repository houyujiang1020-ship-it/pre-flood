import hashlib,json,tempfile,unittest
from pathlib import Path
import numpy as np,torch
from predicted_gate_integration import reconstruct_hard,soft_product,binary_metrics,decompose,gate_recall,retention_ratios
from model_factory import build_siamunet
from two_stage_feasibility import SOURCE,ROOT
T={'stage1_object':{'building':.4,'road':.3},'stage2_status':{'building_flood':.2,'road_flood':.6}}
class PredictedGateTests(unittest.TestCase):
 def test_hard_four_class_and_empty_all(self):
  o=np.zeros((2,2,2));s=np.zeros((2,2,2));h,_=reconstruct_hard(o,s,T);self.assertEqual(h.sum(),0)
  o[:]=1;s[0]=1;s[1]=0;h,_=reconstruct_hard(o,s,T);self.assertTrue(h[1].all() and h[2].all());self.assertFalse(h[0].any() or h[3].any())
 def test_soft_product(self):
  o=np.array([[[.5]],[[.8]]]);s=np.array([[[.2]],[[.25]]]);q=soft_product(o,s);np.testing.assert_allclose(q[:,0,0],[.4,.1,.6,.2])
 def test_gate_recall_metrics_and_decomposition(self):
  y=np.zeros((4,1,3),bool);y[3]=1;o=np.array([[[0,0,0]],[[.4,.4,.1]]]);s=np.array([[[0,0,0]],[[.8,.2,.8]]]);d=decompose(y,o,s,T)['flooded_road'];self.assertEqual(d['stage1_gate_missed']['pixels'],1);self.assertEqual(d['gate_passed_status_non_flooded']['pixels'],1);self.assertEqual(d['correctly_classified_flooded']['pixels'],1)
  h,_=reconstruct_hard(o,s,T);self.assertAlmostEqual(gate_recall(y,h,np.ones((1,3),bool))['flooded_road_gate_recall']['recall'],2/3)
 def test_oracle_retention(self):
  self.assertEqual(retention_ratios({'iou':.2,'f1':.4,'ap':.5},{'iou':.4,'f1':.8,'ap':1}),{'iou':.5,'f1':.5,'ap':.5})
 def test_metric_empty_prediction(self):
  z=np.zeros((4,4));y=np.zeros((4,4),bool);y[:,0]=1;m=np.ones(4,bool);r=binary_metrics(z,y,m,[.5]*4);self.assertEqual(r['flooded_road']['recall'],0)
 def test_threshold_lock_and_chinese_path(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'中文阈值.json';p.write_text(json.dumps(T),encoding='utf-8');h=hashlib.sha256(p.read_bytes()).hexdigest();self.assertEqual(len(h),64);self.assertEqual(json.loads(p.read_text(encoding='utf-8')),T)
 def test_checkpoint_identity(self):
  cp=torch.load(ROOT/'models/experiments/two-stage/stage1-object/best_model.pth',map_location='cpu',weights_only=True);self.assertEqual(cp['split_sha256'],'14f57e129972554d64991f956f3e23f29cc947007605e6b052f8b4001ba8e1b1');m=build_siamunet(SOURCE,'groupnorm',8,2);m.load_state_dict(cp['state_dict'])
if __name__=='__main__':unittest.main()
