import io
import time

from fastapi.testclient import TestClient
from PIL import Image
import pytest
from starlette.datastructures import UploadFile

import peritaje.main as main


@pytest.fixture(scope="module")
def client():
    if not (main.MODEL_DIRECTORY / "damage-s.onnx").exists():
        pytest.skip("Descarga los modelos para ejecutar la integración ONNX real")
    with TestClient(main.app) as value:
        yield value


def picture():
    buffer = io.BytesIO()
    Image.new("RGB", (320, 240), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def test_real_runtime_and_blank_photo_do_not_invent_a_budget(client):
    assert client.get("/health").json()["status"] == "ok"
    response = client.post(
        "/api/analyze", files={"files": ("plain.png", picture(), "image/png")}
    )
    assert response.status_code == 200
    result = response.json()
    assert result["images"][0]["damages"] == []
    assert result["budget_available"] is False
    assert result["estimates"] == []
    pdf = client.get("/api/reports/" + result["id"] + ".pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert pdf.headers["cache-control"] == "no-store"


def test_rejects_corrupt_files_and_out_of_catalog_vehicle(client):
    assert (
        client.post(
            "/api/analyze",
            files={"files": ("broken.jpg", b"not a photo", "image/jpeg")},
        ).status_code
        == 422
    )
    response = client.post(
        "/api/analyze",
        files={"files": ("plain.png", picture(), "image/png")},
        data={"vehicle_json": '{"brand":"Unknown"}'},
    )
    assert response.status_code == 422
    assert (
        client.post(
            "/api/analyze", files=[("files", ("plain.png", picture(), "image/png"))] * 4
        ).status_code
        == 422
    )


def test_expired_case_is_unavailable(client):
    identifier = "00000000-0000-0000-0000-000000000000"
    main.CASES[identifier] = {"stored_at": time.monotonic() - main.TTL - 1}
    assert client.get("/api/reports/" + identifier + ".pdf").status_code == 404
    assert identifier not in main.CASES


def test_oversized_chunked_body_is_stopped_before_multipart_processing(client):
    def stream():
        for _ in range(38):
            yield b"x" * (1024 * 1024)

    response = client.post(
        "/api/analyze",
        content=stream(),
        headers={"Content-Type": "multipart/form-data; boundary=demo"},
    )
    assert response.status_code == 413


def test_multipart_files_remain_in_memory_below_total_limit(client, monkeypatch):
    original = UploadFile.read
    seen = []

    async def inspect(upload, *args, **kwargs):
        seen.append(getattr(upload.file, "_rolled", None))
        return await original(upload, *args, **kwargs)

    monkeypatch.setattr(UploadFile, "read", inspect)
    image = picture() + b"0" * (2 * 1024 * 1024)
    response = client.post(
        "/api/analyze", files={"files": ("large.png", image, "image/png")}
    )
    assert response.status_code == 200
    assert seen and all(value is False for value in seen)
