const $ = (s) => document.querySelector(s),
  make = (tag, text, cls) => {
    const e = document.createElement(tag);
    if (text !== undefined) e.textContent = text;
    if (cls) e.className = cls;
    return e;
  };
let catalog,
  selectedFiles = [];
const money = (n) =>
  new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR" }).format(
    n,
  );
const titles = {
  analysis: "Nueva valoración",
  model: "Modelo y resultados",
  scope: "Alcance de la demo",
};
document.querySelectorAll("nav button").forEach((b) =>
  b.addEventListener("click", () => {
    document
      .querySelectorAll(".view")
      .forEach((e) => e.classList.add("hidden"));
    $("#" + b.dataset.view).classList.remove("hidden");
    document
      .querySelectorAll("nav button")
      .forEach((e) => e.classList.remove("active"));
    b.classList.add("active");
    $("#page-heading").textContent = titles[b.dataset.view];
    window.scrollTo({ top: 0, behavior: "instant" });
  }),
);
function options(selector, values, selected) {
  const target = $(selector);
  target.replaceChildren(
    ...values.map((value) => {
      const o = make("option", value);
      o.value = value;
      return o;
    }),
  );
  if (selected) target.value = selected;
}
function models() {
  options("#vehicle-model", catalog.brands[$("#brand").value]);
}
function filesChanged() {
  $("#file-list").replaceChildren(
    ...selectedFiles.map((f, i) =>
      make(
        "span",
        i +
          1 +
          ". " +
          f.name +
          " · " +
          (f.size / 1024 / 1024).toFixed(1) +
          " MB",
      ),
    ),
  );
}
fetch("/api/catalog")
  .then((r) => {
    if (!r.ok) throw Error("No se pudo cargar el catálogo");
    return r.json();
  })
  .then((d) => {
    catalog = d;
    options("#brand", Object.keys(d.brands), "Seat");
    models();
    options("#engine", d.engines);
    options("#region", d.regions, "Almería");
  })
  .catch(showError);
