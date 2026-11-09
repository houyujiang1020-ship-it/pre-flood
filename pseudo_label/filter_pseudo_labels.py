"""Agreement/variance filtering with explicit 255 ignore pixels."""
from __future__ import annotations

import numpy as np

CLASSES = ("non_flooded_building", "flooded_building", "non_flooded_road", "flooded_road")


def filter_probabilities(predictions: np.ndarray, low: dict, high: dict,
                         max_variance: float, valid: np.ndarray) -> tuple[np.ndarray, dict]:
    """Convert T×4×H×W teacher/TTA probabilities to 4×H×W {0,1,255}.

    Positive and negative decisions need unanimous threshold agreement. Every
    other pixel, including nodata, remains ignored for pseudo-supervision.
    """
    predictions = np.asarray(predictions, dtype=np.float32)
    valid = np.asarray(valid, dtype=bool)
    if predictions.ndim != 4 or predictions.shape[0] < 2 or predictions.shape[1] != 4:
        raise ValueError("Expected >=2 teacher/TTA views and four classes")
    if valid.shape != predictions.shape[2:] or not np.isfinite(predictions).all():
        raise ValueError("Invalid probabilities or valid-mask shape")
    if predictions.min() < 0 or predictions.max() > 1:
        raise ValueError("Probabilities must lie within [0,1]")
    if set(low) != set(CLASSES) or set(high) != set(CLASSES):
        raise ValueError("Every class requires low and high thresholds")
    if not np.isfinite(max_variance) or max_variance < 0:
        raise ValueError("max_variance must be nonnegative")
    for name in CLASSES:
        if not 0 <= low[name] < high[name] <= 1:
            raise ValueError(f"Invalid threshold order: {name}")
    result = np.full(predictions.shape[1:], 255, dtype=np.uint8)
    variance = predictions.var(axis=0)
    for channel, name in enumerate(CLASSES):
        stable = (variance[channel] <= max_variance) & valid
        result[channel][stable & (predictions[:, channel] >= high[name]).all(axis=0)] = 1
        result[channel][stable & (predictions[:, channel] <= low[name]).all(axis=0)] = 0
    stats = {name: {"positive_pixels": int((result[i] == 1).sum()),
                    "negative_pixels": int((result[i] == 0).sum()),
                    "ignored_pixels": int((result[i] == 255).sum()),
                    "accepted_pixels": int((result[i] != 255).sum()),
                    "acceptance_ratio": float((result[i] != 255).mean())}
             for i, name in enumerate(CLASSES)}
    return result, stats


def masked_pseudo_bce(logits, pseudo):
    """BCE on accepted pseudo pixels only; all-ignored batches contribute zero."""
    import torch
    if logits.shape != pseudo.shape or logits.ndim != 4 or logits.shape[1] != 4:
        raise ValueError("Expected matching B×4×H×W tensors")
    if not torch.isfinite(logits).all() or not torch.all((pseudo == 0) | (pseudo == 1) | (pseudo == 255)):
        raise ValueError("Nonfinite logits or invalid pseudo-label values")
    selected = pseudo != 255
    if not selected.any():
        return logits.sum() * 0
    return torch.nn.functional.binary_cross_entropy_with_logits(logits[selected], pseudo[selected].float())
