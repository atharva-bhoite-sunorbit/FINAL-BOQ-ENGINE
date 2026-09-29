from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from backend.models.material_quantity import MaterialQuantity


def calculate_plaster(
    element: ConstructionElement,
    thickness_mm: float = 12.0,
    is_external: bool = False,
) -> list[MaterialQuantity]:
    """
    Calculates plaster materials:
    - Internal: 12mm 1:6 (or 15mm)
    - External: 20mm 1:4 double coat
    - Cement bags and sand volume
    """
    # Plaster is applied to both faces of a wall unless specified
    face_area = float(element.geometry.get("area", 0.0))
    if face_area <= 0:
        length = float(element.geometry.get("length", 0.0))
        height = float(element.geometry.get("height", 3.0))
        face_area = length * height

    if face_area <= 0:
        return []

    # Two faces for internal partition/wall, single face if external
    sides = 1.0 if is_external else 2.0
    plaster_area = face_area * sides
    thickness_m = thickness_mm / 1000.0
    wet_volume = plaster_area * thickness_m
    dry_volume = wet_volume * 1.33

    ratio = "1:4" if is_external else "1:6"
    parts = 5.0 if is_external else 7.0
    cement_cum = dry_volume * (1.0 / parts)
    cement_bags = cement_cum * 28.8
    sand_cum = dry_volume * ((parts - 1.0) / parts)

    results: list[MaterialQuantity] = []
    
    # Plaster surface item
    desc = f"{int(thickness_mm)}mm External Plaster in 1:4 with waterproofing" if is_external else f"{int(thickness_mm)}mm Internal Plaster in 1:6"
    results.append(
        MaterialQuantity(
            material_id=f"MAT-PLS-{element.element_id}",
            material_name=desc,
            category="Finishes & Plaster",
            unit="sqm",
            quantity=round(plaster_area, 2),
            wastage_percent=5.0,
            total_quantity=round(plaster_area * 1.05, 2),
            source_element_id=element.element_id,
            source_element_type=element.element_type,
            calculation_basis=f"{plaster_area:.2f} sqm ({sides} faces) + 5% wastage",
            status=element.status,
            confidence=element.confidence,
            rate=280.0 if is_external else 220.0,
            amount=round(plaster_area * 1.05 * (280.0 if is_external else 220.0), 2),
        )
    )

    # Cement
    results.append(
        MaterialQuantity(
            material_id=f"MAT-CMT-PLS-{element.element_id}",
            material_name="OPC Cement for Plaster",
            category="Cement & Aggregates",
            unit="bags",
            quantity=round(cement_bags, 2),
            wastage_percent=2.5,
            total_quantity=round(cement_bags * 1.025, 2),
            source_element_id=element.element_id,
            source_element_type=element.element_type,
            calculation_basis=f"Plaster vol {wet_volume:.3f} m3 x mix {ratio}",
            status=element.status,
            confidence=element.confidence,
            rate=380.0,
            amount=round(cement_bags * 1.025 * 380.0, 2),
        )
    )

    # Sand
    results.append(
        MaterialQuantity(
            material_id=f"MAT-SND-PLS-{element.element_id}",
            material_name="Screened Plaster Sand",
            category="Cement & Aggregates",
            unit="cum",
            quantity=round(sand_cum, 3),
            wastage_percent=5.0,
            total_quantity=round(sand_cum * 1.05, 3),
            source_element_id=element.element_id,
            source_element_type=element.element_type,
            calculation_basis=f"Plaster vol {wet_volume:.3f} m3 x mix {ratio}",
            status=element.status,
            confidence=element.confidence,
            rate=1850.0,
            amount=round(sand_cum * 1.05 * 1850.0, 2),
        )
    )

    return results
