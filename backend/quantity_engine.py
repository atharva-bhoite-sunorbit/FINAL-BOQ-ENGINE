from __future__ import annotations

import math
from typing import Any, Sequence
from backend.geometry_engine import normalize_length, normalize_area, merge_parallel_walls


def calculate_element_quantities(elements_dict: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Calculates deterministic measurable quantities for every construction element.
    Stores the exact mathematical formula used and traceability links to source elements.
    Strictly follows Section 21 of the requirements.
    """
    quantities: list[dict[str, Any]] = []

    # 1. Walls
    walls = elements_dict.get("walls", [])
    for w in walls:
        elem_id = w.get("element_id", "W001")
        length = float(w.get("length", 0.0))
        thickness = float(w.get("thickness", 0.23))
        height = float(w.get("height", 3.0))
        op_vol = float(w.get("opening_volume", 0.0))
        gross_vol = round(length * thickness * height, 3)
        net_vol = max(0.0, round(gross_vol - op_vol, 3))

        formula = f"length ({length:.2f}m) × thickness ({thickness:.2f}m) × height ({height:.2f}m)"
        if op_vol > 0:
            formula += f" - openings ({op_vol:.3f} m3)"

        quantities.append({
            "quantity_id": f"QTY-W-{elem_id}",
            "element_type": "WALL",
            "subtype": w.get("subtype", "BRICK_WALL"),
            "source_elements": [elem_id],
            "unit": "m3",
            "gross_quantity": gross_vol,
            "deduction_quantity": op_vol,
            "quantity": net_vol,
            "net_quantity": net_vol,
            "formula": formula,
            "floor": w.get("floor", "Ground Floor"),
            "status": "MEASURED",
            "source_entities": w.get("source_entities", []),
        })

    # 2. Columns
    columns = elements_dict.get("columns", [])
    for c in columns:
        elem_id = c.get("element_id", "COL001")
        width = float(c.get("width", 0.3))
        depth = float(c.get("depth", 0.3))
        height = float(c.get("height", 3.0))
        vol = round(width * depth * height, 3)

        quantities.append({
            "quantity_id": f"QTY-C-{elem_id}",
            "element_type": "COLUMN",
            "subtype": c.get("subtype", "RCC_COLUMN"),
            "source_elements": [elem_id],
            "unit": "m3",
            "gross_quantity": vol,
            "deduction_quantity": 0.0,
            "quantity": vol,
            "net_quantity": vol,
            "formula": f"width ({width:.2f}m) × depth ({depth:.2f}m) × height ({height:.2f}m)",
            "floor": c.get("floor", "Ground Floor"),
            "status": "MEASURED",
            "source_entities": c.get("source_entities", []),
        })

    # 3. Beams
    beams = elements_dict.get("beams", [])
    for b in beams:
        elem_id = b.get("element_id", "BM001")
        length = float(b.get("length", 0.0))
        width = float(b.get("width", 0.23))
        depth = float(b.get("depth", 0.45))
        vol = round(length * width * depth, 3)

        quantities.append({
            "quantity_id": f"QTY-B-{elem_id}",
            "element_type": "BEAM",
            "subtype": b.get("subtype", "RCC_BEAM"),
            "source_elements": [elem_id],
            "unit": "m3",
            "gross_quantity": vol,
            "deduction_quantity": 0.0,
            "quantity": vol,
            "net_quantity": vol,
            "formula": f"length ({length:.2f}m) × width ({width:.2f}m) × depth ({depth:.2f}m)",
            "floor": b.get("floor", "Ground Floor"),
            "status": "MEASURED",
            "source_entities": b.get("source_entities", []),
        })

    # 4. Slabs
    slabs = elements_dict.get("slabs", [])
    for s in slabs:
        elem_id = s.get("element_id", "SLB001")
        area = float(s.get("area", 0.0))
        thickness = float(s.get("thickness", 0.15))
        vol = round(area * thickness, 3)

        quantities.append({
            "quantity_id": f"QTY-S-{elem_id}",
            "element_type": "SLAB",
            "subtype": s.get("subtype", "RCC_SLAB"),
            "source_elements": [elem_id],
            "unit": "m3",
            "gross_quantity": vol,
            "deduction_quantity": 0.0,
            "quantity": vol,
            "net_quantity": vol,
            "plan_area_m2": area,
            "formula": f"area ({area:.2f} m2) × thickness ({thickness:.2f}m)",
            "floor": s.get("floor", "Ground Floor"),
            "status": "MEASURED",
            "source_entities": s.get("source_entities", []),
        })

    # 5. Doors
    doors = elements_dict.get("doors", [])
    for d in doors:
        elem_id = d.get("door_id", "D001")
        qty = int(d.get("quantity", 1))
        quantities.append({
            "quantity_id": f"QTY-D-{elem_id}",
            "element_type": "DOOR",
            "subtype": d.get("subtype", "DOOR"),
            "source_elements": [elem_id],
            "unit": "nos",
            "gross_quantity": float(qty),
            "deduction_quantity": 0.0,
            "quantity": float(qty),
            "net_quantity": float(qty),
            "formula": f"count ({qty} nos)",
            "floor": d.get("floor", "Ground Floor"),
            "status": "MEASURED",
            "source_entities": d.get("source_entities", []),
        })

    # 6. Windows
    windows = elements_dict.get("windows", [])
    for w in windows:
        elem_id = w.get("window_id", "W001")
        width = float(w.get("width", 1.2))
        height = float(w.get("height", 1.2))
        count = int(w.get("quantity", 1))
        area = round(width * height * count, 3)

        quantities.append({
            "quantity_id": f"QTY-W-{elem_id}",
            "element_type": "WINDOW",
            "subtype": w.get("subtype", "WINDOW"),
            "source_elements": [elem_id],
            "unit": "m2",
            "gross_quantity": area,
            "deduction_quantity": 0.0,
            "quantity": area,
            "net_quantity": area,
            "count": count,
            "formula": f"width ({width:.2f}m) × height ({height:.2f}m) × count ({count})",
            "floor": w.get("floor", "Ground Floor"),
            "status": "MEASURED",
            "source_entities": [w.get("source_entity")] if w.get("source_entity") else [],
        })

    # 7. Flooring & Rooms
    rooms = elements_dict.get("rooms", [])
    for r in rooms:
        elem_id = r.get("room_id", "RM001")
        area = float(r.get("area", 0.0))
        quantities.append({
            "quantity_id": f"QTY-FLR-{elem_id}",
            "element_type": "FLOOR",
            "subtype": "VITRIFIED_TILE_FLOORING",
            "source_elements": [elem_id],
            "unit": "m2",
            "gross_quantity": area,
            "deduction_quantity": 0.0,
            "quantity": area,
            "net_quantity": area,
            "formula": f"room enclosed area ({area:.2f} m2)",
            "floor": r.get("floor", "Ground Floor"),
            "status": "MEASURED",
            "source_entities": [],
        })

    return quantities


# =====================================================================
# Legacy Helper Functions (Maintained for Backward Compatibility)
# =====================================================================

def area_from_segments(
    segments: list[dict[str, Any]],
    units: str,
    conversion: float = 1.0,
    default_height_m: float | None = None,
    deduct_openings_m2: float = 0.0,
    deduplicate_walls: bool = False,
) -> dict[str, Any]:
    source = []
    total_m2 = 0.0
    assumption_used = False

    working_segments = merge_parallel_walls(segments, units) if deduplicate_walls else segments

    for segment in working_segments:
        length = float(segment.get("length", 0))
        if length <= 0:
            continue

        length_m = normalize_length(length, units)
        height = segment.get("height") or segment.get("thickness") or None
        if height is None:
            height_m = default_height_m if default_height_m is not None else 3.0
            assumption_used = True
        else:
            height_m = normalize_length(float(height), units)
            if height_m < 1.0 or height_m > 10.0:
                height_m = default_height_m if default_height_m is not None else 3.0
                assumption_used = True

        area_m2 = length_m * height_m
        total_m2 += area_m2
        source.append({
            "handle": segment.get("handle"),
            "entity_type": segment.get("entity_type"),
            "layer": segment.get("layer"),
            "length_m": round(length_m, 4),
            "height_m": round(height_m, 4),
            "area_m2": round(area_m2, 4),
            "assumption_used": assumption_used,
        })

    gross_m2 = total_m2
    net_m2 = max(0.0, gross_m2 - deduct_openings_m2)
    formula = "SUM(LENGTH_M × HEIGHT_M)"
    if deduct_openings_m2 > 0:
        formula += f" - DEDUCTIONS({round(deduct_openings_m2, 2)} m²)"

    qty = round(net_m2 * conversion, 2)
    return {
        "quantity": qty,
        "gross_quantity": round(gross_m2 * conversion, 2),
        "opening_deduction": round(deduct_openings_m2 * conversion, 2),
        "unit": "m2" if conversion == 1.0 else "sqft",
        "source_geometry": source,
        "formula": formula,
        "assumption_used": assumption_used,
    }


def linear_length(
    entities: list[dict[str, Any]],
    units: str,
    target_unit: str = "rmt",
) -> dict[str, Any]:
    total_m = 0.0
    source = []
    for e in entities:
        length = float(e.get("length", 0))
        if length <= 0 and e.get("perimeter", 0) > 0:
            length = float(e.get("perimeter", 0))
        if length > 0:
            m = normalize_length(length, units)
            total_m += m
            source.append({"handle": e.get("handle"), "length_m": round(m, 4)})

    return {
        "quantity": round(total_m, 2),
        "unit": target_unit,
        "source_geometry": source,
        "formula": "SUM(LENGTH_M)",
    }
