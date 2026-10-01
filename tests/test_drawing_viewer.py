from __future__ import annotations

import io
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
import ezdxf

from backend.main import app

client = TestClient(app)


def create_custom_layer_dxf() -> bytes:
    """Create a DXF drawing with unusual/non-standard layer names to test layer normalization."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    # Unusual wall layer names
    msp.add_line((0, 0), (12, 0), dxfattribs={"layer": "ARCH_EXT_WALL_230"})
    msp.add_line((12, 0), (12, 8), dxfattribs={"layer": "WALL_PARTITION_115"})
    # Unusual column layer
    msp.add_lwpolyline([(0, 0), (0.45, 0), (0.45, 0.45), (0, 0.45)], close=True, dxfattribs={"layer": "STR_RCC_COLUMN_C1"})
    msp.add_lwpolyline([(12, 0), (12.45, 0), (12.45, 0.45), (12, 0.45)], close=True, dxfattribs={"layer": "STR_RCC_COLUMN_C2"})
    # Unusual door layer
    msp.add_line((3, 0), (4.2, 0), dxfattribs={"layer": "JOINERY_DOOR_D1"})
    # Annotation
    msp.add_text("230MM BRICKWORK MASONRY IN 1:6 MORTAR", dxfattribs={"layer": "TEXT_NOTES", "insert": (1, 1)})

    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


def create_partial_drawing_dxf() -> bytes:
    """Create an architectural drawing missing structural reinforcement to test partial drawing handling."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    # Only architectural walls and doors, no rebar BBS schedule
    msp.add_line((0, 0), (8, 0), dxfattribs={"layer": "A-WALL"})
    msp.add_line((8, 0), (8, 6), dxfattribs={"layer": "A-WALL"})
    msp.add_line((2, 0), (3, 0), dxfattribs={"layer": "A-DOOR"})
    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


def test_upload_sample_project_dxf_and_viewer_geometry():
    sample_path = Path("sample_project.dxf")
    assert sample_path.exists(), "sample_project.dxf must exist in root"

    with open(sample_path, "rb") as f:
        res = client.post("/api/upload", files={"file": ("sample_project.dxf", f, "application/dxf")})

    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True or "items" in data
    doc_id = data["id"]
    assert doc_id

    # Check viewer_geometry payload
    vg = data.get("viewer_geometry")
    assert vg is not None
    assert "entities" in vg
    assert "bounds" in vg
    assert "layers" in vg
    assert len(vg["entities"]) > 0

    # Check confidence breakdown
    cb = data.get("confidence_breakdown")
    assert cb is not None
    assert "composite_score" in cb
    assert "overall_status" in cb
    assert cb["overall_status"] in ["VERIFIED", "CONDITIONALLY_VERIFIED", "REVIEW_REQUIRED"]

    # Check that source_elements are linked to BOQ items
    items = data.get("items", [])
    assert len(items) > 0
    items_with_sources = [item for item in items if (item.get("source_elements") or item.get("source_element_ids"))]
    assert len(items_with_sources) > 0, "At least some BOQ items must have linked source CAD elements"


