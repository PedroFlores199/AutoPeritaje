---
title: AutoPeritaje
emoji: 🚗
colorFrom: green
colorTo: gray
sdk: static
app_file: index.html
license: agpl-3.0
short_description: Daños y presupuesto, con las fotos en tu navegador
---

# AutoPeritaje

Analiza de una a tres fotografías, compara las detecciones con el original y descarga un informe PDF. Los modelos y el presupuesto se ejecutan dentro de tu navegador mediante WebAssembly. Las fotos no se suben a una API.

La primera ejecución descarga unos 52 MB de modelos y el motor. La velocidad depende de tu dispositivo. El presupuesto utiliza el modelo real de TallerMLOps entrenado con órdenes sintéticas y no constituye una valoración profesional.

Prototipo experimental: YOLO11n de daños obtiene 9,85 % de mAP50 de máscaras en prueba interna de Python; puede omitir daños y producir propuestas incorrectas. El experto de piezas se mide por separado. Una foto sin detecciones no acredita que el vehículo esté en buen estado.

[Código completo, entrenamiento y resultados](https://github.com/PedroFlores199/AutoPeritaje) · [Modelos y manifiesto SHA-256](https://github.com/PedroFlores199/AutoPeritaje/releases/tag/models-v1)

Código y modelos YOLO bajo AGPL-3.0. TallerMLOps, ONNX Runtime Web y jsPDF conservan MIT; las demás fuentes y licencias se documentan en el repositorio. La fotografía de ejemplo procede del dataset público de DrBimmer.

Este Space es estático, gratuito y no inicia un servidor de cálculo. Los archivos se preparan localmente desde una revisión fija del código, con verificación SHA-256 del código y de los modelos. No se ejecuta una compilación de pago en Hugging Face.
