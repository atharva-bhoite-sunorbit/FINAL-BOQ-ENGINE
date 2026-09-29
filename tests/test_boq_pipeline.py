from __future__ import annotations

import pytest
from backend.models.construction_element import ConstructionElement
from backend.models.cad_entity import CADEntity
from backend.models.boq_item import BOQItem

from backend.quantity.unit_converter import to_meters, from_meters, to_sqm, to_cum, to_kg
from backend.quantity.deduction_engine import DeductionEngine
from backend.quantity.wastage_engine import WastageEngine
from backend.quantity.volume_calculator import calculate_wall_volume, calculate_column_volume, calculate_beam_volume

from backend.materials.concrete import calculate_concrete
from backend.materials.steel import calculate_steel, bar_weight_per_meter
from backend.materials.brick import calculate_brickwork
from backend.materials.blockwork import calculate_blockwork
from backend.materials.gypsum import calculate_gypsum, calculate_gypsum_partition
from backend.materials.glass import calculate_glass
from backend.materials.aluminium import calculate_aluminium
from backend.materials.flooring import calculate_flooring
from backend.materials.plaster import calculate_plaster
from backend.materials.paint import calculate_paint
from backend.materials.waterproofing import calculate_waterproofing

from backend.boq.boq_grouping import determine_section, group_boq_items
from backend.boq.boq_validator import BOQValidator
from backend.boq.boq_item_builder import BOQItemBuilder
from backend.boq.boq_formatter import format_final_boq_response
from backend.export.excel_engine import generate_boq_excel
from backend.export.pdf_engine import generate_boq_pdf


# 1. Wall Quantity & Volume
def test_wall_quantity_volume():
    length = 12.5
    height = 3.0
    thickness = 0.15
    vol = calculate_wall_volume(length, height, thickness)
    assert vol == pytest.approx(5.625, rel=1e-3)


# 2. Door Deduction
def test_door_deduction():
    length = 12.5
    height = 3.0
    thickness = 0.15
    gross_vol = calculate_wall_volume(length, height, thickness)  # 5.625

    door_ded = DeductionEngine.calculate_opening_deduction(
        opening_width_m=1.0,
        opening_height_m=2.1,
        wall_thickness_m=thickness,
    )
    assert door_ded["deduction_volume_m3"] == pytest.approx(0.315, rel=1e-3)

    net_vol = gross_vol - door_ded["deduction_volume_m3"]
    assert net_vol == pytest.approx(5.310, rel=1e-3)


# 3. Window Deduction
def test_window_deduction():
    thickness = 0.20
    win_ded = DeductionEngine.calculate_opening_deduction(
        opening_width_m=1.2,
        opening_height_m=1.2,
        wall_thickness_m=thickness,
    )
    expected_vol = 1.2 * 1.2 * 0.20  # 0.288
    assert win_ded["deduction_volume_m3"] == pytest.approx(expected_vol, rel=1e-3)


# 4. Brickwork & Mortar
def test_brickwork_calculation():
    elem = ConstructionElement(
        element_id="WAL_001",
        element_type="WALL",
        subtype="BRICK_WALL",
        geometry={"length": 10.0, "height": 3.0, "thickness": 0.23, "volume": 6.9},
        material_hint="BRICK",
        status="MEASURED",
    )
    mats = calculate_brickwork(elem)
    assert len(mats) >= 3
    # 500 bricks per m3 * 6.9 = 3450 bricks
    brick_mat = next(m for m in mats if "Brick" in m.material_name or "BRK" in m.material_code)
    assert brick_mat.net_quantity == pytest.approx(3450.0, rel=1e-2)
    assert brick_mat.total_quantity > brick_mat.net_quantity  # includes wastage


