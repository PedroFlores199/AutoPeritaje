import io
import numpy as np
from PIL import Image
import pytest
from peritaje.inference import Detection, nms, prepare, describe
from peritaje.images import decode, encode


def test_nms_is_class_aware():
    boxes = np.array([[0, 0, 100, 100], [1, 1, 99, 99], [1, 1, 99, 99]], dtype=float)
    keep = nms(boxes, np.array([0.9, 0.8, 0.7]), np.array([0, 0, 1]))
    assert keep.tolist() == [0, 2]


def test_letterbox_does_not_distort_aspect_ratio():
    tensor, (ratio, left, top, width, height) = prepare(
        np.zeros((100, 200, 3), dtype=np.uint8)
    )
    assert (
        tensor.shape == (1, 3, 512, 512)
        and width == 512
        and height == 256
        and top == 128
        and left == 0
    )
    assert ratio == 2.56


def test_damage_piece_uses_mask_overlap_and_keeps_unknown_when_unmatched():
    damage = np.zeros((20, 20), dtype=bool)
    damage[2:5, 2:5] = True
    part = np.zeros((20, 20), dtype=bool)
    part[:10, :10] = True
    rows = describe(
        [
            Detection(0, 0.9, np.array([2, 2, 5, 5]), damage),
            Detection(12, 0.8, np.array([0, 0, 10, 10]), part),
        ]
    )
    assert rows[0]["part"] == "Puerta delantera" and rows[0]["repair_part"] == "Puerta"
    rows = describe([Detection(0, 0.9, np.array([2, 2, 5, 5]), damage)])
    assert rows[0]["part"] == "Sin determinar"


def test_non_image_is_rejected():
    with pytest.raises(ValueError):
        decode(b"not an image")


def test_encoded_result_does_not_keep_source_metadata():
    image = Image.new("RGB", (100, 80), "white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    decoded = decode(buffer.getvalue())
    result = encode(decoded)
    with Image.open(io.BytesIO(result)) as opened:
        assert opened.size == (100, 80) and not opened.getexif()
