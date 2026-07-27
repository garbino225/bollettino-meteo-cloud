#!/usr/bin/env python3
"""
Assembla il PDF finale del bollettino meteorologico professionale.

Uso:
    python3 build_pdf.py report.json --charts-dir charts/ --logo logo.png --out bollettino.pdf

report.json e' scritto dall'agente dopo aver completato l'analisi (sinottica, multi-modello,
parametri avanzati, rischi, attivita'). Questo script si occupa solo dell'impaginazione
professionale: copertina, sommario, tabelle, grafici, infografica, testo.

Formato atteso di report.json:
{
  "title": "Bollettino Meteorologico Professionale",
  "location_label": "Rimini (RN), Emilia-Romagna",
  "period_label": "23-26 luglio 2026",
  "generated_at": "23 luglio 2026, 21:40",
  "moon_phase": "Gibbosa Crescente (95.3% illuminata) - prossima luna piena tra 2.1 giorni (29/07/2026)",
  "sintesi": "paragrafo di sintesi iniziale (poche righe)",
  "sections": [
     {"heading": "Analisi Sinottica", "body": "testo, paragrafi separati da doppio a-capo"},
     {"heading": "...", "body": "...", "table": {"headers": [...], "rows": [[...], ...]}}
  ],
  "risk_table": {"headers": ["Evento", "Livello", "Note"], "rows": [["Temporali", "Medio", "..."]]},
  "activities_table": {"headers": ["Attivita'", "Rischio", "Motivazione"], "rows": [[...]]},
  "reliability_pct": 82,
  "reliability_text": "spiegazione dettagliata del perche'",
  "charts": [{"file": "temperatura.png", "caption": "Temperatura a 2m - confronto modelli"},
             {"file": "ecmwf_medium-mslp-rain_00.png", "caption": "...", "landing_url": "https://charts.ecmwf.int/products/medium-mslp-rain"}, ...],
  "infographic": "infografica.png",
  "conclusione": "sintesi finale, massimo 15 righe",
  "editoriali": "testo con citazioni di meteorologi esperti e link/fonti",
  "outlook_7d": {"headers": ["Giorno", "T.min (C)", "T.max (C)", "Umidita' (%)",
                              "Pressione (hPa)", "Raffica max (kn)", "Direzione vento", "Pioggia (mm)"],
                 "rows": [["ven 25/07", "18", "27", "62", "1015.2", "14", "SE (132°)", "0.0"], ...]},
  "outlook_7d_mare": {"headers": ["Giorno", "Onda max (m)", "Periodo onda (s)", "Direzione onda", "Marea min/max (m)"],
                       "rows": [["ven 25/07", "0.36", "5.6", "ESE (106°)", "-0.77 / -0.15"], ...]}
}
"""
import argparse
import json
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Image, Table,
    TableStyle, PageBreak, NextPageTemplate, FrameBreak, KeepTogether
)
from reportlab.pdfgen import canvas as pdfcanvas

NAVY = colors.HexColor("#1a1a2e")
ORANGE = colors.HexColor("#F59F00")
BLUE = colors.HexColor("#4C6EF5")
GREY = colors.HexColor("#495057")
LIGHT = colors.HexColor("#F8F9FA")
RISK_COLORS = {"Basso": colors.HexColor("#37B24D"), "Medio": colors.HexColor("#F59F00"),
               "Alto": colors.HexColor("#E03131")}

PAGE_W, PAGE_H = A4


