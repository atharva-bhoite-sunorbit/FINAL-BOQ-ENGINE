from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from backend.models.material_quantity import MaterialQuantity


def calculate_door_materials(element: ConstructionElement) -> list[MaterialQuantity]:
    """Calculates door shutter, frame and ironmongery."""
    width = float(element.geometry.get("width", 1.0))
    height = float(element.geometry.get("height", 2.1))
    area = width * height

    results: list[MaterialQuantity] = []

    # Shutter
    results.append(
        MaterialQuantity(
            material_id=f"MAT-DOR-{element.element_id}",
            material_name=f"35mm Flush Door Shutter with Laminate finish ({width:.2f}m x {height:.2f}m)",
            category="Doors & Hardware",
            unit="nos",
            quantity=1.0,
            wastage_percent=0.0,
            total_quantity=1.0,
            source_element_id=element.element_id,
            source_element_type=element.element_type,
            calculation_basis="1 door unit",
            status=element.status,
            confidence=element.confidence,
            rate=3800.0,
            amount=3800.0,
        )
    )

    # Door Frame (WPC / Red Meranti Wood)
    frame_running_m = (2 * height) + width
    results.append(
        MaterialQuantity(
            material_id=f"MAT-DFR-{element.element_id}",
            material_name="WPC / Hardwood Door Frame Section 125x65mm",
            category="Doors & Hardware",
            unit="rmt",
            quantity=round(frame_running_m, 2),
            wastage_percent=3.0,
            total_quantity=round(frame_running_m * 1.03, 2),
            source_element_id=element.element_id,
            source_element_type=element.element_type,
            calculation_basis=f"Frame jambs + head = {frame_running_m:.2f} rmt",
            status=element.status,
            confidence=element.confidence,
            rate=450.0,
            amount=round(frame_running_m * 1.03 * 450.0, 2),
        )
    )

    # Hardware Set (Mortise lock, handle, 3 hinges, tower bolt)
    results.append(
        MaterialQuantity(
            material_id=f"MAT-DHW-{element.element_id}",
            material_name="SS 304 Grade Mortise Lock, Lever Handles, 3 Nos Ball Bearing Hinges & Door Stopper Set",
            category="Hardware & Fittings",
            unit="set",
            quantity=1.0,
            wastage_percent=0.0,
            total_quantity=1.0,
            source_element_id=element.element_id,
            source_element_type=element.element_type,
            calculation_basis="Complete architectural ironmongery set",
            status=element.status,
            confidence=element.confidence,
            rate=1450.0,
            amount=1450.0,
        )
    )

    return results


calculate_doors = calculate_door_materials

__all__ = ["calculate_door_materials", "calculate_doors"]
