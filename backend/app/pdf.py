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
        "KTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#1f4e79"),
        alignment=0,
    )
    subtitle_style = ParagraphStyle(
        "KSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#595959"),
    )
    h2_style = ParagraphStyle(
        "KH2",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#1f4e79"),
        spaceBefore=10,
        spaceAfter=6,
    )
    th_style = ParagraphStyle(
        "KTH",
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=9,
        textColor=colors.white,
        alignment=1,
    )
    td_style = ParagraphStyle(
        "KTD",
        fontName="Helvetica",
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#222222"),
    )
    td_bold = ParagraphStyle(
        "KTDBold",
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#222222"),
    )
    td_right = ParagraphStyle(
        "KTDRight",
        fontName="Helvetica",
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#222222"),
        alignment=2,
    )
    td_right_bold = ParagraphStyle(
        "KTDRightBold",
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#1f4e79"),
        alignment=2,
    )

    story = []

    # 1. Header
    story.append(Paragraph("KRISALA DEVELOPERS", title_style))
    story.append(Paragraph("Geometry-First Construction Estimation & Material Takeoff Report", subtitle_style))
    story.append(Spacer(1, 6))

    proj = boq_data.get("project", {})
    cost = boq_data.get("cost", {})
    items = boq_data.get("items", [])
    mto_items = boq_data.get("materials", {}).get("items", [])

    meta_text = (
        f"<b>Project File:</b> {proj.get('file_name', 'N/A')} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>Units:</b> {str(proj.get('units', 'mm')).upper()} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>BOQ Line Items:</b> {len(items)} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>Material Takeoff Items:</b> {len(mto_items)}"
    )
    story.append(Paragraph(meta_text, td_style))
    story.append(Spacer(1, 10))

    # 2. BOQ Schedule Table
    story.append(Paragraph("Schedule A: Bill of Quantities (BOQ)", h2_style))

    boq_headers = [
        "Sr.", "Code", "Description", "Unit", "Drawing Qty",
        "Base Qty", "Deductions", "Net Qty", "Wastage", "Final Qty",
        "Material Rate", "Labour Rate", "Total Rate", "Amount (₹)",
    ]
    boq_col_widths = [20, 42, 175, 30, 46, 46, 46, 46, 36, 46, 52, 50, 50, 65]

    table_data = [[Paragraph(h, th_style) for h in boq_headers]]

    for idx, item in enumerate(items, start=1):
        desc = f"<b>{item.get('category', '')}</b>: {item.get('description', '')}"
        row = [
            Paragraph(str(item.get("sr_no", idx)), td_style),
            Paragraph(item.get("code", ""), td_bold),
            Paragraph(desc, td_style),
            Paragraph(item.get("unit", ""), td_style),
            Paragraph(f"{item.get('drawing_quantity', item.get('quantity', 0)):,.2f}", td_right),
            Paragraph(f"{item.get('gross_quantity', item.get('quantity', 0)):,.2f}", td_right),
            Paragraph(f"{item.get('opening_deduction', 0.0):,.2f}", td_right),
            Paragraph(f"{item.get('net_quantity', item.get('quantity', 0)):,.2f}", td_right),
            Paragraph(f"{item.get('wastage_pct', 0):g}%", td_style),
            Paragraph(f"{item.get('final_quantity', 0):,.2f}", td_bold),
            Paragraph(f"₹{item.get('material_rate', 0):,.2f}", td_right),
            Paragraph(f"₹{item.get('labour_rate', 0):,.2f}", td_right),
            Paragraph(f"₹{item.get('final_rate', item.get('rate', 0)):,.2f}", td_right),
            Paragraph(f"₹{item.get('amount', 0):,.2f}", td_right_bold),
        ]
        table_data.append(row)

    # Add Subtotal Row
    total_amount = cost.get("subtotal", sum(i.get("amount", 0) for i in items))
    subtotal_row = [
        Paragraph("", td_style),
        Paragraph("", td_style),
        Paragraph("<b>TOTAL DIRECT CONSTRUCTION COST</b>", td_bold),
        Paragraph("", td_style),
        Paragraph("", td_style),
        Paragraph("", td_style),
        Paragraph("", td_style),
        Paragraph("", td_style),
        Paragraph("", td_style),
        Paragraph("", td_style),
        Paragraph("", td_style),
        Paragraph("", td_style),
        Paragraph("", td_style),
        Paragraph(f"<b>₹{total_amount:,.2f}</b>", td_right_bold),
    ]
    table_data.append(subtotal_row)

    boq_table = Table(table_data, colWidths=boq_col_widths, repeatRows=1)
    boq_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e79")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D3D3D3")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.HexColor("#FFFFFF"), colors.HexColor("#F9FBFD")]),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#D9E2EC")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(boq_table)
    story.append(Spacer(1, 14))

    # 3. Material Takeoff (MTO) Schedule
    story.append(Paragraph("Schedule B: Exact Constituent Material Takeoff (MTO)", h2_style))

    mto_headers = [
        "Sr.", "Code", "Constituent Material", "Category", "Derived From",
        "Base Takeoff", "Factor", "Wastage", "Required Qty", "Unit", "Rate (₹)", "Cost (₹)",
    ]
    mto_col_widths = [20, 52, 175, 80, 130, 48, 38, 38, 48, 35, 45, 60]

    mto_data = [[Paragraph(h, th_style) for h in mto_headers]]

    for idx, mat in enumerate(mto_items[:60], start=1):
        mto_row = [
            Paragraph(str(mat.get("sr_no", idx)), td_style),
            Paragraph(mat.get("material_code", ""), td_bold),
            Paragraph(mat.get("material_name", ""), td_style),
            Paragraph(mat.get("category", ""), td_style),
            Paragraph(mat.get("derived_from", ""), td_style),
            Paragraph(f"{mat.get('base_quantity', 0):,.2f}", td_right),
            Paragraph(f"{mat.get('consumption_factor', 1.0):g}", td_style),
            Paragraph(f"{mat.get('wastage_percent', 0):g}%", td_style),
            Paragraph(f"{mat.get('final_quantity', 0):,.2f}", td_bold),
            Paragraph(mat.get("unit", ""), td_style),
            Paragraph(f"₹{mat.get('unit_rate', 0):,.2f}", td_right),
            Paragraph(f"₹{mat.get('total_cost', 0):,.2f}", td_right_bold),
        ]
        mto_data.append(mto_row)

    tot_mat_cost = boq_data.get("materials", {}).get("total_material_cost", sum(m.get("total_cost", 0) for m in mto_items))
    mto_total_row = [
        Paragraph("", td_style),
        Paragraph("", td_style),
        Paragraph("<b>TOTAL MATERIAL TAKEOFF REQUIREMENT</b>", td_bold),
        Paragraph("", td_style),
        Paragraph("", td_style),
        Paragraph("", td_style),
        Paragraph("", td_style),
        Paragraph("", td_style),
        Paragraph("", td_style),
        Paragraph("", td_style),
        Paragraph("", td_style),
        Paragraph(f"<b>₹{tot_mat_cost:,.2f}</b>", td_right_bold),
    ]
    mto_data.append(mto_total_row)

    mto_table = Table(mto_data, colWidths=mto_col_widths, repeatRows=1)
    mto_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0E6655")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D3D3D3")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.HexColor("#FFFFFF"), colors.HexColor("#F4FBF7")]),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#D1E7DD")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(mto_table)
    story.append(Spacer(1, 14))

    # 4. Cost Summary Block
    summary_data = [
        [Paragraph("<b>Cost Component</b>", td_bold), Paragraph("<b>Estimated Amount (INR)</b>", td_right_bold)],
        [Paragraph("Direct Material Cost Takeoff", td_style), Paragraph(f"₹{cost.get('material_cost', 0):,.2f}", td_right)],
        [Paragraph("Direct Labour Cost Estimate", td_style), Paragraph(f"₹{cost.get('labour_cost', 0):,.2f}", td_right)],
        [Paragraph("Subtotal (Direct Construction Cost)", td_bold), Paragraph(f"₹{cost.get('subtotal', 0):,.2f}", td_right_bold)],
        [Paragraph(f"GST / Works Contract Tax ({cost.get('tax_rate', 18)}%)", td_style), Paragraph(f"₹{cost.get('tax', 0):,.2f}", td_right)],
        [Paragraph("<b>GRAND TOTAL PROJECT ESTIMATE</b>", title_style), Paragraph(f"<b>₹{cost.get('grand_total', 0):,.2f}</b>", title_style)],
    ]
    summary_table = Table(summary_data, colWidths=[250, 180])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8F1F9")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#F9F9F9")]),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#D9E2EC")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    story.append(KeepTogether([
        Paragraph("Executive Cost Summary", h2_style),
        summary_table,
    ]))

    doc.build(story)
    return output.getvalue()
