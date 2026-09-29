from __future__ import annotations

import io
import math
from pathlib import Path
import pytest
import ezdxf

from backend.geometry_engine import (
    normalize_length,
    normalize_area,
    normalize_volume,
    distance_point_to_point,
    calculate_length,
    calculate_perimeter,
    calculate_area,
    calculate_bounding_box,
    calculate_centroid,
    calculate_orientation,
    are_parallel,
    are_collinear,
    offset_distance,
    segments_intersect,
    point_in_polygon,
    polygon_contains_polygon,
    spatial_relation,
    calculate_volume,
    normalize_geometry,
    merge_parallel_walls,
)

from backend.dwg_reader import (
    validate_and_inspect_drawing,
    read_drawing,
    get_converter_executable,
    convert_dwg_to_dxf,
)
from backend.element_classifier import classify_construction_elements
from backend.quantity_engine import calculate_element_quantities
from backend.material_engine import map_quantities_to_materials, aggregate_materials
from backend.boq_engine import generate_complete_boq
from backend.excel_engine import generate_boq_excel
from backend.pdf_engine import generate_boq_pdf


# =====================================================================
# FIXTURES: Generate rich DXF with all CAD entity types
# =====================================================================

def create_comprehensive_test_dxf(output_path: Path) -> Path:
    """
    Creates a rich DXF containing all CAD entities:
    LINE, LWPOLYLINE, POLYLINE, ARC, CIRCLE, ELLIPSE, SPLINE, HATCH, INSERT,
    BLOCK, TEXT, MTEXT, DIMENSION, LEADER, 3DFACE, SOLID, POINT, UNKNOWN
    """
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    # Define Layers
    doc.layers.add(name="A-WALL", color=1)
    doc.layers.add(name="S-COLS", color=2)
    doc.layers.add(name="S-BEAM", color=3)
    doc.layers.add(name="S-SLAB", color=4)
    doc.layers.add(name="A-DOOR", color=5)
    doc.layers.add(name="A-WINDOW", color=6)
    doc.layers.add(name="A-FLOR", color=7)
    doc.layers.add(name="MEP-ELEC", color=8)

    # 1. LINE (Wall segments)
    msp.add_line((0, 0), (10, 0), dxfattribs={"layer": "A-WALL"})
    msp.add_line((0, 0.23), (10, 0.23), dxfattribs={"layer": "A-WALL"})

    # 2. LWPOLYLINE (Closed room boundary)
    msp.add_lwpolyline([(0, 0), (10, 0), (10, 8), (0, 8)], close=True, dxfattribs={"layer": "A-FLOR"})

    # 3. POLYLINE (2D/3D polyline)
    msp.add_polyline2d([(1, 1), (5, 1), (5, 4)], close=False, dxfattribs={"layer": "MEP-ELEC"})

    # 4. CIRCLE
    msp.add_circle((15, 5), radius=1.5, dxfattribs={"layer": "S-COLS"})

    # 5. ARC
    msp.add_arc((2, 0), radius=0.9, start_angle=0, end_angle=90, dxfattribs={"layer": "A-DOOR"})

    # 6. ELLIPSE
    msp.add_ellipse((12, 12), major_axis=(2.0, 0.0, 0.0), ratio=0.5, dxfattribs={"layer": "A-FLOR"})

    # 7. SPLINE
    msp.add_spline([(0, 0), (2, 3), (4, 1), (6, 5)], dxfattribs={"layer": "MEP-ELEC"})

    # 8. HATCH
    hatch = msp.add_hatch(color=1, dxfattribs={"layer": "S-SLAB"})
    hatch.set_pattern_fill("ANSI31", scale=1.0)
    hatch.paths.add_polyline_path([(0, 0), (6, 0), (6, 6), (0, 6)], is_closed=True)

    # 9. BLOCK Definition and INSERT
    blk = doc.blocks.new(name="D900_FLUSH")
    blk.add_line((0, 0), (0.9, 0))
    blk.add_arc((0, 0), radius=0.9, start_angle=0, end_angle=90)
    msp.add_blockref("D900_FLUSH", (3, 0), dxfattribs={"layer": "A-DOOR"})

    # 10. TEXT & MTEXT
    msp.add_text("RCC M25 COLUMN 450x450", dxfattribs={"layer": "S-COLS", "insert": (4, 4), "height": 0.25})
    msp.add_mtext("GROUND FLOOR PLAN\n150 THK SLAB", dxfattribs={"layer": "A-WALL", "insert": (0, 10), "char_height": 0.3})

    # 11. DIMENSION
    dim = msp.add_aligned_dim(p1=(0, 0), p2=(10, 0), distance=1.0, dxfattribs={"layer": "A-WALL"})
    dim.render()

    # 12. LEADER
    msp.add_leader(vertices=[(5, 5), (6, 6), (7, 6)], dxfattribs={"layer": "A-WALL"})

    # 13. 3DFACE
    msp.add_3dface([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], dxfattribs={"layer": "S-SLAB"})

    # 14. SOLID
    msp.add_solid([(2, 2), (3, 2), (2, 3), (3, 3)], dxfattribs={"layer": "S-COLS"})

    # 15. POINT
    msp.add_point((5, 5), dxfattribs={"layer": "MEP-ELEC"})

    doc.saveas(output_path)
    return output_path


