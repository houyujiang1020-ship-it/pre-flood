"""Minimal adapter for the Apache-2.0 XD_XD SpaceNet-5 road model."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import torch


def load_architecture(source: Path):
    source = Path(source).resolve()
    spec = importlib.util.spec_from_file_location("mapgos_xdxd_sn5_senet", source)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import XD_XD architecture: {source}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_xdxd_sn5(
    source: Path,
    num_classes: int,
    pretrained_state_dict: Path | None = None,
    road_target_channel: int | None = None,
):
    if num_classes < 1:
        raise ValueError("num_classes must be positive")
    module = load_architecture(source)
    model = module.SeResnext50_32x4d_upsample(num_channels=3, num_classes=8)
    if pretrained_state_dict is not None:
        state = torch.load(pretrained_state_dict, map_location="cpu", weights_only=True)
        model.load_state_dict(state, strict=True)
    if num_classes != 8:
        old = model.final[-1]
        new = torch.nn.Conv2d(
            old.in_channels,
            num_classes,
            kernel_size=old.kernel_size,
            stride=old.stride,
            padding=old.padding,
            bias=old.bias is not None,
        )
        torch.nn.init.kaiming_normal_(new.weight, mode="fan_out", nonlinearity="relu")
        if new.bias is not None:
            torch.nn.init.zeros_(new.bias)
        if pretrained_state_dict is not None and road_target_channel is not None:
            if not 0 <= road_target_channel < num_classes:
                raise ValueError("road_target_channel is outside the new output head")
            with torch.no_grad():
                new.weight[road_target_channel].copy_(old.weight[-1])
                if new.bias is not None:
                    new.bias[road_target_channel].copy_(old.bias[-1])
        model.final[-1] = new
    return model


def freeze_except_output_head(model) -> None:
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    for parameter in model.final[-1].parameters():
        parameter.requires_grad_(True)


def freeze_batchnorm_statistics(model) -> None:
    for layer in model.modules():
        if isinstance(layer, torch.nn.modules.batchnorm._BatchNorm):
            layer.eval()


def parameter_counts(model) -> dict[str, int]:
    return {
        "total": sum(parameter.numel() for parameter in model.parameters()),
        "trainable": sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad),
    }