def test_cad_viewer_endpoints():
    sample_path = Path("sample_project.dxf")
    with open(sample_path, "rb") as f:
        res = client.post("/api/upload", files={"file": ("sample_project.dxf", f, "application/dxf")})
    doc_id = res.json()["id"]

    # 1. GET /api/drawings/{id}/geometry
    res_geom = client.get(f"/api/drawings/{doc_id}/geometry")
    assert res_geom.status_code == 200
    geom_data = res_geom.json()
    assert "entities" in geom_data
    assert "bounds" in geom_data

    # 2. GET /api/drawings/{id}/layers
    res_layers = client.get(f"/api/drawings/{doc_id}/layers")
    assert res_layers.status_code == 200
    layers_data = res_layers.json()
    assert "layers" in layers_data
    assert len(layers_data["layers"]) > 0

    # 3. GET /api/drawings/{id}/elements
    res_elems = client.get(f"/api/drawings/{doc_id}/elements")
    assert res_elems.status_code == 200
    elems_data = res_elems.json()
    assert "elements" in elems_data
    elements = elems_data["elements"]
    assert len(elements) > 0

    first_elem = elements[0]
    first_elem_id = first_elem["element_id"]

    # 4. GET /api/drawings/{id}/elements/{element_id}
    res_elem = client.get(f"/api/drawings/{doc_id}/elements/{first_elem_id}")
    assert res_elem.status_code == 200
    elem_detail = res_elem.json()
    assert elem_detail["element_id"] == first_elem_id
    assert "quantities" in elem_detail

    # 5. GET /api/drawings/{id}/elements/{element_id}/sources
    res_sources = client.get(f"/api/drawings/{doc_id}/elements/{first_elem_id}/sources")
    assert res_sources.status_code == 200
    assert "source_entities" in res_sources.json()

    # 6. GET /api/boq/{id}/items/1/sources
    res_boq_sources = client.get(f"/api/boq/{doc_id}/items/1/sources")
    assert res_boq_sources.status_code == 200
    assert "source_elements" in res_boq_sources.json()

    # 7. GET /api/boq/{id}/items/1/calculation
    res_calc = client.get(f"/api/boq/{doc_id}/items/1/calculation")
    assert res_calc.status_code == 200
    calc_data = res_calc.json()
    assert "formula" in calc_data
    assert "deterministic" in calc_data
    assert calc_data["deterministic"] is True

    # 8. GET /api/drawings/{id}/revisions
    res_rev = client.get(f"/api/drawings/{doc_id}/revisions")
    assert res_rev.status_code == 200
    rev_data = res_rev.json()
    assert "available_revisions" in rev_data

    # 9. GET /api/drawings/{id}/revisions/compare
    res_comp = client.get(f"/api/drawings/{doc_id}/revisions/compare?rev_a=REV-01&rev_b=REV-02")
    assert res_comp.status_code == 200
    comp_data = res_comp.json()
    assert "counts" in comp_data
    assert "quantity_deltas" in comp_data

    # 10. POST /api/drawings/{id}/measure
    res_meas = client.post(
        f"/api/drawings/{doc_id}/measure",
        json={"mode": "distance", "points": [[0, 0], [3, 4]]},
    )
    assert res_meas.status_code == 200
    meas_data = res_meas.json()
    assert meas_data["value"] == pytest.approx(5.0, 0.01)

    # 11. POST /api/drawing/{id}/unit
    res_unit = client.post(
        f"/api/drawing/{doc_id}/unit",
        data={"unit": "m"},
    )
    assert res_unit.status_code == 200
    assert res_unit.json()["unit"] == "m"


def test_custom_layer_normalization():
    """Verify drawing with unusual layers is parsed and classified into standard construction elements."""
    dxf_bytes = create_custom_layer_dxf()
    res = client.post("/api/upload", files={"file": ("unusual_layers.dxf", io.BytesIO(dxf_bytes), "application/dxf")})
    assert res.status_code == 200
    data = res.json()
    elements = data.get("elements", [])
    element_types = [e.get("element_type") for e in elements]
    assert "WALL" in element_types or "Wall" in element_types or "COLUMN" in element_types or "Column" in element_types


def test_partial_drawing_handling():
    """Verify partial drawing does not hallucinate rebar or missing info."""
    dxf_bytes = create_partial_drawing_dxf()
    res = client.post("/api/upload", files={"file": ("partial_arch.dxf", io.BytesIO(dxf_bytes), "application/dxf")})
    assert res.status_code == 200
    data = res.json()
    # Check that rebar items flag schedule required and don't invent arbitrary tons
    items = data.get("items", [])
    for it in items:
        if "rebar" in (it.get("material") or "").lower() or "steel" in (it.get("material") or "").lower():
            assert it.get("status") == "STRUCTURAL_REBAR_DATA_REQUIRED" or it.get("final_quantity") is None or "schedule" in (it.get("calculation") or "").lower()


def test_structured_json_error_handling():
    """Verify that bad files or requests return valid JSON error structure, never HTML or plaintext 500."""
    # Send corrupted file bytes
    corrupt_bytes = b"CORRUPTED_NON_CAD_BINARY_DATA\x00\x01\x02"
    res = client.post("/api/upload", files={"file": ("corrupt.dwg", io.BytesIO(corrupt_bytes), "application/octet-stream")})

    # Response should have JSON content-type
    assert "application/json" in res.headers["content-type"]
    err_json = res.json()
    assert "success" in err_json or "detail" in err_json or "error" in err_json
