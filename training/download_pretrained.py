import argparse
from hashlib import sha256
import json
from pathlib import Path
import urllib.request


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(
        Path(__file__).with_name("pretrained-manifest.json").read_text()
    )
    for item in manifest:
        file = args.directory / item["file"]
        if not file.exists():
            with urllib.request.urlopen(item["url"], timeout=120) as response:
                raw = response.read(item["bytes"] + 1)
            if len(raw) != item["bytes"] or sha256(raw).hexdigest() != item["sha256"]:
                raise ValueError(
                    "Los pesos iniciales no coinciden con la huella verificada"
                )
            file.write_bytes(raw)
        if sha256(file.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError("La huella de los pesos iniciales no coincide")
        print(file.name + ": verificado")