# 5. Blockwork Calculation
def test_blockwork_calculation():
    elem = ConstructionElement(
        element_id="WAL_002",
        element_type="WALL",
        subtype="AAC_BLOCK_WALL",
        geometry={"length": 8.0, "height": 3.0, "thickness": 0.15, "volume": 3.6},
        material_hint="AAC_BLOCK",
        status="MEASURED",
    )
    mats = calculate_blockwork(elem)
    assert len(mats) >= 1
    aac_mat = mats[0]
    assert aac_mat.unit == "nos"
    expected_blocks = 3.6 / (0.6 * 0.2 * 0.15)  # 200 blocks
    assert aac_mat.net_quantity == pytest.approx(expected_blocks, rel=1e-2)


# 6. Concrete Takeoff
def test_concrete_calculation():
    elem = ConstructionElement(
        element_id="COL_001",
        element_type="COLUMN",
        subtype="RCC_COLUMN",
        geometry={"width": 0.3, "depth": 0.45, "height": 3.0, "volume": 0.405},
        material_hint="RCC_M25",
        status="MEASURED",
    )
    mats = calculate_concrete(elem)
    assert len(mats) == 1
    conc = mats[0]
    assert "M25" in conc.material_name
    assert conc.net_quantity == pytest.approx(0.405, rel=1e-3)
    assert conc.total_quantity == pytest.approx(0.405 * 1.025, rel=1e-3)


# 7. Steel Reinforcement (Formula & NOT_AVAILABLE strict rule)
def test_steel_calculation_and_no_fabrication():
    # Weight per meter formula D^2 / 162
    w16 = bar_weight_per_meter(16.0)
    assert w16 == pytest.approx(256.0 / 162.0, rel=1e-3)

    # When no rebar schedule is present, MUST return NOT_AVAILABLE
    elem_no_steel = ConstructionElement(
        element_id="COL_002",
        element_type="COLUMN",
        subtype="RCC_COLUMN",
        geometry={"width": 0.3, "depth": 0.3, "height": 3.0, "volume": 0.27},
        status="MEASURED",
    )
    mats = calculate_steel(elem_no_steel)
    assert len(mats) == 1
    assert mats[0].status == "NOT_AVAILABLE"
    assert mats[0].total_quantity == 0.0

    # When rebar is provided explicitly
    elem_with_steel = ConstructionElement(
        element_id="COL_003",
        element_type="COLUMN",
        subtype="RCC_COLUMN",
        geometry={"width": 0.3, "depth": 0.3, "height": 3.0, "volume": 0.27},
        source_annotations=["8T16 RCC COLUMN"],
        status="MEASURED",
    )
    mats_steel = calculate_steel(elem_with_steel)
    assert len(mats_steel) == 1
    assert mats_steel[0].status in {"MEASURED", "DERIVED"}
    assert mats_steel[0].total_quantity > 0.0


# 8. Gypsum Partition Takeoff (Section 19 exact example)
def test_gypsum_partition_takeoff():
    # length = 28.42m, height = 3m, 2 sides, 2 layers => 28.42 * 3 * 2 * 2 = 341.04 sqm
    elem = ConstructionElement(
        element_id="PAR_001",
        element_type="PARTITION",
        subtype="GYPSUM_PARTITION",
        geometry={"length": 28.42, "height": 3.0, "thickness": 0.075},
        source_annotations=["DOUBLE SKIN 75MM GYPSUM PARTITION"],
        status="MEASURED",
    )
    mats = calculate_gypsum(elem, sides=2, layers_per_side=2)
    board_mat = next(m for m in mats if "Gypsum" in m.material_name or "GYP" in m.material_code)
    assert board_mat.net_quantity == pytest.approx(341.04, rel=1e-2)
    # With 5% wastage => 341.04 * 1.05 = 358.092
    assert board_mat.total_quantity == pytest.approx(358.092, rel=1e-2)


