let font;
async function reportFont() {
  if (font) return font;
  const response = await fetch("./DejaVuSans.ttf");
  if (!response.ok) throw new Error("No se pudo cargar la fuente del informe.");
  const bytes = new Uint8Array(await response.arrayBuffer());
  let value = "";
  for (let i = 0; i < bytes.length; i += 32768)
    value += String.fromCharCode(...bytes.subarray(i, i + 32768));
  font = btoa(value);
  return font;
}

export async function createReport(caseData) {
  const pdf = new jspdf.jsPDF({ unit: "mm", format: "a4" });
  pdf.addFileToVFS("DejaVuSans.ttf", await reportFont());
  pdf.addFont("DejaVuSans.ttf", "DejaVu", "normal");
  pdf.setFont("DejaVu");
  let y = 16;
  const green = [23, 84, 31],
    gray = [94, 107, 99];
  function text(value, size = 9, color = [40, 48, 43], width = 182) {
    pdf.setFontSize(size);
    pdf.setTextColor(...color);
    const lines = pdf.splitTextToSize(String(value), width),
      height = lines.length * size * 0.43;
    if (y + height > 280) {
      pdf.addPage();
      y = 16;
    }
    pdf.text(lines, 14, y);
    y += height + 2;
  }
  function space(height) {
    if (y + height > 280) {
      pdf.addPage();
      y = 16;
    }
  }
  text("AutoPeritaje", 19, green);
  text("Informe orientativo de daños visibles", 12);
  text(
    new Date(caseData.created).toLocaleString("es-ES", { timeZone: "UTC" }) +
      " UTC · " +
      caseData.id.slice(0, 8),
    8,
    gray,
  );
  text(
    `Vehículo de referencia introducido por el usuario: ${caseData.vehicle.brand} ${caseData.vehicle.model} · ${caseData.vehicle.year} · ${caseData.vehicle.kilometers.toLocaleString("es-ES")} km. No identificado por la foto.`,
    8,
    gray,
  );
  for (let index = 0; index < caseData.images.length; index++) {
    const image = caseData.images[index];
    if (index) {
      pdf.addPage();
      y = 16;
    }
    text("Imagen " + (index + 1), 12, green);
    const ratio = Math.min(182 / image.width, 85 / image.height),
      width = image.width * ratio,
      height = image.height * ratio;
    space(height + 10);
    pdf.addImage(
      image.annotated,
      "JPEG",
      14 + (182 - width) / 2,
      y,
      width,
      height,
    );
    y += height + 8;
    if (!image.damages.length) {
      text(
        "No hay detecciones por encima del umbral. No acredita ausencia de daños.",
        9,
      );
      continue;
    }
    const columns = [14, 57, 116, 145];
    function tableHeading() {
      pdf.setFillColor(228, 238, 230);
      pdf.rect(14, y - 4, 182, 8, "F");
      pdf.setFontSize(8);
      pdf.setTextColor(...green);
      ["Daño", "Pieza propuesta", "Confianza", "Gravedad"].forEach((label, i) =>
        pdf.text(label, columns[i] + 2, y + 1),
      );
      y += 10;
    }
    tableHeading();
    for (const damage of image.damages) {
      if (y + 12 > 280) {
        pdf.addPage();
        y = 18;
        tableHeading();
      }
      pdf.setFontSize(8);
      pdf.setTextColor(40, 48, 43);
      const names = pdf.splitTextToSize(damage.name, 39),
        parts = pdf.splitTextToSize(damage.part, 55),
        height = Math.max(names.length, parts.length) * 4 + 3;
      pdf.text(names, columns[0] + 2, y);
      pdf.text(parts, columns[1] + 2, y);
      pdf.text(Math.round(damage.confidence * 100) + " %", columns[2] + 2, y);
      pdf.text(
        ["Leve", "Moderada", "Extensa"][damage.severity - 1],
        columns[3] + 2,
        y,
      );
      y += height;
      pdf.setDrawColor(225, 232, 227);
      pdf.line(14, y - 2, 196, y - 2);
    }
  }
  const money = (value) =>
    new Intl.NumberFormat("es-ES", {
      style: "currency",
      currency: "EUR",
    }).format(value);
  space(Math.min(100, 35 + caseData.estimates.length * 8));
  y += 5;
  text("Estimación de reparación", 12, green);
  text(caseData.budget_note, 8, gray);
  if (!caseData.estimates.length)
    text("No hay partidas disponibles para este caso.", 9);
  for (const item of caseData.estimates)
    text(
      `${item.repair} · ${item.part}: ${money(item.cost_eur)} (${money(item.lower)}–${money(item.upper)})`,
      9,
    );
  y += 3;
  text(
    "Prototipo experimental. El experto ligero de daños obtiene 9,85 % de mAP50 de máscaras en prueba interna. Puede omitir daños y confundir reflejos, huecos o roturas. La gravedad depende del área visible; no mide profundidad ni daños internos. No constituye una valoración profesional.",
    8,
    gray,
  );
  text(
    "Presupuesto: modelo LightGBM de TallerMLOps entrenado con órdenes sintéticas, ejecutado en este navegador. No se suman las partidas. Modelo " +
      (caseData.estimates[0]?.model_version || "no aplicado") +
      ".",
    8,
    gray,
  );
  text(
    "Visión: YOLO11n daños + YOLO11s piezas · ONNX Runtime Web / CPU. Las fotos se han procesado localmente en el navegador.",
    8,
    gray,
  );
  for (let page = 1; page <= pdf.getNumberOfPages(); page++) {
    pdf.setPage(page);
    pdf.setFontSize(8);
    pdf.setTextColor(...gray);
    pdf.text("AutoPeritaje · Informe orientativo", 14, 290);
    pdf.text(String(page), 194, 290, { align: "right" });
  }
  return URL.createObjectURL(pdf.output("blob"));
}
