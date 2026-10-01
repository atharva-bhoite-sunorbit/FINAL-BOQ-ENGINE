from __future__ import annotations

import io
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.construction_type_engine import ConstructionTypeEngine

client = TestClient(app)
cte = ConstructionTypeEngine()


# 1. Test Residential Drawing
def test_residential_classification():
    drawing_data = {
        "filename": "residential_tower_floor_plan.dxf",
        "layers": ["A-WALL", "A-DOOR", "A-WINDOW", "BED-ROOM", "KITCHEN-LAYOUT", "BATH-TOILET"],
        "texts": [
            {"raw_text": "MASTER BEDROOM 4.5m x 4.0m"},
            {"raw_text": "BEDROOM-2 3.8m x 3.6m"},
            {"raw_text": "MODULAR KITCHEN 3.0m x 2.4m"},
            {"raw_text": "ATTACHED TOILET 2.4m x 1.5m"},
            {"raw_text": "BALCONY 1.5m WIDE"},
            {"raw_text": "LIVING & DINING 6.0m x 4.0m"},
        ],
        "entities": [{"entity_type": "LINE", "layer": "A-WALL"} for _ in range(20)],
        "elements": [
            {"element_type": "WALL", "subtype": "AAC_BLOCK_WALL"},
            {"element_type": "DOOR"}, {"element_type": "DOOR"}, {"element_type": "DOOR"},
            {"element_type": "WINDOW"}, {"element_type": "WINDOW"},
            {"element_type": "ROOM", "geometry": {"area": 18.0}},
            {"element_type": "ROOM", "geometry": {"area": 13.5}},
        ],
    }
    result = cte.detect_construction_type(drawing_data)
    assert result["construction_type"] == "Residential"
    assert result["confidence"] >= 0.80
    assert result["confidence_level"] == "High"
    assert any("Bedroom" in ev for ev in result["evidence"])
    assert any("Kitchen" in ev for ev in result["evidence"])


# 2. Test Commercial / Office Building
def test_commercial_office_classification():
    drawing_data = {
        "filename": "corporate_hq_level_03.dxf",
        "layers": ["OFFICE-PARTITION", "CONF-ROOM", "WORKSTATION-GRID", "SERVER-ROOM", "A-DOOR"],
        "texts": [
            {"raw_text": "MD CABIN"},
            {"raw_text": "BOARD ROOM / CONFERENCE ROOM"},
            {"raw_text": "OPEN WORKSTATIONS (48 SEATER)"},
            {"raw_text": "MAIN RECEPTION & LOBBY"},
            {"raw_text": "SERVER ROOM / IT RACK"},
            {"raw_text": "MEETING ROOM 1 & 2"},
        ],
        "entities": [{"entity_type": "LINE", "layer": "OFFICE-PARTITION"} for _ in range(15)],
        "elements": [
            {"element_type": "PARTITION", "subtype": "GLASS_ALUMINIUM_PARTITION"},
            {"element_type": "DOOR"}, {"element_type": "DOOR"},
            {"element_type": "ROOM", "geometry": {"area": 45.0}},
        ],
    }
    result = cte.detect_construction_type(drawing_data)
    assert result["construction_type"] in {"Office Building", "Commercial"}
    assert result["confidence"] >= 0.75
    assert any("Conference" in ev or "Office" in ev or "Cabin" in ev for ev in result["evidence"])


# 3. Test Factory Drawing
def test_factory_classification():
    drawing_data = {
        "filename": "industrial_shop_floor_gantry.dxf",
        "layers": ["FACTORY-SHED", "SHOPFLOOR", "MACHINE-FOUNDATION", "CRANE-GANTRY", "EQUIPMENT"],
        "texts": [
            {"raw_text": "MAIN PRODUCTION LINE & CONVEYOR"},
            {"raw_text": "RAW MATERIAL STORAGE"},
            {"raw_text": "MACHINE SHOP FLOOR"},
            {"raw_text": "PRESS SHOP & HEAVY FOUNDATION"},
            {"raw_text": "LOADING BAY & GANTRY CRANE"},
        ],
        "entities": [{"entity_type": "LWPOLYLINE", "layer": "MACHINE-FOUNDATION"} for _ in range(10)],
        "elements": [
            {"element_type": "STEEL_FRAME"},
            {"element_type": "COLUMN", "subtype": "STEEL_PORTAL"},
            {"element_type": "MACHINE_FOUNDATION"},
            {"element_type": "LOADING_BAY"},
        ],
    }
    result = cte.detect_construction_type(drawing_data)
    assert result["construction_type"] in {"Factory", "Industrial"}
    assert result["confidence"] >= 0.75
    assert any("Machine" in ev or "Production" in ev or "Factory" in ev for ev in result["evidence"])


