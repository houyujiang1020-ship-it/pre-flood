"""Composable research heads built from the repository's pinned U-Net weights."""
from __future__ import annotations

import torch

from model_factory import build_siamunet
from single_unet import attach_single_image_forward


class FoundationSegmentationModel(torch.nn.Module):
    """Single-image PRE foundation; emits building and road object logits."""

    def __init__(self, source, normalization="groupnorm", groups=8):
        super().__init__()
        self.network = attach_single_image_forward(build_siamunet(
            source, normalization, groups, num_classes=6))

    def forward(self, pre: torch.Tensor) -> torch.Tensor:
        """Map B×3×H×W PRE RGB to B×2×H×W building/road logits."""
        if pre.ndim != 4 or pre.shape[1] != 3 or not torch.isfinite(pre).all():
            raise ValueError("Expected finite B×3×H×W PRE input")
        outputs = self.network(pre)
        return outputs[:, (0, 3)]

    def probabilities(self, pre: torch.Tensor) -> torch.Tensor:
        """Return implicit background, building and road probabilities (B×3×H×W)."""
        objects = self.forward(pre).sigmoid()
        background = (1 - objects[:, 0:1]) * (1 - objects[:, 1:2])
        return torch.cat((background, objects), dim=1)


class FloodChangeModel(torch.nn.Module):
    """Shared-encoder SiamUnet-diff trained for flooded-object status probability.

    SpaceNet 8 supplies object status labels, not a continuous flood-water mask.
    This model's output must never be advertised as full flood extent.
    """

    def __init__(self, source, normalization="groupnorm", groups=8):
        super().__init__()
        self.network = build_siamunet(source, normalization, groups, num_classes=1)

    def forward(self, pre: torch.Tensor, post: torch.Tensor) -> torch.Tensor:
        """Map aligned B×3×H×W RGB pairs to B×1×H×W status logits."""
        if pre.ndim != 4 or pre.shape[1] != 3 or post.shape != pre.shape:
            raise ValueError("Expected aligned B×3×H×W PRE/POST inputs")
        if not torch.isfinite(pre).all() or not torch.isfinite(post).all():
            raise ValueError("Nonfinite PRE/POST inputs")
        return self.network(pre, post)
