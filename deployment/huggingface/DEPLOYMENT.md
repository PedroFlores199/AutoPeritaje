# Publicar la demo estática

La demo se sirve como archivos estáticos. No necesita un servidor, secretos, una tarjeta ni un servicio de inferencia. Las fotos se procesan en el navegador del visitante.

## Preparación local

Con Node.js 22 o posterior y tar, desde esta carpeta:

```bash
npm run build
```

El programa descarga la revisión pública fijada en `build.mjs`, verifica el SHA-256 del archivo, prepara los modelos y comprueba sus huellas. Genera `static/` con todos los archivos listos. Para facilitar la subida por la web, coloca las dependencias y los modelos junto al HTML y ajusta únicamente sus rutas relativas. Las huellas del resultado publicado están en `source-manifest.json`.

Crea un Space **Static / Blank / Public** y sube el contenido de `static/` a su raíz, incluido `README.md`. Mantén `sdk: static` y `app_file: index.html`. No añadas `app_build_command`: el servicio pidió créditos para ese paso durante la publicación y la preparación se realizó localmente. No es necesario activar ninguna opción de pago.

Comprueba el ejemplo, la selección de una foto pública y el PDF desde una sesión sin iniciar sesión. El resultado medido se registra en `../../docs/huggingface-validation.json`. El código completo, los modelos y las licencias permanecen disponibles en GitHub.
