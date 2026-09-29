from __future__ import annotations

from typing import Any
from backend.models.construction_element import ConstructionElement
from backend.models.material_quantity import MaterialQuantity


def calculate_brickwork(element: ConstructionElement) -> list[MaterialQuantity]:
    """
    Calculates clay brickwork materials:
    - Standard red bricks (approx 500 nos per cum)
    - Cement in 1:6 mortar (~1.34 bags per cum)
    - Sand in 1:6 mortar (~0.28 cum per cum)
    """
    volume = float(element.geometry.get("volume", 0.0))
    if volume <= 0:
        area = float(element.geometry.get("area", 0.0))
        thickness = float(element.geometry.get("thickness", 0.23))
        volume = area * thickness

    if volume <= 0:
        return []

    results: list[MaterialQuantity] = []
    
    # 1. Bricks
    bricks_per_cum = 500.0
    brick_count = volume * bricks_per_cum
    brick_wastage = 5.0
    total_bricks = brick_count * (1 + brick_wastage / 100.0)

    results.append(
        MaterialQuantity(
            material_id=f"MAT-BRK-{element.element_id}",
            material_name="First Class Red Clay Bricks (Standard Modular)",
            category="Blocks & Masonry",
            unit="nos",
            quantity=round(brick_count, 1),
            wastage_percent=brick_wastage,
            total_quantity=round(total_bricks, 1),
            source_element_id=element.element_id,
            source_element_type=element.element_type,
            calculation_basis=f"Vol {volume:.3f} m3 x 500 nos/m3 + 5% wastage",
            status=element.status,
            confidence=element.confidence,
            rate=9.50,
            amount=round(total_bricks * 9.50, 2),
        )
    )

    # 2. Cement for Mortar (1:6)
    cement_bags = volume * 1.34
    results.append(
        MaterialQuantity(
            material_id=f"MAT-CMT-BRK-{element.element_id}",
            material_name="PPC Cement for Brick Masonry Mortar 1:6",
            category="Cement & Aggregates",
            unit="bags",
            quantity=round(cement_bags, 2),
            wastage_percent=2.5,
            total_quantity=round(cement_bags * 1.025, 2),
            source_element_id=element.element_id,
            source_element_type=element.element_type,
            calculation_basis=f"Vol {volume:.3f} m3 x 1.34 bags/m3",
            status=element.status,
            confidence=element.confidence,
            rate=370.0,
            amount=round(cement_bags * 1.025 * 370.0, 2),
        )
    )

    # 3. Sand for Mortar (1:6)
    sand_cum = volume * 0.28
    results.append(
        MaterialQuantity(
            material_id=f"MAT-SND-BRK-{element.element_id}",
            material_name="River Sand / M-Sand for Masonry Mortar",
            category="Cement & Aggregates",
            unit="cum",
            quantity=round(sand_cum, 3),
            wastage_percent=5.0,
            total_quantity=round(sand_cum * 1.05, 3),
            source_element_id=element.element_id,
            source_element_type=element.element_type,
            calculation_basis=f"Vol {volume:.3f} m3 x 0.28 cum/m3",
            status=element.status,
            confidence=element.confidence,
            rate=1850.0,
            amount=round(sand_cum * 1.05 * 1850.0, 2),
        )
    )

    return results
