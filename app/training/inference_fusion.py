"""Fuse foundation objects with paired-image flooded-object status probabilities."""
from __future__ import annotations

import torch
import torch.nn.functional as F


def fuse_probabilities(foundation_logits: torch.Tensor, flood_logits: torch.Tensor,
                       road_dilation_pixels: int = 0, road_prior_floor: float = 0.25) -> torch.Tensor:
    """Return B×4×H×W probabilities in the existing external class order.

    The dilated road body is a soft prior for flooded roads, never a hard mask.
    Non-flooded/flooded probabilities sum to object presence within each type.
    """
    if foundation_logits.ndim != 4 or foundation_logits.shape[1] != 2:
        raise ValueError("Expected B×2×H×W foundation logits")
    if flood_logits.shape != foundation_logits.shape[:1] + (1,) + foundation_logits.shape[2:]:
        raise ValueError("Expected aligned B×1×H×W flooded-object status logits")
    if not torch.isfinite(foundation_logits).all() or not torch.isfinite(flood_logits).all():
        raise ValueError("Nonfinite fusion logits")
    if type(road_dilation_pixels) is not int or not 0 <= road_dilation_pixels <= 32:
        raise ValueError("Invalid road dilation radius")
    if not 0 < road_prior_floor <= 1:
        raise ValueError("road_prior_floor must be within (0,1]")
    objects = foundation_logits.sigmoid()
    flood = flood_logits.sigmoid()
    building = objects[:, 0:1]
    road = objects[:, 1:2]
    nearby_road = (F.max_pool2d(road, 2 * road_dilation_pixels + 1,
                                stride=1, padding=road_dilation_pixels)
                   if road_dilation_pixels else road)
    road_prior = road_prior_floor + (1 - road_prior_floor) * nearby_road
    flooded_road_status = flood * road_prior
    return torch.cat((building * (1 - flood), building * flood,
                      road * (1 - flooded_road_status), road * flooded_road_status), dim=1)
