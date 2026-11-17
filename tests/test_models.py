import json
from pathlib import Path

import numpy as np
import pytest

from peritaje.inference import InspectionModels, Segmenter


ROOT = Path(__file__).resolve().parents[1]


def test_model_checksum_is_enforced_before_session_creation(tmp_path):
    source = tmp_path / "unexpected.onnx"
    source.write_bytes(b"corrupt model")
    with pytest.raises(ValueError, match="huella"):
        Segmenter(source, "0" * 64)


def test_damage_expert_maps_eight_classes_and_discards_joint_damage_predictions():
    if not (ROOT / "models/damage-s.onnx").exists():
        pytest.skip("Descarga los modelos ONNX")
    models = InspectionModels(
        ROOT / "models", json.loads((ROOT / "models/manifest.json").read_text())
    )
    detections, elapsed = models.predict(np.full((300, 400, 3), 255, dtype=np.uint8))
    assert elapsed > 0
    assert all(0 <= item.class_id < 29 for item in detections)
    assert models.damage.size == models.parts.size == 640
