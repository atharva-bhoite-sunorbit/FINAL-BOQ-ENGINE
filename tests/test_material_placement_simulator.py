from __future__ import annotations

import io
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.material_placement_engine import (
    get_material_placement_rules,
    simulate_tile_placement,
    simulate_brick_placement,
    simulate_concrete_placement,
    simulate_surface_coverage,
    generate_3d_isometric_geometry,
    run_material_placement_simulation,
)

client = TestClient(app)


def test_material_rules_endpoint():
    res = client.get("/api/simulator/rules")
    assert res.status_code == 200
    data = res.json()
    assert "tiles" in data
    assert "brickwork" in data
    assert "concrete" in data
    assert "paint" in data
    assert "reinforcement" in data


def test_tile_placement_simulation():
    boundary = [(0.0, 0.0), (10.0, 0.0), (10.0, 8.0), (0.0, 8.0)]
    params = {
        "tile_length": 0.60,
        "tile_width": 0.60,
        "joint_width": 0.003,
        "pattern": "straight",
        "wastage_percent": 7.0,
    }
    result = simulate_tile_placement(boundary, params)
    assert result["placement_type"] == "tiles"
    assert result["metrics"]["usable_area"] == 80.0
    assert result["metrics"]["full_tiles"] > 0
    assert result["metrics"]["cut_tiles"] > 0
    assert result["metrics"]["procurement_quantity"] > 80.0
    assert len(result["tiles"]) > 0


def test_brick_placement_simulation():
    wall = {
        "element_id": "W-007",
        "length": 8.42,
        "height": 3.0,
        "thickness": 0.23,
        "opening_deduction": 1.24,
    }
    params = {
        "brick_length": 0.23,
        "brick_height": 0.075,
        "brick_width": 0.115,
        "mortar_joint": 0.010,
        "wastage_percent": 5.0,
    }
    result = simulate_brick_placement(wall, params)
    assert result["placement_type"] == "brickwork"
    assert result["metrics"]["total_courses"] > 0
    assert result["metrics"]["estimated_full_bricks"] > 0
    assert result["metrics"]["net_volume_cum"] == pytest.approx(4.57, 0.1)


def test_reinforcement_strict_safety_rule():
    """Verify that reinforcement placement is never invented without BBS schedule."""
    fake_record = {
        "filename": "Tower_A.dwg",
        "elements": [],
        "annotations": [],
    }
    result = run_material_placement_simulation(fake_record, "TMT Rebar Steel")
    assert result["placement_type"] == "reinforcement"
    assert result["metrics"]["confidence"] == 0.0
    assert "Reinforcement placement cannot be reliably generated" in result["warning"]


def test_simulator_api_endpoint_flow():
    sample_path = Path("sample_project.dxf")
    assert sample_path.exists()
    with open(sample_path, "rb") as f:
        res = client.post("/api/upload", files={"file": ("sample_project.dxf", f, "application/dxf")})
    assert res.status_code == 200
    doc_id = res.json()["id"]

    # Test POST /api/simulator/placement for Tiles
    res_tile = client.post(
        "/api/simulator/placement",
        json={
            "drawing_id": doc_id,
            "material": "Floor Tiles",
            "parameters": {"tile_length": 0.60, "tile_width": 0.60, "pattern": "running_bond"},
        },
    )
    assert res_tile.status_code == 200
    tile_data = res_tile.json()
    assert tile_data["placement_type"] == "tiles"
    assert "tiles" in tile_data
    assert "metrics" in tile_data
    assert tile_data["metrics"]["full_tiles"] > 0
    assert "isometric_3d" in tile_data
    assert tile_data["isometric_3d"]["available"] is True

    # Test POST /api/simulator/placement for Brickwork
    res_brick = client.post(
        "/api/simulator/placement",
        json={
            "drawing_id": doc_id,
            "material": "AAC Blockwork Masonry",
            "parameters": {"brick_length": 0.60, "brick_height": 0.20},
        },
    )
    assert res_brick.status_code == 200
    brick_data = res_brick.json()
    assert brick_data["placement_type"] == "brickwork"
    assert "courses_sample" in brick_data

    # Test GET convenience endpoint
    res_get = client.get(f"/api/drawings/{doc_id}/placement/Concrete")
    assert res_get.status_code == 200
    assert res_get.json()["placement_type"] == "concrete"

    # Test Paint and Waterproofing
    res_paint = client.post(
        "/api/simulator/placement",
        json={"drawing_id": doc_id, "material": "Emulsion Paint", "parameters": {"coats": 2}},
    )
    assert res_paint.status_code == 200
    assert res_paint.json()["placement_type"] == "paint"

    # Test Pipes
    res_pipe = client.post(
        "/api/simulator/placement",
        json={"drawing_id": doc_id, "material": "CPVC Plumbing Pipe", "parameters": {"pipe_diameter_mm": 32}},
    )
    assert res_pipe.status_code == 200
    assert res_pipe.json()["placement_type"] == "pipes"

    # Test Doors
    res_door = client.post(
        "/api/simulator/placement",
        json={"drawing_id": doc_id, "material": "Flush Door", "parameters": {}},
    )
    assert res_door.status_code == 200
    assert res_door.json()["placement_type"] == "doors"

