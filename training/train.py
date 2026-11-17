import argparse
import json
from pathlib import Path
import time
import torch
from ultralytics import YOLO


def train(data, output, epochs):
    root = Path(output)
    root.mkdir(parents=True, exist_ok=True)
    results = []
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    for size in ["n", "s"]:
        started = time.perf_counter()
        model = YOLO(f"yolo11{size}-seg.pt")
        model.train(
            data=str(Path(data).resolve()),
            epochs=epochs,
            imgsz=512,
            batch=6,
            device=device,
            workers=2,
            project=str(root.resolve()),
            name="yolo11" + size,
            seed=42,
            deterministic=True,
            patience=8,
            optimizer="AdamW",
            lr0=0.001,
            cos_lr=True,
            mosaic=0.5,
            fliplr=0.5,
            degrees=8,
            freeze=10,
            amp=False,
            plots=True,
            exist_ok=True,
        )
        checkpoint = root / ("yolo11" + size) / "weights/best.pt"
        best = YOLO(checkpoint)
        metrics = best.val(
            data=str(Path(data).resolve()),
            split="test",
            device=device,
            imgsz=512,
            batch=4,
            plots=True,
            project=str(root.resolve()),
            name="test-" + size,
        )
        results.append(
            {
                "model": "yolo11" + size + "-seg",
                "epochs_requested": epochs,
                "device": device,
                "seconds": round(time.perf_counter() - started, 2),
                "metrics": {k: float(v) for k, v in metrics.results_dict.items()},
                "per_class": metrics.summary(),
            }
        )
        (root / "comparison.json").write_text(
            json.dumps(results, indent=2, default=float)
        )
    print(json.dumps(results, indent=2, default=float))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("data")
    p.add_argument("output")
    p.add_argument("--epochs", type=int, default=16)
    a = p.parse_args()
    train(a.data, a.output, a.epochs)