def build_styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("CoverTitle", parent=ss["Title"], fontSize=26, textColor=NAVY,
                           alignment=TA_CENTER, spaceAfter=6))
    ss.add(ParagraphStyle("CoverSub", parent=ss["Normal"], fontSize=15, textColor=GREY,
                           alignment=TA_CENTER, spaceAfter=4))
    ss.add(ParagraphStyle("SectionHeading", parent=ss["Heading1"], fontSize=15, textColor=NAVY,
                           spaceBefore=14, spaceAfter=8, borderColor=ORANGE, borderWidth=0,
                           leftIndent=0))
    ss.add(ParagraphStyle("Body", parent=ss["Normal"], fontSize=9.5, leading=14, textColor=colors.black,
                           alignment=TA_LEFT, spaceAfter=8))
    ss.add(ParagraphStyle("Sintesi", parent=ss["Normal"], fontSize=11, leading=16, textColor=NAVY,
                           spaceAfter=10))
    ss.add(ParagraphStyle("Caption", parent=ss["Normal"], fontSize=8, textColor=GREY,
                           alignment=TA_CENTER, spaceBefore=2, spaceAfter=14))
    ss.add(ParagraphStyle("Footer", parent=ss["Normal"], fontSize=7.5, textColor=GREY))
    return ss


def header_footer(logo_path, title):
    def _draw(c: pdfcanvas.Canvas, doc):
        c.saveState()
        c.setFont("Helvetica", 8)
        c.setFillColor(GREY)
        c.drawString(20 * mm, PAGE_H - 12 * mm, title)
        c.drawRightString(PAGE_W - 20 * mm, PAGE_H - 12 * mm, "meteoP@d0")
        c.setStrokeColor(colors.HexColor("#dee2e6"))
        c.line(20 * mm, PAGE_H - 14 * mm, PAGE_W - 20 * mm, PAGE_H - 14 * mm)
        c.line(20 * mm, 14 * mm, PAGE_W - 20 * mm, 14 * mm)
        c.drawString(20 * mm, 9 * mm, "Generato con meteoP@d0 - dati modelli numerici pubblici (Open-Meteo)")
        c.drawRightString(PAGE_W - 20 * mm, 9 * mm, f"Pag. {doc.page}")
        c.restoreState()
    return _draw


def cover_page(c: pdfcanvas.Canvas, doc, data, logo_path):
    c.saveState()
    c.setFillColor(LIGHT)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    c.setFillColor(NAVY)
    c.rect(0, PAGE_H - 8 * mm, PAGE_W, 8 * mm, fill=1, stroke=0)
    c.setFillColor(ORANGE)
    c.rect(0, PAGE_H - 8.6 * mm, PAGE_W, 0.6 * mm, fill=1, stroke=0)

    logo_bottom_y = PAGE_H - 60 * mm
    if logo_path and os.path.exists(logo_path):
        from PIL import Image as PILImage
        im = PILImage.open(logo_path)
        w, h = im.size
        target_w = 75 * mm
        target_h = target_w * h / w
        logo_top_y = PAGE_H - 35 * mm
        logo_bottom_y = logo_top_y - target_h
        c.drawImage(logo_path, (PAGE_W - target_w) / 2, logo_bottom_y,
                    width=target_w, height=target_h, mask="auto")

    title_y = logo_bottom_y - 22 * mm
    c.setFont("Helvetica-Bold", 22)
    c.setFillColor(NAVY)
    c.drawCentredString(PAGE_W / 2, title_y, "Bollettino Meteorologico Professionale")

    c.setFont("Helvetica", 16)
    c.setFillColor(GREY)
    c.drawCentredString(PAGE_W / 2, title_y - 14 * mm, data.get("location_label", ""))
    c.setFont("Helvetica", 13)
    c.drawCentredString(PAGE_W / 2, title_y - 23 * mm, data.get("period_label", ""))

    c.setFont("Helvetica-Oblique", 9)
    c.drawCentredString(PAGE_W / 2, 25 * mm, f"Generato il {data.get('generated_at', '')}")
    c.drawCentredString(PAGE_W / 2, 20 * mm,
                         "Analisi sinottica, multi-modello e convettiva - fonte dati: Open-Meteo (ECMWF, GFS, ICON, GEM, UKMO, ARPEGE, AROME, HARMONIE)")
    if data.get("moon_phase"):
        c.drawCentredString(PAGE_W / 2, 15 * mm, data["moon_phase"])
    c.restoreState()


