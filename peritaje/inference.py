from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from threading import Lock
import time
import cv2
import numpy as np
import onnxruntime as ort

ort.disable_telemetry_events()
from .domain import (
    CLASSES,
    DAMAGE_CLASSES,
    DAMAGE_NAMES,
    PART_NAMES,
    PART_REPAIR,
    REPAIR_MAP,
)


@dataclass
class Detection:
    class_id: int
    confidence: float
    box: np.ndarray
    mask: np.ndarray


def iou_one(box, others):
    intersection = np.maximum(
        0, np.minimum(box[2:], others[:, 2:]) - np.maximum(box[:2], others[:, :2])
    ).prod(axis=1)
    area = np.maximum(0, box[2:] - box[:2]).prod()
    areas = np.maximum(0, others[:, 2:] - others[:, :2]).prod(axis=1)
    return intersection / np.maximum(area + areas - intersection, 1e-9)


def nms(boxes, scores, classes, threshold=0.45, limit=100):
    remaining = np.argsort(scores)[::-1]
    keep = []
    while len(remaining) and len(keep) < limit:
        chosen = int(remaining[0])
        keep.append(chosen)
        rest = remaining[1:]
        suppress = (classes[rest] == classes[chosen]) & (
            iou_one(boxes[chosen], boxes[rest]) > threshold
        )
        remaining = rest[~suppress]
    return np.array(keep, dtype=int)


