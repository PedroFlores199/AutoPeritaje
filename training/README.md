# Reproducción del entrenamiento

Se necesitan Python 3.12, uv, espacio para el dataset y los entrenamientos. Los tiempos publicados corresponden a un Mac M2 Max con MPS; en CPU el entrenamiento tarda más. La aplicación de servicio utiliza exclusivamente ONNX Runtime CPU.

```bash
uv sync --extra training --extra test --frozen
uv run python training/download_data.py /tmp/peritaje-source
uv run python training/prepare.py /tmp/peritaje-source /tmp/peritaje-prepared
uv run python training/task_datasets.py /tmp/peritaje-source /tmp/peritaje-prepared /tmp/peritaje-covered
uv run python training/download_pretrained.py /tmp/peritaje-pretrained
uv run python training/train_tasks.py /tmp/peritaje-covered/damage/dataset.yaml /tmp/peritaje-pretrained /tmp/peritaje-runs
```

`prepare.py` verifica imágenes, normaliza polígonos con las dimensiones originales, agrupa archivos por SHA-256 y asigna el grupo completo a una partición: módulo 100, 72/14/14. No permite coincidencias exactas entre entrenamiento, validación y prueba. `split-manifest.json` permite contrastar los identificadores usados. No detecta todas las fotos del mismo vehículo ni duplicados transformados.

`task_datasets.py` determina cobertura a partir de las clases anotadas, sin confiar en los nombres de las carpetas. Solo las fotos con anotaciones de daños entran en la tarea de daños. Las de piezas entran en la tarea de piezas; las coincidencias entre tareas conservan la partición global. No hay negativos limpios verificados.

Ambos tamaños de daños parten de pesos COCO oficiales. YOLO11n y YOLO11s: 640 píxeles, hasta 80 épocas, parada temprana de 18, AdamW 0,001, semilla 42, máscaras independientes, backbone completo y aumentos moderados. El script guarda los checkpoints y las métricas de validación. El modelo s se eligió por mAP50 de máscaras de validación; no se cambió al observar que el n resultaba ligeramente mejor en prueba.

## Experto de piezas

La demo conserva el experto de piezas de un entrenamiento conjunto anterior, sin emplear ninguna de sus salidas de daños. Para reproducir esa rama:

```bash
uv run python training/train.py /tmp/peritaje-prepared/dataset.yaml /tmp/peritaje-runs --epochs 16
uv run python training/refine.py /tmp/peritaje-runs/yolo11s/weights/best.pt /tmp/peritaje-prepared/dataset.yaml /tmp/peritaje-runs --epochs 48
```

Esta rama aprendió con anotaciones parciales de ambas tareas. La evaluación final de piezas utiliza únicamente las fotos anotadas para piezas y filtra las otras ocho clases. Se conserva su procedencia como limitación, aunque el resultado de piezas sea considerablemente mejor que el de daños.

## Evaluación y exportación

```bash
uv run python training/evaluate_export.py /tmp/peritaje-runs /tmp/peritaje-covered /tmp/peritaje-export
```

El script evalúa los modelos de daños sobre 112 fotos internas de prueba, el experto de piezas sobre 133, genera las matrices de confusión y exporta ONNX estático de 640 píxeles, opset 17 y sin NMS integrada. Mide doce ejecuciones del motor en CPU tras tres calentamientos. Los pesos seleccionados y los resultados de esta ejecución están en la release `models-v1` y en `docs/`.

Para recrear la galería tras colocar los pesos de servicio verificados en `models/`:

```bash
uv run python scripts/download_models.py
uv run python training/error_gallery.py /tmp/peritaje-covered/damage /tmp/peritaje-errors
```

Las cuatro imágenes son las primeras por SHA-256 que contienen Dent, Scratch, Cracked y Flaking, sin repetir imagen. No se eligen por buenos resultados. La asociación exige clase igual e IoU de máscara de al menos 0,5; los ejemplos usan confianza 0,25.

Los resultados son internos, sobre un dataset pequeño y con anotaciones de calidad desigual. El conjunto global se utilizó durante el desarrollo; no se presenta como una prueba externa intacta. El entrenamiento MPS puede variar entre versiones del entorno aunque se mantenga la semilla.