def make_table(headers, rows, ss, col_widths=None, risk_col=None):
    data = [[Paragraph(f"<b>{h}</b>", ss["Body"]) for h in headers]]
    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            text = str(cell)
            if risk_col is not None and i == risk_col and text in RISK_COLORS:
                cells.append(Paragraph(f'<font color="{RISK_COLORS[text].hexval()}"><b>{text}</b></font>', ss["Body"]))
            else:
                cells.append(Paragraph(text, ss["Body"]))
        data.append(cells)
    t = Table(data, colWidths=col_widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E9ECEF")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#ced4da")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]
    t.setStyle(TableStyle(style))
    return t


def paragraphs_from_body(body, ss):
    flow = []
    for para in body.split("\n\n"):
        para = para.strip()
        if para:
            flow.append(Paragraph(para.replace("\n", "<br/>"), ss["Body"]))
            flow.append(Spacer(1, 4))
    return flow


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("report_json")
    ap.add_argument("--charts-dir", required=True)
    ap.add_argument("--logo", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    with open(args.report_json, encoding="utf-8") as f:
        data = json.load(f)

    ss = build_styles()
    title = data.get("title", "Bollettino Meteorologico Professionale")

    doc = BaseDocTemplate(args.out, pagesize=A4,
                           leftMargin=20 * mm, rightMargin=20 * mm,
                           topMargin=20 * mm, bottomMargin=18 * mm)
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    doc.addPageTemplates([
        PageTemplate(id="cover", frames=[frame],
                     onPage=lambda c, d: cover_page(c, d, data, args.logo)),
        PageTemplate(id="content", frames=[frame], onPage=header_footer(args.logo, title)),
    ])

    story = []
    story.append(NextPageTemplate("content"))
    story.append(PageBreak())

    live = data.get("live_station")
    if live:
        story.append(Paragraph("Dati in Tempo Reale (centralina locale)", ss["SectionHeading"]))
        live_landing_url = live.get("landing_url")
        live_link = f' <link href="{live_landing_url}" color="{BLUE.hexval()}">Pagina della centralina</link>.' if live_landing_url else ""
        story.append(Paragraph(
            f"{live.get('label', '')} &mdash; aggiornato {live.get('updated_at', '')}. "
            f"Lettura strumentale reale, non un dato di modello.{live_link}", ss["Body"]))
        rows = []
        pairs = [
            ("Temperatura", f"{live['temperature_c']}°C" if live.get("temperature_c") is not None else None),
            ("Umidita'", f"{live['humidity_pct']}%" if live.get("humidity_pct") is not None else None),
            ("Pressione", f"{live['pressure_hpa']} hPa" if live.get("pressure_hpa") is not None else None),
            ("Punto di rugiada", f"{live['dewpoint_c']}°C" if live.get("dewpoint_c") is not None else None),
            ("Vento", f"{live['wind_speed_kn']} kn" if live.get("wind_speed_kn") is not None else None),
            ("Raffica", f"{live['wind_gust_kn']} kn" if live.get("wind_gust_kn") is not None else None),
            ("Pioggia oggi", f"{live['rain_today_mm']} mm" if live.get("rain_today_mm") is not None else None),
        ]
        pairs = [p for p in pairs if p[1] is not None]
        for i in range(0, len(pairs), 2):
            chunk = pairs[i:i + 2]
            rows.append([x for pair in chunk for x in pair] if len(chunk) == 2 else [chunk[0][0], chunk[0][1], "", ""])
        story.append(make_table(["Parametro", "Valore", "Parametro", "Valore"], rows, ss))
        story.append(Spacer(1, 10))

    story.append(Paragraph("Sintesi", ss["SectionHeading"]))
    story.append(Paragraph(data.get("sintesi", ""), ss["Sintesi"]))
    story.append(Spacer(1, 6))

    if data.get("risk_table"):
        story.append(Paragraph("Quadro dei Rischi", ss["SectionHeading"]))
        rt = data["risk_table"]
        risk_idx = rt["headers"].index("Livello") if "Livello" in rt["headers"] else 1
        story.append(make_table(rt["headers"], rt["rows"], ss, risk_col=risk_idx))
        story.append(Spacer(1, 10))

    if data.get("infographic"):
        img_path = os.path.join(args.charts_dir, data["infographic"])
        if os.path.exists(img_path):
            from PIL import Image as PILImage
            im = PILImage.open(img_path)
            w, h = im.size
            target_w = doc.width
            target_h = target_w * h / w
            story.append(Image(img_path, width=target_w, height=target_h))
            story.append(Spacer(1, 10))

    for section in data.get("sections", []):
        block = [Paragraph(section["heading"], ss["SectionHeading"])]
        block += paragraphs_from_body(section.get("body", ""), ss)
        if section.get("table"):
            tb = section["table"]
            block.append(make_table(tb["headers"], tb["rows"], ss))
            block.append(Spacer(1, 8))
        story.extend(block)

    if data.get("charts"):
        story.append(PageBreak())
        story.append(Paragraph("Grafici", ss["SectionHeading"]))
        for ch in data["charts"]:
            img_path = os.path.join(args.charts_dir, ch["file"])
            if not os.path.exists(img_path):
                continue
            from PIL import Image as PILImage
            im = PILImage.open(img_path)
            w, h = im.size
            target_w = doc.width
            target_h = target_w * h / w
            max_h = doc.height * 0.42
            if target_h > max_h:
                target_h = max_h
                target_w = target_h * w / h
            caption = ch.get("caption", "")
            landing_url = ch.get("landing_url")
            if landing_url:
                caption += f' &mdash; <link href="{landing_url}" color="{BLUE.hexval()}">pagina sorgente</link>'
            story.append(KeepTogether([
                Image(img_path, width=target_w, height=target_h),
                Paragraph(caption, ss["Caption"]),
            ]))

    if data.get("activities_table"):
        story.append(PageBreak())
        story.append(Paragraph("Attivita' Consigliate", ss["SectionHeading"]))
        at = data["activities_table"]
        risk_idx = at["headers"].index("Rischio") if "Rischio" in at["headers"] else 1
        story.append(make_table(at["headers"], at["rows"], ss, risk_col=risk_idx))
        story.append(Spacer(1, 10))

    if data.get("reliability_text"):
        story.append(Paragraph(f"Affidabilita' della Previsione: {data.get('reliability_pct', '')}%",
                                ss["SectionHeading"]))
        story += paragraphs_from_body(data["reliability_text"], ss)

    if data.get("editoriali"):
        story.append(Paragraph("Editoriali e Approfondimenti di Esperti", ss["SectionHeading"]))
        story += paragraphs_from_body(data["editoriali"], ss)

    if data.get("conclusione"):
        story.append(Paragraph("Conclusioni", ss["SectionHeading"]))
        story += paragraphs_from_body(data["conclusione"], ss)

    if data.get("outlook_7d"):
        story.append(PageBreak())
        story.append(Paragraph("Outlook 7 Giorni", ss["SectionHeading"]))
        story.append(Paragraph(
            "Tendenza estesa a colpo d'occhio (modello best_match, singolo modello: "
            "affidabilita' minore rispetto all'analisi multi-modello dei giorni precedenti).",
            ss["Body"]))
        ot = data["outlook_7d"]
        story.append(make_table(ot["headers"], ot["rows"], ss))
        story.append(Spacer(1, 10))

    if data.get("outlook_7d_mare"):
        story.append(Paragraph("Outlook Mare 7 Giorni", ss["SectionHeading"]))
        om = data["outlook_7d_mare"]
        story.append(make_table(om["headers"], om["rows"], ss))
        story.append(Spacer(1, 10))

    doc.build(story)
    print(f"OK -> {args.out}")


if __name__ == "__main__":
    main()
