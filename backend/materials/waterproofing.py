from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from backend.models.material_quantity import MaterialQuantity


def calculate_waterproofing(
    element: ConstructionElement,
    upturn_height_m: float = 0.30,
) -> list[MaterialQuantity]:
    """
    Calculates waterproofing systems:
    - Base area + perimeter upturn
    - Two-component acrylic polymer modified cementitious coating / APP membrane
    """
    area = float(element.geometry.get("area", 0.0))
    perimeter = float(element.geometry.get("perimeter", 0.0))

    if area <= 0:
        return []

    # Total treatment area includes vertical upturn
    total_area = area + (perimeter * upturn_height_m)
    wastage = 5.0
    treated_area = total_area * (1 + wastage / 100.0)

    results: list[MaterialQuantity] = []
    results.append(
        MaterialQuantity(
            material_id=f"MAT-WPF-{element.element_id}",
            material_name="Two-Component Acrylic Polymer Modified Flexible Cementitious Waterproofing Coating",
            category="Waterproofing & Insulation",
            unit="sqm",
            quantity=round(total_area, 2),
            wastage_percent=wastage,
            total_quantity=round(treated_area, 2),
            source_element_id=element.element_id,
            source_element_type=element.element_type,
            calculation_basis=f"Base {area:.2f} sqm + {perimeter:.2f}m x {upturn_height_m}m upturn + 5% wastage",
            status=element.status,
            confidence=element.confidence,
            rate=450.0,
            amount=round(treated_area * 450.0, 2),
        )
    )

    return results
