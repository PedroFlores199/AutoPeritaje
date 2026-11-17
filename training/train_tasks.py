import argparse
import json
from pathlib import Path
import time
import torch
from ultralytics import YOLO


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("data", type=Path)
    parser.add_argument("weights", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--sizes", nargs="+", choices=["n", "s"], default=["n", "s"])
    args = parser.parse_args()
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    args.output.mkdir(parents=True, exist_ok=True)
    for size in args.sizes:
        started = time.perf_counter()
        name = f"damage-covered-{size}"
        model = YOLO(args.weights / f"yolo11{size}-seg.pt")
        model.train(
            data=str(args.data.resolve()),
            epochs=args.epochs,
            imgsz=640,
            batch=8 if size == "n" else 4,
            device=device,
            workers=2,
            project=str(args.output.resolve()),
            name=name,
            seed=42,
            deterministic=True,
            patience=18,
            optimizer="AdamW",
            lr0=0.001,
            cos_lr=True,
            mosaic=0.2,
            close_mosaic=10,
            fliplr=0.5,
            degrees=5,
            scale=0.3,
            freeze=0,
            overlap_mask=False,
            amp=False,
            plots=True,
            exist_ok=True,
        )
        best = YOLO(args.output / name / "weights/best.pt")
        result = best.val(
            data=str(args.data.resolve()),
            split="val",
            device=device,
            imgsz=640,
            batch=4,
            overlap_mask=False,
            plots=True,
            project=str(args.output.resolve()),
            name=name + "-validation",
        )
        report = {
            "model": f"YOLO11{size}-seg",
            "data_coverage": "Only images annotated for damage; no parts-only images as negative examples",
            "selection_split": "validation",
            "epochs_requested": args.epochs,
            "seconds": round(time.perf_counter() - started, 2),
            "metrics": {k: float(v) for k, v in result.results_dict.items()},
            "per_class": result.summary(),
        }
        (args.output / (name + "-validation.json")).write_text(
            json.dumps(report, indent=2, default=float)
        )


if __name__ == "__main__":
    main()
