from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from backend.models.material_quantity import MaterialQuantity


def calculate_blockwork(element: ConstructionElement) -> list[MaterialQuantity]:
    """
    Calculates AAC / Concrete Blockwork materials:
    - Blocks: 600x200x(thickness) mm -> count = Volume / (0.6 * 0.2 * thickness)
    - Polymer jointing thin-bed adhesive mortar (~18 kg/cum for AAC)
    """
    volume = float(element.geometry.get("volume", 0.0))
    thickness = float(element.geometry.get("thickness", 0.15))
    if volume <= 0:
        area = float(element.geometry.get("area", 0.0))
        volume = area * thickness

    if volume <= 0:
        return []

    block_vol = 0.60 * 0.20 * thickness
    if block_vol <= 0:
        block_vol = 0.018  # default 150mm

    block_count = volume / block_vol
    wastage = 5.0
    total_blocks = block_count * (1 + wastage / 100.0)

    results: list[MaterialQuantity] = []

    results.append(
        MaterialQuantity(
            material_id=f"MAT-AAC-{element.element_id}",
            material_name=f"Autoclaved Aerated Concrete (AAC) Blocks 600x200x{int(thickness*1000)}mm",
            category="Blocks & Masonry",
            unit="nos",
            quantity=round(block_count, 1),
            wastage_percent=wastage,
            total_quantity=round(total_blocks, 1),
            source_element_id=element.element_id,
            source_element_type=element.element_type,
            calculation_basis=f"Vol {volume:.3f} m3 / block volume {block_vol:.4f} m3",
            status=element.status,
            confidence=element.confidence,
            rate=75.0,
            amount=round(total_blocks * 75.0, 2),
        )
    )

    # Thin bed jointing adhesive: 18 kg per cum
    adhesive_kg = volume * 18.0
    results.append(
        MaterialQuantity(
            material_id=f"MAT-ADH-AAC-{element.element_id}",
            material_name="Polymer Modified Thin Bed Jointing Mortar",
            category="Cement & Mortar",
            unit="kg",
            quantity=round(adhesive_kg, 1),
            wastage_percent=3.0,
            total_quantity=round(adhesive_kg * 1.03, 1),
            source_element_id=element.element_id,
            source_element_type=element.element_type,
            calculation_basis=f"Vol {volume:.3f} m3 x 18 kg/m3",
            status=element.status,
            confidence=element.confidence,
            rate=15.0,
            amount=round(adhesive_kg * 1.03 * 15.0, 2),
        )
    )

    return results
