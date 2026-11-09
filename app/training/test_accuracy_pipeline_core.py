"""Focused invariants for pseudo labels, EMA, fusion, and train-only mining."""
import json
from pathlib import Path

import numpy as np
import pytest
import torch

from hard_negative_sampler import load_hard_negatives, resample
from inference_fusion import fuse_probabilities
from mean_teacher import ema_update, paired_weak_strong
from pseudo_label.filter_pseudo_labels import CLASSES, filter_probabilities, masked_pseudo_bce
from pseudo_label.generate_pseudo_labels import forbidden_inputs
from tools.mine_failure_cases import score_masks
from tools.rasterize_gis_labels import read_features
from tools.check_spatial_leakage import audit as audit_spatial_split, positive_overlap
from tools.analyze_road_fp import spatial_counts
from tools.verify_hn_comparability import comparable
from scripts.export_extended_prediction import summarize
from scripts.aggregate_hn_results import selected_row
from scripts.finalize_hn_multiseed import decide as decide_multiseed


def test_pseudo_ignore_and_masked_loss():
    views = np.full((2, 4, 2, 2), 0.5, dtype=np.float32)
    views[:, :, 0, 0] = 0.95
    views[:, :, 0, 1] = 0.02
    mask, stats = filter_probabilities(views, dict.fromkeys(CLASSES, 0.05),
                                       dict.fromkeys(CLASSES, 0.9), 0.001,
                                       np.array([[True, True], [True, False]]))
    assert np.all(mask[:, 0, 0] == 1)
    assert np.all(mask[:, 0, 1] == 0)
    assert np.all(mask[:, 1, :] == 255)
    assert all(value["accepted_pixels"] == 2 for value in stats.values())
    logits = torch.zeros(1, 4, 2, 2, requires_grad=True)
    loss = masked_pseudo_bce(logits, torch.from_numpy(mask[None]))
    assert loss.item() == pytest.approx(np.log(2), rel=1e-5)
    loss.backward()
    assert logits.grad[0, :, 1, :].abs().sum().item() == 0


def test_paired_transform_preserves_temporal_alignment():
    torch.manual_seed(12)
    pre = torch.rand(1, 3, 32, 32) * 0.2
    post = pre + 0.1
    pseudo = torch.zeros(1, 4, 32, 32, dtype=torch.uint8)
    pseudo[:, :, 5, 10] = 1
    weak, strong, selected = paired_weak_strong(pre, post, pseudo, 0.05, 0.05)
    assert torch.allclose(weak[1] - weak[0], torch.full_like(pre, 0.1), atol=1e-6)
    assert strong[0].shape == weak[0].shape
    assert (selected == 1).sum().item() == 4


def test_ema_float_update_and_integer_buffer():
    teacher = torch.nn.BatchNorm2d(2)
    student = torch.nn.BatchNorm2d(2)
    student.weight.data.fill_(3)
    student.num_batches_tracked.fill_(5)
    ema_update(teacher, student, 0.5)
    assert torch.equal(teacher.weight, torch.full_like(teacher.weight, 2))
    assert teacher.num_batches_tracked.item() == 5


def test_soft_fusion_preserves_object_mass():
    object_logits = torch.zeros(1, 2, 4, 4)
    flood_logits = torch.ones(1, 1, 4, 4)
    fused = fuse_probabilities(object_logits, flood_logits, road_dilation_pixels=1)
    assert fused.shape == (1, 4, 4, 4)
    assert torch.allclose(fused[:, 0] + fused[:, 1], torch.full((1, 4, 4), 0.5))
    assert torch.allclose(fused[:, 2] + fused[:, 3], torch.full((1, 4, 4), 0.5))
    assert (fused > 0).all()


def test_mining_counts_and_split_guard(tmp_path: Path):
    result = score_masks(np.array([[0.8, 0.8], [0.1, 0.1]]),
                         np.array([[True, False], [True, False]]),
                         np.ones((2, 2), dtype=bool),
                         np.array([[False, True], [False, False]]), 0.5)
    assert (result["tp"], result["fp"], result["fn"], result["fp_on_normal_road"]) == (1, 1, 1, 1)
    (tmp_path / "metadata.json").write_text(json.dumps({
        "split": "train", "training_eligible_for_mining": False}), encoding="utf-8")
    (tmp_path / "failure_cases.csv").write_text("area,label,fp\nA,1,1\n", encoding="utf-8")
    records = [("/A", {"label": "1"})]
    with pytest.raises(ValueError, match="complete train-only"):
        load_hard_negatives(tmp_path, records, 3)
    (tmp_path / "metadata.json").write_text(json.dumps({
        "split": "train", "training_eligible_for_mining": True}), encoding="utf-8")
    assert load_hard_negatives(tmp_path, records, 3) == {("A", "1")}
    selected, report = resample([0] * 5, records, {("A", "1")}, 3, 42)
    assert selected == [0] * 5 and report["hard_draws"] == 5


