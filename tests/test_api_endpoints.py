from __future__ import annotations

import io
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
import ezdxf

from backend.main import app

client = TestClient(app)


def create_minimal_valid_dxf() -> bytes:
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    # Add a wall line
    msp.add_line((0, 0), (10, 0), dxfattribs={"layer": "I-WALL"})
    # Add another wall line
    msp.add_line((10, 0), (10, 5), dxfattribs={"layer": "I-WALL"})
    # Add a door line
    msp.add_line((2, 0), (3, 0), dxfattribs={"layer": "A-DOOR"})
    # Add a column polyline
    msp.add_lwpolyline([(4, 4), (4.4, 4), (4.4, 4.4), (4, 4.4)], close=True, dxfattribs={"layer": "STR-COL"})
    # Add text annotation
    msp.add_text("75MM GYPSUM PARTITION", dxfattribs={"layer": "I-WALL", "insert": (0, 2)})

    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


def test_health_endpoint():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_dxf_parse_and_boq_flow():
    dxf_bytes = create_minimal_valid_dxf()
    files = {"file": ("test_model.dxf", io.BytesIO(dxf_bytes), "application/dxf")}

    # 1. Upload & Parse
    res_upload = client.post("/api/dxf/parse", files=files)
    assert res_upload.status_code == 200
    data = res_upload.json()
    drawing_id = data["drawing_id"]
    assert drawing_id
    assert data["status"] == "PARSED_SUCCESSFULLY"
    assert data["entity_count"] > 0

    # 2. Get Drawing Audit Report
    res_draw = client.get(f"/api/drawing/{drawing_id}")
    assert res_draw.status_code == 200
    assert res_draw.json()["drawing_id"] == drawing_id

    # 3. Get Elements
    res_elem = client.get(f"/api/elements/{drawing_id}")
    assert res_elem.status_code == 200
    elements_data = res_elem.json()
    assert "elements" in elements_data

    # 4. Get Materials
    res_mat = client.get(f"/api/materials/{drawing_id}")
    assert res_mat.status_code == 200
    materials_data = res_mat.json()
    assert "materials" in materials_data

    # 5. Get BOQ
    res_boq = client.get(f"/api/boq/{drawing_id}")
    assert res_boq.status_code == 200
    boq_data = res_boq.json()
    assert "boq" in boq_data
    assert "reasoning_steps" in boq_data
    assert "drawing_summary" in boq_data
    assert "validation" in boq_data

    # 6. Get Validation Report
    res_val = client.get(f"/api/boq/{drawing_id}/validation")
    assert res_val.status_code == 200
    val_data = res_val.json()
    assert "passed" in val_data

    # 7. Download Excel
    res_excel = client.get(f"/api/boq/{drawing_id}/excel")
    assert res_excel.status_code == 200
    assert "application/vnd.openxmlformats" in res_excel.headers["content-type"]
    assert len(res_excel.content) > 1000

    # 8. Download PDF
    res_pdf = client.get(f"/api/boq/{drawing_id}/pdf")
    assert res_pdf.status_code == 200
    assert "application/pdf" in res_pdf.headers["content-type"]
    assert len(res_pdf.content) > 1000
