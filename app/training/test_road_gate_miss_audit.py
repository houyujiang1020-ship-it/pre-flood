import tempfile,unittest
from pathlib import Path
import numpy as np
from affine import Affine
from road_gate_miss_audit import width_samples,summarize,metric,deterministic_tiles,validate_aligned_patch
from road_morphology import components
class RoadGateAuditTests(unittest.TestCase):
 def test_road_width(self):
  m=np.zeros((20,20),bool);m[5:10,2:18]=1;w,_,_=width_samples(m);self.assertEqual(summarize(w)['p50'],5)
 def test_component_statistics(self):
  m=np.zeros((8,8),bool);m[1:3,1:3]=1;m[5:7,5:7]=1;self.assertEqual(components(m)[1],2)
 def test_native_vs_input_mapping_and_no_fake_upsample(self):
  self.assertEqual(deterministic_tiles(1300,768,128),[0,532]);
  with self.assertRaises(ValueError):deterministic_tiles(512,768,0)
 def test_deterministic_tiling(self):self.assertEqual(deterministic_tiles(1300,512,128),deterministic_tiles(1300,512,128))
 def test_patch_geographic_alignment_and_highres_shape(self):self.assertTrue(validate_aligned_patch((1300,1300),Affine.identity(),(768,768),Affine.translation(10,10)))
 def test_metric_equivalence_and_gate_recall(self):
  y=np.array([[1,1],[0,0]],bool);p=np.array([[1,0],[1,0]],bool);r=metric(y,p);self.assertEqual(r['recall'],.5);self.assertEqual(r['iou'],1/3)
 def test_chinese_path(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'道路宽度.npy';np.save(p,np.ones((2,2)));self.assertEqual(np.load(p).shape,(2,2))
if __name__=='__main__':unittest.main()
