import { BrowserModels, decode, annotate } from "./inference.mjs";
import { describe, estimates } from "./core.mjs";
import { createReport } from "./report.mjs";
import { render } from "./ui.mjs";

const $ = (selector) => document.querySelector(selector);
let selectedFiles = [],
  sampleLoading = false,
  catalog,
  models,
  pricing,
  config,
  reportUrl;
function error(value) {
  $("#error").textContent = value.message || String(value);
  $("#error").classList.remove("hidden");
}
function options(selector, values, selected) {
  $(selector).replaceChildren(
    ...values.map((value) => {
      const item = document.createElement("option");
      item.value = value;
      item.textContent = value;
      return item;
    }),
  );
  if (selected) $(selector).value = selected;
}
function fileList() {
  $("#file-list").replaceChildren(
    ...selectedFiles.map((file, index) => {
      const item = document.createElement("span");
      item.textContent = `${index + 1}. ${file.name} · ${(file.size / 1024 / 1024).toFixed(1)} MB`;
      return item;
    }),
  );
}
const titles = {
  analysis: "Nueva valoración",
  model: "Modelo y resultados",
  scope: "Alcance de la demo",
};
document.querySelectorAll("nav button").forEach((button) =>
  button.addEventListener("click", () => {
    document
      .querySelectorAll(".view")
      .forEach((view) =>
        view.classList.toggle("hidden", view.id !== button.dataset.view),
      );
    document
      .querySelectorAll("nav button")
      .forEach((item) => item.classList.toggle("active", item === button));
    $("#page-heading").textContent = titles[button.dataset.view];
    window.scrollTo({ top: 0, behavior: "instant" });
  }),
);
$("#brand").addEventListener("change", () =>
  options("#vehicle-model", catalog.brands[$("#brand").value]),
);
$("#photos").addEventListener("change", () => {
  selectedFiles = [...$("#photos").files];
  fileList();
});
$("#confidence").addEventListener("input", () => {
  $("#confidence-value").textContent = $("#confidence").value + " %";
});
$("#sample").addEventListener("click", async () => {
  sampleLoading = true;
  $("#sample").disabled = true;
  $("#analyze").disabled = true;
  try {
    const response = await fetch("./sample.jpg");
    if (!response.ok) throw new Error("No está disponible la foto de ejemplo.");
    selectedFiles = [
      new File([await response.blob()], "ejemplo-publico.jpg", {
        type: "image/jpeg",
      }),
    ];
    $("#photos").value = "";
    fileList();
    $("#error").classList.add("hidden");
  } catch (value) {
    error(value);
  } finally {
    sampleLoading = false;
    $("#sample").disabled = false;
    $("#analyze").disabled = !models;
  }
});
$("#upload-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("#error").classList.add("hidden");
  if (!models) {
    error(new Error("Todavía se está preparando la aplicación."));
    return;
  }
  if (!selectedFiles.length || selectedFiles.length > 3) {
    error(new Error("Selecciona entre una y tres fotografías."));
    return;
  }
  const vehicle = {
    brand: $("#brand").value,
    model: $("#vehicle-model").value,
    year: Number($("#year").value),
    kilometers: Number($("#kilometers").value),
    engine: $("#engine").value,
    region: $("#region").value,
  };
  if (
    !catalog.brands[vehicle.brand]?.includes(vehicle.model) ||
    !Number.isInteger(vehicle.year) ||
    vehicle.year < 2004 ||
    vehicle.year > 2026 ||
    !Number.isInteger(vehicle.kilometers) ||
    vehicle.kilometers < 0 ||
    vehicle.kilometers > 600000
  ) {
    error(new Error("Revisa los datos del vehículo de referencia."));
    return;
  }
  const confidence = Number($("#confidence").value) / 100;
  if (!Number.isFinite(confidence) || confidence < 0.1 || confidence > 0.9) {
    error(new Error("El umbral debe estar entre 10 y 90 %."));
    return;
  }
  $("#analyze").disabled = true;
  $("#sample").disabled = true;
  const started = performance.now();
  try {
    const decoded = [];
    for (const file of selectedFiles) decoded.push(await decode(file));
    await models.load();
    const images = [],
      damages = [];
    for (const image of decoded) {
      const result = await models.predict(image, confidence),
        rows = describe(
          result.detections,
          config,
          image.canvas.width,
          image.canvas.height,
        );
      images.push({
        original: image.canvas.toDataURL("image/jpeg", 0.93),
        annotated: annotate(image, result.detections, config),
        damages: rows,
        width: image.canvas.width,
        height: image.canvas.height,
        inference_ms: Math.round(result.milliseconds),
      });
      damages.push(...rows);
      result.detections.length = 0;
    }
    const budget = estimates(
      damages,
      vehicle,
      pricing,
      new Date().getUTCMonth() + 1,
    );
    const data = {
      id: crypto.randomUUID(),
      created: new Date().toISOString(),
      images,
      vehicle,
      estimates: budget.results,
      budget_note:
        (budget.unpriced
          ? budget.unpriced === 1
            ? "Un grupo sin valorar: pieza sin determinar. "
            : `${budget.unpriced} grupos sin valorar: pieza sin determinar. `
          : "") +
        "Partidas orientativas de TallerMLOps, con datos sintéticos. No se suman automáticamente.",
      privacy:
        "Las fotos y el informe se han procesado en este navegador. No se han enviado a un servidor. Cierra o recarga la página para eliminar los resultados.",
      model: "YOLO11n daños + YOLO11s piezas · ONNX Runtime Web / CPU",
      wall_seconds: (performance.now() - started) / 1000,
    };
    $("#analyze").textContent = "Preparando el informe local…";
    if (reportUrl) URL.revokeObjectURL(reportUrl);
    reportUrl = await createReport(data);
    data.wall_seconds = (performance.now() - started) / 1000;
    data.reportUrl = reportUrl;
    render(data, vehicle);
    $("#pdf").download = "autoperitaje-" + data.id.slice(0, 8) + ".pdf";
    $("#local-timing").textContent =
      `Análisis completo: ${data.wall_seconds.toFixed(1)} s · Las siguientes fotos reutilizan los modelos descargados.`;
  } catch (value) {
    error(value);
  } finally {
    $("#analyze").disabled = false;
    $("#sample").disabled = false;
    $("#analyze").textContent = "Analizar fotografías";
  }
});

async function initialize() {
  $("#analyze").disabled = true;
  try {
    [catalog, config, pricing] = await Promise.all(
      ["catalog.json", "config.json", "pricing.json"].map(async (file) => {
        const response = await fetch("./" + file);
        if (!response.ok)
          throw new Error("No se pudo cargar la configuración.");
        return response.json();
      }),
    );
    options("#brand", Object.keys(catalog.brands), "Seat");
    options("#vehicle-model", catalog.brands.Seat, "Ibiza");
    options("#engine", catalog.engines, "Gasolina");
    options("#region", catalog.regions, "Almería");
    models = new BrowserModels(config, (message) => {
      $("#analyze").textContent = message;
    });
    $("#analyze").disabled = sampleLoading;
  } catch (value) {
    error(value);
  }
}
initialize();
