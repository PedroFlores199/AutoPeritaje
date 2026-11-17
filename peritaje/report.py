import io
from datetime import datetime
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image,
    Table,
    TableStyle,
    PageBreak,
    KeepTogether,
)


def money(value):
    return (
        f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".") + " EUR"
    )


def build_report(case):
    buffer = io.BytesIO()
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="SmallNote",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#65756b"),
        )
    )
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=38,
        leftMargin=38,
        topMargin=40,
        bottomMargin=40,
    )
    content = [
        Paragraph("AutoPeritaje", styles["Title"]),
        Paragraph("Informe orientativo de daños visibles", styles["Heading2"]),
        Paragraph(
            "Caso "
            + case["id"][:8]
            + " · "
            + datetime.fromisoformat(case["created"]).strftime("%d/%m/%Y · %H:%M UTC"),
            styles["SmallNote"],
        ),
        Spacer(1, 15),
    ]
    if case.get("vehicle"):
        vehicle = case["vehicle"]
        content.append(
            Paragraph(
                "Vehículo de referencia introducido por el usuario: "
                + escape(
                    f"{vehicle['brand']} {vehicle['model']} · {vehicle['year']} · {vehicle['kilometers']} km"
                )
                + ". No identificado a partir de la fotografía.",
                styles["SmallNote"],
            )
        )
    for index, item in enumerate(case["images"], 1):
        if index > 1:
            content.append(PageBreak())
        content.append(Paragraph("Imagen " + str(index), styles["Heading2"]))
        image = Image(io.BytesIO(item["annotated_bytes"]))
        image._restrictSize(510, 245)
        content.extend([image, Spacer(1, 12)])
        rows = [["Daño", "Pieza", "Confianza", "Gravedad"]]
        rows.extend(
            [
                [
                    Paragraph(d["name"], styles["BodyText"]),
                    Paragraph(d["part"], styles["BodyText"]),
                    f"{d['confidence']:.0%}",
                    ["Leve", "Moderada", "Extensa"][d["severity"] - 1],
                ]
                for d in item["damages"]
            ]
        )
        if len(rows) > 1:
            table = Table(rows, colWidths=[120, 175, 75, 75], repeatRows=1)
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e4eee6")),
                        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#dce5de")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ]
                )
            )
            content.append(table)
        else:
            content.append(
                Paragraph(
                    "No se han identificado daños por encima del umbral. Esto no acredita la ausencia de daños.",
                    styles["BodyText"],
                )
            )
    budget_start = len(content)
    content.append(Spacer(1, 12))
    content.append(Paragraph("Estimación de reparación", styles["Heading2"]))
    content.append(Paragraph(escape(case.get("budget_note", "")), styles["SmallNote"]))
    if case.get("estimates"):
        for estimate in case["estimates"]:
            content.append(
                Paragraph(
                    f"{estimate['repair']} · {estimate['part']}: {money(estimate['cost_eur'])} ({money(estimate['lower'])}–{money(estimate['upper'])})",
                    styles["BodyText"],
                )
            )
        content.append(
            Paragraph(
                "Estimaciones procedentes de TallerMLOps, entrenado con datos sintéticos. Se agrupan daños del mismo tipo y pieza para reducir duplicaciones; no constituyen una factura ni una valoración profesional.",
                styles["SmallNote"],
            )
        )
    else:
        content.append(
            Paragraph(
                "No hay una estimación de coste disponible para este caso.",
                styles["BodyText"],
            )
        )
    content.extend(
        [
            Spacer(1, 15),
            Paragraph(
                "La segmentación detecta daños visibles de la imagen. Puede confundir reflejos, suciedad y sombras, omitir daños pequeños y no observa daños internos. La gravedad se aproxima por área; debe revisarse visualmente. El informe es una demostración de portfolio.",
                styles["SmallNote"],
            ),
            Paragraph(
                "Modelo: "
                + case["model"]
                + " · ONNX / CPU · Huella "
                + case["model_sha256"][:16],
                styles["SmallNote"],
            ),
        ]
    )
    if len(case.get("estimates", [])) <= 6:
        content[budget_start:] = [KeepTogether(content[budget_start:])]

    def footer(canvas, document):
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#65756b"))
        canvas.drawString(38, 22, "AutoPeritaje · Informe orientativo")
        canvas.drawRightString(A4[0] - 38, 22, str(document.page))

    doc.build(content, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
