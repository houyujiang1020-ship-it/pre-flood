import copy
import json
import unittest
from pathlib import Path

import torch
from train_full import masked_loss, split_rows

ROOT = Path(__file__).resolve().parents[2]


class TrainingChecks(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / 'config/training.example.json').read_text(encoding='utf-8'))

    def test_official_pair_splits(self):
        splits = split_rows(self.config, ROOT)
        self.assertEqual([len(splits[name]) for name in ('train', 'validation', 'test')], [4, 1, 1])

    def test_leakage_is_rejected(self):
        self.config['splits']['validation'] = [copy.deepcopy(self.config['splits']['train'][0])]
        with self.assertRaisesRegex(ValueError, 'leakage'):
            split_rows(self.config, ROOT)

    def test_empty_supervision_rejected(self):
        with self.assertRaisesRegex(ValueError, 'valid supervision'):
            masked_loss(torch.zeros(1, 4, 32, 32), torch.zeros(1, 4, 32, 32), torch.zeros(1, 32, 32))

    def test_loss_and_gradient_are_finite(self):
        logits = torch.zeros(1, 4, 32, 32, requires_grad=True)
        loss = masked_loss(logits, torch.zeros_like(logits), torch.ones(1, 32, 32))
        loss.backward()
        self.assertTrue(torch.isfinite(loss))
        self.assertTrue(torch.isfinite(logits.grad).all())


if __name__ == '__main__':
    unittest.main()
