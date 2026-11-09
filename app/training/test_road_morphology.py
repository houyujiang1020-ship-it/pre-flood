import unittest
import numpy as np
from road_morphology import morphology,components,skeletonize
class RoadMorphologyTests(unittest.TestCase):
    def test_exact(self):
        m=np.zeros((15,15),bool);m[6:9,2:13]=1
        r=morphology(m,m)
        self.assertEqual(r['gt_components'],1);self.assertEqual(r['skeleton_recall'],1)
        self.assertEqual(r['fragments_per_matched_gt'],1)
    def test_fragmented(self):
        g=np.zeros((9,15),bool);g[4,1:14]=1;p=g.copy();p[:,7]=0
        r=morphology(g,p);self.assertEqual(r['pred_components'],2);self.assertEqual(r['excess_matched_fragments'],1)
        self.assertLess(r['skeleton_recall'],1)
    def test_empty(self):
        g=np.zeros((8,8),bool);r=morphology(g,g)
        self.assertIsNone(r['skeleton_recall']);self.assertEqual(r['gt_components'],0)
    def test_eight_connected(self):
        g=np.eye(9,dtype=bool);self.assertEqual(components(g)[1],1)
    def test_mask(self):
        g=np.ones((8,8),bool);v=np.zeros_like(g)
        self.assertEqual(morphology(g,g,v)['pred_components'],0)
    def test_skeleton_subset_and_idempotent(self):
        g=np.zeros((12,12),bool);g[2:10,4:8]=1;s=skeletonize(g)
        self.assertTrue(s.any());self.assertTrue((~s|g).all());self.assertTrue(np.array_equal(s,skeletonize(s)))
if __name__=='__main__':unittest.main()
