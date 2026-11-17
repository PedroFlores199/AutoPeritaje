import io
import warnings
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
from .domain import DAMAGE_CLASSES, CLASSES, DAMAGE_NAMES

MAX_BYTES = 12 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 20_000_000


def decode(raw):
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError("Cada imagen debe ocupar entre 1 byte y 12 MB")
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        try:
            with Image.open(io.BytesIO(raw)) as source:
                if source.format not in ["JPEG", "PNG", "WEBP"]:
                    raise ValueError("Formato de imagen no admitido")
                source.load()
                image = ImageOps.exif_transpose(source).convert("RGB")
                image.thumbnail((1600, 1600))
                array = np.asarray(image).copy()
        except (
            OSError,
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
        ) as error:
            raise ValueError("No se ha podido abrir la imagen con seguridad") from error
    return array


def encode(array):
    output = io.BytesIO()
    Image.fromarray(array).save(output, format="PNG")
    return output.getvalue()


def annotate(rgb, detections, show_labels=True):
    image = Image.fromarray(rgb).convert("RGBA")
    overlay = np.zeros((*rgb.shape[:2], 4), dtype=np.uint8)
    colors = [
        (211, 103, 55),
        (209, 158, 49),
        (186, 78, 69),
        (153, 100, 174),
        (73, 148, 164),
        (148, 110, 73),
        (207, 114, 139),
        (131, 142, 65),
    ]
    for detection in detections:
        if detection.class_id >= len(DAMAGE_CLASSES):
            continue
        color = colors[detection.class_id % len(colors)]
        overlay[detection.mask] = (*color, 100)
    image = Image.alpha_composite(image, Image.fromarray(overlay))
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype(
            str(Path(__file__).parent / "fonts/DejaVuSans.ttf"),
            max(20, min(40, rgb.shape[1] // 32)),
        )
    except OSError:
        font = ImageFont.load_default(size=max(20, min(40, rgb.shape[1] // 32)))
    for detection in detections:
        if detection.class_id >= len(DAMAGE_CLASSES):
            continue
        x1, y1, x2, y2 = map(int, detection.box)
        color = colors[detection.class_id % len(colors)]
        draw.rectangle((x1, y1, x2, y2), outline=(*color, 255), width=3)
        if not show_labels:
            continue
        label = (
            DAMAGE_NAMES[CLASSES[detection.class_id]] + f" {detection.confidence:.0%}"
        )
        bounds = draw.textbbox((x1, y1), label, font=font)
        height = bounds[3] - bounds[1] + 10
        top = max(0, y1 - height)
        draw.rectangle(
            (x1, top, min(rgb.shape[1], x1 + bounds[2] - bounds[0] + 12), top + height),
            fill=(*color, 255),
        )
        draw.text((x1 + 5, top + 3), label, font=font, fill="white")
    return np.asarray(image.convert("RGB"))
