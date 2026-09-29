from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from backend.models.material_quantity import MaterialQuantity


def calculate_glass(element: ConstructionElement) -> list[MaterialQuantity]:
    """
    Calculates architectural glass quantities:
    - Area (sqm) = length * height
    - Glass weight (density ~2500 kg/m3) = area * thickness_m * 2500
    - EPDM Gaskets & Silicone Weather Sealant (rmt) = perimeter
    """
    length = float(element.geometry.get("length", 0.0))
    height = float(element.geometry.get("height", 2.40))
    area = float(element.geometry.get("area", 0.0))
    
    if area <= 0 and length > 0:
        area = length * height

    if area <= 0:
        return []

    thickness_mm = 12.0 if "12" in element.subtype else 10.0
    thickness_m = thickness_mm / 1000.0
    weight_kg = area * thickness_m * 2500.0
    perimeter = 2 * (length + height)

    results: list[MaterialQuantity] = []

    # Glass Panes
    wastage = 3.0
    tot_area = area * (1 + wastage / 100.0)
    results.append(
        MaterialQuantity(
            material_id=f"MAT-GLS-{element.element_id}",
            material_name=f"{int(thickness_mm)}mm Clear Toughened Safety Glass (Edge Polished)",
            category="Glass & Glazing",
            unit="sqm",
            quantity=round(area, 2),
            wastage_percent=wastage,
            total_quantity=round(tot_area, 2),
            source_element_id=element.element_id,
            source_element_type=element.element_type,
            calculation_basis=f"Area = {area:.2f} sqm ({length:.2f}m x {height:.2f}m) + 3% wastage",
            status=element.status,
            confidence=element.confidence,
            rate=1950.0,
            amount=round(tot_area * 1950.0, 2),
        )
    )

    # Weather Sealant
    results.append(
        MaterialQuantity(
            material_id=f"MAT-SLT-GLS-{element.element_id}",
            material_name="Neutral Silicone Weather & Structural Sealant",
            category="Sealants & Adhesives",
            unit="rmt",
            quantity=round(perimeter, 2),
            wastage_percent=5.0,
            total_quantity=round(perimeter * 1.05, 2),
            source_element_id=element.element_id,
            source_element_type=element.element_type,
            calculation_basis=f"Glass perimeter joint = {perimeter:.2f} rmt",
            status=element.status,
            confidence=element.confidence,
            rate=45.0,
            amount=round(perimeter * 1.05 * 45.0, 2),
        )
    )

    return results
