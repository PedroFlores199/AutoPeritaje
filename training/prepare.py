import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from PIL import Image
import yaml

DAMAGE_CLASSES = [
    "Dent",
    "Scratch",
    "Broken part",
    "Missing part",
    "Paint chip",
    "Corrosion",
    "Cracked",
    "Flaking",
]
PART_CLASSES = [
    "Front-bumper",
    "Back-bumper",
    "Hood",
    "Trunk",
    "Front-door",
    "Back-door",
    "Fender",
    "Quarter-panel",
    "Rocker-panel",
    "Roof",
    "Windshield",
    "Back-windshield",
    "Front-window",
    "Back-window",
    "Headlight",
    "Tail-light",
    "Mirror",
    "Front-wheel",
    "Back-wheel",
    "Grille",
    "License-plate",
]
CLASSES = DAMAGE_CLASSES + PART_CLASSES


def prepare(source, output):
    source, output = Path(source), Path(output)
    grouped = {}
    rejected = []
    for ann in sorted(source.rglob("ann/*.json")):
        image = ann.parent.parent / "img" / ann.name[:-5]
        if not image.exists():
            rejected.append({"file": str(ann), "reason": "missing image"})
            continue
        digest = sha256(image.read_bytes()).hexdigest()
        group = grouped.setdefault(
            digest, {"image": image, "annotations": [], "origins": []}
        )
        group["annotations"].extend(json.loads(ann.read_text()).get("objects", []))
        group["origins"].append(str(image.relative_to(source)))
    counts = Counter()
    instances = Counter()
    manifest = []
    for digest, group in grouped.items():
        value = int(digest[:8], 16) % 100
        split = "train" if value < 72 else "val" if value < 86 else "test"
        with Image.open(group["image"]) as im:
            im.verify()
        with Image.open(group["image"]) as im:
            width, height = im.size
            im = im.convert("RGB")
            im.thumbnail((1280, 1280))
            destination = output / "images" / split / (digest + ".jpg")
            destination.parent.mkdir(parents=True, exist_ok=True)
            im.save(destination, quality=93)
        labels = set()
        for obj in group["annotations"]:
            name = obj.get("classTitle")
            points = obj.get("points", {}).get("exterior", [])
            if name not in CLASSES or len(points) < 3:
                continue
            normalized = [
                (
                    max(0, min(0.999999, float(x) / width)),
                    max(0, min(0.999999, float(y) / height)),
                )
                for x, y in points
            ]
            if len(set(normalized)) < 3:
                continue
            label = (
                str(CLASSES.index(name))
                + " "
                + " ".join(f"{x:.6f} {y:.6f}" for x, y in normalized)
            )
            labels.add(label)
        if not labels:
            destination.unlink()
            rejected.append({"file": group["origins"][0], "reason": "no valid polygon"})
            continue
        target = output / "labels" / split / (digest + ".txt")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(sorted(labels)) + "\n")
        for line in labels:
            instances[CLASSES[int(line.split()[0])]] += 1
        counts[split] += 1
        manifest.append(
            {
                "id": digest,
                "split": split,
                "origins": group["origins"],
                "instances": len(labels),
            }
        )
    output.mkdir(parents=True, exist_ok=True)
    (output / "dataset.yaml").write_text(
        yaml.safe_dump(
            {
                "path": str(output.resolve()),
                "train": "images/train",
                "val": "images/val",
                "test": "images/test",
                "names": dict(enumerate(CLASSES)),
            },
            sort_keys=False,
        )
    )
    report = {
        "source": "https://huggingface.co/datasets/DrBimmer/car-parts-and-damage-dataset",
        "revision": "2dbf46f7e23eb0d6f551d38e4f77a11fe9d045b9",
        "declared_license": "MIT",
        "split_method": "SHA256 modulo 100, 72/14/14; duplicates grouped before split",
        "splits": dict(counts),
        "instances": dict(instances),
        "rejected": rejected,
        "manifest": manifest,
    }
    (output / "manifest.json").write_text(json.dumps(report, indent=2))
    assert len({m["id"] for m in manifest}) == len(manifest)
    print(
        json.dumps(
            {
                "splits": dict(counts),
                "classes": len(CLASSES),
                "instances": dict(instances),
                "rejected": len(rejected),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("output")
    args = parser.parse_args()
    prepare(args.source, args.output)
