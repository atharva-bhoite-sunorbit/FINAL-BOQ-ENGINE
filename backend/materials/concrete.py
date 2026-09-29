from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from backend.models.material_quantity import MaterialQuantity


def calculate_concrete(element: ConstructionElement, wastage_percent: float = 2.5) -> list[MaterialQuantity]:
    """Calculates ready-mix concrete quantity for structural RCC elements."""
    volume = float(element.geometry.get("volume", 0.0))
    if volume <= 0:
        area = float(element.geometry.get("area", 0.0))
        thickness = float(element.geometry.get("thickness", 0.0) or element.geometry.get("depth", 0.15))
        volume = area * thickness

    if volume <= 0:
        return []

    grade = element.material_hint or "RCC_M25"
    wastage_qty = volume * (wastage_percent / 100.0)
    total_vol = volume + wastage_qty

    rate = 5200.0 if "M30" in grade else (4800.0 if "M25" in grade else 4500.0)

    item = MaterialQuantity(
        material_id=f"MAT-CON-{element.element_id}",
        material_name=f"Design Mix Concrete {grade} (RMC)",
        category="Concrete & Aggregates",
        unit="cum",
        quantity=round(volume, 4),
        wastage_percent=wastage_percent,
        total_quantity=round(total_vol, 4),
        source_element_id=element.element_id,
        source_element_type=element.element_type,
        calculation_basis=f"Volume = {volume:.3f} cum + {wastage_percent}% wastage",
        status=element.status,
        confidence=element.confidence,
        rate=rate,
        amount=round(total_vol * rate, 2),
    )
    return [item]
