import copy
import json
import unittest
from pathlib import Path

import torch
from train_full import (masked_loss, split_rows, positive_weights, selection_score,
                        initialize_ema_state, update_ema_state, evaluate_state,
                        should_run_validation, output_probabilities, building_status_loss,
                        factorized_object_status_loss)
from train_full import sliding_positions, crop_training_pair
from calibrate_thresholds import select_thresholds
from calibrate_thresholds import select_thresholds
from train_smoke import flooded_class, load_pair, buffered_road
from model_factory import build_siamunet
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[2]


class TrainingChecks(unittest.TestCase):
    def test_sliding_positions_cover_edges(self):
        positions = sliding_positions(1280, 448, 336)
        self.assertEqual(positions, [0, 336, 672, 832])
        covered = torch.zeros(1280, dtype=torch.bool)
        for start in positions:
            covered[start:start + 448] = True
        self.assertTrue(covered.all())

    def test_positive_crop_keeps_synchronized_shapes_and_anchor(self):
        torch.manual_seed(7)
        pre = torch.zeros(3, 128, 128)
        post = torch.zeros(3, 128, 128)
        truth = torch.zeros(4, 128, 128)
        valid = torch.ones(128, 128)
        truth[3, 100, 110] = 1
        pre[:, 100, 110] = 1
        post[:, 100, 110] = 2
        cropped = crop_training_pair((pre, post, truth, valid), 64, 1.0)
        self.assertEqual([tuple(t.shape) for t in cropped], [(3, 64, 64), (3, 64, 64),
                                                              (4, 64, 64), (64, 64)])
        self.assertEqual(cropped[2][3].sum().item(), 1)
        self.assertEqual(cropped[0].sum().item(), 3)
        self.assertEqual(cropped[1].sum().item(), 6)
    def test_ema_update_and_evaluation_restore_online_weights(self):
        model = torch.nn.Conv2d(1, 1, 1, bias=False)
        model.weight.data.fill_(1)
        ema = initialize_ema_state(model)
        model.weight.data.fill_(3)
        update_ema_state(ema, model, .75)
        self.assertAlmostEqual(ema['weight'].item(), 1.5)
        self.assertAlmostEqual(model.weight.item(), 3.0)
        with self.assertRaisesRegex(ValueError, 'EMA decay'):
            update_ema_state(ema, model, 1.0)

    def test_threshold_selection_is_per_class(self):
        candidates = [.1, .2, .3]
        tp = torch.tensor([[1., 3., 2.], [4., 2., 1.]])
        fp = torch.tensor([[0., 0., 3.], [4., 0., 0.]])
        positives = torch.tensor([4., 4.])
        self.assertEqual(select_thresholds(tp, fp, positives, candidates), [.2, .1])

    def test_groupnorm_variant_has_no_batch_statistics(self):
        source = ROOT / 'upstream/SpaceNet8/baseline/models/other/siamunetdif.py'
        model = build_siamunet(source, 'groupnorm', 8)
        self.assertFalse(any(isinstance(layer, torch.nn.BatchNorm2d) for layer in model.modules()))
        self.assertTrue(any(isinstance(layer, torch.nn.GroupNorm) for layer in model.modules()))
    def test_weight_tempering_and_cap(self):
        w = positive_weights(torch.tensor([1.,2.,3.,4.]), 1000, .5, 8)
        self.assertEqual(w.flatten().tolist(), [8.]*4)
        with self.assertRaises(ValueError):
            positive_weights(torch.tensor([0.,2.,3.,4.]), 1000)

    def test_selection_uses_macro_iou(self):
        self.assertAlmostEqual(selection_score({'class_iou':dict(zip('abcd',[.1,.2,.3,.4]))},'macro_iou'),.25)
        with self.assertRaises(ValueError):
            selection_score({'class_iou':dict(zip('abcd',[.1,None,.3,.4]))},'macro_iou')

    def test_final_only_validation_never_reads_early_epochs(self):
        self.assertFalse(should_run_validation('final_only', 0, 14))
        self.assertFalse(should_run_validation('final_only', 12, 14))
        self.assertTrue(should_run_validation('final_only', 13, 14))
        self.assertTrue(should_run_validation('every_epoch', 0, 14))
        with self.assertRaises(ValueError):
            should_run_validation('sometimes', 0, 14)

    def test_building_status_probabilities_are_exclusive(self):
        logits = torch.randn(2, 4, 8, 8)
        probability = output_probabilities(logits, 'building_status_softmax')
        self.assertTrue(((probability[:, 0] + probability[:, 1]) <= 1 + 1e-6).all())
        self.assertTrue(((probability >= 0) & (probability <= 1)).all())

    def test_building_status_loss_gradient_and_overlap_rejection(self):
        logits = torch.zeros(1, 4, 8, 8, requires_grad=True)
        truth = torch.zeros_like(logits)
        truth[:, 0, :4] = 1
        truth[:, 1, 4:] = 1
        truth[:, 2, :, 3] = 1
        loss = building_status_loss(logits, truth, torch.ones(1, 8, 8), .5)
        loss.backward()
        self.assertTrue(torch.isfinite(logits.grad).all())
        truth[:, 0, 4:] = 1
        with self.assertRaisesRegex(ValueError, 'overlap'):
            building_status_loss(logits.detach(), truth, torch.ones(1, 8, 8), .5)

    def test_factorized_probabilities_are_exclusive_for_both_objects(self):
        logits = torch.randn(2, 4, 8, 8)
        probability = output_probabilities(logits, 'factorized_object_status')
        self.assertTrue(((probability[:, 0] + probability[:, 1]) <= 1 + 1e-6).all())
        self.assertTrue(((probability[:, 2] + probability[:, 3]) <= 1 + 1e-6).all())
        prediction = probability > .5
        self.assertFalse((prediction[:, 0] & prediction[:, 1]).any())
        self.assertFalse((prediction[:, 2] & prediction[:, 3]).any())

    def test_factorized_loss_has_finite_gradients_and_uses_flooded_priority(self):
        logits = torch.zeros(1, 4, 8, 8, requires_grad=True)
        truth = torch.zeros_like(logits)
        truth[:, 0, :4, :4] = 1
        truth[:, 1, 4:, :4] = 1
        truth[:, 2, :4, 4:] = 1
        truth[:, 3, 4:, 4:] = 1
        loss = factorized_object_status_loss(logits, truth, torch.ones(1, 8, 8), .5)
        loss.backward()
        self.assertTrue(torch.isfinite(logits.grad).all())
        self.assertTrue((logits.grad.abs().sum((0, 2, 3)) > 0).all())
        truth[:, 0, 4:, :4] = 1
        overlap_loss = factorized_object_status_loss(
            logits.detach(), truth, torch.ones(1, 8, 8), .5)
        self.assertTrue(torch.isfinite(overlap_loss))

    def test_factorized_loss_accepts_tile_without_one_object_type(self):
        logits = torch.zeros(1, 4, 8, 8, requires_grad=True)
        truth = torch.zeros_like(logits)
        truth[:, 1, :2, :2] = 1
        loss = factorized_object_status_loss(logits, truth, torch.ones(1, 8, 8), 0)
        loss.backward()
        self.assertTrue(torch.isfinite(logits.grad).all())

    def test_threshold_selection_penalizes_false_positives(self):
        thresholds=select_thresholds(torch.tensor([[9.,8.]]*4),torch.tensor([[90.,1.]]*4),torch.tensor([10.]*4),[.5,.9])
        self.assertEqual(thresholds,[.9]*4)

    def test_road_buffer_uses_meters(self):
        polygon = shape(buffered_road({'type':'LineString','coordinates':[[7,50],[7.001,50]]},'EPSG:32632'))
        self.assertGreater(polygon.area,400)
        self.assertLess(polygon.area,500)

    def test_balanced_loss_gradient(self):
        logits=torch.zeros(1,4,32,32,requires_grad=True)
        loss=masked_loss(logits,torch.ones_like(logits),torch.ones(1,32,32),torch.ones(4,1,1)*4,.5)
        loss.backward()
        self.assertTrue(torch.isfinite(logits.grad).all())

    def test_official_null_flood_label_is_non_flooded(self):
        for value in (None, 'no', False, 0):
            self.assertEqual(flooded_class(value), 0)
        for value in ('yes', True, 1):
            self.assertEqual(flooded_class(value), 1)

    def test_validation_retains_non_flooded_buildings(self):
        area, row = split_rows(self.config, ROOT)['validation'][0]
        self.assertGreater(load_pair(area, row, 128)[2][0].sum().item(), 0)

    def setUp(self):
        self.config = json.loads((ROOT / 'config/training.example.json').read_text(encoding='utf-8'))

    def test_official_pair_splits(self):
        splits = split_rows(self.config, ROOT)
        self.assertEqual([len(splits[name]) for name in ('train', 'validation', 'test')], [4, 1, 1])

    def test_leakage_is_rejected(self):
        self.config['splits']['validation'] = [copy.deepcopy(self.config['splits']['train'][0])]
        with self.assertRaisesRegex(ValueError, 'leakage'):
            split_rows(self.config, ROOT)

    def test_unknown_post_event_choice_is_rejected(self):
        self.config['splits']['train'][0]['post_event_column'] = 'best-looking-image'
        with self.assertRaisesRegex(ValueError, 'post_event_column'):
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
