"""Train-only crop selection that can target sparse flood-road pixels."""
from __future__ import annotations

import math

import torch

GROUP_CHANNELS = {"flooded_road": (3,), "flooded_building": (1,),
                  "normal_object": (0, 2), "background": ()}


def validate_config(config: dict, image_size: int) -> None:
    """Validate fixed crop geometry and a complete categorical sampling policy."""
    if not isinstance(config, dict):
        raise ValueError("class_aware_crop must be an object")
    size = config.get("size")
    if type(size) is not int or size < 32 or size % 16 or size > image_size:
        raise ValueError("class_aware_crop.size must be 32..image_size and divisible by 16")
    weights = config.get("weights")
    if not isinstance(weights, dict) or set(weights) != set(GROUP_CHANNELS):
        raise ValueError("class_aware_crop.weights must include all four groups")
    if any(type(value) not in (int, float) or not math.isfinite(value) or value < 0
           for value in weights.values()) or sum(weights.values()) <= 0:
        raise ValueError("class_aware_crop weights must be nonnegative and nonzero")


def select_crop(pair: tuple[torch.Tensor, ...], config: dict) -> tuple[tuple[torch.Tensor, ...], dict]:
    """Crop PRE/POST/GT/valid synchronously; fall back when a rare class is absent."""
    pre, post, truth, valid = pair
    if pre.ndim != 3 or pre.shape[0] != 3 or post.shape != pre.shape:
        raise ValueError("Expected aligned RGB PRE/POST tensors")
    if truth.shape != (4, *pre.shape[1:]) or valid.shape != pre.shape[1:]:
        raise ValueError("Expected four GT maps and one valid mask on PRE grid")
    if not all(torch.isfinite(t).all() for t in pair) or valid.sum().item() <= 0:
        raise ValueError("Nonfinite tensors or empty valid region")
    height, width = valid.shape
    validate_config(config, min(height, width))
    size = config["size"]
    weights = config["weights"]
    names = tuple(GROUP_CHANNELS)
    chosen = names[torch.multinomial(torch.tensor([weights[name] for name in names], dtype=torch.float64), 1).item()]
    eligible = valid > 0
    for channel in GROUP_CHANNELS[chosen]:
        eligible = eligible & (truth[channel] > 0) if len(GROUP_CHANNELS[chosen]) == 1 else eligible
    if chosen == "normal_object":
        eligible &= (truth[0] > 0) | (truth[2] > 0)
    if chosen == "background":
        eligible &= truth.sum(0) == 0
    fallback = not eligible.any().item()
    if fallback:
        eligible = valid > 0
    locations = torch.nonzero(eligible, as_tuple=False)
    y, x = locations[torch.randint(len(locations), ())].tolist()
    top = max(0, min(height - size, y - int(torch.randint(size, ()).item())))
    left = max(0, min(width - size, x - int(torch.randint(size, ()).item())))
    cropped = tuple(t[..., top:top + size, left:left + size] for t in pair)
    positive = ((cropped[2] > 0) & (cropped[3].unsqueeze(0) > 0)).sum((1, 2)).tolist()
    info = {"requested_group": chosen, "fallback_to_valid": fallback,
            "top": top, "left": left, "size": size,
            "positive_pixels": [int(v) for v in positive],
            "valid_pixels": int((cropped[3] > 0).sum().item())}
    return cropped, info
