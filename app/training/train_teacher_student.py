"""Opt-in supervised + frozen-pseudo-label mean-teacher research training."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

import numpy as np
import torch

import train_full as base
from class_aware_crop import select_crop, validate_config
from mean_teacher import ema_update, paired_weak_strong
from model_factory import build_siamunet

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pseudo_label.pseudo_label_dataset import PseudoLabelDataset  # noqa: E402
from pseudo_label.filter_pseudo_labels import masked_pseudo_bce  # noqa: E402
from pseudo_label.generate_pseudo_labels import load_aligned_pair  # noqa: E402


def load_configuration(path: Path, allow_synthetic_smoke: bool):
    """Verify split and pseudo-label provenance before any training read."""
    cfg = json.loads(path.read_text(encoding="utf-8"))
    supervised = json.loads((ROOT / cfg["supervised_config"]).read_text(encoding="utf-8"))
    if supervised["splits"].get("test"):
        raise ValueError("Teacher-student training must not read test labels")
    pseudo_path = ROOT / cfg["pseudo_manifest"]
    pseudo = json.loads(pseudo_path.read_text(encoding="utf-8"))
    if pseudo.get("synthetic_smoke_only") and not allow_synthetic_smoke:
        raise ValueError("Synthetic pseudo labels require explicit smoke flag")
    if not pseudo.get("training_eligible") and not allow_synthetic_smoke:
        raise ValueError("Pseudo labels are not training-eligible")
    if not pseudo.get("teachers") or len(pseudo["teachers"]) < 2:
        raise ValueError("Pseudo labels need at least two frozen teacher sources")
    if not 0 < cfg["ema_decay"] < 1 or not 0 <= cfg["unsupervised_weight"] <= 2:
        raise ValueError("Invalid EMA/unsupervised weight")
    validate_config(cfg["class_aware_crop"], supervised["image_size"])
    return cfg, supervised, pseudo_path


def main() -> None:
    """Train a separate student/EMA teacher checkpoint with immutable pseudo inputs."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--allow-synthetic-smoke", action="store_true")
    args = parser.parse_args()
    config_path = args.config.resolve()
    cfg, supervised, pseudo_path = load_configuration(config_path, args.allow_synthetic_smoke)
    data = PseudoLabelDataset(pseudo_path, allow_synthetic_smoke=args.allow_synthetic_smoke)
    output = ROOT / cfg["output_dir"]
    output.mkdir(parents=True, exist_ok=True)
    last, best = output / "last_model.pth", output / "best_model.pth"
    if last.exists() and not args.resume:
        raise FileExistsError("Existing teacher-student run")
    seed = int(cfg["seed"])
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    base.DISK_CACHE = ROOT / supervised["cache_dir"]
    base._cached_pair.cache_clear()
    records = base.split_rows(supervised, ROOT)
    source = ROOT / "upstream/SpaceNet8/baseline/models/other/siamunetdif.py"
    initial_path = ROOT / cfg["initial_checkpoint"]
    initial = torch.load(initial_path, map_location="cpu", weights_only=True)
    if initial.get("classes") != base.CLASSES or initial.get("architecture") != "SiamUnet_diff":
        raise ValueError("Initial checkpoint is not a four-class model")
    student = build_siamunet(source, initial["normalization"], initial["groupnorm_groups"]).to(device)
    teacher = build_siamunet(source, initial["normalization"], initial["groupnorm_groups"]).to(device)
    student.load_state_dict(initial["state_dict"], strict=True)
    teacher.load_state_dict(initial["state_dict"], strict=True)
    teacher.eval()
    optimizer = torch.optim.Adam(student.parameters(), lr=float(cfg["learning_rate"]))
    use_amp = bool(cfg.get("amp", False)) and device == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
    identity = {"config_sha256": base.file_sha256(config_path),
                "pseudo_sha256": base.file_sha256(pseudo_path),
                "initial_checkpoint_sha256": base.file_sha256(initial_path)}
    begin, best_score, history = 0, -float("inf"), []
    if args.resume:
        checkpoint = torch.load(last, map_location=device, weights_only=True)
        if checkpoint["inputs"] != identity:
            raise ValueError("Resume input identity mismatch")
        student.load_state_dict(checkpoint["student_state_dict"], strict=True)
        teacher.load_state_dict(checkpoint["teacher_state_dict"], strict=True)
        optimizer.load_state_dict(checkpoint["optimizer"])
        scaler.load_state_dict(checkpoint["scaler"])
        torch.set_rng_state(checkpoint["rng_state"].cpu())
        if device == "cuda":
            torch.cuda.set_rng_state_all([x.cpu() for x in checkpoint["cuda_rng_state"]])
        begin, best_score, history = checkpoint["epoch"], checkpoint["best_score"], checkpoint["history"]
    if cfg["epochs"] <= begin:
        raise ValueError("No remaining epochs")
    for epoch in range(begin, int(cfg["epochs"])):
        student.train()
        losses = []
        for step in range(int(cfg["steps_per_epoch"])):
            area, row = records["train"][int(torch.randint(len(records["train"]), ()).item())]
            paired, crop_info = select_crop(base.cached_pair(area, row, supervised["image_size"]),
                                            cfg["class_aware_crop"])
            pre, post, truth, valid = [tensor.unsqueeze(0).to(device) for tensor in paired]
            unsupervised = data[step % len(data)]
            u_pre, u_post, _ = load_aligned_pair(unsupervised["pre_image"],
                                                       unsupervised["post_image"], supervised["image_size"])
            pseudo = torch.from_numpy(unsupervised["pseudo_mask"].copy()).unsqueeze(0).to(device)
            if pseudo.shape[-2:] != u_pre.shape[-2:]:
                raise ValueError("Pseudo-label grid must match aligned PRE/POST image size")
            weak, strong, selected = paired_weak_strong(
                u_pre.unsqueeze(0).to(device), u_post.unsqueeze(0).to(device), pseudo,
                float(cfg["strong_brightness"]), float(cfg["strong_contrast"]))
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(device_type=device, enabled=use_amp):
                supervised_loss = base.masked_loss(student(pre, post), truth, valid,
                                                   dice_weight=float(cfg["supervised_dice_weight"]))
                student_logits = student(*strong)
                pseudo_loss = masked_pseudo_bce(student_logits, selected)
                with torch.no_grad():
                    teacher_probability = teacher(*weak).sigmoid()
                accepted = selected != 255
                consistency = ((student_logits.sigmoid() - teacher_probability).square()[accepted].mean()
                               if accepted.any() else student_logits.sum() * 0)
                loss = (supervised_loss + float(cfg["unsupervised_weight"]) *
                        (pseudo_loss + float(cfg["consistency_weight"]) * consistency))
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(student.parameters(), 10)
            scaler.step(optimizer)
            scaler.update()
            ema_update(teacher, student, float(cfg["ema_decay"]))
            losses.append(float(loss.detach()))
        teacher.eval()
        student.eval()
        validation = base.evaluate(student, records["validation"], supervised["image_size"], device)
        score = sum(validation["class_iou"].values()) / 4
        record = {"epoch": epoch + 1, "mean_loss": sum(losses) / len(losses),
                  "validation": validation, "macro_iou": score,
                  "pseudo_acceptance": json.loads(pseudo_path.read_text())["aggregate"],
                  "synthetic_smoke_only": bool(args.allow_synthetic_smoke)}
        history.append(record)
        payload = {"student_state_dict": student.state_dict(), "teacher_state_dict": teacher.state_dict(),
                   "optimizer": optimizer.state_dict(), "scaler": scaler.state_dict(),
                   "epoch": epoch + 1, "best_score": max(best_score, score), "history": history,
                   "rng_state": torch.get_rng_state(), "inputs": identity,
                   "model_id": cfg["model_id"], "architecture": "SiamUnet_diff",
                   "classes": base.CLASSES, "normalization": initial["normalization"],
                   "groupnorm_groups": initial["groupnorm_groups"],
                   "pseudo_training_eligible": not bool(args.allow_synthetic_smoke),
                   "production_ready": False}
        if device == "cuda":
            payload["cuda_rng_state"] = torch.cuda.get_rng_state_all()
        base.save_checkpoint(payload, last)
        if score > best_score:
            best_score = score
            base.save_checkpoint(payload, best)
        (output / "history.json").write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"epoch": epoch + 1, "macro_iou": score,
                          "flooded_road_iou": validation["class_iou"]["flooded_road"],
                          "synthetic_smoke_only": bool(args.allow_synthetic_smoke)}), flush=True)


if __name__ == "__main__":
    main()
