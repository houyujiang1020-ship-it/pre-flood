"""Deterministic auxiliary targets for building/road foundation segmentation."""
import numpy as np
import torch

from road_morphology import skeletonize


CHANNELS = ['building_body', 'building_border', 'building_proximity',
            'road_body', 'road_skeleton', 'road_junction']


def _dilate(mask, iterations=1):
    value = np.asarray(mask, dtype=bool)
    for _ in range(iterations):
        padded = np.pad(value, 1, constant_values=False)
        height, width = value.shape
        value = np.logical_or.reduce([padded[y:y + height, x:x + width]
                                      for y in range(3) for x in range(3)])
    return value


def _erode(mask, iterations=1):
    value = np.asarray(mask, dtype=bool)
    for _ in range(iterations):
        padded = np.pad(value, 1, constant_values=False)
        height, width = value.shape
        value = np.logical_and.reduce([padded[y:y + height, x:x + width]
                                       for y in range(3) for x in range(3)])
    return value


def make_auxiliary_targets(labels, valid):
    labels_np = labels.detach().cpu().numpy() > 0
    valid_np = valid.detach().cpu().numpy() > 0
    if labels_np.ndim != 3 or labels_np.shape[0] != 4 or valid_np.shape != labels_np.shape[1:]:
        raise ValueError('Expected four label channels and one matching valid mask')
    building = (labels_np[0] | labels_np[1]) & valid_np
    road = (labels_np[2] | labels_np[3]) & valid_np
    building_border = (_dilate(building) & ~_erode(building)) & valid_np
    closed = _erode(_dilate(building, 2), 2)
    building_proximity = (closed & ~building) & valid_np
    road_skeleton = skeletonize(road) & valid_np
    padded = np.pad(road_skeleton, 1, constant_values=False)
    height, width = road.shape
    neighbors = sum(padded[y:y + height, x:x + width].astype(np.uint8)
                    for y in range(3) for x in range(3) if (y, x) != (1, 1))
    road_junction = _dilate(road_skeleton & (neighbors >= 3), 3) & valid_np
    value = np.stack([building, building_border, building_proximity,
                      road, road_skeleton, road_junction]).astype(np.float32)
    return torch.from_numpy(value)