# =====================================================================
# 1. TESTS FOR GEOMETRY ENGINE (Section 10)
# =====================================================================

def test_geometry_engine_units_normalization():
    assert normalize_length(1000.0, "mm") == pytest.approx(1.0)
    assert normalize_length(100.0, "cm") == pytest.approx(1.0)
    assert normalize_length(1.0, "m") == pytest.approx(1.0)
    assert normalize_length(39.3700787, "inch") == pytest.approx(1.0, rel=1e-4)
    assert normalize_length(3.2808399, "feet") == pytest.approx(1.0, rel=1e-4)

    assert normalize_area(1000000.0, "mm") == pytest.approx(1.0)
    assert normalize_volume(1000000000.0, "mm") == pytest.approx(1.0)


def test_geometry_engine_distance_and_length():
    p1 = [0.0, 0.0]
    p2 = [3.0, 4.0]
    assert distance_point_to_point(p1, p2) == pytest.approx(5.0)

    # Polyline length
    poly = [[0, 0], [3, 0], [3, 4]]
    assert calculate_length(poly, closed=False) == pytest.approx(7.0)
    assert calculate_perimeter(poly, closed=True) == pytest.approx(12.0)


def test_geometry_engine_shoelace_area_and_centroid():
    # 4x5 rectangle -> area 20, centroid (2, 2.5)
    rect = [[0, 0], [4, 0], [4, 5], [0, 5]]
    assert calculate_area(rect) == pytest.approx(20.0)
    cx, cy = calculate_centroid(rect)
    assert cx == pytest.approx(2.0)
    assert cy == pytest.approx(2.5)


def test_geometry_engine_bounding_box():
    pts = [[-2, 3], [5, -1], [1, 10]]
    bbox = calculate_bounding_box(pts)
    assert bbox["min_x"] == -2
    assert bbox["max_x"] == 5
    assert bbox["min_y"] == -1
    assert bbox["max_y"] == 10
    assert bbox["width"] == 7
    assert bbox["height"] == 11


def test_geometry_engine_parallelism_and_offset():
    # Two horizontal parallel segments separated by 0.23m
    s1_a, s1_b = [0.0, 0.0], [10.0, 0.0]
    s2_a, s2_b = [0.0, 0.23], [10.0, 0.23]

    assert are_parallel(s1_a, s1_b, s2_a, s2_b)
    assert offset_distance(s1_a, s1_b, s2_a, s2_b) == pytest.approx(0.23, rel=1e-3)

    # Perpendicular segments are NOT parallel
    s3_a, s3_b = [0.0, 0.0], [0.0, 5.0]
    assert not are_parallel(s1_a, s1_b, s3_a, s3_b)


def test_geometry_engine_collinearity():
    # Collinear segments along x-axis
    p1, p2 = [0.0, 0.0], [5.0, 0.0]
    q1, q2 = [6.0, 0.0], [10.0, 0.0]
    assert are_collinear(p1, p2, q1, q2)

    # Shifted parallel line is NOT collinear if offset > tolerance
    q3, q4 = [0.0, 1.0], [5.0, 1.0]
    assert not are_collinear(p1, p2, q3, q4, dist_tol=0.1)


