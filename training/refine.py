import argparse
import json
from pathlib import Path
import time

import torch
from ultralytics import YOLO


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint")
    parser.add_argument("data")
    parser.add_argument("output")
    parser.add_argument("--epochs", type=int, default=48)
    args = parser.parse_args()
    started = time.perf_counter()
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    model = YOLO(args.checkpoint)
    model.train(
        data=str(Path(args.data).resolve()),
        epochs=args.epochs,
        imgsz=640,
        batch=4,
        device=device,
        workers=2,
        project=str(Path(args.output).resolve()),
        name="s-refined",
        seed=42,
        deterministic=True,
        patience=15,
        optimizer="AdamW",
        lr0=0.0005,
        cos_lr=True,
        mosaic=0.3,
        close_mosaic=8,
        fliplr=0.5,
        degrees=5,
        freeze=0,
        overlap_mask=False,
        amp=False,
        plots=True,
        exist_ok=True,
    )
    best = YOLO(Path(args.output) / "s-refined/weights/best.pt")
    validation = best.val(
        data=str(Path(args.data).resolve()),
        split="val",
        device=device,
        imgsz=640,
        batch=4,
        overlap_mask=False,
        plots=True,
        project=str(Path(args.output).resolve()),
        name="refined-validation",
    )
    result = {
        "model": "yolo11s-seg-refined",
        "training": "full backbone, independent masks, initialized from baseline s",
        "epochs_requested": args.epochs,
        "seconds": round(time.perf_counter() - started, 2),
        "selection_split": "validation",
        "metrics": {k: float(v) for k, v in validation.results_dict.items()},
        "per_class": validation.summary(),
    }
    (Path(args.output) / "refinement-validation.json").write_text(
        json.dumps(result, indent=2, default=float)
    )


if __name__ == "__main__":
    main()
