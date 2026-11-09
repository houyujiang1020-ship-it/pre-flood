"""Frozen two-teacher H/V-TTA pseudo-label generation for new paired imagery."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
import torch
from rasterio.enums import Resampling
from rasterio.warp import reproject

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app/training"))
from model_factory import build_siamunet  # noqa: E402
from pseudo_label.filter_pseudo_labels import CLASSES, filter_probabilities  # noqa: E402

ARCH = ROOT / "upstream/SpaceNet8/baseline/models/other/siamunetdif.py"


def digest(path: Path) -> str:
    """Hash one local input file."""
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_aligned_pair(pre_path: Path, post_path: Path, size: int):
    """Align two real rasters to PRE CRS/transform; return RGB tensors and valid pixels."""
    with rasterio.open(pre_path) as pre:
        if pre.crs is None or pre.count < 3:
            raise ValueError("PRE requires CRS and three RGB bands")
        before = pre.read([1, 2, 3], out_shape=(3, size, size), resampling=Resampling.bilinear)
        before_valid = pre.read_masks(1, out_shape=(size, size), resampling=Resampling.nearest) > 0
        grid = pre.transform * pre.transform.scale(pre.width / size, pre.height / size)
        crs = pre.crs
    after = np.zeros((3, size, size), dtype=np.float32)
    post_valid = np.zeros((size, size), dtype=np.uint8)
    with rasterio.open(post_path) as post:
        if post.crs is None or post.count < 3:
            raise ValueError("POST requires CRS and three RGB bands")
        for channel in range(3):
            reproject(rasterio.band(post, channel + 1), after[channel],
                      src_transform=post.transform, src_crs=post.crs,
                      dst_transform=grid, dst_crs=crs, resampling=Resampling.bilinear)
        reproject(post.dataset_mask(), post_valid, src_transform=post.transform,
                  src_crs=post.crs, dst_transform=grid, dst_crs=crs, resampling=Resampling.nearest)
    valid = before_valid & (post_valid > 0)
    if not valid.any():
        raise ValueError("PRE/POST have no jointly valid spatial pixels")
    if not np.isfinite(before).all() or not np.isfinite(after).all():
        raise ValueError("Nonfinite imagery")
    return torch.from_numpy(before.astype(np.float32) / 255), torch.from_numpy(after / 255), valid


def load_teacher(path: Path, device: str):
    """Strictly load a compatible four-output research teacher."""
    checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    if checkpoint.get("architecture") != "SiamUnet_diff" or checkpoint.get("classes") != list(CLASSES):
        raise ValueError("Teacher checkpoint contract mismatch")
    model = build_siamunet(ARCH, checkpoint["normalization"], checkpoint["groupnorm_groups"])
    model.load_state_dict(checkpoint["state_dict"], strict=True)
    return model.to(device).eval()


def views(model, pre: torch.Tensor, post: torch.Tensor) -> list[np.ndarray]:
    """Predict original, horizontal-flip and vertical-flip views and invert flips."""
    results = []
    with torch.inference_mode():
        for dims in ((), (-1,), (-2,)):
            p = torch.flip(pre, dims) if dims else pre
            q = torch.flip(post, dims) if dims else post
            probability = model(p, q).sigmoid()
            restored = torch.flip(probability, dims) if dims else probability
            if not torch.isfinite(restored).all():
                raise ValueError("Nonfinite teacher probability")
            results.append(restored[0].cpu().numpy())
    return results


def forbidden_inputs(manifest: dict, entries: list[dict], allow_synthetic_smoke: bool) -> None:
    """Never recycle E4 labels/imagery or the reserved Louisiana-West public test."""
    if manifest.get("split") != "unlabeled_train" or not entries:
        raise ValueError("Expected nonempty unlabeled_train manifest")
    if manifest.get("synthetic") and not allow_synthetic_smoke:
        raise ValueError("Synthetic data requires explicit smoke flag")
    split_csv = ROOT / "experiments/accuracy-pipeline-20261005/data_split_manifest.csv"
    with split_csv.open(encoding="utf-8", newline="") as stream:
        protected = {str((ROOT / row[key]).resolve()).casefold() for row in csv.DictReader(stream)
                     for key in ("pre_image", "post_image")}
    protected_names = {Path(path).name for path in protected}
    for item in entries:
        for key in ("pre_image", "post_image"):
            path = (ROOT / item[key]).resolve()
            normalized = str(path).casefold().replace("_", "-")
            if (str(path).casefold() in protected or path.name.casefold() in protected_names
                    or "louisiana-west-test-public" in normalized):
                raise ValueError(f"Protected training/development/test imagery: {path}")


def main() -> None:
    """Generate non-overwriting pseudo masks and per-class acceptance statistics."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-synthetic-smoke", action="store_true")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    items = manifest.get("items", [])
    forbidden_inputs(manifest, items, args.allow_synthetic_smoke)
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(output)
    checkpoints = [ROOT / path for path in cfg["teachers"]]
    if len(checkpoints) < 2 or any(not path.is_file() for path in checkpoints):
        raise ValueError("At least two existing teacher checkpoints are required")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    teachers = [load_teacher(path, device) for path in checkpoints]
    size = int(cfg["image_size"])
    if size < 32 or size % 16:
        raise ValueError("image_size must be >=32 and divisible by 16")
    decisions = []
    output.mkdir(parents=True, exist_ok=False)
    aggregate = {name: {key: 0 for key in ("positive_pixels", "negative_pixels", "ignored_pixels", "accepted_pixels")}
                 for name in CLASSES}
    for item in items:
        pre_path, post_path = (ROOT / item[key] for key in ("pre_image", "post_image"))
        pre, post, valid = load_aligned_pair(pre_path, post_path, size)
        pre = pre.unsqueeze(0).to(device)
        post = post.unsqueeze(0).to(device)
        probabilities = np.stack([result for teacher in teachers for result in views(teacher, pre, post)])
        pseudo, stats = filter_probabilities(probabilities, cfg["low_thresholds"],
                                              cfg["high_thresholds"], cfg["max_variance"], valid)
        name = f"{len(decisions):04d}.npy"
        np.save(output / name, pseudo, allow_pickle=False)
        for class_name in CLASSES:
            for key in aggregate[class_name]:
                aggregate[class_name][key] += stats[class_name][key]
        decisions.append({"sample_id": item["sample_id"], "pre_image": str(pre_path.resolve()),
                          "post_image": str(post_path.resolve()), "pre_sha256": digest(pre_path),
                          "post_sha256": digest(post_path), "pseudo_mask": name,
                          "pseudo_sha256": digest(output / name), "stats": stats})
    total = len(decisions) * size * size
    for name in CLASSES:
        aggregate[name]["acceptance_ratio"] = aggregate[name]["accepted_pixels"] / total
    metadata = {"created_at": datetime.now(timezone.utc).isoformat(),
                "source_manifest_sha256": digest(args.manifest), "config_sha256": digest(args.config),
                "teachers": [{"path": str(path), "sha256": digest(path)} for path in checkpoints],
                "split": "unlabeled_train", "synthetic_smoke_only": bool(manifest.get("synthetic")),
                "training_eligible": not bool(manifest.get("synthetic")),
                "independent_ground_truth": False, "items": decisions, "aggregate": aggregate}
    (output / "pseudo_label_stats.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"samples": len(decisions), "aggregate": aggregate}))


if __name__ == "__main__":
    main()
