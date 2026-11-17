import argparse
from collections import Counter
import json
import os
from pathlib import Path
import yaml

from prepare import DAMAGE_CLASSES, PART_CLASSES


def prepare_tasks(source, prepared, destination):
    manifest = json.loads((prepared / "manifest.json").read_text())
    report = {
        "method": "Preserve global SHA256 splits; include an image only in tasks for which it has annotations. Images annotated only for parts are not damage negatives. Folder names are not trusted: coverage is inferred from actual classTitle values.",
        "tasks": {},
    }
    for task, names, offset in [
        ("damage", DAMAGE_CLASSES, 0),
        ("parts", PART_CLASSES, 8),
    ]:
        target = destination / task
        counts, instances = Counter(), Counter()
        selected_ids = []
        for item in manifest["manifest"]:
            annotated = set()
            for origin in item["origins"]:
                image = source / origin
                annotation = image.parent.parent / "ann" / (image.name + ".json")
                annotated.update(
                    obj.get("classTitle")
                    for obj in json.loads(annotation.read_text()).get("objects", [])
                )
            if not annotated.intersection(names):
                continue
            split, identity = item["split"], item["id"]
            images, labels = target / "images" / split, target / "labels" / split
            images.mkdir(parents=True, exist_ok=True)
            labels.mkdir(parents=True, exist_ok=True)
            image_path = images / (identity + ".jpg")
            if not image_path.exists():
                os.link(prepared / "images" / split / image_path.name, image_path)
            values = []
            for line in (
                (prepared / "labels" / split / (identity + ".txt"))
                .read_text()
                .splitlines()
            ):
                category, coordinates = line.split(" ", 1)
                category = int(category)
                if offset <= category < offset + len(names):
                    values.append(str(category - offset) + " " + coordinates)
                    instances[names[category - offset]] += 1
            assert values, "An annotated task must retain valid polygons"
            (labels / (identity + ".txt")).write_text("\n".join(values) + "\n")
            counts[split] += 1
            selected_ids.append({"id": identity, "split": split})
        config = {
            "path": str(target.resolve()),
            "train": "images/train",
            "val": "images/val",
            "test": "images/test",
            "names": names,
        }
        (target / "dataset.yaml").write_text(yaml.safe_dump(config, sort_keys=False))
        report["tasks"][task] = {
            "splits": dict(counts),
            "instances": dict(instances),
            "known_clean_negative_images": 0,
            "manifest": selected_ids,
        }
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "coverage-audit.json").write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("prepared", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    report = prepare_tasks(args.source, args.prepared, args.destination)
    print(
        json.dumps(
            {
                name: {k: v for k, v in task.items() if k != "manifest"}
                for name, task in report["tasks"].items()
            },
            indent=2,
        )
    )
