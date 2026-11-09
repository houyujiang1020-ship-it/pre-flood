import unittest
import torch
from train_full import configured_loss, masked_loss, road_union_auxiliary_loss


class RoadUnionAuxiliaryTests(unittest.TestCase):
    def test_existing_loss_is_unchanged_when_disabled(self):
        torch.manual_seed(41)
        logits = torch.randn(1, 4, 8, 8)
        truth = torch.randint(0, 2, logits.shape).float()
        valid = torch.ones(1, 8, 8)
        self.assertEqual(configured_loss(logits, truth, valid, 'independent_binary', .5).item(),
                         masked_loss(logits, truth, valid, dice_weight=.5).item())

    def test_auxiliary_uses_either_existing_road_status(self):
        truth = torch.zeros(1, 4, 8, 8)
        truth[:, 2, 1:4, 1:4] = 1
        truth[:, 3, 5:7, 5:7] = 1
        valid = torch.ones(1, 8, 8)
        correct = torch.full_like(truth, -12.0)
        correct[:, 2, 1:4, 1:4] = 12
        correct[:, 3, 5:7, 5:7] = 12
        wrong = torch.full_like(truth, -12.0)
        self.assertLess(road_union_auxiliary_loss(correct, truth, valid).item(), 0.001)
        self.assertGreater(road_union_auxiliary_loss(wrong, truth, valid).item(), 0.8)

    def test_invalid_pixels_cannot_change_loss_or_gradient(self):
        torch.manual_seed(3)
        logits = torch.randn(1, 4, 8, 8, requires_grad=True)
        truth = torch.randint(0, 2, logits.shape).float()
        valid = torch.ones(1, 8, 8)
        valid[:, :, 0] = 0
        value = road_union_auxiliary_loss(logits, truth, valid)
        value.backward()
        self.assertEqual(logits.grad[:, :, :, 0].abs().sum().item(), 0)
        changed = logits.detach().clone()
        changed[:, :, :, 0] = 100
        self.assertAlmostEqual(value.item(), road_union_auxiliary_loss(changed, truth, valid).item(), places=6)


if __name__ == '__main__':
    unittest.main()
