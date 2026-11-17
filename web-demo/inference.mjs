import { candidates, makeMask } from "./core.mjs";

export async function verifiedBytes(url, item, progress = () => {}) {
  const response = await fetch(url);
  if (!response.ok)
    throw new Error(
      "No se pudo descargar " + item.file + ". Vuelve a intentarlo.",
    );
  const reader = response.body.getReader(),
    chunks = [];
  let size = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.length;
    if (size > item.bytes)
      throw new Error("El archivo supera el tamaño esperado.");
    chunks.push(value);
    progress(size, item.bytes);
  }
  if (size !== item.bytes) throw new Error("La descarga está incompleta.");
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.length;
  }
  const digest = [
    ...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)),
  ]
    .map((v) => v.toString(16).padStart(2, "0"))
    .join("");
  if (digest !== item.sha256)
    throw new Error("La huella del modelo no coincide. No se ha ejecutado.");
  return bytes;
}

function dimensions(bytes) {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  if (
    bytes[0] === 137 &&
    bytes[1] === 80 &&
    bytes[2] === 78 &&
    bytes[3] === 71 &&
    bytes.length >= 24
  )
    return [view.getUint32(16), view.getUint32(20)];
  if (bytes[0] === 255 && bytes[1] === 216) {
    let offset = 2;
    while (offset + 9 < bytes.length) {
      if (bytes[offset++] !== 255) break;
      while (bytes[offset] === 255) offset++;
      const marker = bytes[offset++];
      if (marker === 216 || marker === 1 || (marker >= 208 && marker <= 217))
        continue;
      const length = view.getUint16(offset);
      if (length < 2 || offset + length > bytes.length) break;
      if (
        [
          192, 193, 194, 195, 197, 198, 199, 201, 202, 203, 205, 206, 207,
        ].includes(marker)
      )
        return [view.getUint16(offset + 5), view.getUint16(offset + 3)];
      offset += length;
    }
  }
  const text = (start, end) => String.fromCharCode(...bytes.slice(start, end));
  if (bytes.length >= 30 && text(0, 4) === "RIFF" && text(8, 12) === "WEBP") {
    if (text(12, 16) === "VP8X")
      return [
        1 + bytes[24] + (bytes[25] << 8) + (bytes[26] << 16),
        1 + bytes[27] + (bytes[28] << 8) + (bytes[29] << 16),
      ];
    if (text(12, 16) === "VP8 ")
      return [
        view.getUint16(26, true) & 16383,
        view.getUint16(28, true) & 16383,
      ];
    if (text(12, 16) === "VP8L" && bytes[20] === 47)
      return [
        1 + bytes[21] + ((bytes[22] & 63) << 8),
        1 + (bytes[22] >> 6) + (bytes[23] << 2) + ((bytes[24] & 15) << 10),
      ];
  }
  throw new Error("La imagen no es un JPEG, PNG o WebP válido.");
}

export async function decode(file) {
  if (!file.size || file.size > 12 * 1024 * 1024)
    throw new Error("Cada foto debe ocupar entre 1 byte y 12 MB.");
  const raw = new Uint8Array(await file.arrayBuffer()),
    [width, height] = dimensions(raw);
  if (!width || !height || width * height > 20000000)
    throw new Error("La imagen supera el límite de 20 megapíxeles.");
  let bitmap;
  try {
    bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
  } catch {
    throw new Error("No se ha podido abrir la fotografía.");
  }
  if (bitmap.width * bitmap.height > 20000000) {
    bitmap.close();
    throw new Error("La imagen supera el límite de 20 megapíxeles.");
  }
  const ratio = Math.min(1, 1600 / Math.max(bitmap.width, bitmap.height)),
    canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(bitmap.width * ratio));
  canvas.height = Math.max(1, Math.round(bitmap.height * ratio));
  const context = canvas.getContext("2d", { willReadFrequently: true });
  context.fillStyle = "#fff";
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  return {
    canvas,
    pixels: context.getImageData(0, 0, canvas.width, canvas.height),
  };
}

const roundEven = (value) =>
  value - Math.floor(value) === 0.5
    ? 2 * Math.round(value / 2)
    : Math.round(value);
export function prepare(pixels) {
  const { width, height, data } = pixels,
    size = 640,
    ratio = Math.min(size / width, size / height),
    newWidth = roundEven(width * ratio),
    newHeight = roundEven(height * ratio),
    left = Math.floor((size - newWidth) / 2),
    top = Math.floor((size - newHeight) / 2);
  const output = new Float32Array(3 * size * size);
  output.fill(114 / 255);
  for (let y = 0; y < newHeight; y++) {
    const sy = Math.max(
        0,
        Math.min(height - 1, ((y + 0.5) * height) / newHeight - 0.5),
      ),
      y0 = Math.floor(sy),
      y1 = Math.min(height - 1, y0 + 1),
      fy = sy - y0;
    for (let x = 0; x < newWidth; x++) {
      const sx = Math.max(
          0,
          Math.min(width - 1, ((x + 0.5) * width) / newWidth - 0.5),
        ),
        x0 = Math.floor(sx),
        x1 = Math.min(width - 1, x0 + 1),
        fx = sx - x0;
      for (let c = 0; c < 3; c++) {
        const value =
          (1 - fy) *
            ((1 - fx) * data[(y0 * width + x0) * 4 + c] +
              fx * data[(y0 * width + x1) * 4 + c]) +
          fy *
            ((1 - fx) * data[(y1 * width + x0) * 4 + c] +
              fx * data[(y1 * width + x1) * 4 + c]);
        output[c * size * size + (top + y) * size + left + x] =
          Math.round(value) / 255;
      }
    }
  }
  return {
    tensor: output,
    transform: { ratio, left, top, newWidth, newHeight },
  };
}

