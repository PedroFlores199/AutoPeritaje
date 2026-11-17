from hashlib import sha256
import io
from pathlib import Path
import tarfile
import urllib.request

COMMIT = "51320c0ed1ebfb206b8999d7bbd79aa548c1c02b"
SHA256 = "5d0b4fa49b9a3e56e35b1b627681765b292dcf8cf2e62afb9a3a82a839f1bd4b"


def download():
    root = Path(__file__).resolve().parents[1]
    url = "https://codeload.github.com/PedroFlores199/TallerMLOps/tar.gz/" + COMMIT
    with urllib.request.urlopen(url, timeout=60) as response:
        raw = response.read(10 * 1024 * 1024)
    if sha256(raw).hexdigest() != SHA256:
        raise ValueError(
            "La copia de TallerMLOps no coincide con la revisión verificada"
        )
    target = root / "pricing"
    target.mkdir(exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
        for member in archive.getmembers():
            parts = Path(member.name).parts[1:]
            if not parts or ".." in parts or member.issym() or member.islnk():
                continue
            if parts[0] not in {"taller", "data", "LICENSE", "NOTICE.md"}:
                continue
            destination = target.joinpath(*parts)
            if member.isdir():
                destination.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(archive.extractfile(member).read())
    print("TallerMLOps: revisión y huella verificadas")


if __name__ == "__main__":
    download()
