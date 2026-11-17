# Procedencia y licencias

Código de AutoPeritaje y modelos derivados de YOLO: AGPL-3.0. La licencia completa se incluye en LICENSE. Ultralytics y los pesos iniciales YOLO11 proceden de sus repositorios oficiales; entrenamiento con Ultralytics 8.4.214.

Fotografías y anotaciones de ejemplo: [DrBimmer/car-parts-and-damage-dataset](https://huggingface.co/datasets/DrBimmer/car-parts-and-damage-dataset), revisión `2dbf46f7e23eb0d6f551d38e4f77a11fe9d045b9`, declarada MIT por su publicador. Las imágenes de docs son ejemplos de ese conjunto público; no son fotos privadas del autor. No se ha utilizado CarDD. El dataset completo se obtiene de su fuente y no se incluye en este repositorio.

La demo incluye opcionalmente TallerMLOps, de Pedro Flores, bajo MIT. Se descarga su revisión `51320c0ed1ebfb206b8999d7bbd79aa548c1c02b`, verificando SHA-256 antes de extraerla; conserva su LICENSE y NOTICE.md. Su modelo de reparación se entrenó con órdenes sintéticas. No constituye una tarifa comercial.

ONNX Runtime, FastAPI, NumPy, Pillow, OpenCV, ReportLab y las demás dependencias conservan sus respectivas licencias. Los pesos publicados en la release models-v1 se verifican contra models/manifest.json y se ejecutan con ONNX Runtime en CPU; no se requiere PyTorch para servir las fotografías.
