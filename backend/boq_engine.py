from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from backend.quantity_engine import calculate_element_quantities
from backend.material_engine import map_quantities_to_materials

DATA_DIR = Path(__file__).resolve().parent / "data"
RATES_FILE = DATA_DIR / "material_rates.json"


def load_standard_rates() -> dict[str, float]:
    return {
        "CONCRETE": 5200.0,
        "BRICK": 9.5,
        "AAC": 65.0,
        "CEMENT": 380.0,
        "SAND": 1400.0,
        "PLASTER": 185.0,
        "FORMWORK": 380.0,
        "SHUTTERING": 380.0,
        "CENTERING": 420.0,
        "STEEL": 68.0,
        "REBAR": 68.0,
        "GLASS": 1450.0,
        "ALUMINIUM": 380.0,
        "SEALANT": 45.0,
        "SHUTTER": 3500.0,
        "FRAME": 2800.0,
        "HARDWARE": 1200.0,
        "TILE": 850.0,
        "PAINT": 45.0,
        "WATERPROOFING": 165.0,
        "CEILING": 240.0,
    }


def _match_rate(mat_name: str, rates_db: dict[str, float]) -> float:
    uname = mat_name.upper()
    # 1. Exact match
    if uname in rates_db:
        return rates_db[uname]
    # 2. Token match
    for token, rate in rates_db.items():
        if token in uname:
            return rate
    return 100.0  # nominal default rate


def generate_complete_boq(
    drawing_data: dict[str, Any],
    rate_overrides: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Main BOQ generation engine adhering strictly to Sections 21 through 28, and 31.
    Complete deterministic chain:
    DWG entity → geometry → construction element → quantity → material → BOQ item.
    """
    elements_dict = drawing_data.get("construction_elements", {})
    units = drawing_data.get("units", "m")
    texts = [t.get("text", "") for t in drawing_data.get("texts", [])]

    # 1. Calculate Measurable Quantities (Section 21)
    quantities = calculate_element_quantities(elements_dict)

    # 2. Map Elements to Materials & Aggregate (Sections 22, 23, 24)
    material_items, aggregated_materials = map_quantities_to_materials(
        quantities, annotations=texts
    )

    # 3. Apply Approved Rates
    rates_db = load_standard_rates()
    if rate_overrides:
        rates_db.update({k.upper(): float(v) for k, v in rate_overrides.items()})

    boq_items: list[dict[str, Any]] = []
    item_no = 1
    total_cost = 0.0

    # 4. Generate Auditable BOQ Items (Section 25 Traceability, aggregated so each item appears once)
    for mat in aggregated_materials:
        mat_name = mat.get("material", "")
        qty = mat.get("total_quantity")
        status = mat.get("status", "MEASURED")

        # Rate lookup
        matched_rate = _match_rate(mat_name, rates_db)

        if qty is None:
            # Section 23: Strict Rebar handling
            amount = 0.0
            calc_basis = mat.get("calculation_basis", "STRUCTURAL_REBAR_DATA_REQUIRED")
        else:
            amount = round(qty * matched_rate, 2)
            total_cost += amount
            calc_basis = mat.get("calculation_basis", "")

        section = _determine_section(mat.get("category", ""), mat.get("element_type", ""))

        src_elems = mat.get("source_elements", [])
        if not src_elems and mat.get("source_element"):
            src_elems = [mat.get("source_element")]

        boq_item = {
            "item_no": item_no,
            "section": section,
            "element_type": mat.get("element_type", "GEN"),
            "material": mat_name,
            "description": f"Providing and applying / installing {mat_name} strictly conforming to standard specifications.",
            "unit": mat.get("unit", "nos"),
            "gross_quantity": mat.get("quantity"),
            "wastage_percent": mat.get("wastage_percent", 0.0),
            "total_quantity": qty,
            "rate": matched_rate,
            "amount": amount,
            "calculation_basis": calc_basis,
            "source_elements": src_elems,
            "source_entities": mat.get("source_entities", []),
            "status": status,
            "confidence": 0.95 if status == "MEASURED" else (0.0 if status == "STRUCTURAL_REBAR_DATA_REQUIRED" else 0.88),
        }
        boq_items.append(boq_item)
        item_no += 1

    # Final Output JSON Structure conforming exactly to Section 28
    tax = round(total_cost * 0.18, 2)
    grand_total = round(total_cost + tax, 2)

    drawing_summary = {
        "file_name": drawing_data.get("file_name", "Drawing"),
        "units": units,
        "extension": drawing_data.get("extension", ".dxf"),
        "total_entities": len(drawing_data.get("entities", [])),
        "total_layers": len(drawing_data.get("layers", [])),
        "total_blocks": len(drawing_data.get("blocks", [])),
        "total_elements": sum(len(v) for v in elements_dict.values() if isinstance(v, list)),
    }

    return {
        "drawing": drawing_summary,
        "layers": drawing_data.get("layers", []),
        "layers_table": drawing_data.get("layers_table", []),
        "entities": drawing_data.get("entities", []),
        "blocks": drawing_data.get("blocks", []),
        "texts": drawing_data.get("texts", []),
        "dimensions": drawing_data.get("dimensions", []),
        "hatches": drawing_data.get("hatches", []),
        "construction_elements": elements_dict,
        "quantities": quantities,
        "materials": aggregated_materials,
        "material_items": material_items,
        "boq": boq_items,
        "summary": {
            "subtotal": round(total_cost, 2),
            "material_cost": round(total_cost * 0.70, 2),
            "labour_cost": round(total_cost * 0.30, 2),
            "tax": tax,
            "grand_total": grand_total,
        },
        "warnings": drawing_data.get("warnings", []),
        "assumptions": elements_dict.get("assumptions", []),
    }


def _determine_section(category: str, element_type: str) -> str:
    cat = category.upper()
    etype = element_type.upper()
    if "FOUNDATION" in cat or etype in {"FOUNDATION", "FOOTING"}:
        return "1. SUB-STRUCTURE & FOUNDATION"
    if "CONCRETE" in cat or etype in {"COLUMN", "BEAM", "SLAB"}:
        return "2. REINFORCED CEMENT CONCRETE (RCC)"
    if "REINFORCEMENT" in cat or "STEEL" in cat:
        return "3. REINFORCEMENT STEEL"
    if "MASONRY" in cat or "CEMENT" in cat or etype == "WALL":
        return "4. MASONRY & BRICKWORK"
    if "DOOR" in cat or "WINDOW" in cat or etype in {"DOOR", "WINDOW"}:
        return "5. DOORS, WINDOWS & JOINERY"
    if "FINISH" in cat or "FLOOR" in cat or etype in {"FLOOR", "CEILING"}:
        return "6. FINISHES & TILING"
    if "MEP" in cat or etype == "MEP":
        return "7. MEP SERVICES & FIXTURES"
    return "8. MISCELLANEOUS WORKS"


# Backward compatibility for legacy endpoints
def generate_geometry_boq(
    drawing: dict[str, Any],
    rates: Optional[dict[str, Any]] = None,
    rules: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    res = generate_complete_boq(drawing, rates)
    return {
        "boq": res.get("boq", []),
        "materials": res.get("materials", []),
        "quantities": res.get("quantities", []),
        "summary": res.get("summary", {}),
    }
