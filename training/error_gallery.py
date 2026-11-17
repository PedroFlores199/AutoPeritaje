import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from peritaje.images import annotate, decode
from peritaje.inference import Detection, InspectionModels


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    models = InspectionModels(
        root / "models", json.loads((root / "models/manifest.json").read_text())
    )
    selected, used = [], set()
    for category in (0, 1, 6, 7):
        for file in sorted((args.dataset / "labels/test").glob("*.txt")):
            if file.stem not in used and any(
                int(line.split()[0]) == category
                for line in file.read_text().splitlines()
            ):
                selected.append(file)
                used.add(file.stem)
                break
    sheet = Image.new("RGB", (1200, len(selected) * 460), "white")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(str(root / "peritaje/fonts/DejaVuSans.ttf"), 17)
    results = []
    for index, labels in enumerate(selected):
        image_file = args.dataset / "images/test" / (labels.stem + ".jpg")
        rgb = decode(image_file.read_bytes())
        height, width = rgb.shape[:2]
        truth = []
        for line in labels.read_text().splitlines():
            values = line.split()
            points = np.array(values[1:], dtype=float).reshape(-1, 2) * [width, height]
            mask = np.zeros((height, width), dtype=np.uint8)
            cv2.fillPoly(mask, [points.astype(np.int32)], 1)
            box = np.concatenate([points.min(axis=0), points.max(axis=0)])
            truth.append(Detection(int(values[0]), 1.0, box, mask.astype(bool)))
        prediction, elapsed = models.predict(rgb, 0.25)
        prediction = [value for value in prediction if value.class_id < 8]
        matched, tp = set(), 0
        for value in sorted(prediction, key=lambda item: -item.confidence):
            overlaps = [
                float(
                    (value.mask & reference.mask).sum()
                    / max((value.mask | reference.mask).sum(), 1)
                )
                if value.class_id == reference.class_id and j not in matched
                else 0.0
                for j, reference in enumerate(truth)
            ]
            if overlaps and max(overlaps) >= 0.5:
                matched.add(int(np.argmax(overlaps)))
                tp += 1
        for column, values in enumerate((truth, prediction)):
            image = Image.fromarray(annotate(rgb, values, show_labels=column != 0))
            image.thumbnail((570, 370))
            sheet.paste(
                image, (column * 600 + 15 + (570 - image.width) // 2, index * 460 + 55)
            )
            draw.text(
                (column * 600 + 16, index * 460 + 12),
                (
                    "Referencia del dataset"
                    if column == 0
                    else "Predicción ONNX · umbral 25 %"
                ),
                font=font,
                fill="#17541f",
            )
        fp, fn = len(prediction) - tp, len(truth) - tp
        draw.text(
            (16, index * 460 + 427),
            f"{labels.stem[:12]} · Coincidencias IoU ≥ 0,5: {tp} · Propuestas no coincidentes: {fp} · Omitidos: {fn}",
            font=font,
            fill="#343e38",
        )
        results.append(
            {
                "id": labels.stem,
                "split": "internal_test",
                "threshold": 0.25,
                "true_positive_mask_iou50": tp,
                "unmatched_predictions": fp,
                "unmatched_reference_masks": fn,
                "inference_ms": round(elapsed, 2),
                "prepared_image_sha256": sha256(image_file.read_bytes()).hexdigest(),
            }
        )
    args.output.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output / "error-gallery.jpg", quality=92)
    (args.output / "error-examples.json").write_text(
        json.dumps(
            {
                "selection": "First distinct SHA-sorted internal-test image containing Dent, Scratch, Cracked and Flaking; not selected for visual success.",
                "cases": results,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