def prepare(rgb, size=512):
    height, width = rgb.shape[:2]
    ratio = min(size / width, size / height)
    new_width, new_height = round(width * ratio), round(height * ratio)
    resized = cv2.resize(rgb, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
    left = (size - new_width) // 2
    top = (size - new_height) // 2
    canvas = np.full((size, size, 3), 114, dtype=np.uint8)
    canvas[top : top + new_height, left : left + new_width] = resized
    return np.ascontiguousarray(
        canvas.transpose(2, 0, 1)[None], dtype=np.float32
    ) / 255, (ratio, left, top, new_width, new_height)


class Segmenter:
    def __init__(self, path, expected_sha=None, threads=2, class_ids=None):
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError("No se encuentra el modelo ONNX")
        self.sha256 = sha256(path.read_bytes()).hexdigest()
        if expected_sha and self.sha256 != expected_sha:
            raise ValueError("La huella del modelo ONNX no coincide")
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(
            str(path), sess_options=options, providers=["CPUExecutionProvider"]
        )
        self.input_name = self.session.get_inputs()[0].name
        self.lock = Lock()
        shape = self.session.get_inputs()[0].shape
        if (
            len(shape) != 4
            or shape[:2] != [1, 3]
            or shape[2] != shape[3]
            or shape[2] not in (512, 640)
        ):
            raise ValueError(
                "El modelo debe aceptar una imagen RGB cuadrada de 512 o 640 píxeles"
            )
        self.size = shape[2]
        self.class_ids = list(range(len(CLASSES))) if class_ids is None else class_ids
        if not self.class_ids or any(
            value not in range(len(CLASSES)) for value in self.class_ids
        ):
            raise ValueError("Vocabulario no válido")

    def predict(self, rgb, confidence=0.3):
        if not 0.05 <= confidence <= 0.95:
            raise ValueError("Umbral fuera de rango")
        tensor, transform = prepare(rgb, self.size)
        ratio, left, top, new_width, new_height = transform
        height, width = rgb.shape[:2]
        started = time.perf_counter()
        with self.lock:
            outputs = self.session.run(None, {self.input_name: tensor})
        elapsed = (time.perf_counter() - started) * 1000
        prediction = outputs[0][0].T
        prototypes = outputs[1][0]
        count = len(self.class_ids)
        if prediction.shape[1] != 4 + count + prototypes.shape[0]:
            raise ValueError("El vocabulario del modelo no coincide con el manifiesto")
        scores = prediction[:, 4 : 4 + count].max(axis=1)
        classes = prediction[:, 4 : 4 + count].argmax(axis=1)
        valid = scores >= confidence
        prediction, scores, classes = prediction[valid], scores[valid], classes[valid]
        if not len(scores):
            return [], elapsed
        boxes = np.column_stack(
            (
                prediction[:, :2] - prediction[:, 2:4] / 2,
                prediction[:, :2] + prediction[:, 2:4] / 2,
            )
        )
        keep = nms(boxes, scores, classes)
        boxes = boxes[keep]
        scores = scores[keep]
        classes = classes[keep]
        coefficients = prediction[keep, 4 + count :]
        masks = coefficients @ prototypes.reshape(prototypes.shape[0], -1)
        masks = 1 / (1 + np.exp(-np.clip(masks, -35, 35)))
        masks = masks.reshape(-1, *prototypes.shape[1:])
        detections = []
        for box, score, class_id, mask in zip(boxes, scores, classes, masks):
            mask = cv2.resize(
                mask, (self.size, self.size), interpolation=cv2.INTER_LINEAR
            )
            crop = np.zeros((self.size, self.size), dtype=np.float32)
            x1, y1, x2, y2 = np.clip(box, 0, self.size).astype(int)
            crop[y1:y2, x1:x2] = mask[y1:y2, x1:x2]
            original = (
                cv2.resize(
                    crop[top : top + new_height, left : left + new_width],
                    (width, height),
                    interpolation=cv2.INTER_LINEAR,
                )
                > 0.5
            )
            scaled = (box - np.array([left, top, left, top])) / ratio
            scaled[[0, 2]] = np.clip(scaled[[0, 2]], 0, width)
            scaled[[1, 3]] = np.clip(scaled[[1, 3]], 0, height)
            if original.sum() < 4:
                continue
            detections.append(
                Detection(self.class_ids[int(class_id)], float(score), scaled, original)
            )
        return detections, elapsed


class InspectionModels:
    def __init__(self, directory, manifest, threads=2):
        directory = Path(directory)
        self.damage = Segmenter(
            directory / manifest["damage"]["file"],
            manifest["damage"]["sha256"],
            threads,
            list(range(8)),
        )
        self.parts = Segmenter(
            directory / manifest["parts"]["file"], manifest["parts"]["sha256"], threads
        )
        self.sha256 = sha256(
            (self.damage.sha256 + self.parts.sha256).encode()
        ).hexdigest()

    def predict(self, rgb, confidence=0.3):
        started = time.perf_counter()
        damages, _ = self.damage.predict(rgb, confidence)
        parts, _ = self.parts.predict(rgb, max(0.25, confidence))
        return damages + [part for part in parts if part.class_id >= 8], (
            time.perf_counter() - started
        ) * 1000


def describe(detections):
    parts = [d for d in detections if d.class_id >= len(DAMAGE_CLASSES)]
    rows = []
    for damage in [d for d in detections if d.class_id < len(DAMAGE_CLASSES)]:
        label = CLASSES[damage.class_id]
        area = int(damage.mask.sum())
        best = None
        overlap = 0.0
        for part in parts:
            score = float((damage.mask & part.mask).sum() / max(area, 1))
            if score > overlap:
                best, overlap = part, score
        if best is not None and overlap >= 0.15:
            part_class = CLASSES[best.class_id]
            part_name = PART_NAMES.get(part_class, part_class)
            fraction = min(1.0, area / max(int(best.mask.sum()), 1))
            repair_part = PART_REPAIR.get(part_class, "Sin determinar")
        else:
            part_class = None
            part_name = "Sin determinar"
            fraction = area / damage.mask.size
            repair_part = "Sin determinar"
        severity = 3 if fraction > 0.35 else 2 if fraction > 0.08 else 1
        rows.append(
            {
                "damage": label,
                "name": DAMAGE_NAMES[label],
                "confidence": round(damage.confidence, 4),
                "box": [round(float(v), 1) for v in damage.box],
                "part": part_name,
                "part_class": part_class,
                "part_overlap": round(overlap, 3),
                "severity": severity,
                "area_fraction": round(float(fraction), 4),
                "repair": REPAIR_MAP[label],
                "repair_part": repair_part,
                "severity_method": "Heurística por área segmentada; no mide profundidad ni daño interno.",
            }
        )
    return rows
