import tempfile, unittest
from pathlib import Path
import torch
from model_factory import build_siamunet
from two_stage_feasibility import SOURCE, derive, loss_fn

class TwoStageTests(unittest.TestCase):
 def fixture(self):
  y=torch.zeros(4,16,16);y[0,1,1]=1;y[1,2,2]=1;y[2,3,3]=1;y[3,4,4]=1;return y,torch.ones(16,16)
 def test_union_and_flood_membership(self):
  y,v=self.fixture();u,_=derive(y,v,1);self.assertTrue(u[0,2,2]);self.assertTrue(u[1,4,4]);self.assertEqual(u.sum().item(),4)
 def test_oracle_gate_and_valid(self):
  y,v=self.fixture();v[4,4]=0;t,m=derive(y,v,2);self.assertEqual(m[1,4,4],0);self.assertEqual(t[1,4,4],1)
 def test_empty_channel_and_loss(self):
  y=torch.zeros(1,2,8,8);m=torch.ones(1,1,8,8);x=torch.zeros_like(y,requires_grad=True);z=loss_fn(x,y,m);z.backward();self.assertTrue(torch.isfinite(z))
 def test_shape_reload_and_inference(self):
  model=build_siamunet(SOURCE,'groupnorm',8,2);a=torch.zeros(1,3,32,32);o=model(a,a);self.assertEqual(tuple(o.shape),(1,2,32,32))
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'x.pth';torch.save(model.state_dict(),p);other=build_siamunet(SOURCE,'groupnorm',8,2);other.load_state_dict(torch.load(p,weights_only=True));self.assertEqual(tuple(other(a,a).shape),(1,2,32,32))

if __name__=='__main__':unittest.main()