$("#brand").addEventListener("change", models);
$("#photos").addEventListener("change", () => {
  selectedFiles = Array.from($("#photos").files);
  filesChanged();
});
$("#confidence").addEventListener("input", () => {
  $("#confidence-value").textContent = $("#confidence").value + " %";
});
function showError(error) {
  $("#error").textContent = error.message || String(error);
  $("#error").classList.remove("hidden");
}
$("#sample").addEventListener("click", async () => {
  try {
    const r = await fetch("/api/sample");
    if (!r.ok) throw Error("La fotografía de ejemplo no está disponible");
    const blob = await r.blob();
    selectedFiles = [
      new File([blob], "ejemplo-publico.jpg", { type: "image/jpeg" }),
    ];
    $("#photos").value = "";
    filesChanged();
    $("#error").classList.add("hidden");
  } catch (e) {
    showError(e);
  }
});
$("#upload-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("#error").classList.add("hidden");
  if (!selectedFiles.length) {
    showError(
      Error("Selecciona al menos una fotografía o utiliza el ejemplo."),
    );
    return;
  }
  if (
    selectedFiles.length > 3 ||
    selectedFiles.some((f) => f.size > 12 * 1024 * 1024)
  ) {
    showError(Error("Admite hasta tres fotos de un máximo de 12 MB cada una."));
    return;
  }
  const form = new FormData();
  selectedFiles.forEach((f) => form.append("files", f));
  const vehicle = {
    brand: $("#brand").value,
    model: $("#vehicle-model").value,
    year: Number($("#year").value),
    kilometers: Number($("#kilometers").value),
    engine: $("#engine").value,
    region: $("#region").value,
  };
  form.append("vehicle_json", JSON.stringify(vehicle));
  form.append("confidence", Number($("#confidence").value) / 100);
  $("#analyze").disabled = true;
  $("#analyze").textContent = "Analizando fotografías…";
  try {
    const r = await fetch("/api/analyze", { method: "POST", body: form });
    const d = await r.json();
    if (!r.ok)
      throw Error(
        typeof d.detail === "string"
          ? d.detail
          : "Revisa las fotografías y los datos del vehículo.",
      );
    render(d, vehicle);
  } catch (e) {
    showError(e);
  } finally {
    $("#analyze").disabled = false;
    $("#analyze").textContent = "Analizar fotografías";
  }
});
function render(d, vehicle) {
  $("#empty").classList.add("hidden");
  $("#results").classList.remove("hidden");
  $("#image-results").replaceChildren();
  const count = d.images.reduce((n, image) => n + image.damages.length, 0);
  $("#result-count").textContent =
    count +
    " " +
    (count === 1 ? "detección para revisar" : "detecciones para revisar");
  $("#inference").textContent =
    "Inferencia: " +
    Math.round(d.images.reduce((n, i) => n + i.inference_ms, 0)) +
    " ms";
  d.images.forEach((item, index) => {
    const panel = make("article", undefined, "panel image-panel"),
      heading = make("div", undefined, "image-heading"),
      toggles = make("div", undefined, "image-toggle"),
      photo = make("img");
    photo.className = "inspection-photo";
    photo.alt = "Segmentación de daños visibles, imagen " + (index + 1);
    photo.src = item.annotated;
    ["Original", "Detecciones"].forEach((name, k) => {
      const b = make("button", name, k ? "active" : "");
      b.type = "button";
      b.addEventListener("click", () => {
        photo.src = k ? item.annotated : item.original;
        photo.alt =
          (k ? "Segmentación de daños" : "Fotografía original") +
          ", imagen " +
          (index + 1);
        toggles
          .querySelectorAll("button")
          .forEach((e) => e.classList.remove("active"));
        b.classList.add("active");
      });
      toggles.append(b);
    });
    heading.append(make("h2", "Imagen " + (index + 1)), toggles);
    const wrap = make("div", undefined, "damage-table");
    if (item.damages.length) {
      const table = make("table"),
        thead = make("thead"),
        tr = make("tr");
      ["Daño", "Pieza propuesta", "Confianza", "Gravedad"].forEach((t) =>
        tr.append(make("th", t)),
      );
      thead.append(tr);
      table.append(thead);
      const body = make("tbody");
      item.damages.forEach((damage) => {
        const row = make("tr");
        [
          damage.name,
          damage.part,
          Math.round(damage.confidence * 100) + " %",
          ["Leve", "Moderada", "Extensa"][damage.severity - 1],
        ].forEach((t) => row.append(make("td", t)));
        body.append(row);
      });
      table.append(body);
      wrap.append(table);
    } else
      wrap.append(
        make(
          "p",
          "No se detectaron daños por encima del umbral. Revisa la imagen: no acredita ausencia de daños.",
          "empty",
        ),
      );
    panel.append(heading, photo, wrap);
    $("#image-results").append(panel);
  });
  $("#vehicle-summary").textContent =
    "Referencia seleccionada: " +
    vehicle.brand +
    " " +
    vehicle.model +
    " · " +
    vehicle.year +
    " · " +
    new Intl.NumberFormat("es-ES").format(vehicle.kilometers) +
    " km. No inferida de la foto.";
  $("#estimates").replaceChildren(
    ...d.estimates.map((e) => {
      const row = make("div", undefined, "cost-row"),
        label = make("div"),
        amount = make("div");
      label.append(
        make("span", e.repair + " · " + e.part),
        make("small", "TallerMLOps · datos sintéticos"),
      );
      amount.append(
        make("strong", money(e.cost_eur)),
        make("small", money(e.lower) + " – " + money(e.upper)),
      );
      row.append(label, amount);
      return row;
    }),
  );
  $("#budget-note").textContent =
    d.budget_note || "No hay estimación de coste disponible para este caso.";
  $("#privacy").textContent = d.privacy;
  $("#pdf").href = "/api/reports/" + d.id + ".pdf";
  $("#pdf").classList.remove("hidden");
  $("#results").scrollIntoView({ block: "start", behavior: "smooth" });
}
