import argparse
from hashlib import sha256
import json
from pathlib import Path
import urllib.request


def download(directory=None):
    root = Path(__file__).resolve().parents[1]
    directory = Path(directory or root / "models")
    directory.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((root / "models/manifest.json").read_text())
    for name in ("damage", "parts"):
        item = manifest[name]
        target = directory / item["file"]
        if target.exists():
            if sha256(target.read_bytes()).hexdigest() != item["sha256"]:
                raise ValueError(
                    "El archivo existente no coincide con el manifiesto: " + target.name
                )
            print(target.name + ": huella verificada")
            continue
        url = (
            "https://github.com/PedroFlores199/AutoPeritaje/releases/download/models-v1/"
            + item["file"]
        )
        temporary = target.with_suffix(".download")
        try:
            digest, size = sha256(), 0
            with (
                urllib.request.urlopen(url, timeout=120) as response,
                temporary.open("wb") as output,
            ):
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > item["bytes"]:
                        raise ValueError("El archivo supera el tamaño esperado")
                    digest.update(chunk)
                    output.write(chunk)
            if size != item["bytes"] or digest.hexdigest() != item["sha256"]:
                raise ValueError("La descarga no coincide con el manifiesto")
            temporary.replace(target)
            print(target.name + ": descargado y verificado")
        finally:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path)
    download(parser.parse_args().directory)
