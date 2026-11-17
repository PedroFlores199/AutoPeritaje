import argparse
from pathlib import Path
from huggingface_hub import snapshot_download


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    snapshot_download(
        repo_id="DrBimmer/car-parts-and-damage-dataset",
        repo_type="dataset",
        revision="2dbf46f7e23eb0d6f551d38e4f77a11fe9d045b9",
        allow_patterns=["*/img/*", "*/ann/*.json", "*/meta.json", "README.md"],
        local_dir=args.directory,
        token=False,
        max_workers=4,
    )
