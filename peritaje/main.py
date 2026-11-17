import asyncio
import base64
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from uuid import uuid4
import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError, model_validator
from starlette.formparsers import MultiPartParser
from .images import MAX_BYTES, annotate, decode, encode
from .inference import InspectionModels, describe
from .report import build_report

ROOT = Path(__file__).parent.parent
STATIC = Path(__file__).parent / "static"
STATIC.mkdir(exist_ok=True)
MODEL_DIRECTORY = Path(os.getenv("MODEL_DIRECTORY", ROOT / "models"))
TALLER_URL = os.getenv("TALLER_URL", "http://localhost:5105")
CASES = {}
MAX_CASES = 20
TTL = 15 * 60
semaphore = asyncio.Semaphore(1)
request_slots = asyncio.Semaphore(2)
MAX_REQUEST = MAX_BYTES * 3 + 100000
MultiPartParser.spool_max_size = MAX_REQUEST + 1
segmenter = None
CATALOG = json.loads((ROOT / "peritaje/vehicle-catalog.json").read_text())
pricing_app = None
if os.getenv("BUNDLED_PRICING") == "1":
    from taller.main import app as pricing_app


class Vehicle(BaseModel):
    brand: str
    model: str
    year: int = Field(ge=2004, le=2026)
    kilometers: int = Field(ge=0, le=600000)
    region: str
    engine: str
    parts_price_index: float = Field(default=1.0, ge=0.7, le=1.5)

    @model_validator(mode="after")
    def validate_catalog(self):
        if (
            self.brand not in CATALOG["brands"]
            or self.model not in CATALOG["brands"][self.brand]
        ):
            raise ValueError("Marca o modelo fuera del catálogo de demostración")
        if (
            self.region not in CATALOG["regions"]
            or self.engine not in CATALOG["engines"]
        ):
            raise ValueError("Provincia o motorización fuera del catálogo")
        return self


def cleanup():
    expired = [
        key
        for key, value in CASES.items()
        if time.monotonic() - value["stored_at"] > TTL
    ]
    for key in expired:
        CASES.pop(key, None)
    while len(CASES) > MAX_CASES:
        CASES.pop(next(iter(CASES)))


@asynccontextmanager
async def lifespan(app):
    global segmenter
    manifest = json.loads((ROOT / "models/manifest.json").read_text())
    segmenter = InspectionModels(MODEL_DIRECTORY, manifest)

    async def collect():
        while True:
            await asyncio.sleep(30)
            cleanup()

    task = asyncio.create_task(collect())
    yield
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
    CASES.clear()


app = FastAPI(title="AutoPeritaje", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


class BoundedUploads:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] != "http"
            or scope.get("method") != "POST"
            or scope.get("path") != "/api/analyze"
        ):
            return await self.app(scope, receive, send)
        if request_slots.locked():
            return await Response(
                "Hay análisis en curso. Vuelve a intentarlo en unos segundos.",
                status_code=429,
            )(scope, receive, send)
        async with request_slots:
            chunks, total = [], 0
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                chunk = message.get("body", b"")
                total += len(chunk)
                if total > MAX_REQUEST:
                    return await Response(
                        "Solicitud demasiado grande", status_code=413
                    )(scope, receive, send)
                chunks.append(chunk)
                if not message.get("more_body"):
                    break
            body = b"".join(chunks)
            chunks.clear()
            delivered = False

            async def memory_receive():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": body, "more_body": False}
                return await receive()

            await self.app(scope, memory_receive, send)


app.add_middleware(BoundedUploads)


@app.middleware("http")
async def limit_request(request, call_next):
    length = request.headers.get("content-length")
    if length:
        try:
            size = int(length)
        except ValueError:
            return Response("Cabecera de tamaño no válida", status_code=400)
        if size < 0:
            return Response("Tamaño no válido", status_code=400)
        if size > MAX_REQUEST:
            return Response("Solicitud demasiado grande", status_code=413)
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    elif request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/health")
def health():
    return {
        "status": "ok" if segmenter else "loading",
        "model": "YOLO11s-seg · expertos de daños y piezas",
        "runtime": "ONNXRuntime CPU",
        "sha256": segmenter.sha256 if segmenter else None,
    }


@app.get("/api/catalog")
def catalog():
    return CATALOG


@app.get("/api/sample")
def sample():
    return FileResponse(ROOT / "docs/sample.jpg", media_type="image/jpeg")


