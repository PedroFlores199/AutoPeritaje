import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import time

import numpy as np
import onnxruntime as ort
import onnx
import torch
from ultralytics import YOLO
import yaml


def evaluate(checkpoint, data, split, output, name, classes=None):
    model = YOLO(checkpoint)
    result = model.val(
        data=str(data.resolve()),
        split=split,
        device="mps" if torch.backends.mps.is_available() else "cpu",
        imgsz=640,
        batch=4,
        overlap_mask=False,
        plots=True,
        project=str(output.resolve()),
        name=name,
        exist_ok=True,
        classes=classes,
    )
    return {
        "split": split,
        "metrics": {key: float(value) for key, value in result.results_dict.items()},
        "per_class": result.summary(),
    }


def export(checkpoint, destination, threads=2):
    model = YOLO(checkpoint)
    file = Path(
        model.export(
            format="onnx",
            imgsz=640,
            dynamic=False,
            simplify=False,
            opset=17,
            device="cpu",
            nms=False,
        )
    )
    shutil.copyfile(file, destination)
    exported = onnx.load(destination)
    for item in exported.metadata_props:
        if item.key == "description":
            item.value = (
                "AutoPeritaje "
                + destination.stem
                + "; dataset and training configuration in the public repository"
            )
    exported.doc_string = ""
    exported.graph.doc_string = ""
    for node in exported.graph.node:
        node.doc_string = ""
    onnx.save(exported, destination)
    options = ort.SessionOptions()
    options.intra_op_num_threads = threads
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(
        str(destination), sess_options=options, providers=["CPUExecutionProvider"]
    )
    tensor = np.random.default_rng(42).random((1, 3, 640, 640), dtype=np.float32)
    name = session.get_inputs()[0].name
    for _ in range(3):
        session.run(None, {name: tensor})
    timings = []
    for _ in range(12):
        started = time.perf_counter()
        session.run(None, {name: tensor})
        timings.append((time.perf_counter() - started) * 1000)
    return {
        "file": destination.name,
        "sha256": sha256(destination.read_bytes()).hexdigest(),
        "bytes": destination.stat().st_size,
        "input_size": 640,
        "classes": model.names,
        "runtime": ort.__version__,
        "threads": threads,
        "cpu_forward_ms": {
            "median": round(float(np.median(timings)), 2),
            "p95": round(float(np.percentile(timings, 95)), 2),
            "runs": len(timings),
            "warmup": 3,
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("runs", type=Path)
    parser.add_argument("data", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    reports = {}
    for size in ("n", "s"):
        checkpoint = args.runs / f"damage-covered-{size}/weights/best.pt"
        report = evaluate(
            checkpoint,
            args.data / "damage/dataset.yaml",
            "test",
            args.runs,
            f"final-damage-{size}-test",
        )
        report["onnx"] = export(checkpoint, args.output / f"damage-{size}.onnx")
        reports[size] = report
        (args.output / "damage-test.json").write_text(
            json.dumps(reports, indent=2, default=float)
        )
    from prepare import DAMAGE_CLASSES, PART_CLASSES

    parts = args.data / "parts"
    target = args.data / "parts29"
    target.mkdir(exist_ok=True)
    for split in ("train", "val", "test"):
        (target / "images" / split).mkdir(parents=True, exist_ok=True)
        (target / "labels" / split).mkdir(parents=True, exist_ok=True)
        for image in (parts / "images" / split).glob("*.jpg"):
            link = target / "images" / split / image.name
            if not link.exists():
                link.symlink_to(image.resolve())
            original = parts / "labels" / split / (image.stem + ".txt")
            rows = [
                str(int(row.split(" ", 1)[0]) + 8) + " " + row.split(" ", 1)[1]
                for row in original.read_text().splitlines()
            ]
            (target / "labels" / split / original.name).write_text(
                "\n".join(rows) + "\n"
            )
    config = {
        "path": str(target.resolve()),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "names": DAMAGE_CLASSES + PART_CLASSES,
    }
    data = target / "dataset.yaml"
    data.write_text(yaml.safe_dump(config, sort_keys=False))
    checkpoint = args.runs / "s-refined/weights/best.pt"
    parts_report = {
        "validation": evaluate(
            checkpoint, data, "val", args.runs, "final-parts-val", list(range(8, 29))
        ),
        "test": evaluate(
            checkpoint, data, "test", args.runs, "final-parts-test", list(range(8, 29))
        ),
        "onnx": export(checkpoint, args.output / "parts.onnx"),
        "limitation": "Parts expert originates from a joint model trained before coverage correction; damage outputs are discarded. Evaluation uses only images annotated for parts.",
    }
    (args.output / "parts-test.json").write_text(
        json.dumps(parts_report, indent=2, default=float)
    )


if __name__ == "__main__":
    main()
