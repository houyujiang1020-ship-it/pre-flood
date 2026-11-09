import unittest
import numpy as np
from analyze_experiment_d import ranking
class RankingTests(unittest.TestCase):
    def test_perfect(self):
        r=ranking(np.array([.9,.8]),np.array([.2,.1]));self.assertEqual(r['average_precision_exact_ties'],1);self.assertEqual(r['ranking_auc_auxiliary'],1)
    def test_ties(self):
        r=ranking(np.array([.9,.8]),np.array([.8,.1]));self.assertAlmostEqual(r['average_precision_exact_ties'],5/6);self.assertAlmostEqual(r['ranking_auc_auxiliary'],.875)
    def test_monotone_invariance(self):
        p=np.array([.1,.7,.9]);n=np.array([.1,.2,.8]);a=ranking(p,n);b=ranking(p*p,n*n);self.assertEqual(a,b)
if __name__=='__main__':unittest.main()
