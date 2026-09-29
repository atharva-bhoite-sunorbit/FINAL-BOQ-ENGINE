from __future__ import annotations

from io import BytesIO
from typing import Any

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


def generate_boq_pdf(boq_data: dict[str, Any]) -> bytes:
    output = BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        rightMargin=20,
        leftMargin=20,
        topMargin=20,
        bottomMargin=20,
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "PDFTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#1f4e79"),
        alignment=0,
    )
    subtitle_style = ParagraphStyle(
        "PDFSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#595959"),
    )
    h2_style = ParagraphStyle(
        "PDFH2",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#1f4e79"),
        spaceBefore=10,
        spaceAfter=6,
    )
    th_style = ParagraphStyle(
        "PDFTH",
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.white,
        alignment=1,
    )
    td_style = ParagraphStyle(
        "PDFTD",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#222222"),
    )
    td_num_style = ParagraphStyle(
        "PDFTDNum",
        parent=td_style,
        alignment=2,
    )
    td_bold_num_style = ParagraphStyle(
        "PDFTDBoldNum",
        parent=td_style,
        fontName="Helvetica-Bold",
        alignment=2,
    )

    story = []

    # Title & Metadata Header
    story.append(Paragraph("<b>CONSTRUCTION ESTIMATION & BILL OF QUANTITIES (BOQ)</b>", title_style))
    story.append(Paragraph("Client Detailed Estimate & Deterministic CAD-Derived Quantity Takeoff", subtitle_style))
    story.append(Spacer(1, 10))

    # Project Information Card
    draw_summary = boq_data.get("drawing_summary", {})
    filename = draw_summary.get("filename", "CAD Drawing")
    units = draw_summary.get("units", "m")
    entities_count = draw_summary.get("entity_count", 0)
    layers_count = draw_summary.get("layer_count", 0)

    items = boq_data.get("boq", [])
    if not items and "items" in boq_data:
        items = boq_data["items"]

    total_amount = sum(float(it.get("amount", 0.0)) for it in items)

    info_data = [
        [
            Paragraph(f"<b>Drawing File:</b> {filename}", td_style),
            Paragraph(f"<b>Drawing Units:</b> {units}", td_style),
            Paragraph(f"<b>Total CAD Entities:</b> {entities_count}", td_style),
        ],
        [
            Paragraph(f"<b>Layers Detected:</b> {layers_count}", td_style),
            Paragraph(f"<b>Total BOQ Items:</b> {len(items)}", td_style),
            Paragraph(f"<b>Total Estimate:</b> <font color='#1f4e79'><b>₹{total_amount:,.2f}</b></font>", td_style),
        ]
    ]
    info_table = Table(info_data, colWidths=[260, 240, 260])
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F2F6FA")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#D9E2EC")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 12))

    # BOQ Items Table
    story.append(Paragraph("<b>Itemized Construction Bill of Quantities</b>", h2_style))

    table_data = [
        [
            Paragraph("Item", th_style),
            Paragraph("Section & Material", th_style),
            Paragraph("Description / Specification", th_style),
            Paragraph("Unit", th_style),
            Paragraph("Net Qty", th_style),
            Paragraph("Wastage", th_style),
            Paragraph("Total Qty", th_style),
            Paragraph("Rate (₹)", th_style),
            Paragraph("Amount (₹)", th_style),
            Paragraph("Status", th_style),
        ]
    ]

    for it in items:
        net_val = it.get("net_quantity") if it.get("net_quantity") is not None else it.get("quantity")
        tot_val = it.get("total_quantity") if it.get("total_quantity") is not None else it.get("quantity")
        net_q = float(net_val) if net_val is not None else 0.0
        w_pct = float(it.get("wastage_percent", 0.0) or 0.0)
        tot_q = float(tot_val) if tot_val is not None else 0.0
        rate = float(it.get("rate", 0.0) or 0.0)
        amt = float(it.get("amount", tot_q * rate) or 0.0)

        sec = it.get("section", "")
        mat = it.get("material", "")
        desc = it.get("description", "")
        if len(desc) > 130:
            desc = desc[:127] + "..."

        table_data.append([
            Paragraph(str(it.get("item_no", "")), td_style),
            Paragraph(f"<b>{sec}</b><br/>{mat}", td_style),
            Paragraph(desc, td_style),
            Paragraph(str(it.get("unit", "")), td_style),
            Paragraph(f"{net_q:,.2f}", td_num_style),
            Paragraph(f"{w_pct:.0f}%", td_num_style),
            Paragraph(f"<b>{tot_q:,.2f}</b>", td_bold_num_style),
            Paragraph(f"{rate:,.2f}", td_num_style),
            Paragraph(f"<b>₹{amt:,.2f}</b>", td_bold_num_style),
            Paragraph(str(it.get("status", "DERIVED")), td_style),
        ])

    # Total Row
    table_data.append([
        "",
        "",
        Paragraph("<b>GRAND TOTAL ESTIMATED AMOUNT</b>", td_style),
        "",
        "",
        "",
        "",
        "",
        Paragraph(f"<b>₹{total_amount:,.2f}</b>", td_bold_num_style),
        "",
    ])

    col_widths = [30, 110, 240, 35, 55, 45, 60, 60, 75, 50]
    boq_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    boq_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D3D3D3")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#F9FBFC")]),
        ("LINEBELOW", (0, -1), (-1, -1), 1.5, colors.HexColor("#1F4E79")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#EAEFF5")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(boq_table)
    story.append(Spacer(1, 15))

    # Verification Signatures Block
    sig_data = [
        [
            Paragraph("<b>Prepared By:</b><br/><br/><br/>_______________________<br/>Lead Quantity Surveyor", td_style),
            Paragraph("<b>Verified By:</b><br/><br/><br/>_______________________<br/>Chief Structural / Civil Engineer", td_style),
            Paragraph("<b>Client Acceptance:</b><br/><br/><br/>_______________________<br/>Authorized Client Signature & Stamp", td_style),
        ]
    ]
    sig_table = Table(sig_data, colWidths=[260, 240, 260])
    sig_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(KeepTogether([sig_table]))

    doc.build(story)
    return output.getvalue()