export class BrowserModels {
  constructor(config, status) {
    this.config = config;
    this.status = status;
    this.sessions = {};
  }
  async load() {
    if (this.sessions.damage && this.sessions.parts) return;
    if (!window.ort || !window.WebAssembly || !crypto.subtle)
      throw new Error(
        "Utiliza una versión actual de Chrome, Edge, Firefox o Safari mediante HTTPS.",
      );
    ort.env.wasm.numThreads = 1;
    ort.env.wasm.wasmPaths = new URL("./vendor/", location.href).href;
    ort.env.wasm.proxy = true;
    for (const name of ["damage", "parts"]) {
      if (this.sessions[name]) continue;
      const item = this.config.models[name];
      const bytes = await verifiedBytes(
        new URL("./models/" + item.file, location.href),
        item,
        (size, total) =>
          this.status(
            `Cargando ${name === "damage" ? "daños" : "piezas"}: ${(size / 1e6).toFixed(1)} / ${(total / 1e6).toFixed(1)} MB`,
          ),
      );
      this.status(
        "Preparando el modelo de " +
          (name === "damage" ? "daños" : "piezas") +
          "…",
      );
      this.sessions[name] = await ort.InferenceSession.create(bytes, {
        executionProviders: ["wasm"],
        graphOptimizationLevel: "all",
      });
    }
  }
  async predict(image, confidence) {
    const started = performance.now(),
      { tensor, transform } = prepare(image.pixels),
      detections = [];
    for (const name of ["damage", "parts"]) {
      this.status(
        "Analizando " +
          (name === "damage" ? "daños visibles" : "piezas") +
          " en tu navegador…",
      );
      const input = new ort.Tensor("float32", tensor.slice(), [1, 3, 640, 640]);
      const session = this.sessions[name],
        outputs = await session.run({ [session.inputNames[0]]: input }),
        prediction = outputs[session.outputNames[0]],
        proto = outputs[session.outputNames[1]];
      if (
        prediction.dims[1] !== 4 + (name === "damage" ? 8 : 29) + 32 ||
        proto.dims[1] !== 32
      )
        throw new Error("El vocabulario del modelo no coincide.");
      const rows = candidates(
        prediction,
        name === "damage" ? 8 : 29,
        name === "parts" ? Math.max(0.25, confidence) : confidence,
        name === "parts",
      );
      for (const row of rows) {
        const mask = makeMask(
          row,
          proto,
          transform,
          image.canvas.width,
          image.canvas.height,
        );
        if (mask.reduce((a, b) => a + b, 0) < 4) continue;
        const originalBox = row.box.map((value, i) =>
          Math.max(
            0,
            Math.min(
              i % 2 ? image.canvas.height : image.canvas.width,
              (value - (i % 2 ? transform.top : transform.left)) /
                transform.ratio,
            ),
          ),
        );
        detections.push({ ...row, mask, originalBox });
      }
      Object.values(outputs).forEach((value) => value.dispose?.());
      input.dispose?.();
      await new Promise((resolve) => requestAnimationFrame(resolve));
    }
    return { detections, milliseconds: performance.now() - started };
  }
}

export function annotate(image, detections, config) {
  const canvas = document.createElement("canvas");
  canvas.width = image.canvas.width;
  canvas.height = image.canvas.height;
  const context = canvas.getContext("2d");
  context.drawImage(image.canvas, 0, 0);
  const colors = [
      [211, 103, 55],
      [209, 158, 49],
      [186, 78, 69],
      [153, 100, 174],
      [73, 148, 164],
      [148, 110, 73],
      [207, 114, 139],
      [131, 142, 65],
    ],
    overlay = document.createElement("canvas");
  overlay.width = canvas.width;
  overlay.height = canvas.height;
  const overlayContext = overlay.getContext("2d"),
    pixels = overlayContext.createImageData(canvas.width, canvas.height),
    damages = detections.filter((d) => d.classId < 8);
  for (const damage of damages)
    for (let i = 0; i < damage.mask.length; i++)
      if (damage.mask[i]) {
        pixels.data.set(colors[damage.classId], i * 4);
        pixels.data[i * 4 + 3] = 100;
      }
  overlayContext.putImageData(pixels, 0, 0);
  context.drawImage(overlay, 0, 0);
  const fontSize = Math.max(20, Math.min(40, Math.floor(canvas.width / 32)));
  context.font = `600 ${fontSize}px Arial`;
  for (const row of damages) {
    const [x1, y1, x2, y2] = row.originalBox,
      color = "rgb(" + colors[row.classId].join(",") + ")",
      label =
        config.DAMAGE_NAMES[config.CLASSES[row.classId]] +
        " " +
        Math.round(row.confidence * 100) +
        "%";
    context.strokeStyle = color;
    context.lineWidth = 3;
    context.strokeRect(x1, y1, x2 - x1, y2 - y1);
    const top = Math.max(0, y1 - fontSize - 10);
    context.fillStyle = color;
    context.fillRect(
      x1,
      top,
      Math.min(canvas.width - x1, context.measureText(label).width + 12),
      fontSize + 10,
    );
    context.fillStyle = "#fff";
    context.fillText(label, x1 + 5, top + fontSize + 2);
  }
  return canvas.toDataURL("image/jpeg", 0.93);
}
