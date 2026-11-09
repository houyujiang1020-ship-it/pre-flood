"""Geometry-preserving, rare-class and empty-pool crop checks."""
import torch
import pytest

from class_aware_crop import select_crop


def config(weights):
    return {"size": 32, "weights": weights}


def test_flooded_road_crop_aligns_all_tensors():
    torch.manual_seed(7)
    basis = torch.arange(64 * 64).reshape(64, 64).float()
    pre = basis.repeat(3, 1, 1)
    post = pre + 10
    truth = torch.zeros(4, 64, 64)
    truth[3, 45, 52] = 1
    valid = torch.ones(64, 64)
    cropped, info = select_crop((pre, post, truth, valid),
                                config({"flooded_road": 1, "flooded_building": 0,
                                        "normal_object": 0, "background": 0}))
    assert info["requested_group"] == "flooded_road"
    assert not info["fallback_to_valid"]
    assert info["positive_pixels"][3] == 1
    assert torch.equal(cropped[1] - cropped[0], torch.full_like(cropped[0], 10))
    assert torch.equal(cropped[0][0], basis[info["top"]:info["top"] + 32,
                                               info["left"]:info["left"] + 32])


def test_empty_rare_pool_falls_back_without_hanging():
    torch.manual_seed(2)
    pair = (torch.zeros(3, 32, 32), torch.zeros(3, 32, 32),
            torch.zeros(4, 32, 32), torch.ones(32, 32))
    cropped, info = select_crop(pair, config({"flooded_road": 1, "flooded_building": 0,
                                              "normal_object": 0, "background": 0}))
    assert info["fallback_to_valid"]
    assert all(t.shape[-2:] == (32, 32) for t in cropped)


def test_alignment_failure_rejected():
    pair = (torch.zeros(3, 64, 64), torch.zeros(3, 32, 32),
            torch.zeros(4, 64, 64), torch.ones(64, 64))
    with pytest.raises(ValueError, match="aligned"):
        select_crop(pair, config({"flooded_road": 1, "flooded_building": 0,
                                  "normal_object": 0, "background": 0}))