# 9. Glass & Aluminium Partition Takeoff (Section 20 exact example)
def test_glass_partition_takeoff():
    # 34.70m x 2.40m => glass area 83.28 m2
    elem = ConstructionElement(
        element_id="GLP_001",
        element_type="PARTITION",
        subtype="GLASS_ALUMINIUM_PARTITION",
        geometry={"length": 34.70, "height": 2.40, "area": 83.28},
        status="MEASURED",
    )
    mats_glass = calculate_glass(elem)
    assert len(mats_glass) >= 1
    assert mats_glass[0].net_quantity == pytest.approx(83.28, rel=1e-2)

    mats_alu = calculate_aluminium(elem)
    assert len(mats_alu) >= 1
    assert mats_alu[0].net_quantity > 0.0


# 10. Flooring & Skirting
def test_flooring_calculation():
    elem = ConstructionElement(
        element_id="FLR_001",
        element_type="FLOOR",
        subtype="VITRIFIED_TILE_FLOORING",
        geometry={"area": 50.0, "perimeter": 30.0},
        status="MEASURED",
    )
    mats = calculate_flooring(elem)
    tile_mat = next(m for m in mats if "Vitrified" in m.material_name or "TIL" in m.material_code)
    assert tile_mat.net_quantity == pytest.approx(50.0, rel=1e-2)
    skirt_mat = next(m for m in mats if "Skirting" in m.material_name or "SKT" in m.material_code)
    assert skirt_mat.net_quantity == pytest.approx(30.0, rel=1e-2)


# 11. Plastering Takeoff
def test_plaster_calculation():
    elem = ConstructionElement(
        element_id="WAL_003",
        element_type="WALL",
        subtype="INTERNAL_WALL",
        geometry={"length": 5.0, "height": 3.0, "area": 15.0},
        status="MEASURED",
    )
    mats = calculate_plaster(elem, thickness_mm=12.0, is_external=False)
    # 2 faces of wall => 30 sqm
    assert len(mats) >= 2  # cement + sand


# 12. Painting Takeoff
def test_paint_calculation():
    elem = ConstructionElement(
        element_id="WAL_004",
        element_type="WALL",
        subtype="INTERNAL_WALL",
        geometry={"length": 6.0, "height": 3.0, "area": 18.0},
        status="MEASURED",
    )
    mats = calculate_paint(elem)
    assert len(mats) >= 3  # putty, primer, paint


# 13. Waterproofing with Upturn
def test_waterproofing_calculation():
    elem = ConstructionElement(
        element_id="WTP_001",
        element_type="SLAB",
        subtype="TOILET_SUNKEN_SLAB",
        geometry={"area": 12.0, "perimeter": 14.0},
        status="MEASURED",
    )
    mats = calculate_waterproofing(elem, upturn_height_m=0.30)
    assert len(mats) >= 1
    # area 12 + upturn (14 * 0.3 = 4.2) = 16.2 m2
    assert mats[0].net_quantity == pytest.approx(16.2, rel=1e-2)


# 14. Staircase Detection & Calculation
def test_staircase_calculation():
    elem = ConstructionElement(
        element_id="STR_001",
        element_type="STAIRCASE",
        subtype="RCC_DOG_LEGGED_STAIRCASE",
        geometry={"length": 4.5, "width": 1.2, "height": 3.0, "volume": 1.62},
        status="MEASURED",
    )
    mats = calculate_concrete(elem)
    assert len(mats) >= 1
    assert mats[0].net_quantity == pytest.approx(1.62, rel=1e-3)


# 15. Duplicate Entity Prevention
def test_duplicate_entity_prevention():
    v = BOQValidator()
    entities = [
        CADEntity(entity_id="E001", entity_type="LINE", handle="H100"),
        CADEntity(entity_id="E002", entity_type="LINE", handle="H100"),  # Duplicate handle
    ]
    res = v.validate_all(boq_items=[], entities=entities)
    assert any(w["code"] == "DUPLICATE_ENTITIES" for w in res["warnings"])


