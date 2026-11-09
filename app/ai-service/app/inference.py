import json
import time
from pathlib import Path

import numpy as np
from PIL import Image

from .schemas import JobResult

MODEL_NAME = "spectral-change-fallback"
MODEL_VERSION = "0.1.0"


def _read_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB"), dtype=np.uint8)


def _box_count(mask: np.ndarray, radius: int) -> np.ndarray:
    padded = np.pad(mask.astype(np.uint8), radius, mode="edge")
    count = np.zeros(mask.shape, dtype=np.uint16)
    for row in range(radius * 2 + 1):
        for col in range(radius * 2 + 1):
            count += padded[row:row + mask.shape[0], col:col + mask.shape[1]]
    return count


def _binary_cleanup(mask: np.ndarray, radius: int = 2) -> np.ndarray:
    area = (radius * 2 + 1) ** 2
    return (_box_count(mask, radius) >= max(2, area // 3)).astype(np.uint8)


def _edge_mask(gray: np.ndarray) -> np.ndarray:
    gx = np.abs(np.diff(gray.astype(np.int16), axis=1, prepend=gray[:, :1]))
    gy = np.abs(np.diff(gray.astype(np.int16), axis=0, prepend=gray[:1, :]))
    edges = (gx + gy) > 55
    return _box_count(edges, 1) > 0


def predict(pre_path: Path, post_path: Path, output_dir: Path) -> JobResult:
    from .settings import settings
    if settings().backend in ('siamunet-smoke', 'e4-research'):
        from .torch_backend import predict as torch_predict
        return torch_predict(pre_path, post_path, output_dir)
    started = time.perf_counter()
    pre = _read_rgb(pre_path)
    post = _read_rgb(post_path)
    if pre.shape != post.shape:
        raise ValueError(f"Image dimensions differ: pre={pre.shape}, post={post.shape}")

    output_dir.mkdir(parents=True, exist_ok=True)
    pre_f = pre.astype(np.float32) / 255.0
    post_f = post.astype(np.float32) / 255.0
    delta = np.mean(np.abs(post_f - pre_f), axis=2)
    post_gray = np.mean(post_f, axis=2)
    pre_gray = np.mean(pre_f, axis=2)

    # Water-like pixels are relatively blue/dark and changed after the event.
    blue_excess = post_f[:, :, 2] - np.maximum(post_f[:, :, 0], post_f[:, :, 1])
    darkening = pre_gray - post_gray
    flood = _binary_cleanup((delta > 0.12) & ((blue_excess > 0.04) | (darkening > 0.10)), 2)

    # Straight/edge-rich structures provide conservative road/building candidates.
    pre_gray_u8 = np.mean(pre, axis=2).astype(np.uint8)
    edges = _edge_mask(pre_gray_u8)
    road_candidate = _box_count(edges, 1) > 0
    building_candidate = _box_count(edges, 3) >= 2
    flooded_road = (road_candidate & (flood > 0)).astype(np.uint8)
    normal_road = (road_candidate & (flood == 0)).astype(np.uint8)
    flooded_building = (building_candidate & (flood > 0)).astype(np.uint8)
    normal_building = (building_candidate & (flood == 0)).astype(np.uint8)

    masks = {
        "flood_mask": flood,
        "flooded_road": flooded_road,
        "non_flooded_road": normal_road,
        "flooded_building": flooded_building,
        "non_flooded_building": normal_building,
    }
    paths: dict[str, Path] = {}
    for name, mask in masks.items():
        path = output_dir / f"{name}.png"
        Image.fromarray(mask.astype(np.uint8) * 255).save(path)
        paths[name] = path

    overlay = post.copy()
    overlay[flood > 0] = (0.35 * overlay[flood > 0] + 0.65 * np.array([0, 120, 255])).astype(np.uint8)
    overlay[flooded_building > 0] = np.array([255, 40, 40], dtype=np.uint8)
    overlay[flooded_road > 0] = np.array([255, 190, 0], dtype=np.uint8)
    preview_path = output_dir / "preview.png"
    Image.fromarray(overlay).save(preview_path)

    total_pixels = int(flood.size)
    statistics = {
        "width": int(flood.shape[1]),
        "height": int(flood.shape[0]),
        "flood_pixels": int(flood.sum()),
        "flood_ratio": round(float(flood.mean()), 6),
        "flooded_road_pixels": int(flooded_road.sum()),
        "flooded_building_pixels": int(flooded_building.sum()),
        "total_pixels": total_pixels,
        "backend": MODEL_NAME,
        "warning": "Fallback change analysis; not a trained SpaceNet8 checkpoint.",
    }
    stats_path = output_dir / "statistics.json"
    stats_path.write_text(json.dumps(statistics, ensure_ascii=False, indent=2), encoding="utf-8")
    elapsed = time.perf_counter() - started
    return JobResult(
        mask_path=paths["flood_mask"],
        preview_path=preview_path,
        class_masks=paths,
        statistics=statistics,
        inference_seconds=round(elapsed, 6),
        model_version=MODEL_VERSION,
    )
