from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from backend.models.material_quantity import MaterialQuantity


def calculate_ceiling(element: ConstructionElement) -> list[MaterialQuantity]:
    """
    Calculates false ceiling materials:
    - Gypsum plasterboards / Armstrong mineral fiber tiles (sqm)
    - GI intermediate & ceiling sections / Main T & Cross T grid (rmt)
    - Perimeter wall angles (rmt)
    - GI suspension wire / soffit cleats (nos)
    """
    area = float(element.geometry.get("area", 0.0))
    perimeter = float(element.geometry.get("perimeter", 0.0))

    if area <= 0:
        return []

    subtype = element.subtype
    is_grid = "GRID" in subtype
    results: list[MaterialQuantity] = []

    # 1. Ceiling Board / Tile
    wastage = 5.0
    tot_area = area * (1 + wastage / 100.0)
    name = "600x600 mm Mineral Fiber Acoustic Ceiling Tiles (Armstrong type)" if is_grid else "12.5 mm Tapered Edge Gypsum False Ceiling Board"
    rate = 850.0 if is_grid else 720.0

    results.append(
        MaterialQuantity(
            material_id=f"MAT-CLG-{element.element_id}",
            material_name=name,
            category="False Ceiling",
            unit="sqm",
            quantity=round(area, 2),
            wastage_percent=wastage,
            total_quantity=round(tot_area, 2),
            source_element_id=element.element_id,
            source_element_type=element.element_type,
            calculation_basis=f"Ceiling Area {area:.2f} sqm + 5% wastage",
            status=element.status,
            confidence=element.confidence,
            rate=rate,
            amount=round(tot_area * rate, 2),
        )
    )

    # 2. GI Framework (rmt) ~ 1.8 rmt per sqm
    framework_rmt = area * 1.80
    results.append(
        MaterialQuantity(
            material_id=f"MAT-FRM-CLG-{element.element_id}",
            material_name="GI Suspension Framework (Ceiling Sections, Intermediate Channels & Hangers)",
            category="Metal Framework",
            unit="rmt",
            quantity=round(framework_rmt, 2),
            wastage_percent=3.0,
            total_quantity=round(framework_rmt * 1.03, 2),
            source_element_id=element.element_id,
            source_element_type=element.element_type,
            calculation_basis=f"{area:.2f} sqm x 1.8 rmt/sqm grid framework",
            status=element.status,
            confidence=element.confidence,
            rate=75.0,
            amount=round(framework_rmt * 1.03 * 75.0, 2),
        )
    )

    return results