# 4. Test Warehouse Drawing
def test_warehouse_classification():
    drawing_data = {
        "filename": "logistics_fulfillment_center.dxf",
        "layers": ["WAREHOUSE-SLAB", "RACKING-SYSTEM", "LOADING-DOCK", "DISPATCH-BAY"],
        "texts": [
            {"raw_text": "CENTRAL WAREHOUSE BULK STORAGE"},
            {"raw_text": "HIGH BAY HEAVY DUTY PALLET RACKS"},
            {"raw_text": "LOADING DOCK 1 TO 6"},
            {"raw_text": "DISPATCH & STAGING AREA"},
            {"raw_text": "FORKLIFT AISLE 3.2m"},
        ],
        "entities": [{"entity_type": "LINE", "layer": "RACKING-SYSTEM"} for _ in range(15)],
        "elements": [
            {"element_type": "LOADING_DOCK"},
            {"element_type": "HIGH_BAY"},
            {"element_type": "SLAB"},
        ],
    }
    result = cte.detect_construction_type(drawing_data)
    assert result["construction_type"] == "Warehouse"
    assert result["confidence"] >= 0.80
    assert any("Warehouse" in ev or "Storage" in ev or "Dock" in ev for ev in result["evidence"])


# 5. Test Hospital Drawing
def test_hospital_classification():
    drawing_data = {
        "filename": "city_general_hospital_block_b.dxf",
        "layers": ["HOSP-ICU", "HOSP-OT", "WARD-LAYOUT", "MED-GAS", "PHARMACY"],
        "texts": [
            {"raw_text": "INTENSIVE CARE UNIT (ICU - 12 BEDS)"},
            {"raw_text": "OPERATION THEATRE COMPLEX (OT 1 & 2)"},
            {"raw_text": "OUT-PATIENT DEPARTMENT (OPD)"},
            {"raw_text": "CENTRAL NURSE STATION"},
            {"raw_text": "PHARMACY & DISPENSARY"},
            {"raw_text": "PATIENT GENERAL WARD"},
        ],
        "entities": [{"entity_type": "LINE", "layer": "HOSP-ICU"} for _ in range(25)],
        "elements": [
            {"element_type": "WALL"},
            {"element_type": "DOOR"},
            {"element_type": "PARTITION"},
            {"element_type": "ROOM", "geometry": {"area": 35.0}},
        ],
    }
    result = cte.detect_construction_type(drawing_data)
    assert result["construction_type"] == "Hospital"
    assert result["confidence"] >= 0.80
    assert any("Icu" in ev or "Ot" in ev or "Ward" in ev or "Nurse" in ev for ev in result["evidence"])


# 6. Test Hotel / Resort Drawing
def test_hotel_resort_classification():
    drawing_data = {
        "filename": "grand_palace_resort_floor_02.dxf",
        "layers": ["HOTEL-GUEST-ROOM", "SUITE-ROOM", "BANQUET-HALL", "RESTAURANT-DINING", "POOL-DECK"],
        "texts": [
            {"raw_text": "EXECUTIVE GUEST ROOM 201-220"},
            {"raw_text": "PRESIDENTIAL SUITE"},
            {"raw_text": "HOTEL GRAND LOBBY & RECEPTION"},
            {"raw_text": "MULTI-CUISINE RESTAURANT"},
            {"raw_text": "BANQUET HALL"},
            {"raw_text": "SWIMMING POOL & SPA DECK"},
        ],
        "entities": [{"entity_type": "LINE", "layer": "HOTEL-GUEST-ROOM"} for _ in range(30)],
        "elements": [
            {"element_type": "DOOR"}, {"element_type": "DOOR"},
            {"element_type": "BATHROOM"},
            {"element_type": "ROOM", "geometry": {"area": 32.0}},
        ],
    }
    result = cte.detect_construction_type(drawing_data)
    assert result["construction_type"] == "Hotel / Resort"
    assert result["confidence"] >= 0.80
    assert any("Guest Room" in ev or "Resort" in ev or "Banquet" in ev or "Pool" in ev for ev in result["evidence"])


# 7. Test School / College Drawing
def test_school_college_classification():
    drawing_data = {
        "filename": "vidya_mandir_academic_block.dxf",
        "layers": ["SCHOOL-CLASS", "SCIENCE-LAB", "LIBRARY-BLOCK", "AUDITORIUM"],
        "texts": [
            {"raw_text": "CLASSROOM 9-A & 9-B"},
            {"raw_text": "PHYSICS & CHEMISTRY LABORATORY"},
            {"raw_text": "PRINCIPAL CABIN & STAFF ROOM"},
            {"raw_text": "CENTRAL LIBRARY & READING ROOM"},
            {"raw_text": "COLLEGE AUDITORIUM 400 SEATS"},
            {"raw_text": "STUDENT PLAYGROUND"},
        ],
        "entities": [{"entity_type": "LINE", "layer": "SCHOOL-CLASS"} for _ in range(20)],
        "elements": [
            {"element_type": "WALL"},
            {"element_type": "DOOR"},
            {"element_type": "WINDOW"},
            {"element_type": "ROOM", "geometry": {"area": 60.0}},
        ],
    }
    result = cte.detect_construction_type(drawing_data)
    assert result["construction_type"] == "School / College"
    assert result["confidence"] >= 0.80
    assert any("Classroom" in ev or "Laboratory" in ev or "Library" in ev for ev in result["evidence"])


