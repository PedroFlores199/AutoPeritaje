# Demo sin servidor de cálculo

Esta carpeta contiene una aplicación estática completa. ONNX Runtime Web ejecuta YOLO en WebAssembly, el modelo LightGBM exportado calcula las partidas y jsPDF crea el informe. Las fotografías se procesan en el dispositivo del visitante; no se envían a una API.

Hugging Face permite [Static Spaces gratuitos con un paso de construcción](https://huggingface.co/docs/hub/spaces-sdks-static). No necesita Docker, Gradio, una suscripción, claves ni un servicio de inferencia externo.

## Probar desde el repositorio

Node 18 o posterior y Python 3:

```bash
node web-demo/prepare.mjs
python3 -m http.server 5107 --bind 127.0.0.1 --directory web-demo
```

Abre http://localhost:5107. La preparación descarga dos modelos desde la release pública `models-v1` y comprueba tamaño y SHA-256. Los binarios quedan fuera del historial Git. El navegador vuelve a verificar las huellas antes de crear las sesiones.

## Modelo y tiempos

Se usa **YOLO11n para daños** para reducir descarga y trabajo en el dispositivo: 11,65 MB, frente a 40,52 MB del s. Se conserva el experto s de piezas de 40,56 MB y se descartan sus salidas de daños. El motor WebAssembly ocupa unos 14 MB adicionales y se ejecuta en un hilo, dentro de un trabajador para mantener la interfaz operativa.

La mAP50 de máscaras medida en Python para el experto n es 9,85 % sobre 112 imágenes internas. No se presenta como una evaluación completa de la implementación del navegador. La API de Python conserva el experto s, seleccionado por validación. El decodificador de imagen y el redondeo del navegador pueden variar ligeramente respecto a Pillow/OpenCV.

La interfaz muestra por separado el tiempo de inferencia y máscaras, y el tiempo completo del análisis. Este último incluye la primera descarga, la verificación de modelos, la preparación y el PDF. La velocidad depende de la red y del dispositivo. No se requiere WebGPU ni un servicio remoto.

## Presupuestos reales del proyecto TallerMLOps

`pricing.json` contiene los árboles de los dos regresores LightGBM, las categorías del codificador, las medianas numéricas y los cuantiles de calibración del modelo publicado de TallerMLOps. Conserva la revisión de origen, la versión y la huella del artefacto. No se sustituyen sus predicciones por una fórmula de precios.

`core.mjs` reproduce la codificación y la suma de hojas. Ciento veinte combinaciones de referencia, incluidas entradas numéricas ausentes, coinciden con las predicciones Python: coste e intervalos redondeados exactos y error inferior a 1e-7 en horas. Las partidas son sintéticas y orientativas; se agrupan por reparación y pieza y no se suman automáticamente. Una pieza sin asignación no se valora.

La exportación se puede reproducir con `training/export_pricing_web.py`, usando el código y el artefacto de la revisión de TallerMLOps indicada en `pricing.json`.

## Comprobaciones

```bash
node --test web-demo/tests/core.test.mjs
```

Cuatro pruebas cubren NMS por clase, las 120 predicciones de LightGBM, máscaras de referencia de OpenCV y la conservación de piezas desconocidas. Además se ha probado la aplicación real en el navegador: foto de ejemplo, dos fotos, imagen blanca sin detecciones ni presupuesto, rechazo de un archivo dañado y PDF de una o dos páginas. [Referencia del modelo Python sobre la misma foto](../docs/browser-reference.json).

El servidor estático de la prueba solo recibió solicitudes GET de los archivos de la aplicación. No existe una ruta de subida o de análisis remoto. Las fotos se vuelven a codificar en un lienzo y pierden la metadata; los resultados viven en memoria hasta cerrar o recargar la página. Solo se guarda el informe si el visitante lo descarga.

## Distribución

`vendor/manifest.json` conserva versiones, integridad SHA-512 de npm y huellas de los archivos de ONNX Runtime Web y jsPDF. Sus licencias MIT acompañan a las bibliotecas; la fuente DejaVu conserva su licencia. Los modelos derivados de YOLO y el código de esta aplicación se distribuyen bajo AGPL-3.0. El modelo de TallerMLOps conserva MIT. La fotografía de ejemplo procede del dataset público documentado en el repositorio.