# 16. Duplicate Drawing View Prevention
def test_duplicate_drawing_view_prevention():
    v = BOQValidator()
    views = [
        {"title": "GROUND FLOOR PLAN"},
        {"title": "GROUND FLOOR PLAN"},  # Duplicate
    ]
    res = v.validate_all(boq_items=[], views=views)
    assert any(w["code"] == "DUPLICATE_DRAWING_VIEW" for w in res["warnings"])


# 17. Unit Conversion
def test_unit_conversions():
    assert to_meters(3000.0, "mm") == pytest.approx(3.0)
    assert from_meters(3.0, "mm") == pytest.approx(3000.0)
    assert to_sqm(100.0, "sqm") == pytest.approx(100.0)
    assert to_cum(1.0, "m3") == pytest.approx(1.0)
    assert to_kg(1.0, "mt") == pytest.approx(1000.0)


# 18. Wastage Engine
def test_wastage_engine():
    w = WastageEngine()
    res = w.apply_wastage(100.0, "Tile")
    assert res["wastage_percent"] == 5.0
    assert res["wastage_quantity"] == 5.0
    assert res["total_quantity"] == 105.0


# 19. BOQ Grouping & Chronological Order
def test_boq_grouping_chronological():
    sec_earth = determine_section("FOUNDATION", "Excavation in trenches", "Excavation")
    assert "EARTHWORK" in sec_earth

    sec_pcc = determine_section("FOUNDATION", "Plain Cement Concrete", "PCC 1:4:8")
    assert "PCC" in sec_pcc

    sec_rcc = determine_section("COLUMN", "RCC M25 Concrete", "Concrete")
    assert "RCC" in sec_rcc

    sec_steel = determine_section("COLUMN", "TMT Fe 500D Reinforcement Steel", "Rebar")
    assert "REINFORCEMENT STEEL" in sec_steel

    sec_paint = determine_section("WALL", "Acrylic Emulsion Paint", "Paint")
    assert "PAINTING" in sec_paint


# 20. Validation Engine (Invalid Quantity Check)
def test_validation_engine_invalid_deduction():
    v = BOQValidator()
    item_invalid = BOQItem(
        item_no=1,
        section="MASONRY",
        element_type="WALL",
        material="BRICK",
        description="Brick wall",
        unit="m3",
        gross_quantity=5.0,
        deduction_quantity=7.0,  # exceeds gross!
        net_quantity=-2.0,
        wastage_percent=5.0,
        wastage_quantity=-0.1,
        total_quantity=-2.1,
        status="MEASURED",
    )
    res = v.validate_all([item_invalid])
    assert not res["passed"]
    assert any(e["code"] == "INVALID_QUANTITY" for e in res["errors"])


# 21. Export Generation (Excel & PDF)
def test_excel_and_pdf_export_generation():
    boq_payload = {
        "drawing_summary": {"filename": "Sample_Building.dxf", "units": "m", "entity_count": 150, "layer_count": 8},
        "boq": [
            {
                "item_no": 1,
                "section": "4. RCC SUPER-STRUCTURE",
                "element_type": "COLUMN",
                "material": "Design Mix Concrete M25",
                "description": "Providing and laying in position machine batched ready-mix concrete M25...",
                "unit": "cum",
                "net_quantity": 25.5,
                "wastage_percent": 2.5,
                "total_quantity": 26.1375,
                "rate": 4800.0,
                "amount": 125460.0,
                "calculation_basis": "20 columns x 0.3 x 0.45 x 3m",
                "status": "MEASURED",
                "confidence": 0.95,
                "source_entities": ["E001", "E002"],
                "source_layers": ["STR-COL"],
            }
        ]
    }

    excel_bytes = generate_boq_excel(boq_payload)
    assert isinstance(excel_bytes, bytes)
    assert len(excel_bytes) > 2000

    pdf_bytes = generate_boq_pdf(boq_payload)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 2000
