"""Construct the exact SiamUnet variant recorded in a checkpoint."""
import importlib.util
from pathlib import Path

import torch

SUPPORTED_NORMALIZATIONS = ('batchnorm', 'groupnorm')


def _replace_batchnorm(module, groups):
    for name, layer in list(module.named_children()):
        if isinstance(layer, torch.nn.BatchNorm2d):
            if layer.num_features % groups:
                raise ValueError(f'Group count {groups} does not divide {layer.num_features} channels')
            setattr(module, name, torch.nn.GroupNorm(groups, layer.num_features))
        else:
            _replace_batchnorm(layer, groups)


def build_siamunet(source, normalization='batchnorm', groupnorm_groups=8, num_classes=4):
    source = Path(source)
    if normalization not in SUPPORTED_NORMALIZATIONS:
        raise ValueError('Unsupported normalization: ' + str(normalization))
    if type(groupnorm_groups) is not int or groupnorm_groups < 1:
        raise ValueError('groupnorm_groups must be a positive integer')
    spec = importlib.util.spec_from_file_location('floodguard_siamunet_source', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if type(num_classes) is not int or num_classes < 1:
        raise ValueError('num_classes must be a positive integer')
    model = module.SiamUnet_diff(num_classes=num_classes, num_channels=3)
    if normalization == 'groupnorm':
        _replace_batchnorm(model, groupnorm_groups)
    return model