def test_geometry_engine_segment_intersection():
    p1, p2 = [0.0, 0.0], [4.0, 4.0]
    q1, q2 = [0.0, 4.0], [4.0, 0.0]
    hit, pt = segments_intersect(p1, p2, q1, q2)
    assert hit is True
    assert pt == pytest.approx([2.0, 2.0])

    # Disjoint segments
    r1, r2 = [5.0, 0.0], [5.0, 4.0]
    hit_disjoint, _ = segments_intersect(p1, p2, r1, r2)
    assert hit_disjoint is False


def test_geometry_engine_point_in_polygon_and_containment():
    poly = [[0, 0], [10, 0], [10, 10], [0, 10]]
    assert point_in_polygon([5, 5], poly) is True
    assert point_in_polygon([15, 5], poly) is False

    inner_box = [[2, 2], [4, 2], [4, 4], [2, 4]]
    assert polygon_contains_polygon(poly, inner_box) is True

    outside_box = [[8, 8], [12, 8], [12, 12], [8, 12]]
    assert polygon_contains_polygon(poly, outside_box) is False


def test_geometry_engine_spatial_relation():
    poly = [[0, 0], [10, 0], [10, 10], [0, 10]]
    inner = [[2, 2], [4, 2], [4, 4], [2, 4]]
    assert spatial_relation(poly, inner) == "CONTAINS"

    disjoint = [[20, 20], [25, 20], [25, 25], [20, 25]]
    assert spatial_relation(poly, disjoint) == "DISJOINT"


def test_geometry_engine_wall_deduplication():
    # Two parallel lines 0.23m apart (standard brick wall faces)
    wall_segs = [
        {"entity_type": "LINE", "points": [[0, 0], [10, 0]], "handle": "H1", "layer": "A-WALL"},
        {"entity_type": "LINE", "points": [[0, 0.23], [10, 0.23]], "handle": "H2", "layer": "A-WALL"},
    ]
    deduped = merge_parallel_walls(wall_segs, "m")
    # Should deduplicate into 1 centerline representation
    assert len(deduped) == 1
    center = deduped[0]
    assert center["points"][0] == pytest.approx([0.0, 0.115])
    assert center["points"][1] == pytest.approx([10.0, 0.115])
    assert center["thickness"] == pytest.approx(0.23)


# =====================================================================
# 2. TESTS FOR DWG/DXF VALIDATION (Section 2)
# =====================================================================

def test_validation_report_schema(tmp_path: Path):
    dxf_path = create_comprehensive_test_dxf(tmp_path / "test_model.dxf")
    report = validate_and_inspect_drawing(dxf_path)

    assert report["file_name"] == "test_model.dxf"
    assert report["file_type"] == "DXF"
    assert report["converted_to_dxf"] is False
    assert report["units"] in {"m", "mm", "drawing units"}
    assert report["entities_found"] > 0
    assert report["layers_found"] >= 8
    assert report["texts_found"] >= 2
    assert report["dimensions_found"] >= 1
    assert report["hatches_found"] >= 1
    assert isinstance(report["warnings"], list)
    assert isinstance(report["errors"], list)
    assert len(report["errors"]) == 0


def test_validation_report_non_existent_file(tmp_path: Path):
    missing_path = tmp_path / "ghost_file.dwg"
    report = validate_and_inspect_drawing(missing_path)
    assert len(report["errors"]) > 0
    assert "File not found" in report["errors"][0]


def test_validation_report_invalid_extension(tmp_path: Path):
    bad_path = tmp_path / "notes.txt"
    bad_path.write_text("dummy", encoding="utf-8")
    report = validate_and_inspect_drawing(bad_path)
    assert len(report["errors"]) > 0
    assert "Invalid file extension" in report["errors"][0]


# =====================================================================
# 3. TESTS FOR PARSING EVERY ENTITY & METADATA (Sections 3 to 9)
# =====================================================================

