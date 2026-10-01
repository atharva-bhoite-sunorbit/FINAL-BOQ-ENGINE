from __future__ import annotations

import io
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.labour_estimation_engine import LabourEstimationEngine

client = TestClient(app)
lee = LabourEstimationEngine()


def test_labour_engine_mandays_and_costs():
    boq_items = [
        {"section": "RCC", "material": "RCC M25 Concrete", "total_quantity": 10.0, "unit": "cum"},
        {"section": "FORMWORK", "material": "Centering & Shuttering", "total_quantity": 50.0, "unit": "m2"},
        {"section": "STEEL", "material": "TMT Rebar", "total_quantity": 500.0, "unit": "kg"},
        {"section": "MASONRY", "material": "AAC Blocks", "total_quantity": 1500.0, "unit": "nos"},
        {"section": "FINISHES", "material": "Wall Putty & Emulsion Paint", "total_quantity": 100.0, "unit": "m2"},
    ]

    res = lee.estimate_labour_and_timeline(boq_items, "Residential", "Apartment")
    assert "metrics" in res
    assert "trade_breakdown" in res
    assert "phases" in res

    metrics = res["metrics"]
    assert metrics["total_mandays"] > 0
    assert metrics["total_labour_cost_inr"] > 0
    assert metrics["net_working_days"] > 0
    assert metrics["total_calendar_days"] >= metrics["net_working_days"]
    assert metrics["recommended_daily_crew"] >= 6
    assert metrics["peak_workforce"] >= metrics["recommended_daily_crew"]

    # Verify trades
    trades = {t["trade_code"]: t for t in res["trade_breakdown"]}
    assert "masons" in trades
    assert "carpenters" in trades
    assert "helpers" in trades
    assert trades["masons"]["mandays"] > 0

    # Verify 7 CPM phases
    assert len(res["phases"]) == 7
    phase_names = [p["phase_name"] for p in res["phases"]]
    assert any("Superstructure" in p for p in phase_names)
    assert any("Finishes" in p for p in phase_names)


def test_timeline_scaling_by_construction_type():
    boq_items = [
        {"section": "RCC", "material": "RCC M30 Concrete", "total_quantity": 50.0, "unit": "cum"},
        {"section": "STEEL", "material": "Structural Girders & Rebar", "total_quantity": 2500.0, "unit": "kg"},
    ]

    res_res = lee.estimate_labour_and_timeline(boq_items, "Residential", "Apartment")
    res_fac = lee.estimate_labour_and_timeline(boq_items, "Factory", "Light Industrial")

    # Factory projects deploy higher daily workforce to accelerate industrial delivery
    assert res_fac["metrics"]["recommended_daily_crew"] >= res_res["metrics"]["recommended_daily_crew"]


def test_labour_timeline_api_endpoint():
    # Upload test drawing
    from tests.test_api_endpoints import create_minimal_valid_dxf
    dxf_bytes = create_minimal_valid_dxf()
    res_up = client.post("/api/dxf/parse", files={"file": ("labour_test.dxf", io.BytesIO(dxf_bytes), "application/dxf")})
    assert res_up.status_code == 200
    doc_id = res_up.json()["drawing_id"]

    # Call endpoint /api/labour-timeline/{doc_id}
    res = client.get(f"/api/labour-timeline/{doc_id}")
    assert res.status_code == 200
    data = res.json()
    assert "metrics" in data
    assert data["metrics"]["total_mandays"] > 0
    assert "phases" in data
    assert len(data["phases"]) == 7
