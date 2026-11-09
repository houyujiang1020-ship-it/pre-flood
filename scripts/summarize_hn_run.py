"""Write per-epoch metric CSVs and separate compact training curves."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from PIL import Image, ImageDraw


def chart(path: Path, values: list[float | None], title: str) -> None:
    """Draw a readable single-metric epoch line chart with a numeric scale."""
    image = Image.new("RGB", (800, 400), "white")
    draw = ImageDraw.Draw(image)
    left, top, right, bottom = 80, 45, 765, 340
    draw.line(((left, top), (left, bottom), (right, bottom)), fill="black", width=2)
    observed = [float(value) for value in values if value is not None]
    high = max(observed) if observed else 1.0
    high = max(high * 1.1, 0.01)
    draw.text((left, 12), title, fill="black")
    draw.text((6, top), f"{high:.3f}", fill="black")
    draw.text((24, bottom - 10), "0", fill="black")
    draw.text((right - 65, bottom + 12), f"epoch {len(values)}", fill="black")
    points = [(left + (right - left) * index / max(len(values) - 1, 1),
               bottom - (bottom - top) * float(value) / high)
              for index, value in enumerate(values) if value is not None]
    if len(points) > 1:
        draw.line(points, fill=(22, 92, 190), width=3)
    for x, y in points:
        draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=(22, 92, 190))
    image.save(path)


def main() -> None:
    """Summarize one completed training run, without recalculating validation."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    history = json.loads((args.run / "history.json").read_text(encoding="utf-8"))
    if not history or any(row.get("validation") is None for row in history):
        raise ValueError("Run must have per-epoch validation history")
    outputs = (args.run / "train_loss.csv", args.run / "val_metrics.csv",
               args.run / "macro_iou_curve.png", args.run / "flooded_road_iou_curve.png",
               args.run / "flooded_road_precision_curve.png")
    if any(path.exists() for path in outputs):
        raise FileExistsError("Summary outputs already exist")
    rows = []
    with outputs[0].open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("epoch", "train_loss"))
        writer.writeheader()
        writer.writerows({"epoch": row["epoch"], "train_loss": row["train_loss"]} for row in history)
    for row in history:
        validation = row["validation"]
        scores = validation["class_iou"]
        rows.append({"epoch": row["epoch"], "val_loss": validation["loss"],
                     "macro_iou": sum(scores.values()) / 4,
                     "flooded_road_iou": scores["flooded_road"],
                     "flooded_road_precision": validation["class_precision"]["flooded_road"],
                     "flooded_road_recall": validation["class_recall"]["flooded_road"]})
    with outputs[1].open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    for path, key, title in ((outputs[2], "macro_iou", "Macro IoU vs epoch"),
                             (outputs[3], "flooded_road_iou", "Flooded-road IoU vs epoch"),
                             (outputs[4], "flooded_road_precision", "Flooded-road precision vs epoch")):
        chart(path, [row[key] for row in rows], title)
    best_macro = max(rows, key=lambda row: row["macro_iou"])
    best_road = max(rows, key=lambda row: row["flooded_road_iou"])
    print(json.dumps({"best_macro_epoch": best_macro["epoch"],
                      "best_macro_iou": best_macro["macro_iou"],
                      "best_road_epoch": best_road["epoch"],
                      "best_road_iou": best_road["flooded_road_iou"]}))


if __name__ == "__main__":
    main()