def test_parse_every_cad_entity(tmp_path: Path):
    dxf_path = create_comprehensive_test_dxf(tmp_path / "all_entities.dxf")
    parsed = read_drawing(dxf_path)

    entity_types = {e.get("entity_type") for e in parsed["entities"]}

    # Verify minimum required entity types from Section 3
    required_types = [
        "LINE", "LWPOLYLINE", "POLYLINE", "CIRCLE", "ARC", "ELLIPSE",
        "SPLINE", "HATCH", "INSERT", "TEXT", "MTEXT", "DIMENSION",
        "LEADER", "3DFACE", "SOLID", "POINT"
    ]
    for req in required_types:
        assert req in entity_types, f"Required entity {req} missing from extraction!"

    # Verify Section 4: Entity Metadata preserved
    for e in parsed["entities"]:
        assert "handle" in e
        assert "layer" in e
        assert "entity_type" in e
        assert "units" in e

    # Verify Section 5: Layer extraction table
    assert len(parsed["layers_table"]) >= 8
    for l_entry in parsed["layers_table"]:
        assert "name" in l_entry
        assert "color" in l_entry
        assert "linetype" in l_entry
        assert "visibility" in l_entry
        assert "entity_count" in l_entry

    # Verify Section 6: Block extraction
    assert len(parsed["blocks"]) >= 1
    blk = parsed["blocks"][0]
    assert blk["block_name"] == "D900_FLUSH"
    assert "position" in blk
    assert "scale" in blk

    # Verify Section 7: Text extraction
    assert len(parsed["texts"]) >= 2
    for t in parsed["texts"]:
        assert "text" in t
        assert "position" in t
        assert "height" in t

    # Verify Section 8: Dimension extraction
    assert len(parsed["dimensions"]) >= 1
    dim = parsed["dimensions"][0]
    assert "dimension_type" in dim

    # Verify Section 9: Hatch extraction
    assert len(parsed["hatches"]) >= 1
    hatch = parsed["hatches"][0]
    assert "pattern" in hatch
    assert hatch["area"] > 0


# =====================================================================
# 4. TESTS FOR CLASSIFICATION, QUANTITIES & FORMULAS (Sections 11 to 21)
# =====================================================================

def test_construction_elements_classification(tmp_path: Path):
    dxf_path = create_comprehensive_test_dxf(tmp_path / "classify.dxf")
    parsed = read_drawing(dxf_path)
    elements = parsed["construction_elements"]

    # Verify minimum detected categories (Section 11)
    for cat in ("walls", "columns", "doors", "rooms", "floors", "assumptions"):
        assert cat in elements, f"Element category {cat} must be present in output."

    # Verify Section 12: Wall calculation & attributes
    assert len(elements["walls"]) >= 1
    wall = elements["walls"][0]
    assert "length" in wall
    assert "thickness" in wall
    assert "height" in wall
    assert "gross_area" in wall
    assert "gross_volume" in wall
    assert "net_area" in wall
    assert "net_volume" in wall
    assert "source_entities" in wall
    assert "confidence" in wall
    assert "signals" in wall

    # Verify Section 26: Confidence & Signals
    assert 0.0 <= wall["confidence"] <= 1.0
    assert len(wall["signals"]) > 0

    # Verify Section 27: Assumptions list
    assert isinstance(elements["assumptions"], list)
    assert len(elements["assumptions"]) > 0


def test_quantity_engine_deterministic_formulas(tmp_path: Path):
    dxf_path = create_comprehensive_test_dxf(tmp_path / "qty.dxf")
    parsed = read_drawing(dxf_path)
    quantities = calculate_element_quantities(parsed["construction_elements"])

    assert len(quantities) > 0
    for q in quantities:
        assert "quantity" in q
        assert "unit" in q
        assert "formula" in q, "Section 21: Every quantity must store the mathematical formula used!"
        assert "source_elements" in q
        assert len(q["formula"]) > 0


# =====================================================================
# 5. TESTS FOR REINFORCEMENT STEEL STRICT RULE (Section 23)
# =====================================================================

def test_steel_strict_rebar_rule_no_fabrication():
    """
    Section 23: Strict Rebar Rule.
    If structural reinforcement information does not exist:
    {"steel_quantity": null, "status": "STRUCTURAL_REBAR_DATA_REQUIRED"}
    """
    dummy_quantities = [
        {
            "element_type": "COLUMN",
            "source_elements": ["COL001"],
            "net_quantity": 0.405,
            "status": "MEASURED",
            "source_entities": ["H001"],
        }
    ]

    # Without any structural annotation / rebar schedule
    mats, agg = map_quantities_to_materials(dummy_quantities, annotations=[])

    steel_items = [m for m in mats if m.get("category") == "Reinforcement Steel"]
    assert len(steel_items) == 1
    steel_rec = steel_items[0]

    assert steel_rec["steel_quantity"] is None, "Section 23: steel_quantity must be null when schedule absent!"
    assert steel_rec["status"] == "STRUCTURAL_REBAR_DATA_REQUIRED", "Section 23: status must be STRUCTURAL_REBAR_DATA_REQUIRED!"

    # With structural annotation "8T16"
    mats_with_rebar, _ = map_quantities_to_materials(dummy_quantities, annotations=["8T16 RCC COLUMN"])
    steel_with_rebar = next(m for m in mats_with_rebar if "Steel" in m.get("category", ""))
    assert steel_with_rebar["steel_quantity"] is not None
    assert steel_with_rebar["steel_quantity"] > 0
    assert steel_with_rebar["status"] == "MEASURED"


