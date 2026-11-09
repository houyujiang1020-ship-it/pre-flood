"""Train a paired-image flooded-object status head and evaluate E3c+status fusion.

SpaceNet 8 object labels do not supervise continuous open-water flood extent.
This research run never modifies the E4 checkpoint or production service.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch

import train_full as base
from class_aware_crop import select_crop, validate_config
from domain_balanced_sampler import DomainBalancedPositiveSampler
from foundation_flood_models import FloodChangeModel, FoundationSegmentationModel
from inference_fusion import fuse_probabilities
from positive_sampler import tile_categories

ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / "upstream/SpaceNet8/baseline/models/other/siamunetdif.py"


def digest(path: Path) -> str:
    """Stream a file SHA256."""
    return base.file_sha256(path)


def load_foundation(path: Path, device: str):
    """Strictly restore the six-channel single-image E3c foundation."""
    payload = torch.load(path, map_location="cpu", weights_only=True)
    if payload.get("output_channels") not in (None, 6) and payload.get("architecture") != "SingleUNet":
        raise ValueError("Unexpected foundation checkpoint schema")
    network = FoundationSegmentationModel(ARCH)
    network.network.load_state_dict(payload["state_dict"], strict=True)
    return network.to(device).eval()


def initialize_status(model: FloodChangeModel, path: Path) -> dict:
    """Reuse compatible E4 tensors while reinitializing its four-to-one output layer."""
    source = torch.load(path, map_location="cpu", weights_only=True)
    if source.get("architecture") != "SiamUnet_diff" or source.get("classes") != base.CLASSES:
        raise ValueError("Unexpected E4 initialization checkpoint")
    current = model.network.state_dict()
    compatible = {key: value for key, value in source["state_dict"].items()
                  if key in current and current[key].shape == value.shape}
    missing = sorted(set(current) - set(compatible))
    if missing != ["conv11d.bias", "conv11d.weight"]:
        raise ValueError(f"Unexpected initialization mismatch: {missing}")
    current.update(compatible)
    model.network.load_state_dict(current)
    return {"source_sha256": digest(path), "compatible_tensors": len(compatible),
            "reinitialized_tensors": missing}


def status_loss(logits, truth, valid, focal_gamma: float, dice_weight: float):
    """Balanced focal BCE + Dice on known object pixels only."""
    if logits.ndim != 4 or logits.shape[1] != 1 or truth.shape != logits.shape or valid.shape != logits.shape:
        raise ValueError("Expected aligned B×1×H×W status tensors")
    if not torch.isfinite(logits).all() or not torch.isfinite(truth).all():
        raise ValueError("Nonfinite status tensors")
    selected = valid > 0
    if not selected.any():
        return logits.sum() * 0
    binary = torch.nn.functional.binary_cross_entropy_with_logits(logits[selected], truth[selected], reduction="none")
    p = logits[selected].sigmoid()
    pt = torch.where(truth[selected] > 0, p, 1 - p)
    focal = ((1 - pt).pow(focal_gamma) * binary).mean()
    if dice_weight:
        prediction = p
        target = truth[selected]
        dice = 1 - (2 * (prediction * target).sum() + 1) / (prediction.sum() + target.sum() + 1)
        focal = focal + dice_weight * dice
    return focal


def evaluate(foundation, status, records, size, device, road_dilation_pixels, road_prior_floor):
    """Report fixed-0.5 four-class development metrics for the fused candidate."""
    tp = torch.zeros(4, dtype=torch.int64)
    pred = torch.zeros(4, dtype=torch.int64)
    gt = torch.zeros(4, dtype=torch.int64)
    foundation.eval()
    status.eval()
    with torch.inference_mode():
        for area, row in records:
            pre, post, truth, valid = base.cached_pair(area, row, size)
            pre = pre.unsqueeze(0).to(device)
            post = post.unsqueeze(0).to(device)
            probability = fuse_probabilities(foundation(pre), status(pre, post),
                                             road_dilation_pixels, road_prior_floor).cpu()[0]
            if not torch.isfinite(probability).all():
                raise ValueError("Nonfinite fused probabilities")
            prediction = (probability > .5) & (valid > 0)
            expected = (truth > 0) & (valid > 0)
            tp += (prediction & expected).sum((1, 2))
            pred += prediction.sum((1, 2))
            gt += expected.sum((1, 2))
    def ratio(n, d):
        return [float(n[i] / d[i]) if d[i] else None for i in range(4)]
    iou = ratio(tp, pred + gt - tp)
    return {"class_iou": dict(zip(base.CLASSES, iou)),
            "class_precision": dict(zip(base.CLASSES, ratio(tp, pred))),
            "class_recall": dict(zip(base.CLASSES, ratio(tp, gt))),
            "prediction_pixels": dict(zip(base.CLASSES, pred.tolist())),
            "truth_pixels": dict(zip(base.CLASSES, gt.tolist())),
            "macro_iou": sum(iou) / 4, "tile_count": len(records)}


def main() -> None:
    """Run an isolated, resumable CUDA/CPU research experiment."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    config_path = args.config.resolve()
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    if cfg["splits"].get("test"):
        raise ValueError("This experiment must not read test labels")
    size = int(cfg["image_size"])
    validate_config(cfg["class_aware_crop"], size)
    device = cfg.get("device", "cuda")
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    if device not in ("cpu", "cuda"):
        raise ValueError("Unknown device")
    torch.manual_seed(int(cfg["seed"]))
    np.random.seed(int(cfg["seed"]))
    random.seed(int(cfg["seed"]))
    out = ROOT / cfg["output_dir"]
    out.mkdir(parents=True, exist_ok=True)
    last, best = out / "last_model.pth", out / "best_model.pth"
    if last.exists() and not args.resume:
        raise FileExistsError("Run exists; use --resume or a new output_dir")
    base.DISK_CACHE = ROOT / cfg["cache_dir"]
    base._cached_pair.cache_clear()
    records = base.split_rows(cfg, ROOT)
    foundation_path = ROOT / cfg["foundation_checkpoint"]
    e4_path = ROOT / cfg["initialization_checkpoint"]
    foundation = load_foundation(foundation_path, device)
    status = FloodChangeModel(ARCH).to(device)
    init = initialize_status(status, e4_path) if not args.resume else None
    optimizer = torch.optim.Adam(status.parameters(), lr=float(cfg["learning_rate"]))
    use_amp = bool(cfg.get("amp", False)) and device == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
    identities = {"config_sha256": digest(config_path), "foundation_sha256": digest(foundation_path),
                  "e4_sha256": digest(e4_path), "architecture_sha256": digest(ARCH)}
    begin, best_score, history = 0, -float("inf"), []
    if args.resume:
        from torch.torch_version import TorchVersion
        with torch.serialization.safe_globals([TorchVersion]):
            checkpoint = torch.load(last, map_location=device, weights_only=True)
        if checkpoint["inputs"] != identities:
            raise ValueError("Resume identity mismatch")
        status.load_state_dict(checkpoint["state_dict"], strict=True)
        optimizer.load_state_dict(checkpoint["optimizer"])
        scaler.load_state_dict(checkpoint["scaler"])
        torch.set_rng_state(checkpoint["rng_state"].cpu())
        if device == "cuda":
            torch.cuda.set_rng_state_all([x.cpu() for x in checkpoint["cuda_rng_state"]])
        begin, best_score, history = checkpoint["epoch"], checkpoint["best_score"], checkpoint["history"]
    tile_info = []
    for area, row in records["train"]:
        _, _, labels, valid = base.cached_pair(area, row, size)
        tile_info.append(tile_categories(area, row, labels, valid))
    sampler = DomainBalancedPositiveSampler(tile_info, cfg["sampler"], int(cfg["seed"]))
    epochs = int(cfg["epochs"])
    if epochs <= begin:
        raise ValueError("No remaining epochs")
    for epoch in range(begin, epochs):
        status.train()
        indices, tile_report = sampler.sample(epoch)
        summary = {"epoch": epoch + 1, "crops": 0, "fallback": 0,
                   "requested_groups": {key: 0 for key in cfg["class_aware_crop"]["weights"]}}
        losses = []
        for index in indices:
            area, row = records["train"][index]
            pair, info = select_crop(base.cached_pair(area, row, size), cfg["class_aware_crop"])
            summary["crops"] += 1
            summary["fallback"] += int(info["fallback_to_valid"])
            summary["requested_groups"][info["requested_group"]] += 1
            pre, post, labels, valid = [tensor.unsqueeze(0).to(device) for tensor in pair]
            turns = int(torch.randint(4, ()).item())
            pre, post, labels, valid = [torch.rot90(tensor, turns, (-2, -1))
                                        for tensor in (pre, post, labels, valid)]
            if torch.rand(()).item() < .5:
                pre, post, labels, valid = [tensor.flip(-1) for tensor in (pre, post, labels, valid)]
            object_mask = (labels.sum(1, keepdim=True) > 0).float() * valid.unsqueeze(1)
            target = torch.maximum(labels[:, 1:2], labels[:, 3:4])
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(device_type=device, enabled=use_amp):
                logits = status(pre, post)
                loss = status_loss(logits, target, object_mask,
                                   float(cfg["loss"]["focal_gamma"]), float(cfg["loss"]["dice_weight"]))
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(status.parameters(), 10)
            scaler.step(optimizer)
            scaler.update()
            losses.append(float(loss.detach()))
        validation = evaluate(foundation, status, records["validation"], size, device,
                              int(cfg["road_dilation_pixels"]), float(cfg["road_prior_floor"]))
        score = validation["macro_iou"]
        record = {"epoch": epoch + 1, "train_loss": sum(losses) / len(losses),
                  "validation": validation, "crop_sampling": summary,
                  "tile_sampling": {"epoch_size": len(indices), "domain_appearances": tile_report["domain_appearances"]}}
        history.append(record)
        payload = {"state_dict": status.state_dict(), "optimizer": optimizer.state_dict(),
                   "scaler": scaler.state_dict(), "epoch": epoch + 1,
                   "best_score": max(score, best_score), "history": history,
                   "rng_state": torch.get_rng_state(),
                   "inputs": identities, "model_id": cfg["model_id"],
                   "architecture": "SiamUnet_diff_flooded_object_status", "output_channels": 1,
                   "classes": base.CLASSES, "config": cfg, "initialization": init,
                   "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                   "torch_version": str(torch.__version__), "cuda_version": torch.version.cuda,
                   "gpu": torch.cuda.get_device_name(0) if device == "cuda" else None,
                   "production_ready": False}
        if device == "cuda":
            payload["cuda_rng_state"] = torch.cuda.get_rng_state_all()
        base.save_checkpoint(payload, last)
        if score > best_score:
            best_score = score
            base.save_checkpoint(payload, best)
        (out / "history.json").write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")
        (out / "training_sampling_report.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"epoch": epoch + 1, "loss": record["train_loss"],
                          "macro_iou": score, "flooded_road_iou": validation["class_iou"]["flooded_road"]}), flush=True)


if __name__ == "__main__":
    main()
