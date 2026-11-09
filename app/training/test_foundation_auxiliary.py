import unittest
from pathlib import Path

import torch

from foundation_auxiliary import CHANNELS, make_auxiliary_targets
from train_foundation_aux import build_foundation_model, loss_fn
from xdxd_sn5 import build_xdxd_sn5, freeze_except_output_head, parameter_counts


class FoundationAuxiliaryChecks(unittest.TestCase):
    def test_channels_and_primary_unions(self):
        labels = torch.zeros(4, 32, 32)
        labels[0, 4:10, 4:10] = 1
        labels[1, 14:20, 14:20] = 1
        labels[2, 24, 2:30] = 1
        labels[3, 2:30, 24] = 1
        value = make_auxiliary_targets(labels, torch.ones(32, 32))
        self.assertEqual(tuple(value.shape), (6, 32, 32))
        self.assertEqual(len(CHANNELS), 6)
        self.assertTrue(torch.equal(value[0].bool(), (labels[0] + labels[1]).bool()))
        self.assertTrue(torch.equal(value[3].bool(), (labels[2] + labels[3]).bool()))
        self.assertGreater(value[1].sum(), 0)
        self.assertGreater(value[4].sum(), 0)
        self.assertGreater(value[5].sum(), 0)

    def test_invalid_shape_rejected(self):
        with self.assertRaises(ValueError):
            make_auxiliary_targets(torch.zeros(2, 8, 8), torch.ones(8, 8))

    def test_positive_and_channel_weights_raise_primary_false_negative_cost(self):
        logits = torch.zeros(1, 6, 2, 2)
        truth = torch.zeros_like(logits)
        truth[:, 0] = 1
        valid = torch.ones(1, 2, 2)
        plain = loss_fn(logits, truth, valid, dice_weight=0)
        weighted = loss_fn(logits, truth, valid, dice_weight=0,
                           pos_weight=torch.tensor([3, 1, 1, 1, 1, 1]).reshape(6, 1, 1),
                           channel_weight=torch.tensor([2, .5, .5, 2, .5, .5]))
        self.assertGreater(weighted.item(), plain.item())

    def test_single_unet_forward_preserves_full_resolution(self):
        root = Path(__file__).resolve().parents[2]
        config = {'normalization': 'groupnorm', 'groupnorm_groups': 8,
                  'foundation_architecture': 'single_unet_skip'}
        model = build_foundation_model(root, config).eval()
        with torch.inference_mode():
            output = model(torch.rand(1, 3, 32, 32))
        self.assertEqual(tuple(output.shape), (1, 6, 32, 32))

    def test_xdxd_adapter_replaces_and_freezes_only_output_head(self):
        root = Path(__file__).resolve().parents[2]
        source = root / 'upstream/SpaceNet8/05-motokimura/code/spacenet8_model/models/xdxd_sn5/senet.py'
        model = build_xdxd_sn5(source, len(CHANNELS))
        freeze_except_output_head(model)
        counts = parameter_counts(model)
        self.assertEqual(model.final[-1].out_channels, len(CHANNELS))
        self.assertGreater(counts['total'], counts['trainable'])
        self.assertEqual(counts['trainable'],
                         sum(parameter.numel() for parameter in model.final[-1].parameters()))


if __name__ == '__main__':
    unittest.main()