async def estimate(damages, vehicle):
    groups = {}
    for damage in damages:
        key = (damage["repair"], damage["repair_part"])
        groups[key] = max(groups.get(key, 0), damage["severity"])
    results = []
    slots = asyncio.Semaphore(4)
    transport = httpx.ASGITransport(app=pricing_app) if pricing_app else None
    async with httpx.AsyncClient(timeout=5, transport=transport) as client:

        async def one(repair, part, severity):
            if part == "Sin determinar":
                return
            try:
                async with slots:
                    response = await client.post(
                        TALLER_URL + "/api/predict",
                        json={
                            **vehicle,
                            "repair": repair,
                            "part": part,
                            "severity": severity,
                        },
                    )
                    response.raise_for_status()
                    value = response.json()
                results.append(
                    {
                        "repair": repair,
                        "part": part,
                        "cost_eur": value["cost_eur"],
                        "lower": value["cost_interval"]["lower"],
                        "upper": value["cost_interval"]["upper"],
                        "model_version": value["model_version"],
                        "synthetic": True,
                    }
                )
            except (httpx.HTTPError, KeyError, ValueError):
                return

        try:
            async with asyncio.timeout(8):
                await asyncio.gather(
                    *(
                        one(repair, part, severity)
                        for (repair, part), severity in groups.items()
                    )
                )
        except TimeoutError:
            pass
    return results, len(groups) - len(results)


@app.post("/api/analyze")
async def analyze(
    files: list[UploadFile] = File(...),
    vehicle_json: str = Form(
        '{"brand":"Seat","model":"Ibiza","year":2018,"kilometers":120000,"region":"Almería","engine":"Gasolina"}'
    ),
    confidence: float = Form(0.25),
):
    if not 1 <= len(files) <= 3:
        raise HTTPException(422, "Sube entre una y tres imágenes")
    if not 0.1 <= confidence <= 0.9:
        raise HTTPException(422, "El umbral debe estar entre 0,1 y 0,9")
    try:
        vehicle = Vehicle.model_validate_json(vehicle_json).model_dump()
    except (ValidationError, ValueError, TypeError):
        raise HTTPException(
            422, "Los datos del vehículo no son válidos o están fuera del catálogo"
        )
    images = []
    all_damages = []
    async with semaphore:
        for upload in files:
            try:
                raw = await upload.read(MAX_BYTES + 1)
                rgb = await run_in_threadpool(decode, raw)
                detections, elapsed = await run_in_threadpool(
                    segmenter.predict, rgb, confidence
                )
                damages = describe(detections)
                painted = await run_in_threadpool(annotate, rgb, detections)
                images.append(
                    {
                        "original_bytes": encode(rgb),
                        "annotated_bytes": encode(painted),
                        "damages": damages,
                        "inference_ms": round(elapsed, 2),
                        "width": rgb.shape[1],
                        "height": rgb.shape[0],
                    }
                )
                all_damages.extend(damages)
            except ValueError as error:
                raise HTTPException(422, str(error)) from error
            finally:
                await upload.close()
    estimates, unpriced = (
        await estimate(all_damages, vehicle) if all_damages else ([], 0)
    )
    note = (
        (
            f"{unpriced} {'grupo de daños sin valorar' if unpriced == 1 else 'grupos de daños sin valorar'}: pieza sin determinar o servicio de estimación no disponible. "
            if unpriced
            else ""
        )
        + "Las partidas disponibles son orientativas, con datos sintéticos; no se suman automáticamente."
    )
    identifier = str(uuid4())
    case = {
        "id": identifier,
        "created": datetime.now(timezone.utc).isoformat(),
        "stored_at": time.monotonic(),
        "images": images,
        "estimates": estimates,
        "vehicle": vehicle,
        "budget_note": note,
        "model": "YOLO11s-seg · daños (8 clases, cobertura corregida) + piezas (21 clases)",
        "model_sha256": segmenter.sha256,
    }
    cleanup()
    CASES[identifier] = case
    cleanup()
    output = []
    for item in images:
        output.append(
            {
                key: value
                for key, value in item.items()
                if key not in {"original_bytes", "annotated_bytes"}
            }
            | {
                "original": "data:image/png;base64,"
                + base64.b64encode(item["original_bytes"]).decode(),
                "annotated": "data:image/png;base64,"
                + base64.b64encode(item["annotated_bytes"]).decode(),
            }
        )
    return {
        "id": identifier,
        "created": case["created"],
        "images": output,
        "estimates": estimates,
        "vehicle": vehicle,
        "budget_note": note,
        "unpriced_groups": unpriced,
        "model": case["model"],
        "expires_in_seconds": TTL,
        "privacy": "Las imágenes se procesan temporalmente en memoria. Los resultados caducan en unos 15 minutos.",
        "limitations": "Una detección no sustituye una revisión profesional. La estimación utiliza un modelo entrenado con datos sintéticos.",
        "budget_available": bool(estimates),
    }


@app.get("/api/reports/{identifier}.pdf")
async def report(identifier: str):
    cleanup()
    case = CASES.get(identifier)
    if not case:
        raise HTTPException(404, "El informe ha caducado o no existe")
    pdf = await run_in_threadpool(build_report, case)
    return Response(
        pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="peritaje-{identifier}.pdf"'
        },
    )