# =====================================================================
# 6. TESTS FOR MATERIAL AGGREGATION (Section 24)
# =====================================================================

def test_material_aggregation_with_breakdown():
    dummy_mats = [
        {"material": "Concrete M25", "category": "Concrete", "quantity": 320.0, "unit": "m3", "element_type": "SLAB"},
        {"material": "Concrete M25", "category": "Concrete", "quantity": 110.0, "unit": "m3", "element_type": "COLUMN"},
        {"material": "Concrete M25", "category": "Concrete", "quantity": 90.0, "unit": "m3", "element_type": "BEAM"},
    ]
    aggregated = aggregate_materials(dummy_mats)
    assert len(aggregated) == 1
    conc = aggregated[0]

    assert conc["material"] == "Concrete M25"
    assert conc["quantity"] == pytest.approx(520.0)
    assert conc["breakdown"]["slabs"] == pytest.approx(320.0)
    assert conc["breakdown"]["columns"] == pytest.approx(110.0)
    assert conc["breakdown"]["beams"] == pytest.approx(90.0)


# =====================================================================
# 7. TESTS FOR TRACEABILITY & OUTPUT JSON SCHEMA (Sections 25, 28, 31)
# =====================================================================

def test_complete_boq_traceability_and_schema(tmp_path: Path):
    dxf_path = create_comprehensive_test_dxf(tmp_path / "boq_trace.dxf")
    parsed = read_drawing(dxf_path)
    boq_output = generate_complete_boq(parsed)

    # Verify Section 28 Schema Keys
    expected_top_keys = [
        "drawing", "layers", "entities", "blocks", "texts",
        "dimensions", "hatches", "construction_elements",
        "quantities", "materials", "warnings", "assumptions"
    ]
    for key in expected_top_keys:
        assert key in boq_output, f"Section 28 structured JSON missing key: '{key}'"

    # Verify Section 25 Traceability:
    # BOQ item → material → construction element → source entity
    assert len(boq_output["boq"]) > 0
    for it in boq_output["boq"]:
        assert "item_no" in it
        assert "material" in it
        assert "calculation_basis" in it
        assert "source_elements" in it
        assert "status" in it
        assert "confidence" in it


# =====================================================================
# 8. TESTS FOR EXCEL & PDF EXPORT GENERATION (Section 30)
# =====================================================================

def test_excel_and_pdf_export_generation(tmp_path: Path):
    dxf_path = create_comprehensive_test_dxf(tmp_path / "export_test.dxf")
    parsed = read_drawing(dxf_path)
    boq_output = generate_complete_boq(parsed)

    excel_bytes = generate_boq_excel(boq_output)
    assert isinstance(excel_bytes, bytes)
    assert len(excel_bytes) > 2000

    pdf_bytes = generate_boq_pdf(boq_output)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 2000


def test_unique_entries_in_boq_and_materials(tmp_path: Path):
    """
    Verifies that in both BOQ and Material list, every work item and material
    appears EXACTLY ONCE (no multiple duplicate entries for the same material).
    """
    dxf_path = create_comprehensive_test_dxf(tmp_path / "dedup_test.dxf")
    parsed = read_drawing(dxf_path)
    boq_output = generate_complete_boq(parsed)

    # 1. Verify BOQ entries are unique
    boq_items = boq_output["boq"]
    assert len(boq_items) > 0
    seen_boq = set()
    for it in boq_items:
        key = (it["material"].strip().upper(), it["unit"].strip().lower())
        assert key not in seen_boq, f"Duplicate BOQ item found for: {key}"
        seen_boq.add(key)

    # 2. Verify Material Takeoff entries are unique
    materials = boq_output["materials"]
    assert len(materials) > 0
    seen_materials = set()
    for mat in materials:
        mat_key = mat["material"].strip().upper()
        assert mat_key not in seen_materials, f"Duplicate Material entry found for: {mat_key}"
        seen_materials.add(mat_key)

