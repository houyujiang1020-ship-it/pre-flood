import unittest,json,tempfile
from pathlib import Path
import torch
from road_overlap_loss import road_tversky_loss,overlap_components,assert_d_configuration
from train_full import masked_loss
class RoadLossTests(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(17)
        self.y=torch.randint(2,(1,4,4,4)).float();self.m=torch.ones(1,4,4);self.z=torch.randn_like(self.y)
    def test_perfect(self):
        z=(self.y*2-1)*50
        self.assertLess(road_tversky_loss(z,self.y,self.m).item(),1e-6)
    def test_all_zero_prediction(self):
        self.assertTrue(torch.isfinite(road_tversky_loss(torch.full_like(self.y,-50),self.y,self.m)))
    def test_all_one_prediction(self):
        self.assertTrue(torch.isfinite(road_tversky_loss(torch.full_like(self.y,50),self.y,self.m)))
    def test_empty_road_gt(self):
        y=self.y.clone();y[:,2:]=0
        a=road_tversky_loss(torch.full_like(y,-10),y,self.m)
        b=road_tversky_loss(torch.full_like(y,10),y,self.m)
        self.assertTrue(torch.isfinite(a+b));self.assertGreater(b.item(),a.item())
    def test_nonempty_road_gt(self):
        y=self.y.clone();y[:,2:]=1
        self.assertTrue(torch.isfinite(road_tversky_loss(self.z,y,self.m)))
    def test_valid_mask_exclusion_and_grad(self):
        m=self.m.clone();m[:,:,0]=0
        z=self.z.clone().requires_grad_();a=road_tversky_loss(z,self.y,m);a.backward()
        self.assertEqual(z.grad[:,:,:,0].abs().sum().item(),0)
        changed=self.z.clone();changed[:,:,:,0]=100
        y=self.y.clone();y[:,:,:,0]=1-y[:,:,:,0]
        self.assertEqual(a.item(),road_tversky_loss(changed,y,m).item())
    def test_building_loss_and_gradient_unchanged(self):
        a=self.z.clone().requires_grad_();b=self.z.clone().requires_grad_()
        masked_loss(a,self.y,self.m,dice_weight=.5).backward();road_tversky_loss(b,self.y,self.m).backward()
        self.assertTrue(torch.equal(a.grad[:,:2],b.grad[:,:2]))
        dice,replaced=overlap_components(self.z,self.y,self.m)
        self.assertTrue(torch.equal(dice[:2],replaced[:2]))
    def test_road_loss_changes(self):
        dice,replaced=overlap_components(self.z,self.y,self.m)
        self.assertFalse(torch.allclose(dice[2:],replaced[2:]))
    def test_symmetric_equivalence(self):
        self.assertTrue(torch.allclose(masked_loss(self.z,self.y,self.m,dice_weight=.5),road_tversky_loss(self.z,self.y,self.m,alpha=.5,beta=.5),atol=1e-7))
    def test_alpha_fp_beta_fn(self):
        y=torch.zeros(1,4,1,2);y[:,:,:,0]=1
        p=torch.tensor([.2,.1]).repeat(1,4,1,1);z=torch.logit(p);m=torch.ones(1,1,2)
        _,r=overlap_components(z,y,m)
        expected=1-(.2+.5)/(.2+.4*.1+.6*.8+.5)
        self.assertAlmostEqual(r[2].item(),expected,places=6)
    def test_nonzero_finite_gradient(self):
        z=self.z.clone().requires_grad_();road_tversky_loss(z,self.y,self.m).backward()
        self.assertTrue(torch.isfinite(z.grad).all());self.assertGreater(z.grad.abs().sum().item(),0)
    def test_empty_mask_rejected(self):
        with self.assertRaises(ValueError):road_tversky_loss(self.z,self.y,self.m*0)
    def test_chinese_path(self):
        with tempfile.TemporaryDirectory(prefix='道路损失') as d:
            p=Path(d)/'张量.pt';torch.save({'z':self.z,'y':self.y,'m':self.m},p)
            v=torch.load(p,weights_only=True)
            self.assertEqual(road_tversky_loss(v['z'],v['y'],v['m']).item(),road_tversky_loss(self.z,self.y,self.m).item())
    def test_config_and_undeclared_change(self):
        root=Path(__file__).resolve().parents[2]
        location=json.loads((root/'experiments/diagnostics/experiment-d-preflight-20260912/run-location.json').read_text())
        c=json.loads((root/location['config']).read_text());b=json.loads((root/'models/candidates/germany-reviewed-v1/candidate_manifest.json').read_text())['training_configuration']
        assert_d_configuration(c,b)
        for k,value in [('learning_rate',.001),('dice_weight',.7),('epochs',41),('sampler',{}),('seed',5)]:
            with self.assertRaises(ValueError):assert_d_configuration({**c,k:value},b)
if __name__=='__main__':unittest.main()
