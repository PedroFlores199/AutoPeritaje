const $ = (selector) => document.querySelector(selector);
const make = (tag, text, cls) => {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (cls) element.className = cls;
  return element;
};
const money = (value) =>
  new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR" }).format(
    value,
  );
export function render(d, vehicle) {
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
  $("#pdf").href = d.reportUrl;
  $("#pdf").classList.remove("hidden");
  $("#results").scrollIntoView({ block: "start", behavior: "smooth" });
}
