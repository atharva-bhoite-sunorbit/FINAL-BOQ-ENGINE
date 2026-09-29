from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from backend.models.material_quantity import MaterialQuantity


def calculate_formwork(element: ConstructionElement, wastage_percent: float = 5.0) -> list[MaterialQuantity]:
    """
    Calculates formwork / shuttering contact area for structural RCC elements:
    - Columns: 2 * (w + d) * h
    - Beams: (2 * depth + width) * length
    - Slabs: Bottom soffit contact area (length * width or plan area)
    - Footings: Perimeter * depth
    - Walls / Shear walls: 2 * length * height
    """
    geo = element.geometry
    etype = element.element_type.upper()
    length = float(geo.get("length", 0.0))
    width = float(geo.get("width", 0.0) or geo.get("thickness", 0.0) or 0.3)
    height = float(geo.get("height", 0.0) or geo.get("depth", 0.0) or 3.0)
    area = float(geo.get("area", 0.0))

    contact_area = 0.0
    formula_basis = ""

    if etype == "COLUMN":
        depth = float(geo.get("depth", width) or width)
        contact_area = 2 * (width + depth) * height
        formula_basis = f"Column 2 x ({width:.2f} + {depth:.2f}) x {height:.2f}m = {contact_area:.2f} m2"

    elif etype == "BEAM":
        depth = float(geo.get("depth", height) or 0.45)
        contact_area = (2 * depth + width) * length
        formula_basis = f"Beam (2 x {depth:.2f} + {width:.2f}) x {length:.2f}m = {contact_area:.2f} m2"

    elif etype in {"SLAB", "FLOOR", "ROOF"}:
        contact_area = area if area > 0 else (length * width)
        formula_basis = f"Slab soffit area = {contact_area:.2f} m2"

    elif etype in {"FOOTING", "FOUNDATION"}:
        perimeter = 2 * (length + width) if (length > 0 and width > 0) else float(geo.get("perimeter", 0.0))
        depth = float(geo.get("depth", 0.45) or 0.45)
        contact_area = perimeter * depth
        formula_basis = f"Footing perimeter {perimeter:.2f}m x depth {depth:.2f}m = {contact_area:.2f} m2"

    elif etype in {"WALL", "SHEAR_WALL", "RETAINING_WALL"}:
        contact_area = 2 * length * height
        formula_basis = f"Wall 2 faces x {length:.2f}m x {height:.2f}m = {contact_area:.2f} m2"

    else:
        contact_area = area if area > 0 else (length * height)
        formula_basis = f"Structural contact area = {contact_area:.2f} m2"

    if contact_area <= 0:
        return []

    tot_shuttering = contact_area * (1 + wastage_percent / 100.0)

    return [
        MaterialQuantity(
            material_id=f"MAT-SHUT-{element.element_id}",
            material_name="Centering and Shuttering with Film-Faced Marine Plywood / Steel Props",
            category="Formwork & Scaffolding",
            unit="m2",
            quantity=round(contact_area, 4),
            wastage_percent=wastage_percent,
            total_quantity=round(tot_shuttering, 4),
            source_element_id=element.element_id,
            source_element_type=element.element_type,
            source_entities=element.source_entities,
            source_layers=element.source_layers,
            calculation_basis=f"{formula_basis} + {wastage_percent}% wastage",
            status=element.status,
            confidence=element.confidence,
            rate=420.0,
            amount=round(tot_shuttering * 420.0, 2),
        )
    ]
