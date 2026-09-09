from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak


def money(x):
    return f"₹{float(x or 0):,.2f}"


def build_pdf(path: Path, report_id, filename, analysis, materials, boq):
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title="Construction BOQ Report",
    )

    styles = getSampleStyleSheet()
    title = ParagraphStyle("TitleX", parent=styles["Title"], alignment=TA_CENTER, fontSize=19)
    small = ParagraphStyle("SmallX", parent=styles["BodyText"], fontSize=7.5, leading=9)

    story = [
        Paragraph("CONSTRUCTION BOQ ENGINE", title),
        Paragraph("Dynamic DWG Material Estimation & Bill of Quantities", 
                  ParagraphStyle("Sub", parent=styles["BodyText"], alignment=TA_CENTER)),
        Spacer(1, 8),
    ]

    info = [
        ["Drawing", filename],
        ["Report ID", report_id],
        ["Entities", analysis.get("entities", 0)],
        ["Layers", analysis.get("layers", 0)],
        ["Units", analysis.get("units", "Verify scale")],
        ["Element types", analysis.get("element_types", 0)],
    ]
    t = Table(info, colWidths=[38*mm, 140*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (0,-1), colors.lightgrey),
        ("GRID", (0,0), (-1,-1), .4, colors.grey),
        ("FONTSIZE", (0,0), (-1,-1), 8),
    ]))
    story += [t, Spacer(1, 10)]

    story.append(Paragraph("1. Construction Elements", styles["Heading2"]))
    rows = [["Element", "Count", "Length (m)", "Area (m²)"]]
    for e in analysis.get("elements", []):
        rows.append([e["name"], e["count"], f'{e["length_m"]:.3f}', f'{e["area_m2"]:.3f}'])
    if len(rows) == 1:
        rows.append(["None detected", 0, "0", "0"])
    et = Table(rows, repeatRows=1, colWidths=[65*mm, 25*mm, 40*mm, 40*mm])
    et.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#e9eef5")),
        ("GRID", (0,0), (-1,-1), .4, colors.grey),
        ("FONTSIZE", (0,0), (-1,-1), 8),
    ]))
    story += [et]

    story.append(Paragraph("2. Material Requirement", styles["Heading2"]))
    rows = [["Material", "Qty", "Unit", "Source", "Basis"]]
    for m in materials.get("items", []):
        rows.append([
            m["material"], f'{m["quantity"]:,.3f}', m["unit"],
            m["source"], Paragraph(m["basis"], small)
        ])
    if len(rows) == 1:
        rows.append(["No material calculated", "0", "—", "REVIEW", ""])
    mt = Table(rows, repeatRows=1, colWidths=[43*mm, 22*mm, 18*mm, 30*mm, 65*mm])
    mt.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#e9eef5")),
        ("GRID", (0,0), (-1,-1), .4, colors.grey),
        ("FONTSIZE", (0,0), (-1,-1), 7),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
    ]))
    story += [mt, PageBreak()]

    story.append(Paragraph("3. Bill of Quantities", styles["Heading2"]))
    rows = [["#", "Description", "Category", "Qty", "Unit", "Rate", "Amount", "Status"]]
    for r in boq.get("items", []):
        rows.append([
            r["sr_no"], r["description"], r.get("category","Material"), f'{r["quantity"]:,.3f}', r["unit"],
            money(r["rate"]), money(r["amount"]), r["status"]
        ])
    rows.append(["", "", "", "", "", "GRAND TOTAL", money(boq.get("grand_total", 0)), "INR"])

    bt = Table(rows, repeatRows=1, colWidths=[8*mm, 38*mm, 20*mm, 19*mm, 15*mm, 23*mm, 27*mm, 25*mm])
    bt.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#e9eef5")),
        ("GRID", (0,0), (-1,-1), .4, colors.grey),
        ("FONTSIZE", (0,0), (-1,-1), 7),
        ("ALIGN", (3,1), (6,-1), "RIGHT"),
        ("FONTNAME", (5,-1), (6,-1), "Helvetica-Bold"),
    ]))
    story += [bt, Spacer(1, 10)]

    story.append(Paragraph("4. Parser Diagnostics & Verification Notes", styles["Heading2"]))
    for d in analysis.get("diagnostics", []):
        status = "OK" if d.get("success") else "FAILED"
        story.append(Paragraph(
            f"{d.get('parser', 'parser')}: {status} (return code {d.get('return_code')})", small
        ))
    for note in analysis.get("notes", []):
        story.append(Paragraph("• " + note, small))
    story.append(Spacer(1, 5))
    story.append(Paragraph(materials.get("warning", ""), small))

    doc.build(story)