def test_geojson_crs_must_be_explicit(tmp_path: Path):
    path = tmp_path / "buildings.geojson"
    path.write_text('{"type":"FeatureCollection","features":[]}', encoding="utf-8")
    with pytest.raises(ValueError, match="vector-crs"):
        read_features(path, None)


def test_pseudo_source_rejects_synthetic_without_flag_and_reserved_test():
    manifest = {"split": "unlabeled_train", "synthetic": True}
    images = [{"pre_image": "not-protected/pre.tif", "post_image": "not-protected/post.tif"}]
    with pytest.raises(ValueError, match="Synthetic"):
        forbidden_inputs(manifest, images, False)
    reserved = [{"pre_image": "11/Louisiana-West_Test_Public/pre.tif",
                 "post_image": "11/Louisiana-West_Test_Public/post.tif"}]
    with pytest.raises(ValueError, match="Protected"):
        forbidden_inputs({"split": "unlabeled_train"}, reserved, False)


def test_extended_prediction_summary_is_object_status_not_water_mask():
    probability = np.full((4, 2, 2), 0.25, dtype=np.float32)
    probability[1, 0, 0] = 0.8
    valid = np.array([[True, False], [True, True]])
    result = summarize(probability, valid)
    assert result["building_probability_mean"] == pytest.approx((0.8 + 0.25 + 0.25) / 3)
    assert "not a continuous flood-water mask" in result["note"]


def test_spatial_leakage_detects_bbox_and_neighbor_even_with_distinct_paths():
    left = {"sample_id": "a", "AOI": "X", "pre_path": "pre-a.tif", "post_path": "post-a.tif",
            "split": "TRAIN_NEW", "bbox": (0, 0, 2, 2), "tile": (1, 2, 3)}
    right = {"sample_id": "b", "AOI": "X", "pre_path": "pre-b.tif", "post_path": "post-b.tif",
             "split": "SPATIAL_VAL_NEW", "bbox": (1, 1, 3, 3), "tile": (1, 3, 3)}
    assert positive_overlap(left["bbox"], right["bbox"])
    result = audit_spatial_split([left], [right], [])
    assert not result["pass"]
    assert len(result["cross_split_bbox_overlap"]) == 1
    assert len(result["cross_split_neighbor_tiles"]) == 1


def test_spatial_fp_near_far_partition():
    predicted = torch.zeros(32, 32, dtype=torch.bool)
    predicted[10, 11] = True
    predicted[30, 30] = True
    roads = torch.zeros_like(predicted)
    roads[10, 10] = True
    result = spatial_counts(predicted, torch.zeros_like(predicted),
                            torch.ones_like(predicted), roads, (5,))
    assert result[0]["fp_near_road"] == 1
    assert result[0]["fp_far_from_road"] == 1


def test_checkpoint_selection_keeps_epoch_metrics_together():
    rows = [{"epoch": 1, "validation": {"class_iou": {
                "non_flooded_building": 0.5, "flooded_building": 0.5,
                "non_flooded_road": 0.5, "flooded_road": 0.1}}},
            {"epoch": 2, "validation": {"class_iou": {
                "non_flooded_building": 0.1, "flooded_building": 0.1,
                "non_flooded_road": 0.1, "flooded_road": 0.6}}}]
    assert selected_row(rows, "best_macro")["epoch"] == 1
    assert selected_row(rows, "best_road")["epoch"] == 2


def test_hn_comparability_rejects_non_sampling_change():
    base = {"model_id": "b", "output_dir": "one", "seed": 42, "epochs": 15,
            "sampler": {"epoch_size": 200}, "learning_rate": 0.0003,
            "initialization_checkpoint": "clean.pth", "splits": {"train": [1], "validation": [2]}}
    candidate = dict(base, model_id="h", output_dir="two",
                     hard_negative_mining={"top_fraction": 0.1, "weight": 3})
    assert comparable(base, candidate)["same_except_hard_negative_sampling"]
    with pytest.raises(ValueError, match="Non-sampling"):
        comparable(base, dict(candidate, learning_rate=0.001))


def test_multiseed_gate_needs_two_jointly_improved_seeds():
    from scripts.finalize_hn_multiseed import METRICS
    rows = []
    for seed in (42, 3407, 2026):
        baseline = {key: 0.1 for key in METRICS}
        candidate = {key: 0.11 if seed == 42 else 0.09 for key in METRICS}
        rows.extend([{"model": "E4_NEW_BASELINE", "seed": seed, **baseline},
                     {"model": "HN10_W5", "seed": seed, **candidate}])
    result = decide_multiseed(rows)
    assert result["decision"] == "KEEP_E4"
    assert result["joint_improved_seed_count"] == 1
