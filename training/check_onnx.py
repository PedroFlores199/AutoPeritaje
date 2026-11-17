import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

import numpy as np
import onnxruntime as ort
import torch
from ultralytics.nn.autobackend import AutoBackend

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from peritaje.images import decode
from peritaje.inference import prepare


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("runs", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    tensor = prepare(decode((root / "docs/sample.jpg").read_bytes()), 640)[0]
    torch.set_num_threads(2)
    report = {}
    for name, file in [("damage-covered-s", "damage-s.onnx"), ("s-refined", "parts.onnx")]:
        model = AutoBackend(model=args.runs / name / "weights/best.pt", device="cpu", verbose=False)
        with torch.no_grad():
            reference = model(torch.from_numpy(tensor))[0]
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        path = root / "models" / file
        engine = ort.InferenceSession(str(path), sess_options=options, providers=["CPUExecutionProvider"])
        outputs = engine.run(None, {engine.get_inputs()[0].name: tensor})
        errors = [float(np.max(np.abs(a.cpu().numpy() - b))) for a, b in zip(reference, outputs)]
        passed = errors[0] < .05 and errors[1] < .001
        report[file] = {"maximum_absolute_error_prediction": errors[0], "maximum_absolute_error_prototypes": errors[1], "prediction_tolerance": .05, "prototype_tolerance": .001, "passed": passed, "sha256": sha256(path.read_bytes()).hexdigest(), "input": "Public sample.jpg, same RGB letterbox 640 tensor", "comparison": "Ultralytics PyTorch CPU vs ONNX Runtime CPU raw outputs after removing local paths from metadata"}
        if not passed:
            raise ValueError("La exportación no supera la comprobación numérica")
    args.output.write_text(json.dumps(report, indent=2))
