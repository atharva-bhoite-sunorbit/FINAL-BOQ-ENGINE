from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from backend.models.material_quantity import MaterialQuantity


def calculate_aluminium_framework(element: ConstructionElement) -> list[MaterialQuantity]:
    """
    Calculates architectural aluminium section profiles:
    - Running meters = perimeter + intermediate mullions
    - Weight: ~1.2 kg per rmt for standard partition/window profiles
    """
    length = float(element.geometry.get("length", 0.0))
    height = float(element.geometry.get("height", 2.40))
    
    if length <= 0:
        area = float(element.geometry.get("area", 0.0))
        length = area / height if height > 0 else 0.0

    if length <= 0:
        return []

    # Perimeter frame + mullions every 1.2m
    mullions = max(1, round(length / 1.2))
    total_frame_rmt = (2 * length) + (2 * height) + (mullions * height)
    total_wt_kg = total_frame_rmt * 1.20

    wastage = 3.0
    tot_wt = total_wt_kg * (1 + wastage / 100.0)

    results: list[MaterialQuantity] = []
    results.append(
        MaterialQuantity(
            material_id=f"MAT-ALU-{element.element_id}",
            material_name="Powder Coated Extruded Aluminium Section (6063-T6, 65-85 micron)",
            category="Glass & Aluminium",
            unit="kg",
            quantity=round(total_wt_kg, 2),
            wastage_percent=wastage,
            total_quantity=round(tot_wt, 2),
            source_element_id=element.element_id,
            source_element_type=element.element_type,
            calculation_basis=f"Frame {total_frame_rmt:.2f} rmt x 1.2 kg/m + 3% wastage",
            status=element.status,
            confidence=element.confidence,
            rate=280.0,
            amount=round(tot_wt * 280.0, 2),
        )
    )

    # Hardware & EPDM Beading
    results.append(
        MaterialQuantity(
            material_id=f"MAT-BDG-{element.element_id}",
            material_name="EPDM Wedge Gaskets & Glazing Beading",
            category="Hardware & Fittings",
            unit="rmt",
            quantity=round(total_frame_rmt * 2, 2),
            wastage_percent=5.0,
            total_quantity=round(total_frame_rmt * 2 * 1.05, 2),
            source_element_id=element.element_id,
            source_element_type=element.element_type,
            calculation_basis="Beading along both sides of frame profile",
            status=element.status,
            confidence=element.confidence,
            rate=35.0,
            amount=round(total_frame_rmt * 2 * 1.05 * 35.0, 2),
        )
    )

    return results


calculate_aluminium = calculate_aluminium_framework

__all__ = ["calculate_aluminium_framework", "calculate_aluminium"]