# 8. Test Mixed-Use Drawing
def test_mixed_use_classification():
    drawing_data = {
        "filename": "podium_tower_mixed_development.dxf",
        "layers": ["RETAIL-SHOPS", "COMM-SHOWROOM", "BED-ROOM", "KITCHEN-FLAT"],
        "texts": [
            {"raw_text": "GROUND FLOOR RETAIL SHOP 1-10"},
            {"raw_text": "COMMERCIAL SHOWROOM"},
            {"raw_text": "RETAIL DISPLAY AREA"},
            {"raw_text": "2-BHK APARTMENT MASTER BEDROOM"},
            {"raw_text": "RESIDENTIAL KITCHEN"},
            {"raw_text": "BEDROOM-2 & BALCONY"},
        ],
        "entities": [{"entity_type": "LINE", "layer": "RETAIL-SHOPS"} for _ in range(30)],
        "elements": [
            {"element_type": "WALL"},
            {"element_type": "DOOR"},
            {"element_type": "PARTITION"},
            {"element_type": "ROOM", "geometry": {"area": 25.0}},
        ],
    }
    result = cte.detect_construction_type(drawing_data)
    assert result["construction_type"] == "Mixed Use"
    assert len(result.get("components", [])) >= 2
    types = [c["type"] for c in result["components"]]
    assert "Residential" in types
    assert ("Commercial" in types or "Commercial Complex" in types)


# 9. Test Poor / Empty Drawing
def test_poor_empty_drawing_no_guesswork():
    drawing_data = {
        "filename": "empty_draft.dxf",
        "layers": ["0", "Defpoints"],
        "texts": [],
        "entities": [],
        "elements": [],
    }
    result = cte.detect_construction_type(drawing_data)
    assert result["construction_type"] == "Other / Unknown"
    assert result["confidence_level"] == "Low"
    assert result["status"] == "NEEDS_REVIEW"
    assert "insufficient" in result["classification_reason"].lower()


# 10. Test Drawing with Insufficient Signals
def test_insufficient_evidence_drawing():
    drawing_data = {
        "filename": "random_line.dxf",
        "layers": ["LAYER_1"],
        "texts": [{"raw_text": "MISC NOTE"}],
        "entities": [{"entity_type": "LINE", "layer": "LAYER_1"}],
        "elements": [{"element_type": "UNCLASSIFIED"}],
    }
    result = cte.detect_construction_type(drawing_data)
    assert result["construction_type"] == "Other / Unknown"
    assert result["confidence_level"] == "Low"
    assert result["status"] == "NEEDS_REVIEW"


# 11. Test API Endpoints
def test_api_construction_type_endpoints():
    # Test on existing sample project upload
    res = client.get("/health")
    assert res.status_code == 200

    # Test /api/construction-type/detect with invalid input
    res_err = client.post("/api/construction-type/detect")
    assert res_err.status_code == 400

    # Parse sample drawing
    from tests.test_api_endpoints import create_minimal_valid_dxf
    dxf_bytes = create_minimal_valid_dxf()
    res_up = client.post("/api/dxf/parse", files={"file": ("unit_test_sample.dxf", io.BytesIO(dxf_bytes), "application/dxf")})
    assert res_up.status_code == 200
    doc_id = res_up.json()["drawing_id"]

    # Call /api/construction-type/detect with doc_id
    res_det = client.post("/api/construction-type/detect", data={"drawing_id": doc_id})
    assert res_det.status_code == 200
    det_data = res_det.json()
    assert "construction_type" in det_data
    assert "confidence" in det_data
    assert "evidence" in det_data

    # Call /api/construction-type/confirm to override as Commercial - Office
    res_conf = client.post("/api/construction-type/confirm", data={
        "drawing_id": doc_id,
        "construction_type": "Commercial",
        "construction_subtype": "Retail Store",
        "reason": "Engineer verified as ground floor retail shop",
    })
    assert res_conf.status_code == 200
    conf_data = res_conf.json()
    assert conf_data["construction_type"] == "Commercial"
    assert conf_data["classification_source"] == "engineer"

    # Verify retrieval endpoint
    res_get = client.get(f"/api/construction-type/{doc_id}")
    assert res_get.status_code == 200
    assert res_get.json()["construction_type"] == "Commercial"
    assert res_get.json()["classification_source"] == "engineer"
